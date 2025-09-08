'''
Estudiarlo
'''

import numpy as np
import soundcard as sc
import webrtcvad
import time
from collections import deque
import warnings

# (opcional) silenciar warning de pkg_resources de webrtcvad
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

# ====== Parámetros ======
RATE = 16000
FRAME_MS = 20
FRAME = RATE * FRAME_MS // 1000
VAD_AGGR = 2
THR_CLOSE = 0.65
THR_OPEN  = 0.55
ASR_CHUNK_MS = 500
ASR_CHUNK = RATE * ASR_CHUNK_MS // 1000

def norm_xcorr(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    a = a[:n] - np.mean(a[:n])
    b = b[:n] - np.mean(b[:n])
    na = np.linalg.norm(a) + 1e-8
    nb = np.linalg.norm(b) + 1e-8
    return float(np.dot(a, b) / (na * nb))

def to_pcm16(mono_f32: np.ndarray) -> bytes:
    x = np.clip(mono_f32, -1.0, 1.0)
    x = (x * 32767.0).astype(np.int16)
    return x.tobytes()

def pick_loopback_microphone():
    """
    Intenta elegir un micrófono de loopback de forma robusta.
    1) Usa el nombre del speaker por defecto con include_loopback=True.
    2) Si falla, toma el primer micrófono con isloopback=True.
    3) Si no hay, lista opciones para que el usuario elija manualmente.
    """
    default_speaker = sc.default_speaker()
    # Intento 1: loopback del speaker por defecto
    try:
        lb = sc.get_microphone(default_speaker.name, include_loopback=True)
        if getattr(lb, "isloopback", False):
            return lb
    except Exception:
        pass

    # Intento 2: primer loopback disponible
    for m in sc.all_microphones(include_loopback=True):
        if getattr(m, "isloopback", False):
            return m

    # Si no encontró, informar y listar dispositivos
    print("[ERR] No se encontró dispositivo loopback.")
    print("[INFO] Micrófonos disponibles (incluyendo loopback):")
    for m in sc.all_microphones(include_loopback=True):
        print("   -", m, "| isloopback:", getattr(m, "isloopback", None))
    return None

def main():
    mic = sc.default_microphone()
    loopback_mic = pick_loopback_microphone()

    print(f"[INFO] Mic: {mic}")
    if loopback_mic is None:
        print("[FATAL] No hay loopback disponible. En Linux (PulseAudio/PipeWire) suele aparecer como 'Monitor of ...'.")
        print("       En macOS necesitas instalar un driver (BlackHole, Loopback).")
        return
    print(f"[INFO] Loopback: {loopback_mic}")

    print("[INFO] Ctrl+C para salir.")
    vad = webrtcvad.Vad(VAD_AGGR)

    gate_open = False
    asr_buffer = deque()
    frames_count = 0

    # NOTA: ahora ambos son Microphone.recorder()
    with mic.recorder(samplerate=RATE, channels=1, blocksize=FRAME) as mic_rec, \
         loopback_mic.recorder(samplerate=RATE, channels=2, blocksize=FRAME) as spk_rec:

        while True:
            mic_frame = mic_rec.record(numframes=FRAME).astype(np.float32).flatten()

            spk_frame = spk_rec.record(numframes=FRAME).astype(np.float32)
            # Promedio a mono si viene estéreo
            if spk_frame.ndim == 2:
                spk_mono = np.mean(spk_frame, axis=1).astype(np.float32)
            else:
                spk_mono = spk_frame.astype(np.float32).flatten()

            frames_count += 1

            # VAD
            pcm16 = to_pcm16(mic_frame)
            has_voice = vad.is_speech(pcm16, sample_rate=RATE)
            if not has_voice:
                if gate_open:
                    gate_open = False
                    asr_buffer.clear()
                    print("[GATE] CERRADO (silencio)")
                continue

            # Correlación mic vs loopback
            corr = norm_xcorr(mic_frame, spk_mono)

            # Histeresis
            if gate_open:
                if corr >= THR_CLOSE:
                    gate_open = False
                    asr_buffer.clear()
                    print(f"[GATE] CERRADO (corr={corr:.2f} ~ sistema)")
            else:
                if corr <= THR_OPEN:
                    gate_open = True
                    print(f"[GATE] ABIERTO (corr={corr:.2f} ~ persona)")

            if gate_open:
                asr_buffer.append(mic_frame.copy())
                total = sum(len(x) for x in asr_buffer)
                if total >= ASR_CHUNK:
                    chunk = np.concatenate(list(asr_buffer))[:ASR_CHUNK]
                    asr_buffer.clear()
                    dur = len(chunk) / RATE
                    print(f"[ASR] Enviando chunk de {dur:.2f}s (gate=abierto)")
                    # Aquí integrarías faster-whisper:
                    # segments, info = whisper.transcribe(audio=chunk, language="es", vad_filter=False)
                    # for s in segments: print(f"[TXT] {s.start:.2f}-{s.end:.2f}: {s.text}")

            if frames_count % int((2000 / FRAME_MS)) == 0:
                state = "ABIERTO" if gate_open else "CERRADO"
                print(f"[DBG] corr={corr:.2f} | gate={state}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SALIR] bye!")
