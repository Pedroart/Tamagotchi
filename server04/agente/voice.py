from queue import SimpleQueue, Empty
from dataclasses import dataclass
from typing import Tuple, Optional
import time
import threading
import os
import wave
from datetime import datetime


FRONTEND_PUBLIC = os.path.join(
    os.path.dirname(__file__),  # carpeta actual (ej: server04/agente)
    "..",                       # sube a server04/
    "live2d-ws-starter", "public", "out_wav"
)
FRONTEND_PUBLIC = os.path.abspath(FRONTEND_PUBLIC)

os.makedirs(FRONTEND_PUBLIC, exist_ok=True)

try:
    import sounddevice as sd
    HAS_SD = True
except Exception:
    HAS_SD = False

from piper.voice import PiperVoice

from config import *
from agente.event_bus import event_bus
from agente.logger import logger

MODEL_PATH = "assets/es_MX-claude-14947-epoch-high.onnx"

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

        # --- MODO DE SALIDA: 'wav' para guardar archivos, 'play' para reproducir por parlantes
        self.output_mode = "wav"  # cambia a "play" si quieres reproducir

        self.voice = PiperVoice.load(MODEL_PATH)
        self.sr = self.voice.config.sample_rate

        # --- Inicializaciones faltantes ---
        self._wav_dir = FRONTEND_PUBLIC
        os.makedirs(self._wav_dir, exist_ok=True)
        self._current_wav: Optional[wave.Wave_write] = None

        self.stream: Optional["sd.RawOutputStream"] = None
        self._stream_lock = threading.Lock()
        self._abort_current = False
        self._need_reopen = False
        self._running = False


        if HAS_SD and self.output_mode == "play":
            self._ensure_stream_open()
        else:
            logger.info("sounddevice no disponible o modo 'wav'; se continuará sin reproducción en vivo.")

    # ---------- utilidades de audio ----------
    def _ensure_stream_open(self):
        if not HAS_SD:
            return
        with self._stream_lock:
            if self.stream is not None:
                try:
                    if getattr(self.stream, "active", False):
                        return
                except Exception:
                    pass
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
        logger.info("⏹️ Corte inmediato de reproducción (manteniendo stream abierto).")
        self._abort_current = True
        self._need_reopen = True
        if clear_queue:
            self._clear_queue()
        if self.stream is not None:
            with self._stream_lock:
                try:
                    self.stream.abort()
                except Exception as e:
                    logger.info(f"No se pudo abortar el stream: {e}")

    def close(self):
        try:
            with self._stream_lock:
                if self.stream is not None:
                    try: self.stream.stop()
                    except Exception: pass
                    try: self.stream.close()
                    except Exception: pass
                    self.stream = None
        finally:
            self._running = False

    # ---------- síntesis ----------
    def synthesize(self, texto: str):
        if self._need_reopen and self.output_mode == "play":
            self._ensure_stream_open()
            self._need_reopen = False

        try:
            for chunk in self.voice.synthesize(texto):
                if self._abort_current:
                    self._abort_current = False
                    break

                # Guardar WAV si está abierto
                if self._current_wav is not None:
                    try:
                        self._current_wav.writeframes(chunk.audio_int16_bytes)
                    except Exception as e:
                        logger.warning(f"Fallo al escribir WAV: {e}")

                # Reproducir si corresponde
                if self.output_mode == "play" and self.stream is not None:
                    try:
                        with self._stream_lock:
                            if self._need_reopen:
                                self._ensure_stream_open()
                                self._need_reopen = False
                            if self.stream is not None:
                                self.stream.write(chunk.audio_int16_bytes)
                    except Exception as e:
                        logger.warning(f"Fallo al escribir en stream: {e}. Reabriremos el stream.")
                        try:
                            if self.stream is not None:
                                self.stream.close()
                        except Exception:
                            pass
                        self.stream = None
                        self._need_reopen = True

        except Exception as e:
            logger.info(f"Error en síntesis TTS: {e}")

    # ---------- bucle principal ----------
    def run(self):
        logger.info("VoicePlater iniciado.")
        self._running = True
        fname = ""
        try:
            while self._running:
                try:
                    texto, expresion, modo = self._oraciones_queue.get(timeout=0.1)
                except Empty:
                    continue

                self._abort_current = False

                # Enviar animación (ojo con typos en 'expresion')
                try:
                    if self.output_mode != "wav":
                        event_bus.emit("sprite.play", expresion, modo)
                except Exception as e:
                    logger.warning(f"No se pudo emitir 'sprite.play': {e}")

                # Abrir WAV si estamos en modo 'wav'
                self._current_wav = None
                if self.output_mode == "wav":
                    try:
                        fname = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".wav"
                        path = os.path.join(self._wav_dir, fname)
                        wf = wave.open(path, "wb")
                        wf.setnchannels(1)
                        wf.setsampwidth(2)  # int16
                        wf.setframerate(self.sr)
                        self._current_wav = wf
                        logger.info(f"Grabando WAV: {path}")
                    except Exception as e:
                        logger.warning(f"No se pudo abrir WAV: {e}")

                try:
                    self.synthesize(texto)
                finally:
                    # Cerrar WAV al terminar
                    if self._current_wav is not None:
                        try:
                            self._current_wav.close()
                            logger.info("WAV cerrado.")
                        except Exception as e:
                            logger.warning(f"Al cerrar WAV: {e}")

                        try:
                            event_bus.emit("ui.speak", {
                                "path": fname,   # ruta local → web_actions la convertirá a URL
                                "expression": expresion,          # opcional
                                "waitEnd": True                   # el front esperará a que termine
                            })
                        except Exception as e:
                            logger.warning(f"No se pudo emitir 'ui.speak': {e}")
                        
                        self._current_wav = None
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
