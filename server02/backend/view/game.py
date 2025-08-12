import pygame, sys
from core.camera import Camera
from core.tilemap import TileMap
from anim_lpc import SpriteBank
from actors.player import Player
from ai_agent import BollaAgent
from event_bus import event_bus

class Game:
    def __init__(self, cfg, controls, mic_streamer=None):
        pygame.init()
        self.cfg = cfg
        self.controls = controls
        self.screen = pygame.display.set_mode((cfg["SCREEN_W"], cfg["SCREEN_H"]))
        pygame.display.set_caption("RPG 5x5 — modular")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 22)

        self.cam = Camera(cfg)
        self.map = TileMap(cfg)

        # Carga banco de sprites; si falla, seguimos con fallback
        self.bank = None
        try:
            self.bank = SpriteBank(
                cfg["HERO_SPRITESHEET"], cfg["HERO_INDEX_CSV"],
                fw=cfg["FRAME_W"], fh=cfg["FRAME_H"]
            )
        except Exception as e:
            print("[WARN] No se pudo cargar sprites:", e)

        self.player = Player(cfg, self.cam, self.bank)
        # Agente autónomo
        self.agent = BollaAgent(cfg["MAP_W"], cfg["MAP_H"])  # escucha world.tick/ai.heard/player.reached

        # --- micrófono ---
        self.mic = mic_streamer
        self.mic_active = False

        self.running = True
        self.run_held = False

        # Suscripciones al EventBus
        self.unsubs = []
        self.unsubs.append(event_bus.subscribe("ai.step", self.ev_ai_step))
        self.unsubs.append(event_bus.subscribe("ai.move_to", self.ev_ai_move_to))
        self.unsubs.append(event_bus.subscribe("anim.play", self.ev_anim_play))
        self.unsubs.append(event_bus.subscribe("ai.say", self.ev_ai_say))
        self.unsubs.append(event_bus.subscribe("player.face", self.ev_face))

        self.running = True
        self.run_held = False

        
    # --- Handlers de EventBus ---
    def ev_ai_step(self, dc: int = 0, dr: int = 0):
        self.player.request_move(dc, dr)

    def ev_ai_move_to(self, col: int, row: int):
        # Movimiento simple hacia el objetivo: da un paso por frame en eje prioritario
        if col != self.player.c:
            self.player.request_move(1 if col > self.player.c else -1, 0)
        elif row != self.player.r:
            self.player.request_move(0, 1 if row > self.player.r else -1)
        # Si ya está en (col,row), no hace nada.

    def ev_anim_play(self, name: str, fps: int | None = None, loop: bool = True, restart: bool = True):
        self.player.play_anim(name, fps=fps, loop=loop, restart=restart)

    
    def ev_ai_say(self, text: str):
        print("[AI SAY]", text)
    def ev_face(self, direction: str):
            self.player.face(direction)

    def handle_keydown(self, key):
        if key in self.controls["quit"]:
            self.running = False; return
        if key in self.controls["toggle_run"]:
            self.run_held = True
            self.player.toggle_run(True)

        # --- Toggle mic con ESPACIO ---
        if key == pygame.K_SPACE and self.mic:
            if not self.mic_active:
                self.mic.start()
                self.mic_active = True
            else:
                self.mic.stop()
                self.mic_active = False
            return

        dc = dr = 0
        if key in self.controls["up"]:    dr = -1
        if key in self.controls["down"]:  dr =  1
        if key in self.controls["left"]:  dc = -1
        if key in self.controls["right"]: dc =  1
        if dc or dr:
            self.player.request_move(dc, dr)

        if "bigger" in self.controls and key in self.controls["bigger"]:
            self.cfg["SPRITE_SCALE"] = min(3.0, self.cfg.get("SPRITE_SCALE", 1.0) * 1.1)
        if "smaller" in self.controls and key in self.controls["smaller"]:
            self.cfg["SPRITE_SCALE"] = max(0.3, self.cfg.get("SPRITE_SCALE", 1.0) / 1.1)

        if key == pygame.K_1:
            event_bus.emit("ai.heard", text="ve al 1, 0")
        if key == pygame.K_2:
            event_bus.emit("ai.heard", text="ve al 5, 0")



    def handle_keyup(self, key):
        if key in self.controls["toggle_run"]:
            self.run_held = False
            self.player.toggle_run(False)

    def loop(self):
        FPS = self.cfg["FPS"]
        try:
            while self.running:
                dt = self.clock.tick(FPS) / 1000.0
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        self.running = False
                    elif e.type == pygame.KEYDOWN:
                        self.handle_keydown(e.key)
                    elif e.type == pygame.KEYUP:
                        self.handle_keyup(e.key)

                self.player.update(dt)
                event_bus.emit("world.tick", dt=dt, t=pygame.time.get_ticks()/1000.0)
                self.screen.fill(self.cfg["BG_COLOR"])
                self.map.draw(self.screen, self.cam)
                self.player.draw(self.screen)

                # HUD
                self.screen.blit(self.font.render(
                    "ESPACIO: mic  • WASD/Flechas: mover • Shift: correr • ESC: salir",
                    True, (220,220,230)), (10, 8))
                # Indicador de mic
                mic_text = "Mic: ON" if self.mic_active else "Mic: off"
                mic_col  = (240,80,80) if self.mic_active else (150,160,170)
                self.screen.blit(self.font.render(mic_text, True, mic_col), (10, 30))

                pygame.display.flip()
        finally:
            # apaga el mic si quedó activo (evita crashes en PortAudio/SDL)
            if self.mic_active and self.mic:
                try: self.mic.stop()
                except: pass
            pygame.quit()
            sys.exit()