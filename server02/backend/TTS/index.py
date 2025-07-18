import asyncio
import websockets
import tempfile
from faster_whisper import WhisperModel

# Carga del modelo (elige tiny/base/small/medium/large)
model = WhisperModel("small", device="cpu", compute_type="int8")

async def handle_audio(websocket):
    print("Cliente conectado")
    
    async for message in websocket:
        print("📥 Recibido audio (bytes)", len(message))
        
        # Guardar audio temporalmente
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(message)
            tmp_path = tmp.name
        
        # Transcribir
        segments, info = model.transcribe(tmp_path, language="en")
        text = " ".join([seg.text for seg in segments])
        
        print(f"✅ Transcripción: {text}")
        
        # Enviar resultado al cliente
        await websocket.send(text)

async def main():
    async with websockets.serve(handle_audio, "0.0.0.0", 8000):
        print("🚀 Servidor WebSocket escuchando en ws://localhost:8000")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
