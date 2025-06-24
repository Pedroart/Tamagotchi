import os
import asyncio
import threading
import numpy as np
import sounddevice as sd
import paho.mqtt.client as mqtt
from kokoro_onnx import Kokoro

# MQTT Config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_TEXTO = "habla/texto"
TOPIC_PARAR = "habla/stop"
TOPIC_ESTADO = "habla/estado"

# Cargar modelo Kokoro
kokoro = Kokoro("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")

# Estado de voz
reproduciendo = False
parar_evento = threading.Event()

# MQTT client (global para publicar estado desde hilos)
client = mqtt.Client()

def publicar_estado(estado):
    client.publish(TOPIC_ESTADO, estado)

async def hablar_async(texto, voice_name="af_sarah", emotion="neutral"):
    global reproduciendo

    reproduciendo = True
    publicar_estado("hablando")
    parar_evento.clear()

    try:
        stream = kokoro.create_stream(texto, voice=voice_name, speed=1.0, lang="es")
        async for samples, sample_rate in stream:
            if parar_evento.is_set():
                break
            sd.play(samples, sample_rate)
            sd.wait()
    except Exception as e:
        print("❌ Error en reproducción:", e)

    reproduciendo = False
    publicar_estado("parado")

# Hilo puente que lanza asyncio desde entorno no-async
def hilo_hablar(texto):
    asyncio.run(hablar_async(texto))

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    print("📡 Conectado a MQTT")
    client.subscribe(TOPIC_TEXTO)
    client.subscribe(TOPIC_PARAR)

def on_message(client, userdata, msg):
    global reproduciendo, parar_evento

    if msg.topic == TOPIC_TEXTO:
        texto = msg.payload.decode()
        print(f"🗣️ Texto recibido: {texto}")
        if reproduciendo:
            print("🔁 Deteniendo reproducción anterior...")
            parar_evento.set()
            sd.stop()
        threading.Thread(target=hilo_hablar, args=(texto,), daemon=True).start()

    elif msg.topic == TOPIC_PARAR:
        if reproduciendo:
            print("⏹️ Parando voz...")
            parar_evento.set()
            sd.stop()
            publicar_estado("parado")

# Iniciar MQTT
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print("✅ Servicio TTS con Kokoro iniciado")
client.loop_forever()
