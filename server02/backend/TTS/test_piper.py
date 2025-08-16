# piper_benchmark.py
import re
import time
import argparse

try:
    import sounddevice as sd
    HAS_SD = True
except Exception:
    HAS_SD = False

from piper.voice import PiperVoice

WORD_RE = re.compile(r"\w+", flags=re.UNICODE)

def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))

def synthesize_and_measure(voice: PiperVoice, text: str, stream=None):
    """
    Devuelve métricas por utterance:
      - ttfb_ms
      - dur_audio_s
      - rtf
      - tiempo_total_ms
      - ms_por_palabra
      - palabras
    Reproduce si 'stream' no es None.
    """
    palabras = count_words(text)
    sr = voice.config.sample_rate
    channels = 1

    t0 = time.perf_counter()
    t_first = None
    total_samples = 0

    for chunk in voice.synthesize(text):
        if t_first is None:
            t_first = time.perf_counter()
        if stream is not None:
            # Escribe bytes crudos INT16
            stream.write(chunk.audio_int16_bytes)
        total_samples += len(chunk.audio_int16_bytes) // 2  # int16=2 bytes

    t1 = time.perf_counter()

    if t_first is None:
        # No llegó ningún chunk (texto vacío u error)
        return {
            "ttfb_ms": None,
            "dur_audio_s": 0.0,
            "rtf": None,
            "tiempo_total_ms": round((t1 - t0) * 1000.0, 2),
            "ms_por_palabra": None,
            "palabras": palabras,
        }

    dur_audio_s = total_samples / max(1, sr * channels)
    ttfb_ms = (t_first - t0) * 1000.0
    tiempo_total_ms = (t1 - t0) * 1000.0
    rtf = (t1 - t0) / max(1e-9, dur_audio_s)
    ms_por_palabra = (tiempo_total_ms / max(1, palabras)) if palabras else None

    return {
        "ttfb_ms": round(ttfb_ms, 2),
        "dur_audio_s": round(dur_audio_s, 3),
        "rtf": round(rtf, 3),
        "tiempo_total_ms": round(tiempo_total_ms, 2),
        "ms_por_palabra": round(ms_por_palabra, 2) if ms_por_palabra else None,
        "palabras": palabras,
    }

def main():
    ap = argparse.ArgumentParser(description="Benchmark simple de Piper TTS")
    ap.add_argument("-m", "--model", required=True, help="Ruta al modelo .onnx de Piper")
    ap.add_argument("-t", "--text", default="Hola, esta es una prueba de síntesis con Piper.",
                    help="Texto a sintetizar")
    ap.add_argument("-n", "--repeat", type=int, default=1, help="Número de repeticiones")
    ap.add_argument("--no-audio", action="store_true", help="No reproducir audio (solo medir)")
    args = ap.parse_args()

    print(f"🔊 Cargando modelo Piper: {args.model}")
    voice = PiperVoice.load(args.model)
    sr = voice.config.sample_rate
    print(f"✅ Modelo listo. sample_rate={sr} Hz")

    # Abrir stream si hay audio
    stream = None
    if not args.no_audio:
        if not HAS_SD:
            print("⚠️ sounddevice no disponible; se medirá sin reproducir audio.")
        else:
            try:
                stream = sd.RawOutputStream(samplerate=sr, channels=1, dtype="int16")
                stream.start()
            except Exception as e:
                print(f"⚠️ No se pudo abrir salida de audio: {e}. Se medirá sin audio.")
                stream = None

    # Ejecutar repeticiones
    totals = {"ttfb_ms": 0.0, "rtf": 0.0, "ms_por_palabra": 0.0}
    counts = {"ttfb_ms": 0, "rtf": 0, "ms_por_palabra": 0}

    for i in range(1, args.repeat + 1):
        print(f"\n▶️  Utterance {i}/{args.repeat}: {args.text!r}")
        m = synthesize_and_measure(voice, args.text, stream=stream)
        print(
            f"   TTFB: {m['ttfb_ms']} ms | Audio: {m['dur_audio_s']} s | "
            f"RTF: {m['rtf']} | Total: {m['tiempo_total_ms']} ms | "
            f"ms/palabra: {m['ms_por_palabra']} | palabras: {m['palabras']}"
        )

        # Acumular promedios (ignorando None)
        for k in ["ttfb_ms", "rtf", "ms_por_palabra"]:
            if m[k] is not None:
                totals[k] += m[k]
                counts[k] += 1

    # Cerrar stream
    if stream is not None:
        try:
            stream.stop(); stream.close()
        except Exception:
            pass

    # Resumen
    def avg(key):
        return round(totals[key] / counts[key], 3) if counts[key] else None

    print("\n📊 Promedios:")
    print(f"   TTFB medio: {avg('ttfb_ms')} ms")
    print(f"   RTF medio: {avg('rtf')}")
    print(f"   ms/palabra medio: {avg('ms_por_palabra')}")

if __name__ == "__main__":
    main()
