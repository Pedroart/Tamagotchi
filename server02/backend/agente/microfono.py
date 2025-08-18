# microfono.py
from serviceController import ServiceController
from config import *
# ----
import asyncio, json, threading
import numpy as np
import sounddevice as sd

from event_bus import event_bus
from logger import logger

SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 1600  # 100 ms a 16 kHz -> 1600 frames -> 3200 bytes

class Microfono(ServiceController):
    def __init__(self):
        super().__init__(SERVICE_URI_STT, SERVICE_NAME_STT)
        self.status_microfono = False

        # ---- Infra de streaming ----
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._pump_task: asyncio.Task | None = None
        self._sd_stream: sd.InputStream | None = None

        # ---- Event loop propio (hilo dedicado) ----
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop, name="MicrofonoLoop", daemon=True
        )
        self._loop_thread.start()

        event_bus.subscribe("speak.flag", self._toggle_microfono)
        self.add_listener(self._service_listener)

    # Arranque del loop propio
    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # API pública para iniciar (conexión WS en su loop)
    def start(self):
        self._submit(self.connect())

    # Apagado ordenado (cierra WS, detiene stream y loop)
    def shutdown(self):
        # detén audio/pipe y cierra WS dentro del loop
        self._submit(self._graceful_close())
        # luego detén el loop
        try:
            if not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
        # no hacemos join del daemon thread (opcional si quieres bloquear)

    async def _graceful_close(self):
        try:
            await self.stop_stream()
        except Exception:
            pass
        try:
            await self.close()
        except Exception:
            pass

    def _submit(self, coro: asyncio.coroutines):
        """Agenda una corutina en el loop propio, desde cualquier hilo."""
        if self._loop.is_closed():
            logger.error("[Microfono] Loop ya está cerrado; no puedo agendar tarea.")
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception as e:
            logger.exception(f"[Microfono] No se pudo agendar tarea: {e}")

    # --- callback del event bus (puede venir de cualquier hilo) ---
    def _toggle_microfono(self):
        self.status_microfono = not self.status_microfono
        if self.status_microfono:
            print('Microfono prendido')
            self._submit(self.start_stream())
        else:
            print('Microfono apagado')
            self._submit(self.stop_stream())

    # ---- manejo del audio ----
    def _on_audio(self, indata, frames, time_info, status):
        """Callback de sounddevice: se ejecuta en OTRO hilo."""
        if status:
            logger.warning(f"[Microfono] status stream: {status}")
        # Garantiza int16 mono
        pcm = (indata.astype(np.int16) if indata.dtype != np.int16 else indata).tobytes()
        # IMPORTANTE: asyncio.Queue NO es thread-safe → usar call_soon_threadsafe
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, pcm)
        except Exception:
            # si el loop ya se cerró, ignoramos silenciosamente
            pass

    async def _audio_pump(self):
        """Toma bytes de la cola y los envía por WS como BINARIO."""
        try:
            while self.status_microfono:
                try:
                    chunk = await asyncio.wait_for(self._queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                if not self.ws:
                    continue
                await self.ws.send(chunk)  # binario directo
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            logger.exception(f"[Microfono] error en _audio_pump: {ex}")

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

    # ---- integración con STT ----
    async def start_stream(self):
        await self.send("__START__")
        # self.reset_memoria()  # si aplica
        self._start_recording()
        if self._pump_task is None or self._pump_task.done():
            self._pump_task = asyncio.create_task(self._audio_pump())

    async def stop_stream(self):
        self._stop_recording()
        if self._pump_task is not None:
            try:
                await asyncio.wait_for(self._pump_task, timeout=0.5)
            except asyncio.TimeoutError:
                self._pump_task.cancel()
            finally:
                self._pump_task = None
        await self.send("__END__")

    async def _service_listener(self, msg: str):
        try:
            data = json.loads(msg)
            tipo = data.get("type")
            texto = data.get("text", "")
            if tipo == "partial":
                logger.info(f"[STT][parcial] {texto}")
                event_bus.emit("stt.partial", texto)
            elif tipo == "final":
                logger.info(f"[STT][final] {texto}")
                event_bus.emit("stt.final", texto)
            else:
                logger.warning(f"[STT] tipo desconocido: {data}")
        except Exception as e:
            logger.warning(f"Mensaje no JSON o inesperado: {msg} | Error: {e}")
