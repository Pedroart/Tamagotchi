import asyncio
import sounddevice as sd
from kokoro_onnx import Kokoro

async def main():
    kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

    text = "¡Hola! Esto se genera en tiempo real con Kokoro‑onnx."
    stream = kokoro.create_stream(text, voice="af_sarah", speed=1.0, lang="es")

    async for samples, sample_rate in stream:
        sd.play(samples, sample_rate)
        sd.wait()

if __name__ == "__main__":
    asyncio.run(main())
