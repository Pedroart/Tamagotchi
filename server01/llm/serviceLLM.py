import requests
import paho.mqtt.client as mqtt
import json

# MQTT config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_INPUT = "voz/texto"
TOPIC_OUTPUT = "habla/texto"

# Ollama config
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

def generar_respuesta_corta(prompt):
    payload = {
        "model": MODEL,
        "system": "Responde en español con una sola frase, de forma clara y breve.",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "top_p": 0.7,
        "max_tokens": 20,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            return "[Error al generar respuesta]"
    except Exception as e:
        return f"[Error: {e}]"

# Callback cuando llega un mensaje
def on_message(client, userdata, msg):
    prompt = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] Prompt recibido: {prompt}")
    respuesta = generar_respuesta_corta(prompt)
    print(f"[LLM] Respuesta: {respuesta}")
    client.publish(TOPIC_OUTPUT, respuesta)

# Inicializar cliente MQTT
client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(TOPIC_INPUT)
client.loop_forever()
