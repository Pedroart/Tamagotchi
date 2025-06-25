import requests
import paho.mqtt.client as mqtt
import json, time
import threading

# MQTT config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_INPUT = "voz/texto"
TOPIC_OUTPUT = "habla/texto"
TOPIC_ESTADO = "habla/estado"

# Ollama config
MODEL = "llama3.2:1b"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Evento de espera
tts_listo = threading.Event()

def generar_respuesta(prompt, client):
    # Esperar que TTS esté listo
    if not tts_listo.is_set():
        print("⏳ Esperando a que TTS esté listo...")
        tts_listo.wait()
        print("✅ TTS está listo. Comenzando generación...")

    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "options": {
            "num_thread": 1,
            "temperature": 0.3,
            "top_p": 0.3,
            "num_ctx": 100,
            "max_tokens": 8,
        }
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
            if any(sep in content for sep in (".", ";", ",", "?", "!")):
                info = client.publish(TOPIC_OUTPUT, buffer.strip(), qos=1, retain=True)
                print("📤 Publicado: ", buffer.strip())
                buffer = ""

        if buffer.strip():
            result = client.publish(TOPIC_OUTPUT, buffer.strip(), qos=1, retain=True)
            result.wait_for_publish()

def on_message(client, userdata, msg):
    if msg.topic == TOPIC_INPUT:
        prompt = msg.payload.decode("utf-8").strip()
        print(f"[MQTT] Prompt recibido: {prompt}")
        generar_respuesta(prompt, client)
    elif msg.topic == TOPIC_ESTADO:
        estado = msg.payload.decode("utf-8").strip().lower()
        if estado == "listo":
            print("📶 Señal de 'listo' recibida desde TTS.")
            tts_listo.set()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("📡 Conectado a MQTT")
        client.subscribe(TOPIC_INPUT)
        client.subscribe(TOPIC_ESTADO)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

print("✅ Servicio LLM listo. Esperando mensajes...")
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n👋 Interrupción detectada. Cerrando servicio LLM...")
    client.disconnect()
    print("🛑 Desconectado correctamente de MQTT.")
