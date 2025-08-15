# stt_runtime.py
import threading, asyncio
from services.service_stt import ServiceSTT  # usa el service_stt.py que ya tienes

class STTRuntime:
    """Levanta un loop asyncio en un hilo separado y expone helpers thread-safe."""
    def __init__(self, max_parciales: int = 10):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.stt: ServiceSTT | None = None
        self.max_parciales = max_parciales

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.stt = ServiceSTT(max_parciales=self.max_parciales)
        # inicia la conexión persistente y deja el loop vivo
        self.loop.run_until_complete(self.stt.start())
        self.loop.run_forever()

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def start_session(self):
        if self.stt:
            return asyncio.run_coroutine_threadsafe(self.stt.start_stream(), self.loop)

    def send_chunk(self, data: bytes):
        if self.stt and data:
            return asyncio.run_coroutine_threadsafe(self.stt.send_audio_chunk(data), self.loop)

    def stop_session(self):
        if self.stt:
            return asyncio.run_coroutine_threadsafe(self.stt.stop_stream(), self.loop)

    def stop(self):
        try:
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
