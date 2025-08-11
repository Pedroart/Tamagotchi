import asyncio
import json
import threading
import numpy as np
import sounddevice as sd
from queue import Queue, Empty
import re
import websockets
import time
from piper.voice import PiperVoice

# === Configuración ===
WS_HOST = "0.0.0.0"
WS_PORT = 8765
FIN_DE_LOTE = "__FIN__"
MODEL_PATH = "TTS/es_MX-claude-14947-epoch-high.onnx"

EMOCIONES = {
    "alegre": {"speed": 1.3},
    "triste": {"speed": 0.7},
    "neutral": {"speed": 1.0},
}

# === Inicialización ===
print("🔊 Cargando modelo Piper...")
voice = PiperVoice.load(MODEL_PATH)
sample_rate = voice.config.sample_rate
print("✅ Piper listo.")

# === Variables globales ===
parar_evento = threading.Event()
cola_texto = Queue()
clientes_websocket = set()
orden_global = 0
main_loop = asyncio.new_event_loop()

# === Funciones auxiliares ===
def split_oraciones(texto):
    texto = re.sub(r'\s+', ' ', texto).strip()
    return [o.strip() for o in re.split(r'(?<=[.!?])\s+', texto) if o.strip()]

async def broadcast_estado(estado):
    if not clientes_websocket: return
    mensaje = json.dumps({"estado": estado})
    for ws in list(clientes_websocket):
        try:
            await ws.send(mensaje)
        except:
            clientes_websocket.discard(ws)

# === Pipeline: síntesis + reproducción en vivo ===
def pipeline_sintetizador_reproductor():
    with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
        while True:
            try:
                texto, emocion, orden = cola_texto.get(timeout=1)
            except Empty:
                continue

            if texto == FIN_DE_LOTE:
                asyncio.run_coroutine_threadsafe(broadcast_estado("parado"), main_loop)
                cola_texto.task_done()
                continue

            print(f"🎙️ [{orden}] Sintetizando + reproduciendo → {texto}")
            asyncio.run_coroutine_threadsafe(broadcast_estado("hablando"), main_loop)

            for chunk in voice.synthesize(texto):
                if parar_evento.is_set():
                    break
                data = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
                stream.write(data)

            asyncio.run_coroutine_threadsafe(broadcast_estado("parado"), main_loop)
            cola_texto.task_done()

# === WebSocket handler ===
async def handler(websocket):
    global orden_global
    clientes_websocket.add(websocket)
    print("📡 Cliente conectado")
    await websocket.send(json.dumps({"estado": "listo"}))

    try:
        async for mensaje in websocket:
            datos = json.loads(mensaje)
            cmd = datos.get("cmd")

            if cmd == "say":
                texto = datos.get("text", "").strip()
                emocion = datos.get("emotion", "neutral")
                if texto:
                    orden_global = 0
                    for oracion in split_oraciones(texto):
                        orden_global += 1
                        cola_texto.put((oracion, emocion, orden_global))
                    orden_global += 1
                    cola_texto.put((FIN_DE_LOTE, emocion, orden_global))

            elif cmd == "stop":
                parar_evento.set()
                with cola_texto.mutex:
                    cola_texto.queue.clear()
                await websocket.send(json.dumps({"estado": "parado"}))
                parar_evento.clear()

    finally:
        clientes_websocket.discard(websocket)
        print("❌ Cliente desconectado")

# === Servidor WebSocket ===
async def ws_main():
    print(f"✅ WS TTS activo en ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()

def start_ws_server():
    asyncio.set_event_loop(main_loop)
    main_loop.create_task(ws_main())
    main_loop.run_forever()

# === Iniciar pipeline ===
threading.Thread(target=pipeline_sintetizador_reproductor, daemon=True).start()
start_ws_server()
