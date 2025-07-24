import soundfile as sf
from kokoro_onnx import Kokoro

# Carga del modelo y voces
kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

# Generar audio
samples, sample_rate = kokoro.create(
    "¡Hola! Esto es generado con Kokoro en CPU.",
    voice="af_sarah",      # Voz en español (americano femenino)
    speed=1.0,
    lang="es"           # Código de idioma español (puede variar)
)

# Guardar o reproducir
sf.write("respuesta.wav", samples, sample_rate)
print("Se generó respuesta.wav")
