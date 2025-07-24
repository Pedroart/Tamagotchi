import asyncio
import websockets
import json
from pynput import keyboard as kb

from audio_input import AudioInput
from partial_comparison import (
    comparar_parciales_difflib,
    comparar_parciales_llm,
    imprimir_resultados_difflib,
    imprimir_resultados_llm
)

# Configuración
STT_URI = "ws://localhost:55000"
TTS_URI = "ws://localhost:8765"

# Estado global
parcial_anterior = None          # para comparar con el siguiente
memoria_incremental = ""         # texto consolidado incrementalmente
borrador_anticipado = ""         # pensamiento preliminar en tiempo real

# Instancia de audio
audio = AudioInput()


# =====================================================
# ENVÍO DE TEXTO AL SERVIDOR TTS
# =====================================================
async def send_to_tts(ws_tts, texto: str, emotion="neutral"):
    payload = {
        "cmd": "say",
        "text": texto,
        "emotion": emotion
    }
    await ws_tts.send(json.dumps(payload))
    print(f"📤 Enviado al TTS: {texto} [{emotion}]")


# =====================================================
# CLIENTE UNIFICADO
# =====================================================
async def unified_client():
    global parcial_anterior, memoria_incremental, borrador_anticipado
    audio.main_loop = asyncio.get_running_loop()

    # Conexiones WebSocket
    audio.websocket_stt = await websockets.connect(STT_URI, max_size=50*1024*1024)
    websocket_tts = await websockets.connect(TTS_URI)

    print(f"✅ Conectado a STT en {STT_URI}")
    print(f"✅ Conectado a TTS en {TTS_URI}")

    # === Lector STT ===
    async def stt_receiver():
        global parcial_anterior, memoria_incremental, borrador_anticipado

        async for msg in audio.websocket_stt:

            # ========== PARCIALES ==========
            if msg.startswith("(parcial)"):
                print(f"📝 Parcial: {msg}")

                # Si existe un parcial anterior, comparamos
                if parcial_anterior:
                    # Usamos comparación semántica con LLM si está disponible
                    data_llm = await comparar_parciales_llm(parcial_anterior, msg)
                    imprimir_resultados_llm(data_llm)
                    texto_consolidado = data_llm["consolidado"]

                else:
                    # Primer parcial → lo tomamos directo
                    texto_consolidado = msg.replace("(parcial)", "").strip()

                # Actualizamos memoria incremental
                memoria_incremental = texto_consolidado
                print(f"🧠 Memoria incremental actual: {memoria_incremental}")

                # Pensamiento anticipado: aquí podríamos usar LangGraph #3,
                # por ahora simulamos un borrador incremental
                borrador_anticipado = f"Estoy entendiendo que preguntas sobre: {memoria_incremental}"
                print(f"🤔 Borrador anticipado: {borrador_anticipado}")

                # Guardamos este parcial para comparar el siguiente
                parcial_anterior = msg

            # ========== FINAL ==========
            else:
                print(f"✅ Final recibido: {msg.strip()}")

                # Consolidamos final + memoria + borrador anticipado
                final_text = msg.strip()
                respuesta_final = consolidar_final_simple(
                    memoria_incremental,
                    final_text,
                    borrador_anticipado
                )

                print(f"✅ Respuesta final consolidada: {respuesta_final}")

                # Mandar la respuesta al TTS
                await send_to_tts(websocket_tts, respuesta_final, emotion="neutral")

                # Reset para la próxima frase
                parcial_anterior = None
                memoria_incremental = ""
                borrador_anticipado = ""

    # === Lector TTS ===
    async def tts_receiver():
        async for msg in websocket_tts:
            print(f"🔊 Estado TTS: {msg}")

    # Lanzar tareas en paralelo
    asyncio.create_task(stt_receiver())
    asyncio.create_task(tts_receiver())

    # Listener de teclado → toggle mic
    def on_press(key):
        if key == kb.Key.space:
            asyncio.run_coroutine_threadsafe(audio.toggle_mic(), audio.main_loop)
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
# CONSOLIDAR FINAL (por ahora simple)
# =====================================================
def consolidar_final_simple(memoria: str, final_text: str, borrador: str) -> str:
    """
    Esta función genera la respuesta final.
    Más adelante la reemplazaremos por LangGraph #2.
    """
    return f"{final_text}"  # Por ahora devolvemos el texto final directo


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    try:
        asyncio.run(unified_client())
    except KeyboardInterrupt:
        print("👋 Cerrando cliente...")
