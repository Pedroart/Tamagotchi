import asyncio
import json
import threading
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro
from queue import Queue, Empty
import re
import websockets

# ======================
# Configuración
# ======================
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# ======================
# Mapeo de emociones → voz + velocidad
# ======================
EMOCIONES = {
    "alegre": {"voice": "af_heart", "speed": 1.3},
    "triste": {"voice": "af_heart", "speed": 0.7},
    "neutral": {"voice": "af_heart", "speed": 1.0},
}

# ======================
# Cargar modelo Kokoro
# ======================
print("🔊 Cargando modelo Kokoro...")
voice = Kokoro("TTS/kokoro-v1.0.int8.onnx", "TTS/voices-v1.0.bin")
sample_rate = 24000  # Frecuencia estándar de Kokoro

# ======================
# Estado global y colas
# ======================
parar_evento = threading.Event()
cola_texto = Queue()   # Oraciones pendientes por sintetizar
cola_audio = Queue()   # Audio pendiente por reproducir
clientes_websocket = set()

# ======================
# Función para dividir texto en oraciones cortas
# ======================
def split_oraciones(texto: str, max_palabras=10):
    """
    Divide el texto por .,¡!¿? o conjunciones y/o.
    Si una oración sigue siendo larga, la fragmenta en bloques de max_palabras.
    """
    partes = re.split(r'[.,¡!¿?\n]|\sy\s|\sY\s|\so\s|\sO\s', texto)
    oraciones_finales = []

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        palabras = parte.split()
        if len(palabras) <= max_palabras:
            oraciones_finales.append(parte)
        else:
            for i in range(0, len(palabras), max_palabras):
                fragmento = " ".join(palabras[i:i + max_palabras])
                oraciones_finales.append(fragmento)

    return oraciones_finales

# ======================
# Broadcast de estado
# ======================
async def broadcast_estado(estado, extra=None):
    """Envía estado a todos los clientes WebSocket conectados."""
    if clientes_websocket:
        msg = {"estado": estado}
        if extra:
            msg.update(extra)
        payload = json.dumps(msg)
        await asyncio.gather(*(c.send(payload) for c in clientes_websocket))

# ======================
# 🧠 Sintetizador (productor)
# ======================
def sintetizador():
    while True:
        try:
            texto, emocion = cola_texto.get(timeout=1)
        except Empty:
            continue

        print(f"🎙️ Sintetizando oración: [{emocion}] {texto}")
        try:
            cfg = EMOCIONES.get(emocion, EMOCIONES["neutral"])
            samples, sr = voice.create(
                texto,
                voice=cfg["voice"],
                speed=cfg["speed"],
                lang="es"
            )

            if parar_evento.is_set():
                print("⛔ Interrupción durante síntesis.")
            else:
                audio_int16 = (samples * 32767).astype(np.int16).tobytes()
                cola_audio.put((audio_int16, texto))

        except Exception as e:
            print(f"❌ Error al sintetizar: {e}")

        cola_texto.task_done()

# ======================
# 🔊 Reproductor (consumidor)
# ======================
def reproductor():
    # Usamos un solo OutputStream abierto de forma persistente
    with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
        while True:
            # Esperar hasta que haya al menos 2 bloques en cola para mayor fluidez
            while cola_audio.qsize() < 2:
                threading.Event().wait(0.05)

            try:
                audio_buffer, texto_actual = cola_audio.get(timeout=1)
            except Empty:
                continue

            asyncio.run(broadcast_estado("hablando", {"texto": texto_actual}))
            data = np.frombuffer(audio_buffer, dtype=np.int16)
            stream.write(data)
            asyncio.run(broadcast_estado("parado", {"texto": texto_actual}))

            cola_audio.task_done()

# ======================
# Handler WebSocket
# ======================
async def handler(websocket):
    clientes_websocket.add(websocket)
    print("📡 Cliente conectado")
    await websocket.send(json.dumps({"estado": "listo"}))

    try:
        async for message in websocket:
            print(f"📩 WS mensaje: {message}")
            try:
                data = json.loads(message)
            except:
                continue

            cmd = data.get("cmd")
            if cmd == "say":
                texto = data.get("text", "").strip()
                emocion = data.get("emotion", "neutral")
                if texto:
                    oraciones = split_oraciones(texto)
                    for o in oraciones:
                        cola_texto.put((o, emocion))
                    print(f"🗣️ Encoladas {len(oraciones)} oraciones con emoción '{emocion}'.")

            elif cmd == "stop":
                print("🛑 Recibido comando STOP")
                parar_evento.set()
                with cola_texto.mutex:
                    cola_texto.queue.clear()
                with cola_audio.mutex:
                    cola_audio.queue.clear()
                await websocket.send(json.dumps({"estado": "parado"}))
                parar_evento.clear()

    except Exception as e:
        print(f"❌ Error WS: {e}")

    finally:
        clientes_websocket.remove(websocket)
        print("❌ Cliente desconectado")

# ======================
# Lanzar hilos productor/consumidor
# ======================
# 🔥 Lanzamos 2 hilos sintetizadores en paralelo para mayor velocidad
for _ in range(2):
    threading.Thread(target=sintetizador, daemon=True).start()

# Un solo hilo reproductor
threading.Thread(target=reproductor, daemon=True).start()

# ======================
# Iniciar servidor WebSocket
# ======================
async def ws_main():
    print(f"✅ WS TTS en ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()

try:
    asyncio.run(ws_main())
except KeyboardInterrupt:
    print("\n👋 Cerrando servidor WS...")
