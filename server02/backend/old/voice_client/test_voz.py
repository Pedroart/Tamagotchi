import asyncio
import sounddevice as sd
import numpy as np

from servicio.serviceSTT import ServiceSTT

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = 'int16'
CHUNK_DURATION = 0.1  # 100ms por chunk
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

async def enviar_audio_microfono(stt: ServiceSTT, duracion_segundos=4):
    """
    Captura el micrófono por `duracion_segundos` y envía los chunks al STT.
    """
    loop = asyncio.get_event_loop()
    cola_audio = asyncio.Queue()

    # Callback del stream -> mete chunks en la cola
    def audio_callback(indata, frames, time, status):
        if status:
            print("⚠️", status)
        # PCM int16 listo para enviar
        audio_chunk = indata.copy().tobytes()
        loop.call_soon_threadsafe(cola_audio.put_nowait, audio_chunk)

    # Abrir stream del micrófono
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=audio_callback):
        print(f"🎙️ Grabando por {duracion_segundos}s...")

        # Esperar que termine la grabación
        grabando = asyncio.create_task(asyncio.sleep(duracion_segundos))

        while not grabando.done():
            try:
                chunk = await asyncio.wait_for(cola_audio.get(), timeout=0.5)
                await stt.send_audio_chunk(chunk)
            except asyncio.TimeoutError:
                continue

    print("✅ Grabación terminada")

async def main():
    stt = ServiceSTT(max_parciales=5)
    await stt.connect()

    # 🔥 1. START
    await stt.start_stream()
    print("⚡ START enviado")

    # 🔊 2. Capturar y enviar audio
    await enviar_audio_microfono(stt, duracion_segundos=15)

    # 🏁 3. STOP
    await stt.stop_stream()
    print("🏁 STOP enviado")

    # ⏳ Esperar respuesta final del servidor
    await asyncio.sleep(3)
    print("📝 Último parcial:", stt.last_partial)
    print("✅ Último final:", stt.last_final)

    await stt.close()

asyncio.run(main())
