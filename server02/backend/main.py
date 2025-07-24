import asyncio
import websockets
import json
import sounddevice as sd
import numpy as np
from pynput import keyboard as kb
import difflib
import re

# === CONFIGURACIÓN ===
STT_URI = "ws://localhost:55000"  # Servidor de reconocimiento
TTS_URI = "ws://localhost:8765"   # Servidor Kokoro TTS
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

mic_active = False
stream = None
main_loop = None

# === ESTADO ===
parcial_anterior = None  # se usará como referencia para evaluar el siguiente parcial

# =====================================================
# FUNCIONES DE AUDIO MICRÓFONO → ENVÍO AL STT
# =====================================================
def mic_callback(indata, frames, time, status):
    if status:
        print(f"⚠️ Estado mic: {status}")
    pcm_chunk = (indata[:, 0] * 32767).astype(np.int16).tobytes()
    if main_loop and websocket_stt:
        asyncio.run_coroutine_threadsafe(websocket_stt.send(pcm_chunk), main_loop)

async def start_mic():
    global stream, mic_active
    if stream is None:
        await websocket_stt.send("__START__")
        print("🎙️ Micrófono ACTIVADO")
        mic_active = True
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_SIZE,
            callback=mic_callback
        )
        stream.start()

async def stop_mic():
    global stream, mic_active
    if stream is not None:
        stream.stop()
        stream.close()
        stream = None
        mic_active = False
        await websocket_stt.send("__END__")
        print("🔇 Micrófono DESACTIVADO")

async def toggle_mic():
    if mic_active:
        await stop_mic()
    else:
        await start_mic()

# =====================================================
# FUNCIONES PARA COMPARAR PARCIALES
# =====================================================
def normalizar(texto: str):
    return re.sub(r'[^a-z0-9áéíóúüñ ]+', '', texto.lower()).strip()

def similitud(p1, p2):
    return difflib.SequenceMatcher(None, p1, p2).ratio()

def comparar_parciales(anterior, actual):
    anterior_tokens = normalizar(anterior).split()
    actual_tokens   = normalizar(actual).split()
    resultados = []
    for palabra_prev in anterior_tokens:
        mejor_sim = 0.0
        mejor_match = "-"
        for palabra_actual in actual_tokens:
            sim = similitud(palabra_prev, palabra_actual)
            if sim > mejor_sim:
                mejor_sim = sim
                mejor_match = palabra_actual
        resultados.append((palabra_prev, mejor_match, mejor_sim))
    return resultados

# =====================================================
# CLIENTE UNIFICADO
# =====================================================
async def unified_client():
    global websocket_stt, websocket_tts, main_loop, parcial_anterior
    main_loop = asyncio.get_running_loop()

    # Conexiones a ambos servicios
    websocket_stt = await websockets.connect(STT_URI, max_size=50*1024*1024)
    websocket_tts = await websockets.connect(TTS_URI)

    print(f"✅ Conectado a STT en {STT_URI}")
    print(f"✅ Conectado a TTS en {TTS_URI}")

    # === Lector STT ===
    async def stt_receiver():
        global parcial_anterior
        async for msg in websocket_stt:
            if msg.startswith("(parcial)"):
                print(f"📝 Parcial: {msg}")

                # Si tenemos parcial anterior → compararlo
                if parcial_anterior:
                    cambios = comparar_parciales(parcial_anterior, msg)
                    print("📊 Evolución vs parcial anterior:")
                    for prev_word, new_match, sim in cambios:
                        print(f"  {prev_word:<12} → {new_match:<12} ({sim*100:.1f}%)")

                # Actualizar para siguiente ciclo
                parcial_anterior = msg

            else:
                # Texto final recibido
                print(f"✅ Final recibido: {msg}")
                await send_to_tts(msg.strip(), emotion="neutral")

                # Reiniciar referencia de parciales
                parcial_anterior = None

    # === Lector TTS ===
    async def tts_receiver():
        async for msg in websocket_tts:
            print(f"🔊 Estado TTS: {msg}")

    # Lanzar receptores paralelos
    asyncio.create_task(stt_receiver())
    asyncio.create_task(tts_receiver())

    # Listener de teclado → toggle mic
    def on_press(key):
        if key == kb.Key.space:
            asyncio.run_coroutine_threadsafe(toggle_mic(), main_loop)
        elif key == kb.Key.esc:
            print("🛑 Saliendo...")
            return False

    listener = kb.Listener(on_press=on_press)
    listener.start()
    print("✅ Pulsa ESPACIO para alternar micrófono ON/OFF (ESC para salir)")

    # Mantener vivo
    while listener.running:
        await asyncio.sleep(0.1)

# =====================================================
# ENVÍO DE TEXTO AL SERVIDOR TTS
# =====================================================
async def send_to_tts(texto: str, emotion="neutral"):
    payload = {
        "cmd": "say",
        "text": texto,
        "emotion": emotion
    }
    await websocket_tts.send(json.dumps(payload))
    print(f"📤 Enviado al TTS: {texto} [{emotion}]")

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    try:
        asyncio.run(unified_client())
    except KeyboardInterrupt:
        print("👋 Cerrando cliente...")
