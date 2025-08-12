from assets import resolve_assets

ASSETS_DIR = resolve_assets()

CONFIG = {
    "MAP_W": 5, "MAP_H": 5, "TILE_WORLD": 1.0,

    "SCREEN_W": 900, "SCREEN_H": 600,
    "BG_COLOR": (18, 22, 26),
    "GROUND_COLOR": (185, 210, 190),
    "GRID_COLOR": (40, 48, 56),
    "FAR_TINT": (140, 160, 150),

    "CAM_X": 2.5, "CAM_Y": 3.0, "CAM_Z": -6.0,
    "FOCAL": 700.0,
    "SCENE_Y_OFFSET": -600//3,

    "START_C": 2, "START_R": 2,
    "STEP_TIME": 0.14,

    "SPRITE_WORLD_H": 2.0,
    "MIN_SCREEN_H": 40,
    "MAX_SCREEN_H": 320,
    "SPRITE_SCALE": 1.0,

    "FRAME_W": 64, "FRAME_H": 64,
    "ANIM_FRAMES": 9, "ANIM_DT": 0.08,
    "ANIM_FPS_DEFAULT": 10,
    "ANIM_FPS_WALK": 12,
    "ANIM_FPS_IDLE": 4,

    "HERO_SPRITESHEET": str((ASSETS_DIR / "hero.png").resolve()),
    "HERO_INDEX_CSV":   str((ASSETS_DIR / "hero_index.csv").resolve()),

    "FPS": 60,
}
