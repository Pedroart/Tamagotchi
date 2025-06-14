import sounddevice as sd
import numpy as np
import threading

class Microfono:
    def __init__(self, bus):
        self.running = True
        self.bus = bus

    def escuchar(self):
        def callback(indata, frames, time, status):
            if not self.running:
                raise sd.CallbackStop()
            volumen = np.linalg.norm(indata) * 10
            self.bus.publish("audio/volumen", volumen)

        with sd.InputStream(callback=callback):
            while self.running:
                sd.sleep(100)

    def start(self):
        threading.Thread(target=self.escuchar, daemon=True).start()

    def stop(self):
        self.running = False