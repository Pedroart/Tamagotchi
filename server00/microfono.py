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
import asyncio

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

FILTERS = [
    "subtítulos realizados por la comunidad de amara.org",
    "subtitulado por la comunidad de amara.org",
    "thank you for watching",
    "thanks for watching",
    "❤️ translated by amara.org community",
    "¡Hasta luego! Nos vemos en el próximo video. ¡Chau!"
    # puedes añadir más patrones aquí...
]

def clean_transcription(texto: str) -> str:
    t = texto.strip()
    lower = t.lower()
    for pat in FILTERS:
        if lower.endswith(pat):
            return t[:len(t) - len(pat)].rstrip(" -–—,.:;")
    return t

class Microfono:
    def __init__(self, bus, umbral=5, silencio_max=5.0):
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

            ahora = time.time()

            if self.ia_hablando:
                return

            if volumen > self.umbral:
                if not self.grabando:
                    print("🎤 Iniciando grabación...")
                    self.bus.publish("audio/grabando", True)
                    self.grabando = True
                    self.buffer.clear()
                self.ultimo_sonido = ahora

            if self.grabando:
                self.buffer.append(indata.copy())

                # si pasó suficiente tiempo en silencio, detener grabación
                if ahora - self.ultimo_sonido > self.silencio_max:
                    print("🛑 Deteniendo grabación...")
                    self.bus.publish("audio/grabando", False)
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
        wav_buffer.name = "grabacion.wav"
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.fs)
            wf.writeframes((audio_np * 32767).astype(np.int16).tobytes())

        wav_buffer.seek(0)  # Rebobinar buffer para leerlo desde el principio

        # Enviar a la API de OpenAI
        response = openai.audio.transcriptions.create(
            model="whisper-1",
            file=wav_buffer,
            language="es"
        )

        texto = response.text   
        limpieza = clean_transcription(texto)
        if limpieza != texto:
            print(f"📝 Frase filtrada:\nAntes: «{texto}»\nDespués: «{limpieza}»")
        print("📝 Transcripción final:", limpieza)
        if len(limpieza) <= 1:
            return

        self.bus.publish("audio/transcripcion", limpieza)
        
        

        return limpieza

    def start(self):
        threading.Thread(target=self.escuchar, daemon=True).start()

    def stop(self):
        self.running = False
