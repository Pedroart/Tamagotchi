import os
import sys
import contextlib
import time
import threading
import paho.mqtt.client as mqtt
from RealtimeSTT import AudioToTextRecorder

modo = "manual"
solicitar_escucha = False

# MQTT Config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_MODO = "voz/modo"
TOPIC_ACCION = "voz/escuchar"
TOPIC_ESTADO = "voz/estado"
TOPIC_TEXTO = "voz/texto"

# Oculta stderr molesto de NNPACK
@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

# MQTT Callback
def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC_MODO)
    client.subscribe(TOPIC_ACCION)

def on_message(client, userdata, msg):
    global modo, solicitar_escucha

    if msg.topic == TOPIC_MODO:
        modo = msg.payload.decode().strip()
        print(f"🔄 Modo cambiado a: {modo}")

    elif msg.topic == TOPIC_ACCION and modo == "manual":
        solicitar_escucha = True

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Arranca cliente MQTT en segundo plano
threading.Thread(target=client.loop_forever, daemon=True).start()

# Callbacks de STT
def on_text(text):
    print(f"\n🗣️  Texto detectado: {text}")
    client.publish(TOPIC_TEXTO, text)

def on_recording_start():
    client.publish(TOPIC_ESTADO, "escuchando")

def on_recording_stop():
    client.publish(TOPIC_ESTADO, "procesando")

# Cargar el STT
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



with recorder:
    print("Modelo cargado")
    try:
        while True:
            if modo == "auto":
                recorder.text(on_text)

            elif modo == "manual":
                if solicitar_escucha:
                    recorder.text(on_text)
                    solicitar_escucha = False
    except KeyboardInterrupt:
        print("\n👋 Interrupción detectada. Cerrando STT...")

