import pygame
from core.utils import lerp
from anim_lpc import Animator, blit_anchored_by_feet, scale_to_height
from event_bus import event_bus

class Player:
    def __init__(self, cfg, cam, bank):
        self.cfg = cfg
        self.cam = cam
        self.c = cfg["START_C"]; self.r = cfg["START_R"]
        self._wc = float(self.c); self._wr = float(self.r)

        self.step_time_base = cfg["STEP_TIME"]
        self.step_time = self.step_time_base
        self.moving = False
        self.tmove = 0.0
        self.from_tile = (self.c, self.r)
        self.to_tile = (self.c, self.r)
        self.facing = "down"

        # Animator (puede no tener banco -> quedará en fallback)
        self.anim = None
        if bank and getattr(bank, "anims", None):
            self.anim = Animator(bank, default="idle_down",
                                 fps=cfg["ANIM_FPS_DEFAULT"], loop=True)
            self.anim.fps_overrides.update({
                "walk_down": cfg["ANIM_FPS_WALK"], "walk_up": cfg["ANIM_FPS_WALK"],
                "walk_left": cfg["ANIM_FPS_WALK"], "walk_right": cfg["ANIM_FPS_WALK"],
                "idle_down": cfg["ANIM_FPS_IDLE"], "idle_up": cfg["ANIM_FPS_IDLE"],
                "idle_left": cfg["ANIM_FPS_IDLE"], "idle_right": cfg["ANIM_FPS_IDLE"],
            })

        self.sprite_world_h = cfg["SPRITE_WORLD_H"]
        self.min_screen_h = cfg["MIN_SCREEN_H"]
        self.max_screen_h = cfg["MAX_SCREEN_H"]

    def request_move(self, dc, dr):
        if self.moving or (dc == 0 and dr == 0): return
        self.facing = "right" if dc>0 else "left" if dc<0 else ("down" if dr>0 else "up")
        nc = max(0, min(self.cfg["MAP_W"]-1, self.c + dc))
        nr = max(0, min(self.cfg["MAP_H"]-1, self.r + dr))
        if (nc, nr) != (self.c, self.r):
            self.from_tile = (self.c, self.r)
            self.to_tile = (nc, nr)
            self.c, self.r = nc, nr
            self.tmove = 0.0
            self.moving = True
            event_bus.emit("player.move_start", to_col=nc, to_row=nr)

    def toggle_run(self, enabled):
        self.step_time = self.step_time_base * (0.65 if enabled else 1.0)

    def play_anim(self, name: str, *, fps=None, loop=True, restart=True):
        """Fuerza una animación por nombre del CSV (p.ej., 'slash_up')."""
        if getattr(self, "anim", None):
            try:
                self.anim.set(name, fps=fps, loop=loop, restart=restart)
            except Exception:
                pass

    def face(self, direction: str):
        if direction in ("down", "up", "left", "right"):
            self.facing = direction

    def _choose_anim(self):
        if not self.anim: return
        base = "walk" if self.moving else "idle"
        name = f"{base}_{self.facing}"
        if name in self.anim.bank.anims:
            self.anim.set(name)
        else:
            for alt in ([name] +
                        [f"{base}_{d}" for d in ("down","right","up","left")] +
                        ["idle_down","walk_down"]):
                if alt in self.anim.bank.anims:
                    self.anim.set(alt); break

    def update(self, dt):
        if self.moving:
            self.tmove += dt
            a = min(self.tmove / max(1e-6, self.step_time), 1.0)
            ease = 1 - (1 - a)*(1 - a)
            self._wc = lerp(self.from_tile[0], self.to_tile[0], ease)
            self._wr = lerp(self.from_tile[1], self.to_tile[1], ease)
            if a >= 1.0:
                self.moving = False
                event_bus.emit("player.reached", col=self.c, row=self.r)
        else:
            self._wc, self._wr = float(self.c), float(self.r)

        self._choose_anim()
        if getattr(self, "anim", None):
            self.anim.update(dt)

    def draw(self, screen):
        foot = ((self._wc + 0.5)*self.cfg["TILE_WORLD"], 0.0, (self._wr + 0.5)*self.cfg["TILE_WORLD"])
        pr = self.cam.project(*foot)
        if pr is None: return
        (sx, sy), Zc = pr

        h_screen = self.cam.focal * (self.sprite_world_h / Zc)
        h_screen *= self.cfg.get("SPRITE_SCALE", 1.0)
        h_screen = max(self.min_screen_h, min(self.max_screen_h, h_screen))

        if not self.anim:
            w = int(h_screen * 0.7)
            rect = pygame.Rect(int(sx - w/2), int(sy - h_screen), w, int(h_screen))
            pygame.draw.rect(screen, (240,80,80), rect, border_radius=6)
            pygame.draw.rect(screen, (25,25,25), rect, width=2, border_radius=6)
            return

        img = self.anim.frame()
        if img is None:
            w = int(h_screen * 0.7)
            rect = pygame.Rect(int(sx - w/2), int(sy - h_screen), w, int(h_screen))
            pygame.draw.rect(screen, (240,80,80), rect, border_radius=6)
            pygame.draw.rect(screen, (25,25,25), rect, width=2, border_radius=6)
            return

        img = scale_to_height(img, int(h_screen))
        blit_anchored_by_feet(screen, img, int(sx), int(sy))
