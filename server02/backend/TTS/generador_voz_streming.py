import asyncio
import json
import threading
import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro
from queue import Queue, Empty
import re
import websockets
import time

# ======================
# Configuración
# ======================
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# ======================
# Mapeo de emociones → voz + velocidad
# ======================
EMOCIONES = {
    "alegre": {"voice": "af_bella", "speed": 1.3},
    "triste": {"voice": "af_bella", "speed": 0.7},
    "neutral": {"voice": "af_bella", "speed": 1.0},
}

# ======================
# Cargar modelo Kokoro
# ======================
print("🔊 Cargando modelo Kokoro...")
voice1 = Kokoro("TTS/kokoro-v1.0.int8.onnx", "TTS/voices-v1.0.bin")
voice2 = Kokoro("TTS/kokoro-v1.0.int8.onnx", "TTS/voices-v1.0.bin")

print("🚀 Precalentando modelo Kokoro...")
voice1.create("Hola", voice="af_bella", speed=1.0, lang="es")
voice2.create("Hola", voice="af_bella", speed=1.0, lang="es")

sample_rate = 24000  # Frecuencia estándar de Kokoro

# ======================
# Estado global y colas
# ======================
parar_evento = threading.Event()
cola_texto = Queue()   # Oraciones pendientes por sintetizar
cola_audio = Queue()   # Audio pendiente por reproducir
clientes_websocket = set()

# Para mantener el orden de los fragmentos
orden_global = 0

# ======================
# Función para dividir texto en oraciones cortas
# ======================

FIN_DE_LOTE = "__FIN__"

import re

def split_oraciones(texto: str, max_palabras=10, min_palabras=None):
    """
    Divide texto en fragmentos equilibrados:
    1) Separa por oraciones (puntuación y saltos de línea).
    2) Cada oración > max_palabras se trocea en sub-oraciones de max_palabras.
    3) Junta sub-oraciones adyacentes hasta que cada chunk tenga entre min_palabras y max_palabras.
    """
    if min_palabras is None:
        # Por defecto, un 40% de max_palabras
        min_palabras = max(1, max_palabras * 40 // 100)

    # 1) Fragmentar por oraciones (conservando la puntuación)
    sentencias = re.split(r'(?<=[\.\?!])\s+|\n+', texto.strip())
    piezas = []

    # 2) Trocear oraciones largas
    for s in sentencias:
        s = s.strip()
        if not s:
            continue
        palabras = s.split()
        if len(palabras) <= max_palabras:
            piezas.append(s)
        else:
            # trocear en bloques de max_palabras
            for i in range(0, len(palabras), max_palabras):
                trozo = " ".join(palabras[i:i + max_palabras])
                piezas.append(trozo)

    # 3) Agrupar en chunks equilibrados
    resultado = []
    chunk = []
    cuenta = 0

    def cerrar_chunk():
        nonlocal chunk, cuenta
        if chunk:
            resultado.append(" ".join(chunk).strip())
        chunk, cuenta = [], 0

    for trozo in piezas:
        n = len(trozo.split())
        # Si al agregar sobrepasamos max, cerramos chunk actual
        if cuenta + n > max_palabras:
            # Si el chunk actual se queda muy corto (< min), lo dejamos igual;
            # de lo contrario, lo cerramos y comenzamos uno nuevo.
            cerrar_chunk()

        # Agregamos el trozo al chunk
        chunk.append(trozo)
        cuenta += n

        # Si justo llegamos al max o quedamos dentro de [min, max], podemos cerrarlo
        if cuenta >= min_palabras:
            cerrar_chunk()

    # Añadimos cualquier resto
    cerrar_chunk()
    return resultado

# ======================
# Broadcast de estado (robusto)
# ======================
async def broadcast_estado(estado, extra=None):
    if not clientes_websocket:
        return
    msg = {"estado": estado}
    if extra:
        msg.update(extra)
    payload = json.dumps(msg)

    to_remove = []
    for ws in list(clientes_websocket):
        try:
            await ws.send(payload)
        except Exception:
            # cliente ya no responde
            to_remove.append(ws)
    # eliminar clientes desconectados sin error
    for ws in to_remove:
        clientes_websocket.discard(ws)

# ======================
# 🧠 Sintetizador (productor)
# ======================
kokoro_lock = threading.Lock()

def sintetizador(instancia_id):
    """
    Hilo sintetizador que usa una instancia específica de Kokoro.
    instancia_id = 1 usa voice1, instancia_id = 2 usa voice2
    """
    voice_instance = voice1 if instancia_id == 1 else voice2

    while True:
        try:
            texto, emocion, orden = cola_texto.get(timeout=1)
        except Empty:
            continue

        # ✅ FIN DE LOTE → mandar marcador directo con orden
        if texto == FIN_DE_LOTE:
            cola_audio.put((orden, None, FIN_DE_LOTE))
            cola_texto.task_done()
            continue

        print(f"🎙️ [Hilo {instancia_id}] Sintetizando oración [{orden}]: [{emocion}] {texto}")
        try:
            cfg = EMOCIONES.get(emocion, EMOCIONES["neutral"])
            samples, sr = voice_instance.create(
                texto,
                voice=cfg["voice"],
                speed=cfg["speed"],
                lang="es"
            )

            if parar_evento.is_set():
                print(f"⛔ Hilo {instancia_id}: interrupción durante síntesis.")
            else:
                audio_int16 = (samples * 32767).astype(np.int16).tobytes()
                cola_audio.put((orden, audio_int16, texto))

        except Exception as e:
            print(f"❌ Hilo {instancia_id} error al sintetizar: {e}")

        cola_texto.task_done()

# ======================
# 🔊 Reproductor (consumidor ordenado)
# ======================
def reproductor():
    esperado = 1
    en_lote = False
    buffer_ordenado = {}

    with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
        while True:
            try:
                orden, audio_buffer, texto_actual = cola_audio.get(timeout=1)
            except Empty:
                threading.Event().wait(0.05)
                continue

            buffer_ordenado[orden] = (audio_buffer, texto_actual)

            # procesar en orden secuencial
            while esperado in buffer_ordenado:
                audio_buffer, texto_actual = buffer_ordenado.pop(esperado)

                # FIN_DE_LOTE → termina lote
                if texto_actual == FIN_DE_LOTE:
                    main_loop.call_soon_threadsafe(
                        asyncio.create_task,
                        broadcast_estado("parado", {})
                    )
                    print("✅ Lote finalizado correctamente")
                    en_lote = False
                    esperado = 1          # <-- vuelve a 1
                    buffer_ordenado.clear()
                    ultimo_fragmento = time.time()

                    break  # salir del while interno

                # Primer bloque del lote → mandar "hablando"
                if not en_lote:
                    main_loop.call_soon_threadsafe(
                        asyncio.create_task,
                        broadcast_estado("hablando", {}),
                    )
                    en_lote = True

                # reproducir audio
                data = np.frombuffer(audio_buffer, dtype=np.int16)
                stream.write(data)

                esperado += 1

            cola_audio.task_done()

# ======================
# Handler WebSocket
# ======================
async def handler(websocket):
    global orden_global
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
                    texto = re.sub(r'\s+', ' ', texto).strip()
                    # 🔄 Reiniciar numeración de fragmentos para nuevo lote
                    orden_global = 0

                    # dividir y asignar orden
                    oraciones = split_oraciones(texto)
                    for o in oraciones:
                        orden_global += 1
                        cola_texto.put((o, emocion, orden_global))
                    # al final también un FIN_DE_LOTE
                    orden_global += 1
                    cola_texto.put((FIN_DE_LOTE, emocion, orden_global))
                    print(f"🗣️ Encoladas {len(oraciones)} oraciones + FIN_DE_LOTE")


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
        clientes_websocket.discard(websocket)
        print("❌ Cliente desconectado")

# ======================
# Lanzar hilos productor/consumidor
# ======================
main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

async def ws_main():
    print(f"✅ WS TTS en ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(
        handler,
        WS_HOST,
        WS_PORT,
    ):
        await asyncio.Future()  # Mantener vivo

def start_ws_server():
    main_loop.create_task(ws_main())
    main_loop.run_forever()

# Lanzar sintetizadores y reproductor antes del WS
threading.Thread(target=sintetizador, args=(1,), daemon=True).start()
threading.Thread(target=sintetizador, args=(2,), daemon=True).start()
threading.Thread(target=reproductor, daemon=True).start()

# Luego iniciamos servidor
start_ws_server()
