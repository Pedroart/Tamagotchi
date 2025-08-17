import os
from dotenv import load_dotenv

load_dotenv()

SPRITE_W_DEFAULT, SPRITE_H_DEFAULT = 234, 266
FPS_ANIM_DEFAULT = 5
BG_COLOR_DEFAULT = (20, 20, 20)
ASSETS_DIR_DEFAULT = "assets"
SHEET_NAME_DEFAULT = "spritesheet.png"
CSV_NAME_DEFAULT = "anims.csv"

API_KEY_OPENAI = os.getenv("OPENAI_API_KEY")