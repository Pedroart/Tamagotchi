import requests
import paho.mqtt.client as mqtt
import json, time

# MQTT config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_INPUT = "voz/texto"
TOPIC_OUTPUT = "habla/texto"

# Ollama config
MODEL = "llama3.2:1b"
OLLAMA_URL = "http://localhost:11434/api/chat"

def generar_respuesta(prompt):
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "top_p" : 0.7,
        "max_tokens": 10
    }
    t0 = time.time()
    resp = requests.post(OLLAMA_URL, json=payload)
    dt = time.time() - t0

    if resp.status_code != 200:
        print("❌ HTTP:", resp.status_code, resp.text)
        return None

    data = resp.json()
    print("📥 JSON completo:", json.dumps(data, indent=2, ensure_ascii=False))

    # Extraer contenido directamente de data["message"]
    if "message" in data and "content" in data["message"]:
        text = data["message"]["content"].strip()
        print(f"⏱️ {dt:.2f}s para {len(text.split())} palabras")
        return text
    else:
        print("⚠️ No se encontró 'message.content'")
        return None

def on_message(client, userdata, msg):
    prompt = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] Prompt recibido: {prompt}")
    respuesta = generar_respuesta(prompt)
    if respuesta:
        print(f"[LLM] Respuesta: {respuesta}")
        client.publish(TOPIC_OUTPUT, respuesta)
    else:
        print("[LLM] No se generó respuesta")

client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(TOPIC_INPUT)
client.loop_forever()
