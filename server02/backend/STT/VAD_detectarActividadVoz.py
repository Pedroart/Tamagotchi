import numpy as np
import sounddevice as sd
import torch
from silero_vad import load_silero_vad, VADIterator
import webrtcvad

# ==== Configuración ====
SR = 16000                  # frecuencia de muestreo
BLOCK_SIZE = 512            # para Silero (32 ms aprox)
FRAME_DURATION_MS = 30      # WebRTC solo admite 10, 20 o 30 ms
FRAME_SIZE = int(SR * FRAME_DURATION_MS / 1000)

# ==== Inicializar modelos ====
print("📥 Cargando modelos...")
silero_model = load_silero_vad()
silero_iter = VADIterator(silero_model, sampling_rate=SR)

webrtc_vad = webrtcvad.Vad(2)  # sensibilidad (0=menos, 3=más)

print("✅ Modelos cargados. Comparando...")

def callback(indata, frames, time, status):
    if status:
        print(f"⚠️ {status}")
    
    # --- Silero ---
    audio_f32 = indata[:, 0].astype(np.float32)
    silero_event = silero_iter(audio_f32, return_seconds=True)
    silero_label = "…"  # por defecto no hay cambio
    if silero_event:
        if 'start' in silero_event:
            silero_label = "🟢 START"
        elif 'end' in silero_event:
            silero_label = "🔴 END"
    
    # --- WebRTC ---
    audio_pcm = (indata[:, 0] * 32767).astype(np.int16)
    webrtc_result = []
    for start in range(0, len(audio_pcm), FRAME_SIZE):
        frame = audio_pcm[start:start+FRAME_SIZE]
        if len(frame) < FRAME_SIZE:
            break
        if webrtc_vad.is_speech(frame.tobytes(), sample_rate=SR):
            webrtc_result.append(True)
        else:
            webrtc_result.append(False)

    # Si la mayoría de frames del bloque tienen voz → voz
    if webrtc_result:
        ratio_voice = sum(webrtc_result) / len(webrtc_result)
        webrtc_label = "🟢 VOZ" if ratio_voice > 0.5 else "🔴 SILENCIO"
    else:
        webrtc_label = "…"

    # Mostrar comparación
    print(f"Silero: {silero_label:<10} | WebRTC: {webrtc_label}")

with sd.InputStream(samplerate=SR, blocksize=BLOCK_SIZE, channels=1, callback=callback):
    print("🎙️ Comparando Silero vs WebRTC en tiempo real (Ctrl+C para salir)")
    sd.sleep(15_000)  # escucha 15 segundos
