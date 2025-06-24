import os
import sys
import contextlib
import time
import keyboard
from RealtimeSTT import AudioToTextRecorder

modo = "manual"

@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

def on_text(text):
    print(f"\n🗣️  USUARIO: {text}")

def on_recording_start():
    print("🎤 Escuchando...")

def on_recording_stop():
    print("⏹️  Grabación terminada")

with suppress_stderr():
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
        on_recording_start=on_recording_start,
        on_recording_stop=on_recording_stop,
    )

print("Presiona [a] para modo automático, [m] para modo manual.")
print("En modo manual, presiona [espacio] para grabar.")

with recorder:
    while True:
        if keyboard.is_pressed('a'):
            if modo != "auto":
                print("🔁 Cambiado a modo AUTOMÁTICO")
                modo = "auto"
                time.sleep(0.5)

        elif keyboard.is_pressed('m'):
            if modo != "manual":
                print("🛑 Cambiado a modo MANUAL")
                modo = "manual"
                time.sleep(0.5)

        if modo == "auto":
            recorder.text(on_text)

        elif modo == "manual":
            if keyboard.is_pressed('space'):
                print("🎤 Iniciando grabación manual")
                recorder.text(on_text)
                time.sleep(0.5)  # Para evitar múltiples activaciones seguidas
