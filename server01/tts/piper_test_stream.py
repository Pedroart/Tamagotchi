import numpy as np
import sounddevice as sd
from piper.voice import PiperVoice

model = "es_ES-sharvard-medium.onnx"
voice = PiperVoice.load(model)

stream = sd.OutputStream(
    samplerate=voice.config.sample_rate,
    channels=1,
    dtype='int16'
)
stream.start()

for chunk in voice.synthesize_stream_raw("Esto suena instantáneamente con Piper"):
    data = np.frombuffer(chunk, dtype=np.int16)
    stream.write(data)

stream.stop()
stream.close()
