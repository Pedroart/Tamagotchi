import time
import os
import threading
import numpy as np
import sounddevice as sd
import paho.mqtt.client as mqtt
from piper.voice import PiperVoice
from queue import Queue, Empty

# MQTT Config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_TEXTO = "habla/texto"
TOPIC_PARAR = "habla/stop"
TOPIC_ESTADO = "habla/estado"

# Cargar modelo Piper
print("🔊 Cargando modelo de voz...")
voice = PiperVoice.load("tts/es_ES-sharvard-medium.onnx")
sample_rate = voice.config.sample_rate

# Estado y colas
reproduciendo = False
parar_evento = threading.Event()
cola_texto = Queue()
cola_audio = Queue()

def publicar_estado(estado):
    client.publish(TOPIC_ESTADO, estado)

# 🧠 Sintetiza el texto (productor)
def sintetizador():
    while True:
        try:
            texto = cola_texto.get(timeout=1)
        except Empty:
            continue

        print(f"🎙️ Sintetizando: {texto}")
        audio_buffer = bytearray()
        try:
            for chunk in voice.synthesize_stream_raw(texto):
                if parar_evento.is_set():
                    print("⛔ Interrupción durante síntesis.")
                    break
                audio_buffer += chunk
        except Exception as e:
            print(f"❌ Error al sintetizar: {e}")
            cola_texto.task_done()
            continue

        if not parar_evento.is_set() and audio_buffer:
            cola_audio.put(audio_buffer)
        cola_texto.task_done()

# 🔊 Reproduce el audio (consumidor)
def reproductor():
    global reproduciendo
    while True:
        try:
            audio_buffer = cola_audio.get(timeout=1)
        except Empty:
            continue

        reproducido = False
        reproduciendo = True
        publicar_estado("hablando")

        try:
            with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                data = np.frombuffer(audio_buffer, dtype=np.int16)
                stream.write(data)
                reproducido = True
        except Exception as e:
            print(f"❌ Error durante reproducción: {e}")

        reproduciendo = False
        if reproducido:
            publicar_estado("parado")
        cola_audio.task_done()

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("📡 Conectado a MQTT correctamente")
        client.subscribe(TOPIC_TEXTO)
        client.subscribe(TOPIC_PARAR)
        client.publish(TOPIC_ESTADO, "listo")
        print("📶 Estado publicado: listo")
    else:
        print(f"❌ Fallo al conectar al broker. Código rc={rc}")

def on_message(client, userdata, msg):
    global reproduciendo
    print(f"📩 MQTT: {msg.topic} → {msg.payload.decode()}")

    if msg.topic == TOPIC_TEXTO:
        texto = msg.payload.decode().strip()
        cola_texto.put(texto)
        print(f"🗣️ Encolado: {texto}")

    elif msg.topic == TOPIC_PARAR:
        print("🛑 Recibido comando de stop.")
        parar_evento.set()
        with cola_texto.mutex:
            cola_texto.queue.clear()
        with cola_audio.mutex:
            cola_audio.queue.clear()
        print("🧹 Colas limpiadas.")

# Lanzar hilos de procesamiento
threading.Thread(target=sintetizador, daemon=True).start()
threading.Thread(target=reproductor, daemon=True).start()

# Iniciar cliente MQTT
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print("✅ Servicio TTS listo. Esperando mensajes...")
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n👋 Interrupción detectada. Cerrando servicio TTS...")
    client.disconnect()
    print("🛑 Desconectado correctamente.")
