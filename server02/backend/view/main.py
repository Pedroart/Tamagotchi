# view/main.py
from game import Game
from config import CONFIG
from controls import CONTROLS

from services.stt_runtime import STTRuntime
from services.mic_stream import MicStreamer
from services.service_tts import TTSRuntime   # ← NUEVO
from services.solucion_service import SolucionService

from event_bus import event_bus
event_bus.enable_trace("ai.heard", "ai.move_to", "ai.goal", "ai.state", "speech.state")  # ← añade speech.state

def main():
    # --- TTS: conexión persistente al servidor Piper (ws://localhost:8765) ---
    tts = TTSRuntime("ws://localhost:8765", fast_fire_and_forget=True)
    tts.start()

    # (opcional) smoke test de voz al iniciar
    tts.say("Hola, probando síntesis.", emotion="alegre", interrupt=True)
    sol = SolucionService(
    independence=3,          # 0 mute, 1 backchannel, 2 assistant, 3 autonomous
    comment_interval_sec=3,  # cada cuánto puede emitir una palabra breve
    barge_in=False           # no interrumpir al TTS cuando está hablando
)

    # --- STT: conexión persistente + mic ---
    stt_rt = STTRuntime(max_parciales=10)
    stt_rt.start()
    mic = MicStreamer(stt_rt)

    # (opcional) puente si quieres que el TTS lea el texto final del STT directamente
    # event_bus.subscribe("STT_FINAL", lambda text: event_bus.emit("SOLUCION/FINAL", text))

    try:
        Game(CONFIG, CONTROLS, mic_streamer=mic).loop()
    finally:
        # cierre ordenado
        try:
            mic.stop()
        except:
            pass
        try:
            stt_rt.stop()
        except:
            pass
        try:
            tts.stop()     # ← detén también el runtime del TTS
        except:
            pass

if __name__ == "__main__":
    main()
