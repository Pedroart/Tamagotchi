from piper import PiperVoice

model_path = "es_ES-sharvard-medium.onnx"
voice = PiperVoice.load(model_path)

audio = voice.speak("Hola ¿cómo estás?", output_path="respuesta.wav")

import os
os.system("aplay respuesta.wav")  # o tu reproductor preferido
