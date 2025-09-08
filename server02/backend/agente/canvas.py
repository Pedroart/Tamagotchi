# sprite_player.py
import csv
import sys
import pygame
import cv2            # === VISTA: OpenCV para homografía
import numpy as np    # === VISTA: NumPy para arrays
from dataclasses import dataclass
from pathlib import Path
from queue import SimpleQueue
from typing import List, Tuple, Optional, Dict

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

    Extensión: Interpolación de vista (homografía)
      Teclas:
        V: vista ON/OFF
        F1: guardar Pose A (cuadrilátero actual)
        F2: guardar Pose B
        A:  cargar Pose A en editor
        B:  cargar Pose B en editor
        G:  mostrar/ocultar contorno
        ←/→: ajustar t (0..1)
      Mouse (Vista ON):
        arrastrar los 4 puntos del cuadrilátero (0=TL,1=TR,2=BR,3=BL)
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
        window_scale: int = 2,
        fullscreen: bool = True,
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

        # === VISTA: estado del editor/warp
        self.view_on: bool = False
        self.view_show_edges: bool = True
        self.view_t: float = 0.0  # interpolación [0..1] entre A y B
        self.view_drag_idx: Optional[int] = None
        self.view_pts: Optional[np.ndarray] = None  # cuadrilátero actual para edición (4x2 float32)
        self.view_poseA: Optional[np.ndarray] = None
        self.view_poseB: Optional[np.ndarray] = None

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
            self.idx = self._first_with_frames(0)

        self.frame_idx = 0
        self.acc = 0.0

        # Overlay opcional
        try:
            font = pygame.font.SysFont(None, 22)
        except Exception:
            font = None

        # === VISTA: inicialización de puntos por defecto (rect centrado)
        # Se definen respecto al tamaño de la ventana; iremos actualizando al vuelo
        def _default_quad(w, h, fw, fh):
            # fw,fh = tamaño del frame (considerando window_scale)
            cx, cy = w//2, h//2
            halfw, halfh = fw//2, fh//2
            return np.array([
                [cx - halfw, cy - halfh],  # TL
                [cx + halfw, cy - halfh],  # TR
                [cx + halfw, cy + halfh],  # BR
                [cx - halfw, cy + halfh],  # BL
            ], dtype=np.float32)

        running = True
        while running:
            dt = clock.tick(120) / 1000.0

            # Eventos de ventana
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False

                    # === VISTA: teclas de control
                    elif e.key == pygame.K_v:
                        self.view_on = not self.view_on
                        # al encender la vista, inicializa el quad si está vacío
                        if self.view_on and self.view_pts is None:
                            # usa el tamaño del frame escalado actual
                            fw = self.sprite_w * max(1, self.window_scale)
                            fh = self.sprite_h * max(1, self.window_scale)
                            self.view_pts = _default_quad(screen.get_width(), screen.get_height(), fw, fh)

                    elif e.key == pygame.K_g:
                        self.view_show_edges = not self.view_show_edges

                    elif e.key == pygame.K_F1:
                        # guarda Pose A
                        if self.view_pts is not None:
                            self.view_poseA = self.view_pts.copy()
                            logger.info("[Vista] Guardada Pose A")
                    elif e.key == pygame.K_F2:
                        # guarda Pose B
                        if self.view_pts is not None:
                            self.view_poseB = self.view_pts.copy()
                            logger.info("[Vista] Guardada Pose B")

                    elif e.key == pygame.K_a:
                        # cargar A al editor
                        if self.view_poseA is not None:
                            self.view_pts = self.view_poseA.copy()
                            logger.info("[Vista] Cargada Pose A al editor")
                    elif e.key == pygame.K_b:
                        # cargar B al editor
                        if self.view_poseB is not None:
                            self.view_pts = self.view_poseB.copy()
                            logger.info("[Vista] Cargada Pose B al editor")

                    elif e.key == pygame.K_LEFT:
                        self.view_t = max(0.0, self.view_t - 0.05)
                    elif e.key == pygame.K_RIGHT:
                        self.view_t = min(1.0, self.view_t + 0.05)

                    # Compatibilidad tuya previa:
                    elif e.key == pygame.K_SPACE:
                        event_bus.emit("speak.flag")

                # === VISTA: drag de puntos
                if self.view_on:
                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        if self.view_pts is not None:
                            mx, my = e.pos
                            best, d2b = None, 1e12
                            for i, (x, y) in enumerate(self.view_pts):
                                d2 = (mx - x) * (mx - x) + (my - y) * (my - y)
                                if d2 < d2b:
                                    best, d2b = i, d2
                            if d2b <= (12 * 12) * 9:  # radio de selección generoso
                                self.view_drag_idx = best
                    elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                        self.view_drag_idx = None
                    elif e.type == pygame.MOUSEMOTION and self.view_drag_idx is not None:
                        mx, my = e.pos
                        mx = min(max(mx, 0), screen.get_width()-1)
                        my = min(max(my, 0), screen.get_height()-1)
                        self.view_pts[self.view_drag_idx] = (mx, my)

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

            # Render
            screen.fill(self.bg_color)
            frame = anim.frames[self.frame_idx] if anim.count > 0 else None

            if frame is not None:
                if not self.view_on:
                    # --- Render clásico (centrado + scale) ---
                    if self.window_scale != 1:
                        frame_to_draw = pygame.transform.scale(
                            frame,
                            (self.sprite_w * self.window_scale, self.sprite_h * self.window_scale)
                        )
                    else:
                        frame_to_draw = frame
                    dst_xy = ((screen.get_width() - frame_to_draw.get_width()) // 2,
                              (screen.get_height() - frame_to_draw.get_height()) // 2)
                    screen.blit(frame_to_draw, dst_xy)

                else:
                    # --- VISTA: Render con homografía ---
                    # 1) Asegurar cuadrilátero base si no existe
                    if self.view_pts is None:
                        fw = self.sprite_w * max(1, self.window_scale)
                        fh = self.sprite_h * max(1, self.window_scale)
                        self.view_pts = _default_quad(screen.get_width(), screen.get_height(), fw, fh)

                    # 2) Elegir destino final (interpolado si hay A y B)
                    dst_used = self.view_pts
                    if (self.view_poseA is not None) and (self.view_poseB is not None):
                        t = float(self.view_t)
                        dst_used = (1.0 - t) * self.view_poseA + t * self.view_poseB
                        dst_used = dst_used.astype(np.float32)

                    # 3) Surface -> BGRA numpy
                    # Nota: array3d da (W,H,3) RGB, hay que transponer
                    arr_rgb = pygame.surfarray.array3d(frame)      # (W,H,3)
                    arr_rgb = np.transpose(arr_rgb, (1, 0, 2))     # (H,W,3)
                    # A canal alfa si existe; si no, creamos alfa=255
                    if frame.get_masks()[3] != 0:
                        # Surface tiene alfa; convertimos por pixel
                        arr_rgba = pygame.surfarray.array_alpha(frame)
                        arr_rgba = np.transpose(arr_rgba, (1, 0))  # (H,W)
                        bgra = np.dstack([arr_rgb[...,2], arr_rgb[...,1], arr_rgb[...,0], arr_rgba])
                    else:
                        alpha = np.full((arr_rgb.shape[0], arr_rgb.shape[1], 1), 255, dtype=np.uint8)
                        bgra = np.dstack([arr_rgb[...,2], arr_rgb[...,1], arr_rgb[...,0], alpha])

                    # 4) Homografía: del rectángulo fuente (frame) al quad destino (pantalla)
                    h_src, w_src = bgra.shape[:2]
                    src_pts = np.array([[0,0],[w_src-1,0],[w_src-1,h_src-1],[0,h_src-1]], dtype=np.float32)
                    Hm = cv2.getPerspectiveTransform(src_pts, dst_used.astype(np.float32))

                    # 5) Warp al tamaño de la pantalla, preservando alfa
                    warped = cv2.warpPerspective(
                        bgra, Hm,
                        (screen.get_width(), screen.get_height()),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=(0,0,0,0)
                    )

                    # 6) BGRA -> RGBA y Surface
                    rgba = warped[..., [2,1,0,3]]  # B,G,R,A -> R,G,B,A
                    surf = pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")
                    screen.blit(surf, (0, 0))

                    # 7) Dibujar contorno y puntos si se desea
                    if self.view_show_edges and self.view_pts is not None:
                        ptsi = dst_used.astype(int)
                        pygame.draw.polygon(screen, (0, 255, 255), ptsi, 2)
                        for i, (x, y) in enumerate(ptsi):
                            pygame.draw.circle(screen, (255, 20, 200), (int(x), int(y)), 8)
                            if font:
                                screen.blit(font.render(str(i), True, (20,20,20)), (int(x)-6, int(y)-8))

            # HUD simple
            if font:
                try:
                    anim = self.animations[self.idx]
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

                    # === VISTA: HUD
                    if self.view_on:
                        info3 = font.render(
                            f"VISTA: ON  t={self.view_t:.2f}  (F1->A, F2->B, A/B cargar, ←/→ interp, G edges)",
                            True, (180, 255, 220)
                        )
                        screen.blit(info3, (10, 52))
                    else:
                        info3 = font.render("VISTA: OFF (pulsa V para activar)", True, (140, 160, 170))
                        screen.blit(info3, (10, 52))
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
