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

def generar_respuesta(prompt, client):
    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "top_p": 0.7,
        "max_tokens": 8
    }
    with requests.post(OLLAMA_URL, json=payload, stream=True) as resp:
        if resp.status_code != 200:
            print("❌ HTTP:", resp.status_code, resp.text)
            return

        buffer = ""
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            content = data.get("message", {}).get("content", "")
            if not content:
                continue

            buffer += content
            # detectamos delimitador
            if any(sep in content for sep in (".", ";", ",","?","¡")):
                client.publish(TOPIC_OUTPUT, buffer.strip())
                #print(f'Procesado: {buffer.strip()}')
                buffer = ""

        # si queda algo sin enviar al final
        if buffer.strip():
            client.publish(TOPIC_OUTPUT, buffer.strip())

def on_message(client, userdata, msg):
    prompt = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] Prompt recibido: {prompt}")
    generar_respuesta(prompt, client)


client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(TOPIC_INPUT)
client.loop_forever()
