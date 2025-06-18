import cv2
import threading

class Camara:
    def __init__(self, bus):
        self.frame = None
        self.running = True
        self.bus = bus

        ruta = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(ruta)
        if self.face_cascade.empty():
            raise RuntimeError(f"No se pudo cargar el clasificador desde {ruta}")

    def capturar(self):
        cap = cv2.VideoCapture(0)
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                self.frame = frame

                rostros, detectado = self.detectar_rostro(frame)

                self.bus.publish("imagen/nueva", frame)
                #self.bus.publish("imagen/detectado", detectado)
        cap.release()

    def detectar_rostro(self, frame, scaleFactor=1.1, minNeighbors=5, minSize=(30,30)):
        """
        Detecta rostros en un frame usando Haar Cascade.

        Parámetros:
        - frame: imagen BGR capturada
        - scaleFactor: aumento incremental de escala (default 1.1)
        - minNeighbors: cantidad de detecciones cercanas necesarias (default 5)
        - minSize: tamaño mínimo (w,h) en píxeles (default 30x30)

        Retorna:
        - rostros: lista de tuplas (x, y, w, h)
        - detectado: True si hay al menos un rostro
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=scaleFactor,
            minNeighbors=minNeighbors,
            minSize=minSize,
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        #print(rostros)
        return rostros, len(rostros) > 0

    def start(self):
        threading.Thread(target=self.capturar, daemon=True).start()

    def stop(self):
        self.running = False