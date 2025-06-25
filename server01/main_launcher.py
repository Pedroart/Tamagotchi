import subprocess
import os

# Ruta base del entorno virtual
VENV_PATH = os.path.join(os.getcwd(), ".venv", "bin", "python")

# Servicios a lanzar
SERVICIOS = [
    "stt/serviceStt.py",
    "tts/serviceTTS_piper.py",
    # "ui_chat.py",  # descomenta si tienes UI
]

procesos = []

try:
    for script in SERVICIOS:
        print(f"🚀 Lanzando {script}...")
        p = subprocess.Popen([VENV_PATH, script]
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        procesos.append(p)

    print("✅ Todos los servicios están corriendo. Ctrl+C para detener.")

    import curses
    curses.wrapper(test.main)

except KeyboardInterrupt:
    print("\n🛑 Interrupción detectada. Cerrando servicios...")
    for p in procesos:
        p.terminate()

