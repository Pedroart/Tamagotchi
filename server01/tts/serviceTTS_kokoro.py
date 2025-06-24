import asyncio
import json
import threading
import sounddevice as sd
import paho.mqtt.client as mqtt
from kokoro_onnx import Kokoro

# Configuración MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_TEXTO = "habla/texto"
TOPIC_PARAR = "habla/stop"
TOPIC_ESTADO = "habla/estado"

kokoro = Kokoro("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
is_playing = False
stop_signal = False
current_thread = None

# 🎭 Simulación de emociones por parámetros
def get_voice_params(emotion):
    if emotion == "feliz":
        return {"speed": 1.2}
    elif emotion == "triste":
        return {"speed": 0.85}
    elif emotion == "enojado":
        return {"speed": 1.3}
    else:
        return {"speed": 1.0}

def publish_estado(state):
    client.publish(TOPIC_ESTADO, state, retain=True)

# 🎧 Hilo de reproducción
def reproducir(text, emotion):
    global is_playing, stop_signal

    is_playing = True
    publish_estado("hablando")

    try:
        params = get_voice_params(emotion)
        stream = kokoro.create_stream(
            text, voice="af_sarah", speed=params["speed"], lang="es"
        )

        for samples, sample_rate in stream:
            if stop_signal:
                break
            sd.play(samples, sample_rate)
            sd.wait()

    except Exception as e:
        print("[ERROR reproducción]", e)

    finally:
        is_playing = False
        stop_signal = False
        publish_estado("detenido")

# 📥 MQTT: Manejo de texto entrante
def on_texto(client, userdata, msg):
    global current_thread, stop_signal

    try:
        payload = json.loads(msg.payload.decode())
        text = payload.get("text", "")
        emotion = payload.get("emotion", "neutral")

        if not text:
            return

        # Si hay algo en curso, se interrumpe
        if is_playing:
            stop_signal = True
            sd.stop()
            if current_thread:
                current_thread.join()

        # Inicia nuevo hilo de reproducción
        current_thread = threading.Thread(target=reproducir, args=(text, emotion))
        current_thread.start()

    except Exception as e:
        print("[ERROR texto]", e)

# 📥 MQTT: Parar reproducción
def on_parar(client, userdata, msg):
    global stop_signal
    if is_playing:
        stop_signal = True
        sd.stop()
        publish_estado("detenido")

# 🔌 Configuración MQTT
client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT)
client.message_callback_add(TOPIC_TEXTO, on_texto)
client.message_callback_add(TOPIC_PARAR, on_parar)
client.subscribe([(TOPIC_TEXTO, 0), (TOPIC_PARAR, 0)])

print("[MQTT] Esperando comandos TTS...")
publish_estado("listo")
client.loop_forever()
