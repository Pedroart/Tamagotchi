import curses
import time

# Estados posibles
STATES = {
    "idle": ("⚪", "IDLE"),
    "listening": ("🟢", "ESCUCHANDO"),
    "processing": ("🔵", "PROCESANDO"),
    "speaking": ("🟣", "HABLANDO"),
}

# Historial de conversación
chat_history = [
    ("USUARIO", "Hola"),
    ("LUCI", "Hola, ¿en qué puedo ayudarte?")
]

# Estado inicial
current_state = "idle"


def draw_tabs(stdscr, active_tab):
    tabs = [" Chatbot ", " Configuración "]
    x = 2
    for idx, tab in enumerate(tabs):
        attr = curses.A_REVERSE if idx == active_tab else curses.A_NORMAL
        stdscr.addstr(0, x, tab, attr)
        x += len(tab) + 2


def draw_status_box(stdscr, state_key):
    h, w = stdscr.getmaxyx()
    icon, label = STATES[state_key]
    box_h, box_w = 5, 20
    y, x = 2, w // 2 - box_w // 2

    for i in range(box_h):
        stdscr.addstr(y + i, x, " " * box_w, curses.A_DIM)
    stdscr.addstr(y + 1, x + box_w // 2 - 1, icon, curses.A_BOLD)
    stdscr.addstr(y + 3, x + box_w // 2 - len(label) // 2, label)


def draw_chat_history(stdscr, history):
    h, w = stdscr.getmaxyx()
    y = h - len(history) * 2 - 2
    for speaker, text in history[-5:]:
        stdscr.addstr(y, 2, f"{speaker}: {text}")
        y += 2


def draw_config_screen(stdscr):
    stdscr.addstr(4, 4, "Pantalla de configuración (vacía por ahora)", curses.A_DIM)


def main(stdscr):
    global current_state
    curses.curs_set(0)
    stdscr.nodelay(True)

    active_tab = 0
    last_state = None
    last_tab = None

    while True:
        changed = False
        try:
            key = stdscr.getkey()
            if key == 'KEY_RIGHT':
                active_tab = (active_tab + 1) % 2
                changed = True
            elif key == 'KEY_LEFT':
                active_tab = (active_tab - 1) % 2
                changed = True
            elif key.lower() == 'q':
                break
            elif key.lower() == 'l':
                current_state = "listening"
                changed = True
            elif key.lower() == 'p':
                current_state = "processing"
                changed = True
            elif key.lower() == 's':
                current_state = "speaking"
                changed = True
            elif key.lower() == 'i':
                current_state = "idle"
                changed = True
        except:
            pass

        if current_state != last_state or active_tab != last_tab or changed:
            stdscr.clear()
            draw_tabs(stdscr, active_tab)
            if active_tab == 0:
                draw_status_box(stdscr, current_state)
                draw_chat_history(stdscr, chat_history)
            else:
                draw_config_screen(stdscr)
            stdscr.refresh()
            last_state = current_state
            last_tab = active_tab

        time.sleep(0.05)


curses.wrapper(main)
