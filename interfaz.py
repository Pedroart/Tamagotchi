import pygame
import sys
import csv

ANCHO_FRAME = 64
ALTO_FRAME = 64

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


class Interfaz:
    def __init__(self, bus):
        self.running = True
        self.fps = 30
        self.pantalla = None
        self.reloj = pygame.time.Clock()
        self.bus = bus
        self.accion_actual = ""
        self.bus.subscribe("accion", self.recibir_accion)

        self.ancho = 128
        self.alto = 168
        self.escala = 2


    def recibir_accion(self, accion):
        print("UI recibe acción:", accion)
        self.accion_actual = accion

    def iniciar(self):
        pygame.init()
        self.pantalla = pygame.display.set_mode((self.ancho, self.alto))
        pygame.display.set_caption("Tamagotchi")
        self.reloj = pygame.time.Clock()
        self.fuente = pygame.font.SysFont(None, 18)

        self.spritesheet = pygame.image.load("assets/personaje.png").convert_alpha()
        self.animaciones = cargar_animaciones("assets/animaciones.txt")

    def render_loop(self):
        self.iniciar()
        fuente = pygame.font.SysFont(None, 24)
        while self.running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False

            self.pantalla.fill((0, 0, 0))
            texto = fuente.render(f"Acción: {self.accion_actual}", True, (255, 255, 255))
            self.pantalla.blit(texto, (10, 130))
            pygame.display.flip()
            self.reloj.tick(self.fps)

        pygame.quit()
        sys.exit()

    def stop(self):
        self.running = False