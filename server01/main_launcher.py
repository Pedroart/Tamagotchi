import subprocess
import os

# Ruta base del entorno virtual
VENV_PATH = os.path.join(os.getcwd(), ".venv", "bin", "python")

# Servicios a lanzar
SERVICIOS = [
    "stt/serviceStt.py",
    "tts/serviceTTS_piper.py",
    "llm/serviceLLM.py",
    "interfaz/test.py",
    # "ui_chat.py",  # descomenta si tienes UI
]

procesos = []

try:
    for script in SERVICIOS:
        print(f"🚀 Lanzando {script}...")
        if "interfaz" in script:
            p = subprocess.run([VENV_PATH, script])  # permite stdout/stderr
        else:
            p = subprocess.Popen([VENV_PATH, script],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)

    print("✅ Todos los servicios están corriendo. Ctrl+C para detener.")

except KeyboardInterrupt:
    print("\n🛑 Interrupción detectada. Cerrando servicios...")
    for p in procesos:
        p.terminate()

