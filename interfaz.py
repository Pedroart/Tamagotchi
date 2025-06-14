import pygame
import sys

class Interfaz:
    def __init__(self, bus):
        self.running = True
        self.fps = 30
        self.pantalla = None
        self.reloj = pygame.time.Clock()
        self.bus = bus
        self.accion_actual = ""
        self.bus.subscribe("accion", self.recibir_accion)

    def recibir_accion(self, accion):
        print("UI recibe acción:", accion)
        self.accion_actual = accion

    def iniciar(self):
        pygame.init()
        self.pantalla = pygame.display.set_mode((128, 168))
        pygame.display.set_caption("Juego con Entrada AI")

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