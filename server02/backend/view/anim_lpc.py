from __future__ import annotations
import pygame, csv, os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class Animation:
    name: str
    frames: List[pygame.Surface]
    loop: bool = True

def load_animation_index(csv_path: str) -> List[Tuple[int, str, int]]:
    out = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            r, name, cnt = row
            out.append((int(r), name.strip(), int(cnt)))
    return out

def slice_frame(sheet: pygame.Surface, col: int, row: int, fw: int, fh: int) -> pygame.Surface:
    rect = pygame.Rect(col*fw, row*fh, fw, fh)
    surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
    surf.blit(sheet, (0, 0), rect)
    return surf

class SpriteBank:
    def __init__(self, sheet_path: str, index_csv: str, fw: int = 64, fh: int = 64):
        if not os.path.exists(sheet_path):
            raise FileNotFoundError(sheet_path)
        if not os.path.exists(index_csv):
            raise FileNotFoundError(index_csv)
        self.sheet = pygame.image.load(sheet_path).convert_alpha()
        self.fw, self.fh = fw, fh
        self.cols = self.sheet.get_width() // fw
        self.rows = self.sheet.get_height() // fh

        index = load_animation_index(index_csv)
        self.anims: Dict[str, Animation] = {}
        for row, name, count in index:
            if row < 0 or row >= self.rows:
                continue
            count = min(count, self.cols)
            frames = [slice_frame(self.sheet, i, row, fw, fh) for i in range(count)]
            self.anims[name] = Animation(name=name, frames=frames, loop=True)

    def get(self, name: str) -> Animation:
        if name not in self.anims:
            raise KeyError(f"Animación no encontrada: {name}")
        return self.anims[name]

class Animator:
    def __init__(self, bank: SpriteBank, default: str, fps: int = 12, loop: bool = True):
        self.bank = bank
        self.fps_default = fps
        self.fps_overrides: Dict[str, int] = {}
        self.loop_overrides: Dict[str, bool] = {}
        self._acc = 0.0
        self.set(default, fps=fps, loop=loop, restart=True)

    def set(self, name: str, *, fps: Optional[int] = None, loop: Optional[bool] = None, restart: bool = False):
        if not restart and getattr(self, "name", None) == name:
            return
        self.name = name
        anim = self.bank.get(name)
        self.frames = anim.frames
        self.loop = self.loop_overrides.get(name, anim.loop if loop is None else loop)
        self.fps = self.fps_overrides.get(name, self.fps_default if fps is None else fps)
        self.i = 0
        self._acc = 0.0

    def update(self, dt: float):
        if len(self.frames) <= 1 or self.fps <= 0:
            return
        self._acc += dt
        frame_time = 1.0 / self.fps
        while self._acc >= frame_time:
            self._acc -= frame_time
            self.i += 1
            if self.i >= len(self.frames):
                if self.loop:
                    self.i = 0
                else:
                    self.i = len(self.frames) - 1

    def frame(self) -> pygame.Surface:
        return self.frames[self.i]

def blit_anchored_by_feet(surface: pygame.Surface, img: pygame.Surface, foot_x: int, foot_y: int):
    surface.blit(img, (foot_x - img.get_width() // 2, foot_y - img.get_height()))

def scale_to_height(img: pygame.Surface, target_h: int) -> pygame.Surface:
    if target_h <= 1:
        return img
    w = max(1, int(img.get_width() * (target_h / img.get_height())))
    return pygame.transform.smoothscale(img, (w, target_h))
