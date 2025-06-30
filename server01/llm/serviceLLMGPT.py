import os
import openai
import paho.mqtt.client as mqtt
import threading
import time

# MQTT config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_INPUT = "voz/texto"
TOPIC_OUTPUT = "habla/texto"
TOPIC_ESTADO = "habla/estado"

# OpenAI config
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-3.5-turbo"

tts_listo = threading.Event()

def generar_respuesta(prompt, client):
    if not tts_listo.is_set():
        print("⏳ Esperando a que TTS esté listo...")
        tts_listo.wait()
        print("✅ TTS listo. Generando respuesta...")

    buffer = ""
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        top_p=0.3,
        stream=True
    )

    # Procesar cada fragmento del stream
    for chunk in response:
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", "")
        if content:
            buffer += content
            # publicar al llegar a un separador
            if any(sep in content for sep in (".", ";", ",", "?", "!")):
                client.publish(TOPIC_OUTPUT, buffer.strip(), qos=1, retain=True)
                print("📤 Publicado:", buffer.strip())
                buffer = ""
    # publicar resto
    if buffer.strip():
        client.publish(TOPIC_OUTPUT, buffer.strip(), qos=1, retain=True)
        print("📤 Publicado final:", buffer.strip())

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode("utf-8").strip()
    if topic == TOPIC_INPUT:
        print(f"[MQTT] Prompt recibido: {payload}")
        generar_respuesta(payload, client)
    elif topic == TOPIC_ESTADO:
        if payload.lower() == "listo":
            print("📶 TTS está listo.")
            tts_listo.set()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("📡 Conectado a MQTT")
        client.subscribe(TOPIC_INPUT)
        client.subscribe(TOPIC_ESTADO)
    else:
        print("⚠️ Error conexión MQTT:", rc)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print("✅ Servicio LLM (OpenAI) listo. Esperando mensajes...")
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n👋 Interrupción, desconectando MQTT...")
    client.disconnect()
    print("🛑 Desconectado.")
