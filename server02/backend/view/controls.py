import pygame

CONTROLS = {
    "up":    [pygame.K_w, pygame.K_UP],
    "down":  [pygame.K_s, pygame.K_DOWN],
    "left":  [pygame.K_a, pygame.K_LEFT],
    "right": [pygame.K_d, pygame.K_RIGHT],
    "quit":  [pygame.K_ESCAPE],
    "toggle_run": [pygame.K_LSHIFT, pygame.K_RSHIFT],
    "bigger":  [pygame.K_EQUALS, pygame.K_KP_PLUS],
    "smaller": [pygame.K_MINUS,  pygame.K_KP_MINUS],
}
