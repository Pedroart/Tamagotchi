import subprocess
import os

# Ruta base del entorno virtual
VENV_PATH = os.path.join(os.getcwd(), ".venv", "bin", "python")

# Servicios a lanzar
SERVICIOS = [
    "stt/service_stt.py",
    "tts/service_tts.py",
    # "ui_chat.py",  # descomenta si tienes UI
]

procesos = []

try:
    for script in SERVICIOS:
        print(f"🚀 Lanzando {script}...")
        p = subprocess.Popen([VENV_PATH, script])
        procesos.append(p)

    print("✅ Todos los servicios están corriendo. Ctrl+C para detener.")

    # Esperar a que todos terminen (bloquea aquí)
    for p in procesos:
        p.wait()

except KeyboardInterrupt:
    print("\n🛑 Interrupción detectada. Cerrando servicios...")
    for p in procesos:
        p.terminate()
