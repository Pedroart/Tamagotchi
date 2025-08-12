import pygame, sys
from core.camera import Camera
from core.tilemap import TileMap
from anim_lpc import SpriteBank
from actors.player import Player

class Game:
    def __init__(self, cfg, controls):
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

        self.running = True
        self.run_held = False

    def handle_keydown(self, key):
        if key in self.controls["quit"]:
            self.running = False; return
        if key in self.controls["toggle_run"]:
            self.run_held = True
            self.player.toggle_run(True)

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

    def handle_keyup(self, key):
        if key in self.controls["toggle_run"]:
            self.run_held = False
            self.player.toggle_run(False)

    def loop(self):
        FPS = self.cfg["FPS"]
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.running = False
                elif e.type == pygame.KEYDOWN: self.handle_keydown(e.key)
                elif e.type == pygame.KEYUP:   self.handle_keyup(e.key)

            self.player.update(dt)

            self.screen.fill(self.cfg["BG_COLOR"])
            self.map.draw(self.screen, self.cam)
            self.player.draw(self.screen)

            self.screen.blit(self.font.render(
                "WASD/Flechas: mover • Shift: correr • ESC: salir", True, (220,220,230)), (10, 8))
            self.screen.blit(self.font.render(
                f"Tile: ({self.player.c},{self.player.r})", True, (200,240,210)), (10, 30))

            pygame.display.flip()

        pygame.quit()
        sys.exit()
