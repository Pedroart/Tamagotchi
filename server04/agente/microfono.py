# microfono.py (versión local: STT directo, sin WS)
from agente.config import *
from agente.event_bus import event_bus
from agente.logger import logger

import asyncio, threading, io, time, json, tempfile, os
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 1600  # 100 ms a 16 kHz -> 1600 frames -> 3200 bytes

# Parámetros de transcripción (los mismos que tu servidor)
INIT_MODEL_TRANSCRIPTION = "tiny"   # cámbialo a "base" / "small" si necesitas mejor calidad
INIT_MODEL_DEVICE = "cpu"           # "cuda" si tienes GPU
INIT_MODEL_COMPUTE_TYPE = "int8"    # "float16"/"int8_float16" en GPU
INIT_LANGUAGE = "es"

INACTIVITY_TIMEOUT     = 0.5   # s sin audio => flush final
PARTIAL_EVAL_INTERVAL  = 0.2   # cada cuánto sacamos parcial
WINDOW_SEC             = 1   # ventana de contexto para parciales

class Microfono:
    def __init__(self):
        self.status_microfono = False

        # Infra de audio/async
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._sd_stream: sd.InputStream | None = None

        # Loop dedicado
        self._loop = asyncio.new_event_loop()
        self._workers: list[asyncio.Task] = []

        # Buffer y estado STT
        self._audio_buffer = io.BytesIO()
        self._last_packet_ts: float | None = None
        self._last_partial_ts: float = time.time()
        self._partial_running = False
        self._ending = False

        # Modelo
        self._model: WhisperModel | None = None

        # Suscripciones
        event_bus.subscribe("speak.flag", self._toggle_microfono)

        logger.info("[Microfono] listo (modo STT local)")

    # ---------- ciclo de vida ----------
    def start(self):
        """Inicializa el loop y carga el modelo en un hilo aparte."""
        threading.Thread(target=self._run_loop, daemon=True).start()
        self._submit(self._load_model())

    def shutdown(self):
        self._submit(self._graceful_close())
        try:
            if not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro: asyncio.coroutines):
        if self._loop.is_closed():
            logger.error("[Microfono] Loop cerrado; no puedo agendar.")
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception as e:
            logger.exception(f"[Microfono] No se pudo agendar: {e}")

    async def _load_model(self):
        try:
            logger.info(f"[Microfono] Cargando modelo Whisper '{INIT_MODEL_TRANSCRIPTION}'...")
            self._model = WhisperModel(
                INIT_MODEL_TRANSCRIPTION,
                device=INIT_MODEL_DEVICE,
                compute_type=INIT_MODEL_COMPUTE_TYPE
            )
            logger.info("[Microfono] Modelo cargado.")
        except Exception as e:
            logger.exception(f"[Microfono] Error cargando modelo: {e}")

    async def _graceful_close(self):
        try:
            await self.stop_stream()
        except Exception:
            pass
        # cancelar workers
        for t in self._workers:
            t.cancel()
        self._workers.clear()
        # parar stream sd
        try:
            if self._sd_stream is not None:
                self._sd_stream.stop(); self._sd_stream.close()
        finally:
            self._sd_stream = None

    # ---------- toggles ----------
    def _toggle_microfono(self):
        self.status_microfono = not self.status_microfono
        if self.status_microfono:
            print('Microfono prendido')
            self._submit(self.start_stream())
        else:
            print('Microfono apagado')
            self._submit(self.stop_stream())

    # ---------- sounddevice ----------
    def _on_audio(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"[Microfono] status stream: {status}")
        pcm = (indata.astype(np.int16) if indata.dtype != np.int16 else indata).tobytes()
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, pcm)
        except Exception:
            pass

    def _start_recording(self):
        if self._sd_stream is not None:
            return
        self._sd_stream = sd.InputStream(
            samplerate=SAMPLERATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCKSIZE,
            callback=self._on_audio,
        )
        self._sd_stream.start()

    def _stop_recording(self):
        try:
            if self._sd_stream is not None:
                self._sd_stream.stop()
                self._sd_stream.close()
        finally:
            self._sd_stream = None

    # ---------- helpers STT ----------
    def _reset_buffer(self):
        self._audio_buffer = io.BytesIO()
        self._last_packet_ts = None
        self._last_partial_ts = time.time()
        self._partial_running = False
        self._ending = False
        logger.info("[Microfono] 🔄 buffer STT reseteado")

    def _pcm_to_text(self, raw_data: bytes) -> str:
        if not raw_data or self._model is None:
            return ""
        audio_np = np.frombuffer(raw_data, dtype=np.int16)
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = tmp.name
                sf.write(wav_path, audio_np, SAMPLERATE, format="WAV")
            segments, _ = self._model.transcribe(
                wav_path, language=INIT_LANGUAGE, vad_filter=False
            )
            return " ".join(seg.text for seg in segments)
        except Exception as e:
            logger.info(f"[Microfono] ❌ _pcm_to_text: {e}")
            return ""
        finally:
            if wav_path and os.path.exists(wav_path):
                try: os.unlink(wav_path)
                except Exception: pass

    def _transcribe_partial(self) -> str:
        data = self._audio_buffer.getvalue()
        window_bytes = int(SAMPLERATE * CHANNELS * 2 * WINDOW_SEC)
        tail = data[-window_bytes:]
        return self._pcm_to_text(tail)

    def _transcribe_final(self) -> str:
        return self._pcm_to_text(self._audio_buffer.getvalue())

    # ---------- workers ----------
    async def _stt_worker(self):
        """Consume chunks, genera parciales y finales, emite por event_bus."""
        self._reset_buffer()
        while self.status_microfono:
            try:
                # intenta leer chunk; si no llega nada, revisa inactividad
                chunk = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                self._audio_buffer.write(chunk)
                self._last_packet_ts = time.time()

                # logging simple
                buf_bytes = self._audio_buffer.getbuffer().nbytes
                duration = buf_bytes / (SAMPLERATE * CHANNELS * 2)
                logger.info(f"[Microfono] 📥 +{len(chunk)}B  buffer≈{duration:.2f}s")

                # ¿lanzamos parcial?
                if (
                    not self._ending and
                    not self._partial_running and
                    (time.time() - self._last_partial_ts) >= PARTIAL_EVAL_INTERVAL
                ):
                    self._partial_running = True
                    asyncio.create_task(self._run_partial())

            except asyncio.TimeoutError:
                # chequear inactividad => flush final
                if (
                    not self._ending and
                    self._last_packet_ts and
                    (time.time() - self._last_packet_ts) > INACTIVITY_TIMEOUT
                ):
                    # evitar parciales concurrentes
                    while self._partial_running:
                        await asyncio.sleep(0.02)
                    await self._flush_final()
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.exception(f"[Microfono] error _stt_worker: {ex}")

    async def _run_partial(self):
        try:
            text = self._transcribe_partial()
            if text.strip():
                logger.info(f"[Microfono] 📝 Parcial: {text}")
                # emite igual que antes:
                event_bus.emit("stt.partial", text)
        finally:
            self._partial_running = False
            self._last_partial_ts = time.time()

    async def _flush_final(self):
        """Saca transcripción final, emite evento y resetea."""
        if self._audio_buffer.getbuffer().nbytes > 0:
            text = self._transcribe_final()
            logger.info(f"[Microfono] ✅ FINAL: {text}")
            event_bus.emit("stt.final", text)
        self._reset_buffer()

    # ---------- API pública (igual que tenías) ----------
    async def start_stream(self):
        # enciende grabación y STT local
        self._start_recording()
        # lanza worker si no está
        stt = asyncio.create_task(self._stt_worker())
        self._workers.append(stt)

    async def stop_stream(self):
        # detiene grabación
        self._stop_recording()
        # marca fin y espera parcial si corre
        self._ending = True
        while self._partial_running:
            await asyncio.sleep(0.02)
        # hace flush final
        await self._flush_final()
        # cancela worker
        for t in self._workers:
            t.cancel()
        self._workers.clear()

# instancia y worker del hilo (igual que antes)
micro = Microfono()

def _microfono_worker():
    micro.start()
