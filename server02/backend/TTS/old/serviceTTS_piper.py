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

# Estado de voz
reproduciendo = False
parar_evento = threading.Event()
cola_texto = Queue()

def publicar_estado(estado):
    client.publish(TOPIC_ESTADO, estado)

def procesar_cola():
    global reproduciendo
    while True:
        try:
            texto = cola_texto.get(timeout=1)
        except Empty:
            continue

        parar_evento.clear()
        reproduciendo = True
        publicar_estado("hablando")

        try:
            with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                for chunk in voice.synthesize_stream_raw(texto):
                    if parar_evento.is_set():
                        print("⏹️ Voz interrumpida.")
                        break
                    data = np.frombuffer(chunk, dtype=np.int16)
                    stream.write(data)
        except Exception as e:
            print(f"❌ Error durante reproducción: {e}")

        reproduciendo = False
        publicar_estado("parado")
        cola_texto.task_done()

# Hilo que procesa la cola permanentemente
threading.Thread(target=procesar_cola, daemon=True).start()

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
        if reproduciendo:
            print("🛑 Cancelando voz actual...")
            parar_evento.set()
        # También puedes vaciar la cola:
        with cola_texto.mutex:
            cola_texto.queue.clear()
        print("🗑️ Cola de texto vaciada.")

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
