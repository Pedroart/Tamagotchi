import pygame
import math
import json
import os

# ================== Ventana / colores ==================
WIDTH, HEIGHT = 1200, 800
BG = (0, 0, 0)
CYAN = (255, 255, 0)            # AMARILLO
VIGNETTE_ALPHA = 300

GRID_DIV = 12
CONFIG_PATH = "tron_grid_config.json"      # mismo archivo para compartir config

# ================== Utils 2D ==================
def vsub(a,b): return (a[0]-b[0], a[1]-b[1])
def vadd(a,b): return (a[0]+b[0], a[1]+b[1])
def vmul(a,s): return (a[0]*s, a[1]*s)
def vlen(a): return math.hypot(a[0], a[1])
def vnorm(a):
    L = vlen(a)
    return (a[0]/L, a[1]/L) if L>1e-9 else (0.0,0.0)
def clamp(x,a,b): return max(a, min(b, x))

def line_intersection(P, d, Q, e):
    A = ((d[0], -e[0]), (d[1], -e[1]))
    b = (Q[0]-P[0], Q[1]-P[1])
    det = A[0][0]*A[1][1] - A[0][1]*A[1][0]
    if abs(det) < 1e-9: return None
    t = (b[0]*A[1][1] - b[1]*A[0][1]) / det
    return (P[0] + t*d[0], P[1] + t*d[1])

# ================== Homografía ==================
def gauss_solve(A, B):
    n = len(B)
    M = [row[:] + [B[i]] for i,row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("Sistema singular")
        M[col], M[piv] = M[piv], M[col]
        fac = M[col][col]
        for j in range(col, n+1): M[col][j] /= fac
        for r in range(n):
            if r == col: continue
            fac = M[r][col]
            for j in range(col, n+1): M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]

def compute_homography(src, dst):
    (x0,y0),(x1,y1),(x2,y2),(x3,y3) = src
    (X0,Y0),(X1,Y1),(X2,Y2),(X3,Y3) = dst
    A=[]; B=[]
    for (x,y),(X,Y) in zip(src,dst):
        A.append([x,y,1, 0,0,0, -x*X, -y*X]); B.append(X)
        A.append([0,0,0, x,y,1, -x*Y, -y*Y]); B.append(Y)
    h = gauss_solve(A,B)
    return [[h[0],h[1],h[2]],
            [h[3],h[4],h[5]],
            [h[6],h[7],1.0]]

def apply_H(Hm, p):
    x,y = p
    X = Hm[0][0]*x + Hm[0][1]*y + Hm[0][2]
    Y = Hm[1][0]*x + Hm[1][1]*y + Hm[1][2]
    Ww= Hm[2][0]*x + Hm[2][1]*y + 1.0
    if abs(Ww) < 1e-9: return None
    return (X/Ww, Y/Ww)

# ================== Cuartos (quads) desde O, X, Y, Z ==================
def build_plane_quads(O, X, Y, Z):
    O = tuple(O); X = tuple(X); Y = tuple(Y); Z = tuple(Z)
    dirX = vnorm(vsub(X,O)); dirY = vnorm(vsub(Y,O)); dirZ = vnorm(vsub(Z,O))
    Lx = max(120.0, vlen(vsub(X,O)))
    Ly = max(120.0, vlen(vsub(Y,O)))
    Lz = max(120.0, vlen(vsub(Z,O)))

    # Piso
    P00 = O
    P10 = vadd(O, vmul(dirX, Lx))
    P01 = vadd(O, vmul(dirZ, Lz))
    P11 = line_intersection(P10, dirZ, P01, dirX) or vadd(P10, vmul(dirZ, Lz))
    floor_quad = [P00, P10, P11, P01]

    # Pared X (usa Y y Z)
    PX10 = vadd(O, vmul(dirY, Ly))
    PX01 = vadd(O, vmul(dirZ, Lz))
    PX11 = line_intersection(PX10, dirZ, PX01, dirY) or vadd(PX10, vmul(dirZ, Lz))
    wallX_quad = [P00, PX10, PX11, PX01]

    # Pared Z (usa Y y X)
    PZ10 = vadd(O, vmul(dirY, Ly))
    PZ01 = vadd(O, vmul(dirX, Lx))
    PZ11 = line_intersection(PZ10, dirX, PZ01, dirY) or vadd(PZ10, vmul(dirX, Lx))
    wallZ_quad = [P00, PZ10, PZ11, PZ01]

    return floor_quad, wallX_quad, wallZ_quad

# ================== Render de grilla (con atenuación) ==================
def draw_perspective_grid(surface, quad, div=12, color=CYAN, glow_levels=3,
                          atten_u=False, atten_v=False):
    src = [(0,0),(1,0),(1,1),(0,1)]
    Hm  = compute_homography(src, quad)

    def glow_line(a,b, alpha_scale=1.0):
        if a is None or b is None: return
        for i in range(glow_levels, 0, -1):
            t = 2 + i*2
            base = 40 + i*30
            alpha = clamp(int(base*alpha_scale), 0, 255)
            g = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(g, (*color, alpha), a, b, t)
            surface.blit(g, (0,0))
        gg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(gg, (*color, clamp(int(255*alpha_scale),0,255)), a, b, 2)
        surface.blit(gg,(0,0))

    for i in range(div+1):
        u = i/div
        a = apply_H(Hm,(u,0.0)); b = apply_H(Hm,(u,1.0))
        alpha_scale = 1.0 - (0.55*u if atten_u else 0.0)
        glow_line(a,b,alpha_scale)

    for j in range(div+1):
        v = j/div
        a = apply_H(Hm,(0.0,v)); b = apply_H(Hm,(1.0,v))
        alpha_scale = 1.0 - (0.55*v if atten_v else 0.0)
        glow_line(a,b,alpha_scale)

    return Hm  # devolvemos la homografía por si la queremos reutilizar

# ================== Vignette ==================
def draw_vignette(surface, alpha=VIGNETTE_ALPHA):
    if alpha <= 0: return
    vign = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx, cy = WIDTH//2, HEIGHT//2
    max_r = int(math.hypot(cx, cy))
    steps = 16
    for i in range(steps,0,-1):
        r0 = int(max_r * i / steps)
        a  = int(alpha * (i/steps)**2)
        pygame.draw.circle(vign, (0,0,0,a), (cx,cy), r0)
    surface.blit(vign,(0,0))

# ================== Config ==================
def save_config(path, O,X,Y,Z, grid_div, color, vignette_alpha, sprite_state):
    data = {
        "O": O, "X": X, "Y": Y, "Z": Z,
        "grid_div": grid_div,
        "color": list(color),
        "vignette_alpha": vignette_alpha,
        "sprite": sprite_state
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_config(path):
    if not os.path.exists(path): return None
    with open(path,"r",encoding="utf-8") as f:
        d = json.load(f)
    O = [float(d["O"][0]), float(d["O"][1])]
    X = [float(d["X"][0]), float(d["X"][1])]
    Y = [float(d["Y"][0]), float(d["Y"][1])]
    Z = [float(d["Z"][0]), float(d["Z"][1])]
    grid_div = int(d.get("grid_div", GRID_DIV))
    color = tuple(int(c) for c in d.get("color", list(CYAN)))
    vign = int(d.get("vignette_alpha", VIGNETTE_ALPHA))
    sprite = d.get("sprite", None)
    return O,X,Y,Z, grid_div, color, vign, sprite

# ================== Main ==================
def main():
    global GRID_DIV, CYAN, VIGNETTE_ALPHA
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Tron room + Sprite holográfico")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)

    # ----- Vista isométrica por defecto -----
    iso_len = 260
    iso_alt = 220
    O = [WIDTH*0.55, HEIGHT*0.62]
    c30, s30 = math.cos(math.pi/6), math.sin(math.pi/6)
    X = [O[0] + iso_len*c30, O[1] - iso_len*s30]
    Z = [O[0] - iso_len*c30, O[1] - iso_len*s30*0.2]
    Y = [O[0] - iso_len*0.7, O[1] - iso_alt]

    # ----- Sprite -----
    # Debe existir "hologram.png" (fondo transparente)
    sprite_img = pygame.image.load("hologram.png").convert_alpha()
    sprite_native_size = sprite_img.get_size()

    # Estado del sprite en coordenadas del piso (u,v in [0,1])
    sprite = {
        "u": 0.5,          # posición horizontal sobre piso (0..1)
        "v": 0.55,         # profundidad sobre piso (0..1)
        "size_near": 420,  # alto (px) cuando está cerca
        "size_far": 160,   # alto (px) cuando está lejos
        "depth_curve": 1.25, # curva para escalado por profundidad
        "x_offset": 0,     # ajuste fino en pantalla (px)
        "y_offset": 0
    }

    # Cargar config previa
    loaded = load_config(CONFIG_PATH)
    if loaded is not None:
        O,X,Y,Z, GRID_DIV, CYAN, VIGNETTE_ALPHA, spr = loaded
        if isinstance(spr, dict):
            sprite.update(spr)

    handles = {"O": O, "X": X, "Y": Y, "Z": Z}
    dragging = None
    offset = (0,0)

    running = True
    while running:
        dt = clock.tick(60)/1000.0
        # ===== Eventos =====
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: running = False
                elif e.key == pygame.K_g: GRID_DIV = min(40, GRID_DIV+1)
                elif e.key == pygame.K_h: GRID_DIV = max(4, GRID_DIV-1)
                elif e.key == pygame.K_r:
                    # Reset a vista iso y sprite centrado
                    O[:] = [WIDTH*0.55, HEIGHT*0.62]
                    X[:] = [O[0] + iso_len*c30, O[1] - iso_len*s30]
                    Z[:] = [O[0] - iso_len*c30, O[1] - iso_len*s30*0.2]
                    Y[:] = [O[0] - iso_len*0.7, O[1] - iso_alt]
                    GRID_DIV = 12; CYAN=(255,255,0); VIGNETTE_ALPHA=110   # AMARILLO EN RESET
                    sprite.update({"u":0.5,"v":0.55,"size_near":420,"size_far":160,"depth_curve":1.25,"x_offset":0,"y_offset":0})
                elif e.key == pygame.K_s:
                    save_config(CONFIG_PATH, O,X,Y,Z, GRID_DIV, CYAN, VIGNETTE_ALPHA, sprite)
                elif e.key == pygame.K_l:
                    loaded = load_config(CONFIG_PATH)
                    if loaded is not None:
                        O,X,Y,Z, GRID_DIV, CYAN, VIGNETTE_ALPHA, spr = loaded
                        if isinstance(spr, dict):
                            sprite.update(spr)
                # mover sprite sobre el piso
                elif e.key == pygame.K_a: sprite["u"] = clamp(sprite["u"] - 0.02, 0.0, 1.0)
                elif e.key == pygame.K_d: sprite["u"] = clamp(sprite["u"] + 0.02, 0.0, 1.0)
                elif e.key == pygame.K_w: sprite["v"] = clamp(sprite["v"] - 0.02, 0.0, 1.0)
                elif e.key == pygame.K_s: sprite["v"] = clamp(sprite["v"] + 0.02, 0.0, 1.0)
                # escalar manual
                elif e.key == pygame.K_q: sprite["size_near"] = max(50, sprite["size_near"] - 10)
                elif e.key == pygame.K_e: sprite["size_near"] = min(1200, sprite["size_near"] + 10)
                elif e.key == pygame.K_z: sprite["size_far"]  = max(30, sprite["size_far"] - 10)
                elif e.key == pygame.K_x: sprite["size_far"]  = min(800, sprite["size_far"] + 10)
                elif e.key == pygame.K_1: sprite["depth_curve"] = max(0.7, sprite["depth_curve"] - 0.05)
                elif e.key == pygame.K_2: sprite["depth_curve"] = min(2.0, sprite["depth_curve"] + 0.05)
                # offsets finos en pantalla
                elif e.key == pygame.K_UP:    sprite["y_offset"] -= 4
                elif e.key == pygame.K_DOWN:  sprite["y_offset"] += 4
                elif e.key == pygame.K_LEFT:  sprite["x_offset"] -= 4
                elif e.key == pygame.K_RIGHT: sprite["x_offset"] += 4

            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx,my = e.pos
                for name,p in handles.items():
                    if (mx-p[0])**2 + (my-p[1])**2 <= 13*13:
                        dragging = name
                        offset = (p[0]-mx, p[1]-my)
                        break
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                dragging = None
            elif e.type == pygame.MOUSEMOTION and dragging:
                mx,my = e.pos
                handles[dragging][0] = clamp(mx + offset[0], 0, WIDTH)
                handles[dragging][1] = clamp(my + offset[1], 0, HEIGHT)

        # ===== Construcción de planos y homografías =====
        floor_q, wallX_q, wallZ_q = build_plane_quads(O, X, Y, Z)

        screen.fill(BG)

        H_wallZ = draw_perspective_grid(screen, wallZ_q, GRID_DIV, CYAN, 3, atten_u=True,  atten_v=False)
        H_wallX = draw_perspective_grid(screen, wallX_q, GRID_DIV, CYAN, 3, atten_u=False, atten_v=True)
        H_floor = draw_perspective_grid(screen, floor_q, GRID_DIV, CYAN, 3, atten_u=True,  atten_v=True)

        # ===== Sprite: posicionamiento y escala por "profundidad" =====
        # Base (los pies) en el piso:
        u = sprite["u"]; v = sprite["v"]
        base = apply_H(H_floor, (u, v))
        if base is not None:
            # Profundidad aproximada: usamos (u+v)/2 (más cerca = menor valor)
            depth01 = clamp((u + v) * 0.5, 0.0, 1.0)
            # curva: 0..1 -> factor
            t = depth01 ** sprite["depth_curve"]
            h_px = int(sprite["size_far"] * t + sprite["size_near"] * (1.0 - t))
            # Escalado proporcional
            sw, sh = sprite_native_size
            scale = h_px / max(1, sh)
            scaled = pygame.transform.smoothscale(sprite_img, (int(sw*scale), int(sh*scale)))

            # Colocar con el “pivote” en los pies (centro-x, bottom-y)
            bx, by = base
            bx += sprite["x_offset"]; by += sprite["y_offset"]
            dst = (int(bx - scaled.get_width()/2), int(by - scaled.get_height()))
            screen.blit(scaled, dst)

        # ===== Ejes y manejadores =====
        pygame.draw.line(screen, CYAN, O, X, 2)
        pygame.draw.line(screen, CYAN, O, Y, 2)
        pygame.draw.line(screen, CYAN, O, Z, 2)
        for name, tip in (("X", X), ("Y", Y), ("Z", Z)):
            pygame.draw.circle(screen, CYAN, (int(tip[0]), int(tip[1])), 6, 2)
            screen.blit(font.render(name, True, (255,255,180)), (tip[0]+10, tip[1]-12))  # texto amarillento
        pygame.draw.circle(screen, CYAN, (int(O[0]), int(O[1])), 7, 2)
        screen.blit(font.render("O", True, (255,255,180)), (O[0]+10, O[1]-12))          # texto amarillento

        # ===== HUD =====
        hud = [
            "Arrastra O, X, Y, Z para amoldar el cuarto (paredes + piso).",
            f"[W/S/A/D] mueve sprite (u={sprite['u']:.2f}, v={sprite['v']:.2f})",
            f"[Q/E] size_near={sprite['size_near']}   [Z/X] size_far={sprite['size_far']}   [1/2] curva={sprite['depth_curve']:.2f}",
            f"[Flechas] offset ({sprite['x_offset']},{sprite['y_offset']})   [S/L] guardar/cargar   [R] reset",
        ]
        y=10
        for t in hud:
            screen.blit(font.render(t, True, (255,235,160)), (12,y)); y+=22  # HUD en tono cálido

        draw_vignette(screen, VIGNETTE_ALPHA)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
