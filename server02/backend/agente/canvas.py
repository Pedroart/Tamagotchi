# sprite_player.py
import csv
import sys
import pygame
from dataclasses import dataclass
from pathlib import Path
from queue import SimpleQueue
from typing import List, Tuple, Optional, Dict, Callable


from config import *
from event_bus import event_bus
from logger import logger


# -----------------------------------------------------------

@dataclass
class Animation:
    name: str
    frames: List[pygame.Surface]

    @property
    def count(self) -> int:
        return len(self.frames)

@dataclass
class PlayerState:
    name: str
    loop: bool
    playing: bool
    frame_idx: int

class SpritePlayer:
    """
    Reproductor de animaciones por eventos usando Pygame.

    Eventos escuchados:
      - "sprite.play", name:str, mode:str ("loop"|"once")
      - "sprite.default"
      - "sprite.get"
      - Opcionales: "sprite.pause", "sprite.resume", "sprite.toggle_loop"

    Emite:
      - "sprite.state", dict(name, loop, playing, frame_idx)
      - "[WARN]/[ERR]" por print si algo sale mal
    """
    def __init__(
        self,
        base_dir: Path = None,
        assets_dir: str = ASSETS_DIR_DEFAULT,
        sheet_name: str = SHEET_NAME_DEFAULT,
        csv_name: str = CSV_NAME_DEFAULT,
        sprite_w: int = SPRITE_W_DEFAULT,
        sprite_h: int = SPRITE_H_DEFAULT,
        fps_anim: int = FPS_ANIM_DEFAULT,
        bg_color: Tuple[int, int, int] = BG_COLOR_DEFAULT,
        window_scale: int = 3,
        fullscreen: bool = False,
        vsync: bool = True,
        default_anim: Optional[str] = None,
    ):
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.assets_dir = assets_dir
        self.sheet_name = sheet_name
        self.csv_name = csv_name
        self.sprite_w = sprite_w
        self.sprite_h = sprite_h
        self.fps_anim = fps_anim
        self.bg_color = bg_color
        self.window_scale = window_scale
        self.fullscreen = fullscreen
        self.vsync = vsync

        self.animations: List[Animation] = []
        self.anim_lookup: Dict[str, int] = {}
        self.idx: int = 0
        self.frame_idx: int = 0
        self.acc: float = 0.0
        self.loop_mode: bool = True
        self.playing: bool = True
        self.default_anim_name: Optional[str] = default_anim
        

        # Cola de comandos para thread-safety
        self._cmd_queue: "SimpleQueue[Tuple[str, tuple, dict]]" = SimpleQueue()

        # Suscripciones (callbacks encolan, no tocan Pygame directo)
        event_bus.subscribe("sprite.play", self._on_play)
        event_bus.subscribe("sprite.default", self._on_default)
        event_bus.subscribe("sprite.get", self._on_get)
        event_bus.subscribe("sprite.pause", self._on_pause)
        event_bus.subscribe("sprite.resume", self._on_resume)
        event_bus.subscribe("sprite.toggle_loop", self._on_toggle_loop)

    # ---------- Callbacks de eventos (solo encolan) ----------
    def _on_play(self, name: str, mode: str = "loop"):
        self._cmd_queue.put(("play", (name, mode), {}))

    def _on_default(self):
        self._cmd_queue.put(("default", (), {}))

    def _on_get(self):
        self._cmd_queue.put(("get", (), {}))

    def _on_pause(self):
        self._cmd_queue.put(("pause", (), {}))

    def _on_resume(self):
        self._cmd_queue.put(("resume", (), {}))

    def _on_toggle_loop(self):
        self._cmd_queue.put(("toggle_loop", (), {}))

    # ---------- API pública ----------
    def run(self):
        """Inicializa Pygame, carga recursos y entra al bucle principal (bloqueante)."""
        sheet_path, csv_path = self._resolve_assets()
        pygame.init()

        flags = pygame.DOUBLEBUF
        if self.fullscreen: flags |= pygame.FULLSCREEN

        width = self.sprite_w * self.window_scale
        height = self.sprite_h * self.window_scale

        try:
            screen = pygame.display.set_mode((width, height), flags, vsync=1 if self.vsync else 0)
        except TypeError:
            screen = pygame.display.set_mode((width, height), flags)

        pygame.display.set_caption("SpritePlayer")
        clock = pygame.time.Clock()

        sheet = pygame.image.load(str(sheet_path)).convert_alpha()
        self.animations = self._slice_all(sheet, self._parse_csv(csv_path))
        self.anim_lookup = {a.name: i for i, a in enumerate(self.animations)}

        if not self.animations:
            logger.info("No hay animaciones cargadas. Revisa el CSV/sheet.")
            pygame.quit()
            return

        # Selección de animación por defecto
        if self.default_anim_name and self.default_anim_name in self.anim_lookup:
            self.idx = self.anim_lookup[self.default_anim_name]
        else:
            # si no se especifica, toma la primera con frames
            self.idx = self._first_with_frames(0)

        self.frame_idx = 0
        self.acc = 0.0

        # Overlay opcional
        try:
            font = pygame.font.SysFont(None, 22)
        except Exception:
            font = None

        logger.info("ESC para salir. Control por EventBus: "
              "sprite.play(name, mode='loop'|'once'), sprite.default, sprite.get, sprite.pause, sprite.resume, sprite.toggle_loop")

        running = True
        while running:
            dt = clock.tick(120) / 1000.0

            # Eventos de ventana
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    event_bus.emit("speak.flag")

            # Procesa comandos del bus
            self._drain_commands()

            # Avance de animación
            anim = self.animations[self.idx]
            if self.playing and anim.count > 0:
                self.acc += dt
                if self.acc >= 1.0 / max(1, self.fps_anim):
                    self.acc -= 1.0 / max(1, self.fps_anim)
                    if self.loop_mode:
                        self.frame_idx = (self.frame_idx + 1) % anim.count
                    else:
                        if self.frame_idx + 1 < anim.count:
                            self.frame_idx += 1
                        # en "once", se queda en el último frame

            # Render
            screen.fill(self.bg_color)
            if anim.count > 0:
                dst_xy = ((screen.get_width() - self.sprite_w) // 2,
                          (screen.get_height() - self.sprite_h) // 2)
                screen.blit(anim.frames[self.frame_idx], dst_xy)

            if font:
                try:
                    info1 = font.render(
                        f"{anim.name} ({self.frame_idx+1}/{max(1,anim.count)})",
                        True, (220, 220, 220)
                    )
                    info2 = font.render(
                        f"Loop: {'ON' if self.loop_mode else 'OFF'}  Estado: {'Play' if self.playing else 'Pause'}",
                        True, (180, 180, 180)
                    )
                    screen.blit(info1, (10, 8))
                    screen.blit(info2, (10, 30))
                except Exception:
                    pass

            pygame.display.update()

        pygame.quit()

    # ---------- Helpers internos ----------
    def _resolve_assets(self) -> Tuple[Path, Path]:
        sheet = (self.base_dir / self.assets_dir / self.sheet_name).resolve()
        csvp = (self.base_dir / self.assets_dir / self.csv_name).resolve()
        if not sheet.exists() or not csvp.exists():
            logger.info("No se encuentra el spritesheet o el CSV.")
            logger.info("Sheet:", sheet, sheet.exists()); logger.info("CSV:", csvp, csvp.exists())
            sys.exit(1)
        return sheet, csvp

    # CSV = nombre, fila, nframes  (col_inicio = 0 por defecto)
    def _parse_csv(self, csv_path: Path) -> List[Tuple[str, int, int, int]]:
        defs = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            for name, row_s, nframes_s, descripcion in csv.reader(f):
                name = name.strip()
                r = int(row_s)
                n = max(1, int(nframes_s))
                defs.append((name, r, 0, n))
        return defs

    def _slice_all(self, sheet: pygame.Surface, anim_defs: List[Tuple[str, int, int, int]]) -> List[Animation]:
        sw, sh = sheet.get_size()
        animations: List[Animation] = []
        for name, row, start_col, nframes in anim_defs:
            frames: List[pygame.Surface] = []
            for i in range(nframes):
                col = start_col + i
                x, y = col * self.sprite_w, row * self.sprite_h
                if x < 0 or y < 0 or x + self.sprite_w > sw or y + self.sprite_h > sh:
                    logger.warning(f"{name}: frame fuera del sheet (row={row}, col={col})")
                    break
                fr = pygame.Surface((self.sprite_w, self.sprite_h), pygame.SRCALPHA)
                fr.blit(sheet, (0, 0), pygame.Rect(x, y, self.sprite_w, self.sprite_h))
                frames.append(fr.convert_alpha())
            if not frames:
                logger.warning(f"Animación '{name}' sin frames válidos.")
            animations.append(Animation(name, frames))
        return animations

    def _first_with_frames(self, i: int) -> int:
        if not self.animations:
            return 0
        tries = 0
        while self.animations[i].count == 0 and tries < len(self.animations):
            i = (i + 1) % len(self.animations)
            tries += 1
        return i

    def _emit_state(self):
        anim = self.animations[self.idx]
        state = PlayerState(
            name=anim.name,
            loop=self.loop_mode,
            playing=self.playing,
            frame_idx=self.frame_idx
        )
        # Publica el estado actual
        event_bus.emit("sprite.state", {
            "name": state.name,
            "loop": state.loop,
            "playing": state.playing,
            "frame_idx": state.frame_idx
        })

    def _drain_commands(self):
        while not self._cmd_queue.empty():
            cmd, args, kwargs = self._cmd_queue.get()
            if cmd == "play":
                name, mode = args
                idx = self.anim_lookup.get(name)
                if idx is None:
                    logger.warning(f"sprite.play: animación '{name}' no existe")
                    continue
                self.idx = idx
                self.frame_idx = 0
                self.acc = 0.0
                self.loop_mode = (str(mode).lower() == "loop")
                self.playing = True
                self._emit_state()

            elif cmd == "default":
                if self.default_anim_name and self.default_anim_name in self.anim_lookup:
                    self.idx = self.anim_lookup[self.default_anim_name]
                else:
                    self.idx = self._first_with_frames(0)
                self.frame_idx = 0
                self.acc = 0.0
                self.playing = True
                self._emit_state()

            elif cmd == "get":
                self._emit_state()

            elif cmd == "pause":
                self.playing = False
                self._emit_state()

            elif cmd == "resume":
                self.playing = True
                self._emit_state()

            elif cmd == "toggle_loop":
                self.loop_mode = not self.loop_mode
                self._emit_state()
