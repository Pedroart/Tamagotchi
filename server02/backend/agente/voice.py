from queue import SimpleQueue, Empty
from dataclasses import dataclass
from typing import Tuple, Optional
import threading

try:
    import sounddevice as sd
    HAS_SD = True
except Exception:
    HAS_SD = False

from piper.voice import PiperVoice

from config import *
from event_bus import event_bus
from logger import logger

MODEL_PATH = "TTS/es_MX-claude-14947-epoch-high.onnx"

@dataclass
class Oracione:
    texto: str
    expresion: str
    modo: str

@dataclass
class VoiceState:
    speak: bool

class VoicePlater:
    def __init__(self):
        self._oraciones_queue: "SimpleQueue[Tuple[str, str, str]]" = SimpleQueue()
        event_bus.subscribe("voice.speak", self._speak)
        event_bus.subscribe("voice.stop", self._stop_now)

        self.voice = PiperVoice.load(MODEL_PATH)
        self.sr = self.voice.config.sample_rate

        self.stream: Optional["sd.RawOutputStream"] = None
        self._stream_lock = threading.Lock()      # protege start/abort/close
        self._abort_current = False               # bandera de cancelación cooperativa
        self._need_reopen = False                 # pedir reapertura tras abort/fallo
        self._running = False

        if HAS_SD:
            self._ensure_stream_open()
        else:
            logger.info("sounddevice no disponible; se continuará sin audio.")

    # ---------- utilidades de audio ----------
    def _ensure_stream_open(self):
        """Asegura que exista un stream arrancado y listo para escribir."""
        if not HAS_SD:
            return
        with self._stream_lock:
            if self.stream is not None:
                # Si ya está activo, no hagas nada
                try:
                    # .active existe en sounddevice.Stream; si falla, intentar escribir lo detectará
                    if getattr(self.stream, "active", False):
                        return
                except Exception:
                    pass
                # si no está activo, intentar start; si falla, recrear
                try:
                    self.stream.start()
                    logger.info("Stream reanudado.")
                    return
                except Exception:
                    try:
                        self.stream.close()
                    except Exception:
                        pass
                    self.stream = None

            # Crear uno nuevo
            try:
                self.stream = sd.RawOutputStream(
                    samplerate=self.sr,
                    channels=1,
                    dtype="int16",
                    blocksize=0,
                )
                self.stream.start()
                logger.info("Salida de audio abierta.")
            except Exception as e:
                logger.warning(f"No se pudo abrir salida de audio: {e}. Continuando sin audio.")
                self.stream = None

    # ---------- eventos ----------
    def _speak(self, texto: str = "", expresion: str = "", modo: str = ""):
        self._oraciones_queue.put((texto, expresion, modo))

    def _clear_queue(self):
        try:
            while True:
                self._oraciones_queue.get_nowait()
        except Empty:
            pass

    def _stop_now(self, clear_queue: bool = True):
        """Corta YA la reproducción sin cerrar el stream, y descarta la cola si se pide."""
        logger.info("⏹️ Corte inmediato de reproducción (manteniendo stream abierto).")
        # Señal cooperativa para que synthesize() salga de su bucle
        self._abort_current = True
        self._need_reopen = True  # pediremos reapertura limpia antes del próximo write

        if clear_queue:
            self._clear_queue()

        # Abort rápido del stream (descarta buffers). Lo protegemos con lock.
        if self.stream is not None:
            with self._stream_lock:
                try:
                    self.stream.abort()
                except Exception as e:
                    logger.info(f"No se pudo abortar el stream: {e}")

    def close(self):
        # no limpies _abort_current aquí; sólo cierra recursos
        try:
            with self._stream_lock:
                if self.stream is not None:
                    try:
                        self.stream.stop()
                    except Exception:
                        pass
                    try:
                        self.stream.close()
                    except Exception:
                        pass
                    self.stream = None
        finally:
            self._running = False

    # ---------- síntesis ----------
    def synthesize(self, texto: str):
        """
        Sintetiza 'texto' con Piper. Respeta cancelación cooperativa.
        """
        # Asegura que el stream esté listo (o deshabilitado si no hay audio)
        if self._need_reopen:
            self._ensure_stream_open()
            self._need_reopen = False

        try:
            for chunk in self.voice.synthesize(texto):
                # ¿Nos pidieron abortar?
                if self._abort_current:
                    # limpiar la bandera y salir
                    self._abort_current = False
                    break

                if self.stream is not None:
                    try:
                        with self._stream_lock:
                            # Es posible que alguien haya abortado justo antes
                            if self._need_reopen:
                                # reapertura perezosa
                                self._ensure_stream_open()
                                self._need_reopen = False
                            if self.stream is not None:
                                self.stream.write(chunk.audio_int16_bytes)
                    except Exception as e:
                        # Cualquier error al escribir: marca para reabrir en la próxima utterance
                        logger.warning(f"Fallo al escribir en stream: {e}. Reabriremos el stream.")
                        try:
                            if self.stream is not None:
                                self.stream.close()
                        except Exception:
                            pass
                        self.stream = None
                        self._need_reopen = True
                        # No interrumpimos Piper; simplemente dejamos de intentar escribir
                        # para esta utterance.
                else:
                    # Sin audio: sólo consumimos los chunks
                    pass

        except Exception as e:
            logger.info(f"Error en síntesis TTS: {e}")

    # ---------- bucle principal ----------
    def run(self):
        logger.info("VoicePlater iniciado.")
        self._running = True

        try:
            while self._running:
                try:
                    texto, expresion, modo = self._oraciones_queue.get(timeout=0.1)
                except Empty:
                    continue

                # Reset de cancelación para esta utterance
                self._abort_current = False

                # Dispara animación primero
                try:
                    event_bus.emit("sprite.play", expresion, modo)
                except Exception as e:
                    logger.warning(f"No se pudo emitir 'sprite.play': {e}")

                # Sintetiza (respeta cancelación)
                self.synthesize(texto)

        except KeyboardInterrupt:
            logger.info("Interrumpido por teclado.")
        finally:
            self.close()
            logger.info("VoicePlater finalizado.")

vp = VoicePlater()

def _voice_worker():
    try:
        vp.run()
    finally:
        vp.close()
