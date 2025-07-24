import asyncio
import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

class AudioInput:
    def __init__(self):
        self.stream = None
        self.mic_active = False
        self.main_loop = None
        self.websocket_stt = None

    def mic_callback(self, indata, frames, time, status):
        if status:
            print(f"⚠️ Estado mic: {status}")
        pcm_chunk = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        if self.main_loop and self.websocket_stt:
            asyncio.run_coroutine_threadsafe(
                self.websocket_stt.send(pcm_chunk),
                self.main_loop
            )

    async def start_mic(self):
        if self.stream is None:
            await self.websocket_stt.send("__START__")
            print("🎙️ Micrófono ACTIVADO")
            self.mic_active = True
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SIZE,
                callback=self.mic_callback
            )
            self.stream.start()

    async def stop_mic(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            self.mic_active = False
            await self.websocket_stt.send("__END__")
            print("🔇 Micrófono DESACTIVADO")

    async def toggle_mic(self):
        if self.mic_active:
            await self.stop_mic()
        else:
            await self.start_mic()
