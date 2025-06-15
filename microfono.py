import sounddevice as sd
import numpy as np
import threading
import queue
import time
import wave
from io import BytesIO
import openai
from dotenv import load_dotenv
import os

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

class Microfono:
    def __init__(self, bus, umbral=5, silencio_max=2.0):
        self.running = True
        self.bus = bus
        self.umbral = umbral
        self.silencio_max = silencio_max  # segundos de silencio para detener grabación

        self.grabando = False
        self.buffer = []
        self.ultimo_sonido = time.time()
        self.fs = 44100  # Frecuencia de muestreo
        self.ia_hablando = False

        self.bus.subscribe("ia/hablando", self.recibir_estado_ia)

    def recibir_estado_ia(self, hablando):
        print(f"🤖 IA está hablando: {hablando}")
        self.ia_hablando = bool(hablando)

    def escuchar(self):
        def callback(indata, frames, time_info, status):
            if not self.running:
                raise sd.CallbackStop()

            volumen = np.linalg.norm(indata) * 10
            self.bus.publish("audio/volumen", volumen)

            ahora = time.time()

            if self.ia_hablando:
                return

            if volumen > self.umbral:
                if not self.grabando:
                    print("🎤 Iniciando grabación...")
                    self.grabando = True
                    self.buffer.clear()
                self.ultimo_sonido = ahora

            if self.grabando:
                self.buffer.append(indata.copy())

                # si pasó suficiente tiempo en silencio, detener grabación
                if ahora - self.ultimo_sonido > self.silencio_max:
                    print("🛑 Deteniendo grabación...")
                    self.grabando = False
                    #self.guardar_audio()
                    self.transcribir_audio_api_en_memoria()

        with sd.InputStream(callback=callback, channels=1, samplerate=self.fs):
            while self.running:
                sd.sleep(100)

    def guardar_audio(self):
        if not self.buffer:
            return
        audio = np.concatenate(self.buffer, axis=0)
        nombre_archivo = f"grabacion_{int(time.time())}.wav"
        with wave.open(nombre_archivo, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.fs)
            wf.writeframes((audio * 32767).astype(np.int16).tobytes())
        print(f"💾 Audio guardado: {nombre_archivo}")

    def transcribir_audio_api_en_memoria(self):
        if not self.buffer:
            return

        # Convertir buffer de NumPy a WAV en memoria
        audio_np = np.concatenate(self.buffer, axis=0)
        wav_buffer = BytesIO()

        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.fs)
            wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())

        wav_buffer.seek(0)  # Rebobinar buffer para leerlo desde el principio

        # Enviar a la API de OpenAI
        response = openai.Audio.transcribe(
            model="whisper-1",
            file=wav_buffer,
            filename="grabacion.wav",  # Necesario para que OpenAI lo trate como audio válido
            language="es"
        )

        texto = response["text"]
        print("📝 Transcripción:", texto)
        self.bus.publish("audio/transcripcion", texto)
        return texto

    def start(self):
        threading.Thread(target=self.escuchar, daemon=True).start()

    def stop(self):
        self.running = False
