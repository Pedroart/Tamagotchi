import threading
import time

class Gestor:
    def __init__(self, bus, agente):
        self.bus = bus
        self.agente = agente
        self.running = True
        self.volumen = 0
        self.imagen = None
        self.bus.subscribe("audio/volumen", self.recibir_volumen)
        self.bus.subscribe("imagen/nueva", self.recibir_imagen)

    def recibir_volumen(self, volumen):
        self.volumen = volumen

    def recibir_imagen(self, imagen):
        self.imagen = imagen

    def ciclo(self):
        while self.running:
            if self.volumen > 15:
                texto = "caminar"  # reemplazar con Whisper
                accion = self.agente.procesar(texto, self.imagen)
                self.bus.publish("accion", accion)
            time.sleep(0.2)

    def start(self):
        threading.Thread(target=self.ciclo, daemon=True).start()

    def stop(self):
        self.running = False