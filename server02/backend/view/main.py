from game import Game
from config import CONFIG
from controls import CONTROLS

if __name__ == "__main__":
    Game(CONFIG, CONTROLS).loop()
