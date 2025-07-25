import asyncio
import sounddevice as sd
import sys

from servicio.serviceSTT import ServiceSTT
from servicio.serviceTTS import TTSService
from servicio.solucionService import SolucionService

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = 'int16'
CHUNK_DURATION = 0.1  # 100ms
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)


class MicController:
    def __init__(self, stt: ServiceSTT):
        self.stt = stt
        self.loop = asyncio.get_event_loop()
        self.audio_queue = asyncio.Queue()
        self.stream = None
        self.running = False
        self.sender_task = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print("⚠️", status)
        audio_chunk = indata.copy().tobytes()
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, audio_chunk)

    async def _send_loop(self):
        """Lee la cola y envía audio al STT mientras está activo"""
        while self.running:
            try:
                chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.5)
                await self.stt.send_audio_chunk(chunk)
            except asyncio.TimeoutError:
                continue

    async def start(self):
        """Activa el micrófono y notifica al STT"""
        if self.running:
            print("🎙️ Micrófono ya está ON")
            return

        # Avisar al STT que inicia
        await self.stt.start_stream()

        # Abrir stream del micro
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=self._audio_callback
        )
        self.stream.start()

        self.running = True
        print("🎤 Micrófono ACTIVADO")

        # Lanzar tarea para enviar audio
        self.sender_task = asyncio.create_task(self._send_loop())

    async def stop(self):
        """Detiene micrófono y notifica al STT"""
        if not self.running:
            print("🔇 Micrófono ya estaba OFF")
            return

        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        print("🔇 Micrófono DESACTIVADO")

        # Avisar al STT que terminó
        await self.stt.stop_stream()


async def main():
    # 1. Conectar al servidor STT
    stt = ServiceSTT(max_parciales=5)
    await stt.connect()

    mic = MicController(stt)
    solucion = SolucionService()
    tts = TTSService(uri="ws://localhost:8765")
    asyncio.create_task(tts.run())
    print("✅ Conectado. Pulsa ENTER para alternar micrófono ON/OFF. CTRL+C para salir.")

    # Ejecutar en paralelo la lectura de teclado
    while True:
        # Esperar ENTER sin bloquear asyncio
        key = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        key = key.strip()

        if not mic.running:
            # Activar micro
            await mic.start()
        else:
            # Desactivar micro
            await mic.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
