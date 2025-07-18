import asyncio
import websockets
import time
import jiwer
import os
import soundfile as sf
import csv
import random
import psutil

# GPU opcional
try:
    from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo
    nvmlInit()
    def get_gpu_memory():
        handle = nvmlDeviceGetHandleByIndex(0)
        mem = nvmlDeviceGetMemoryInfo(handle)
        return mem.used / (1024*1024)  # MB
except Exception:
    def get_gpu_memory():
        return 0.0

SERVER_URI = "ws://localhost:55000"
AUDIO_DIR = "TTS/dataTest/es_pe_female"
INDEX_FILE = os.path.join(AUDIO_DIR, "line_index.tsv")
OUTPUT_CSV = "evaluation_results.csv"

# Normalizador para ignorar puntuación
import jiwer
normalize = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.Strip(),
    jiwer.RemoveMultipleSpaces()
])

def get_audio_duration(file_path):
    f = sf.SoundFile(file_path)
    return len(f) / f.samplerate

def get_resource_usage():
    process = psutil.Process(os.getpid())
    cpu_percent = process.cpu_percent(interval=None)
    mem_mb = process.memory_info().rss / (1024*1024)
    return cpu_percent, mem_mb

async def send_audio_and_get_transcription(file_path):
    async with websockets.connect(SERVER_URI, max_size=50 * 1024 * 1024) as ws:
        with open(file_path, "rb") as f:
            audio_data = f.read()

        start_time = time.perf_counter()
        await ws.send(audio_data)
        transcription = await ws.recv()
        latency = time.perf_counter() - start_time

        return transcription.strip(), latency

def load_reference_transcriptions():
    refs = {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                fname, text = parts[0], parts[1]
                refs[fname] = text
    return refs

async def evaluate_dataset():
    refs = load_reference_transcriptions()
    
    # ✅ Tomar solo 50 audios aleatorios
    all_files = list(refs.items())
    random.shuffle(all_files)
    selected_files = all_files[:50]

    # CSV: headers
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "filename",
            "audio_duration_s",
            "latency_s",
            "speed_ratio",
            "WER",
            "CPU_percent",
            "RAM_MB",
            "GPU_MB",
            "reference_text",
            "hypothesis_text"
        ])

    wer_scores, latencies, durations, ratios = [], [], [], []

    for fname, ref_text in selected_files:
        audio_path = os.path.join(AUDIO_DIR, fname + ".wav")
        if not os.path.exists(audio_path):
            print(f"⚠️ No existe {audio_path}, lo salto...")
            continue

        # Duración real del audio
        audio_duration = get_audio_duration(audio_path)

        print(f"▶️ Enviando {fname}... ({audio_duration:.2f}s)")
        
        # Medir recursos antes
        cpu_before, ram_before = get_resource_usage()
        gpu_before = get_gpu_memory()

        # Enviar audio y obtener transcripción
        hyp_text, latency = await send_audio_and_get_transcription(audio_path)

        # Medir recursos después
        cpu_after, ram_after = get_resource_usage()
        gpu_after = get_gpu_memory()

        cpu_usage = cpu_after - cpu_before
        ram_usage = ram_after - ram_before
        gpu_usage = gpu_after - gpu_before

        # Calcular WER normalizado
        ref_norm = normalize(ref_text)
        hyp_norm = normalize(hyp_text)

        wer = jiwer.wer(ref_norm, hyp_norm)

        speed_ratio = latency / audio_duration if audio_duration > 0 else 0

        wer_scores.append(wer)
        latencies.append(latency)
        durations.append(audio_duration)
        ratios.append(speed_ratio)

        print(f"   ✅ Ref: {ref_text}")
        print(f"   🤖 Hyp: {hyp_text}")
        print(f"   ⏱️ Audio: {audio_duration:.2f}s | Procesado: {latency:.2f}s | Velocidad: {speed_ratio:.2f}x | WER: {wer:.2%}")
        print(f"   💻 CPU Δ{cpu_usage:.2f}% | RAM Δ{ram_usage:.2f}MB | GPU Δ{gpu_usage:.2f}MB\n")

        # Guardar fila en CSV
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                fname,
                f"{audio_duration:.2f}",
                f"{latency:.2f}",
                f"{speed_ratio:.2f}",
                f"{wer:.4f}",
                f"{cpu_usage:.2f}",
                f"{ram_usage:.2f}",
                f"{gpu_usage:.2f}",
                ref_text,
                hyp_text
            ])

    # Promedios finales
    avg_wer = sum(wer_scores) / len(wer_scores) if wer_scores else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    avg_duration = sum(durations) / len(durations) if durations else 0
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0

    print("📊 RESULTADOS FINALES")
    print(f"  ➡️ Audios evaluados: {len(wer_scores)}")
    print(f"  ⏱️ Latencia promedio: {avg_latency:.2f}s")
    print(f"  🎵 Duración promedio: {avg_duration:.2f}s")
    print(f"  ⚡ Velocidad promedio: {avg_ratio:.2f}x tiempo real")
    print(f"  ❌ WER promedio: {avg_wer:.2%}")
    print(f"  ✅ Resultados guardados en {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(evaluate_dataset())
