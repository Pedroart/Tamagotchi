import pygame
import sys
import csv
import threading
import cv2
import sounddevice as sd
import numpy as np

# --- Configuración ---
ANCHO_FRAME = 64
ALTO_FRAME = 64
ESCALA = 2
FPS = 10
running = True  # bandera global para cerrar todo

# --- Cámara en hilo paralelo (sin mostrar) ---
def iniciar_camara():
    cap = cv2.VideoCapture(0)
    while running and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        # Aquí puedes procesar frame si quieres (IA, detección, etc.)
    cap.release()

# --- Micrófono en hilo paralelo ---
def escuchar_microfono():
    def callback(indata, frames, time, status):
        if not running:
            raise sd.CallbackStop()
        volumen = np.linalg.norm(indata) * 10
        print("Volumen micrófono:", round(volumen, 2))

    with sd.InputStream(callback=callback):
        while running:
            sd.sleep(100)

# --- Cargar animaciones desde archivo ---
def cargar_animaciones(ruta_archivo):
    animaciones = []
    with open(ruta_archivo, newline='') as archivo:
        lector = csv.reader(archivo)
        for fila, nombre, cantidad in lector:
            animaciones.append({
                "nombre": nombre,
                "fila": int(fila),
                "frames": int(cantidad)
            })
    return animaciones

# --- Obtener frame desde spritesheet ---
def obtener_frame(spritesheet, fila, frame_index):
    rect = pygame.Rect(
        frame_index * ANCHO_FRAME,
        fila * ALTO_FRAME,
        ANCHO_FRAME,
        ALTO_FRAME
    )
    frame = pygame.Surface((ANCHO_FRAME, ALTO_FRAME), pygame.SRCALPHA)
    frame.blit(spritesheet, (0, 0), rect)
    return frame

# --- Lanzar hilos de cámara y micrófono ---
threading.Thread(target=iniciar_camara, daemon=True).start()
threading.Thread(target=escuchar_microfono, daemon=True).start()

# --- Inicializar Pygame ---
pygame.init()
pantalla = pygame.display.set_mode((ANCHO_FRAME * ESCALA, ALTO_FRAME * ESCALA + 40))
pygame.display.set_caption("Juego con Cámara y Micrófono")
clock = pygame.time.Clock()

# --- Cargar spritesheet y animaciones ---
spritesheet = pygame.image.load("assets/personaje.png").convert_alpha()
animaciones = cargar_animaciones("assets/animaciones.txt")

# --- Control del juego ---
indice_animacion = 0
frame_actual = 0

# --- Bucle principal ---
while running:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            running = False
        elif evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_ESCAPE:
                running = False
            elif evento.key == pygame.K_RIGHT:
                indice_animacion = (indice_animacion + 1) % len(animaciones)
                frame_actual = 0
            elif evento.key == pygame.K_LEFT:
                indice_animacion = (indice_animacion - 1) % len(animaciones)
                frame_actual = 0

    # Obtener datos actuales
    anim = animaciones[indice_animacion]
    fila = anim["fila"]
    nombre = anim["nombre"]
    total_frames = anim["frames"]

    # Dibujar frame actual
    pantalla.fill((30, 30, 30))
    frame = obtener_frame(spritesheet, fila, frame_actual)
    frame_escalado = pygame.transform.scale(frame, (ANCHO_FRAME * ESCALA, ALTO_FRAME * ESCALA))
    pantalla.blit(frame_escalado, (0, 0))

    # Mostrar nombre de animación
    fuente = pygame.font.SysFont(None, 24)
    texto = fuente.render(f"{nombre} ({frame_actual + 1}/{total_frames})", True, (255, 255, 255))
    pantalla.blit(texto, (10, ALTO_FRAME * ESCALA + 10))

    pygame.display.flip()
    clock.tick(FPS)

    # Avanzar frame
    frame_actual = (frame_actual + 1) % total_frames

# --- Salida limpia ---
pygame.quit()
cv2.destroyAllWindows()
sys.exit()
