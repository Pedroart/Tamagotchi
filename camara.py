import cv2
import threading

class Camara:
    def __init__(self, bus):
        self.frame = None
        self.running = True
        self.bus = bus

    def capturar(self):
        cap = cv2.VideoCapture(0)
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                self.frame = frame
                self.bus.publish("imagen/nueva", frame)
        cap.release()

    def start(self):
        threading.Thread(target=self.capturar, daemon=True).start()

    def stop(self):
        self.running = False