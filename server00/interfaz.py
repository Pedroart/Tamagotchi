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
        self.fps = 60
        self.pantalla = None
        self.reloj = pygame.time.Clock()
        self.bus = bus
        self.animacion_actual = ""
        self.bus.subscribe("ui/animacion", self.recibir_animacion)
        self.escala = 18  # escala más grande para fullscreen
        self.frame_actual = 0
        self.tiempo_ultimo_frame = 0
        self.tiempo_por_frame = 100  # milisegundos por frame
        self.animacion_datos = None

    def recibir_animacion(self, animacion):
        #print("UI recibe acción:", animacion)
        self.animacion_actual = animacion
        self.frame_actual = 0
        self.tiempo_ultimo_frame = pygame.time.get_ticks()
        self.animacion_datos = next((a for a in self.animaciones if a["nombre"] == animacion), None)

    def iniciar(self):
        pygame.init()
        info = pygame.display.Info()
        self.ancho = info.current_w
        self.alto = info.current_h
        self.pantalla = pygame.display.set_mode((self.ancho, self.alto), pygame.FULLSCREEN)
        pygame.display.set_caption("Tamagotchi")
        self.fuente = pygame.font.SysFont(None, 18)
        self.spritesheet = pygame.image.load("assets/personaje.png").convert_alpha()
        self.animaciones = cargar_animaciones("assets/animaciones.txt")

    def render_loop(self):
        self.iniciar()
        fuente = pygame.font.SysFont(None, 24)
        
        self.recibir_animacion("idle_up")

        while self.running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    self.running = False

            self.pantalla.fill((0, 0, 0))

            # Dibujar animación si hay una activa
            if self.animacion_actual and self.animacion_datos:
                tiempo_actual = pygame.time.get_ticks()
                if tiempo_actual - self.tiempo_ultimo_frame >= self.tiempo_por_frame:
                    self.tiempo_ultimo_frame = tiempo_actual
                    self.frame_actual += 1

                if self.frame_actual >= self.animacion_datos["frames"]:
                    self.recibir_animacion("idle_up")
                    self.frame_actual = 0  # Reiniciar frame
                
                frame = obtener_frame(self.spritesheet, self.animacion_datos["fila"], self.frame_actual)
                frame = pygame.transform.scale(frame, (ANCHO_FRAME * self.escala, ALTO_FRAME * self.escala))
                x = (self.ancho - ANCHO_FRAME * self.escala) // 2
                y = (self.alto - ALTO_FRAME * self.escala) // 2
                self.pantalla.blit(frame, (x, y))

            # Texto informativo
            texto = fuente.render(f"Animacion: {self.animacion_actual}", True, (255, 255, 255))
            self.pantalla.blit(texto, (10, self.alto - 30))

            pygame.display.flip()
            self.reloj.tick(self.fps)

        pygame.quit()
        sys.exit()

    def stop(self):
        self.running = False
