import paho.mqtt.client as mqtt
import curses
import time

# MQTT Config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_MODO = "voz/modo"
TOPIC_ACCION = "voz/escuchar"
TOPIC_TEXTO = "voz/texto"
TOPIC_RESPUESTA = "voz/estado"
changed = True


COLOR_STATES = {
    "idle": 1,
    "listening": 2,
    "processing": 3,
    "speaking": 4,
}

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
modo_actual = "manual"

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
    stdscr.addstr(y + 1, x + box_w // 2 - 1, "  ", curses.color_pair(COLOR_STATES[state_key]) | curses.A_REVERSE)
    stdscr.addstr(y + 3, x + box_w // 2 - len(label) // 2, label, curses.color_pair(COLOR_STATES[state_key]) | curses.A_REVERSE)


def draw_chat_history(stdscr, history):
    h, w = stdscr.getmaxyx()
    visible_history = history[-5:]  # Solo los últimos 5 mensajes
    y = h - len(visible_history) * 2 - 2  # Altura basada solo en esos
    for speaker, text in visible_history:
        stdscr.addstr(y, 2, f"{speaker}: {text}")
        y += 2



def draw_config_screen(stdscr):
    stdscr.addstr(4, 4, "Pantalla de configuración (vacía por ahora)", curses.A_DIM)


# MQTT client
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC_TEXTO)
    client.subscribe(TOPIC_RESPUESTA)

def on_message(client, userdata, msg):
    global chat_history, current_state,changed
    if msg.topic == TOPIC_TEXTO:
        chat_history.append(("USUARIO", msg.payload.decode()))
    elif msg.topic == TOPIC_RESPUESTA:
        chat_history.append(("LUCI", msg.payload.decode()))
        if msg.payload.decode().lower() == "hablando":
            current_state = "speaking"
        elif msg.payload.decode().lower() == "procesando":
            current_state = "processing"
        elif msg.payload.decode().lower() == "escuchando":
            current_state = "listening"
        else:
            current_state = "idle"
    changed = True

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

def main(stdscr):
    global current_state, modo_actual,changed

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)   # IDLE
    curses.init_pair(2, curses.COLOR_GREEN, -1)   # LISTENING
    curses.init_pair(3, curses.COLOR_BLUE, -1)    # PROCESSING
    curses.init_pair(4, curses.COLOR_MAGENTA, -1) # SPEAKING


    curses.curs_set(0)
    stdscr.nodelay(True)

    active_tab = 0
    last_state = None
    last_tab = None

    while True:
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
            elif key.lower() == 'm':
                modo_actual = "auto" if modo_actual == "manual" else "manual"
                client.publish(TOPIC_MODO, modo_actual)
                changed = True
            elif key.lower() == 'h':
                client.publish(TOPIC_ACCION, "1")
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
            changed = False

        time.sleep(0.05)


curses.wrapper(main)
