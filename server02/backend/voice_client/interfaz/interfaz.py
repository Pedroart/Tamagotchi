import pygame
import sys
import csv
from typing import Dict, List, Callable
from utils.EventBus import event_bus

# ===========================
# Configuración global
# ===========================
ANCHO_FRAME = 64
ALTO_FRAME = 64

# ===========================
# Funciones utilitarias
# ===========================
def cargar_animaciones(ruta_archivo: str) -> List[Dict[str, int]]:
    """
    Carga la lista de animaciones desde un archivo CSV.
    
    Input:
      ruta_archivo (str): Ruta del archivo CSV con formato:
          fila,nombre,cantidad_frames

    Output:
      Lista de dicts con:
          {"nombre": str, "fila": int, "frames": int}
    """
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


def obtener_frame(spritesheet: pygame.Surface, fila: int, frame_index: int) -> pygame.Surface:
    """
    Extrae un frame específico del spritesheet.

    Input:
      spritesheet: imagen con todas las animaciones
      fila: en qué fila de la hoja está la animación
      frame_index: número de frame (columna)

    Output:
      Surface con el frame extraído
    """
    rect = pygame.Rect(
        frame_index * ANCHO_FRAME,
        fila * ALTO_FRAME,
        ANCHO_FRAME,
        ALTO_FRAME
    )
    frame = pygame.Surface((ANCHO_FRAME, ALTO_FRAME), pygame.SRCALPHA)
    frame.blit(spritesheet, (0, 0), rect)
    return frame


# ===========================
# Clase principal de UI
# ===========================
class Interfaz:
    def __init__(self):
        # Configuración base
        self.running = True
        self.fps = 60
        self.reloj = pygame.time.Clock()
        self.escala = 18               # escala grande para fullscreen
        self.frame_actual = 0
        self.tiempo_por_frame = 100    # ms por frame (10 fps)
        self.tiempo_ultimo_frame = 0

        # Animación actual
        self.animacion_actual: str = ""
        self.animacion_datos: Dict | None = None
        self.animaciones: List[Dict] = []

        # Se suscribe al EventBus para escuchar cambios de animación
        event_bus.subscribe("ui/animacion", self.recibir_animacion)

    # ===========================
    # Métodos principales
    # ===========================
    def iniciar(self):
        """Inicializa Pygame, fullscreen y recursos gráficos."""
        pygame.init()
        info = pygame.display.Info()
        self.ancho = info.current_w
        self.alto = info.current_h
        self.pantalla = pygame.display.set_mode((self.ancho, self.alto), pygame.FULLSCREEN)
        pygame.display.set_caption("Tamagotchi UI")

        # Fuente
        self.fuente = pygame.font.SysFont(None, 24)

        # Carga imágenes y datos de animaciones
        self.spritesheet = pygame.image.load("./assets/personaje.png").convert_alpha()
        self.animaciones = cargar_animaciones("./assets/animaciones.txt")

        # Empieza en idle_up
        self.recibir_animacion("idle_up")

    def recibir_animacion(self, nombre_animacion: str):
        """
        Callback para cuando se recibe un evento de cambio de animación.
        
        Input:
          nombre_animacion (str): nombre que debe coincidir con el CSV
        
        Output:
          Ninguno, pero cambia self.animacion_actual y resetea el frame
        """
        self.animacion_actual = nombre_animacion
        self.frame_actual = 0
        self.tiempo_ultimo_frame = pygame.time.get_ticks()
        # Busca datos en la lista de animaciones
        self.animacion_datos = next((a for a in self.animaciones if a["nombre"] == nombre_animacion), None)

    def actualizar_frame(self):
        """
        Avanza el frame de la animación según el tiempo transcurrido.
        """
        if not self.animacion_datos:
            return

        tiempo_actual = pygame.time.get_ticks()
        if tiempo_actual - self.tiempo_ultimo_frame >= self.tiempo_por_frame:
            self.tiempo_ultimo_frame = tiempo_actual
            self.frame_actual += 1

            # Si ya pasamos el último frame, volvemos a idle
            if self.frame_actual >= self.animacion_datos["frames"]:
                event_bus.emit("ui/animacion", "idle_up")

    def dibujar_animacion(self):
        """
        Dibuja el frame actual de la animación centrado en pantalla.
        """
        if not self.animacion_datos:
            return

        frame = obtener_frame(self.spritesheet, self.animacion_datos["fila"], self.frame_actual)
        frame = pygame.transform.scale(frame, (ANCHO_FRAME * self.escala, ALTO_FRAME * self.escala))
        x = (self.ancho - ANCHO_FRAME * self.escala) // 2
        y = (self.alto - ALTO_FRAME * self.escala) // 2
        self.pantalla.blit(frame, (x, y))

    def dibujar_texto(self):
        """
        Dibuja información de depuración (nombre de la animación actual).
        """
        texto = self.fuente.render(f"Animacion: {self.animacion_actual}", True, (255, 255, 255))
        self.pantalla.blit(texto, (10, self.alto - 30))

    def procesar_eventos(self):
        """
        Procesa eventos de teclado y salida.
        """
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                self.running = False

    def render_loop(self):
        """Bucle principal de renderizado."""
        self.iniciar()

        while self.running:
            # 1. Procesa entrada
            self.procesar_eventos()

            # 2. Lógica
            self.actualizar_frame()

            # 3. Dibujado
            self.pantalla.fill((0, 0, 0))
            self.dibujar_animacion()
            self.dibujar_texto()
            pygame.display.flip()

            # 4. Control de FPS
            self.reloj.tick(self.fps)

        pygame.quit()
        sys.exit()

    def stop(self):
        """Permite detener la interfaz desde otro hilo/modulo."""
        self.running = False
