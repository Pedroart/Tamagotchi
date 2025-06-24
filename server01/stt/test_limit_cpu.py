from RealtimeSTT import AudioToTextRecorder

def on_text(text):
    print(f"\n>> {text}")

recorder = AudioToTextRecorder(
    model="tiny",                     # modelo más rápido compatible
    device="cpu",                     # evita GPU si no está disponible
    compute_type="int8",              # usa cuantización si está soportada
    language="es",                    # evita autodetección (más lenta)
    batch_size=1,                     # más rápido para CPUs lentas
    beam_size=1,                      # greedy decoding = menos carga
    use_microphone=True,             # usa micro local
    spinner=False,                    # desactiva animación
    enable_realtime_transcription=False,  # importante: desactivar realtime si estás en CPU
    level=40,                         # logging.ERROR = menos salida en consola
    no_log_file=True,                 # evita I/O en disco
    handle_buffer_overflow=True,      # evita errores en buffers saturados
    print_transcription_time=False,   # desactiva benchmarking si no lo necesitas
)

with recorder:
    while True:
        recorder.text(on_text)
