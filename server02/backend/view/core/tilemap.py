import pygame
from core.utils import lerp, shade_color

class TileMap:
    def __init__(self, cfg):
        self.w = cfg["MAP_W"]; self.h = cfg["MAP_H"]
        self.T = cfg["TILE_WORLD"]
        self.ground = cfg["GROUND_COLOR"]
        self.grid = cfg["GRID_COLOR"]
        self.far_tint = cfg["FAR_TINT"]

    def tile_corners(self, c, r):
        x0, x1 = c*self.T, (c+1)*self.T
        z0, z1 = r*self.T, (r+1)*self.T
        return [(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)]

    def draw(self, screen, cam):
        tiles = []
        for rr in range(self.h):
            for cc in range(self.w):
                pts2d, depths, ok = [], [], True
                for (x, y, z) in self.tile_corners(cc, rr):
                    pr = cam.project(x, y, z)
                    if pr is None: ok = False; break
                    (sx, sy), Zc = pr
                    pts2d.append((sx, sy)); depths.append(Zc)
                if ok:
                    tiles.append((sum(depths)/4.0, pts2d))

        if not tiles: return
        tiles.sort(key=lambda t: t[0], reverse=True)
        maxZ = max(t[0] for t in tiles); minZ = min(t[0] for t in tiles)
        span = max(1e-6, maxZ - minZ)

        for avgZ, pts in tiles:
            k = (avgZ - minZ) / span
            col = shade_color(self.ground, self.far_tint, k)
            pygame.draw.polygon(screen, col, pts)
            pygame.draw.polygon(screen, self.grid, pts, width=1)
