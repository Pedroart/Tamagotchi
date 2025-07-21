import asyncio
import websockets

async def send_audio(file_path):
    uri = "ws://localhost:55000"
    async with websockets.connect(uri) as ws:
        # Leer archivo de audio
        with open(file_path, "rb") as f:
            audio_data = f.read()
        
        await ws.send(audio_data)
        print("📤 Audio enviado")

        # Esperar respuesta
        text = await ws.recv()
        print("📝 Transcripción recibida:", text)

asyncio.run(send_audio("TTS/dataTest/es_pe_female/pef_00610_00009675047.wav"))
