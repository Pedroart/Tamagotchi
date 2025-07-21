import os
import sys
import contextlib

# Contexto para ocultar stderr (mensajes de C++)
@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

# Ocultar stderr durante la importación del módulo problemático
with suppress_stderr():
    from RealtimeSTT import AudioToTextRecorder

def on_text(text):
    print(f"\n>> {text}")

recorder = AudioToTextRecorder(
    model="tiny",
    device="cpu",
    compute_type="int8",
    language="es",
    batch_size=1,
    beam_size=1,
    use_microphone=True,
    spinner=False,
    enable_realtime_transcription=False,
    level=40,
    no_log_file=True,
    handle_buffer_overflow=True,
    print_transcription_time=False,
)

with recorder:
    while True:
        recorder.text(on_text)
