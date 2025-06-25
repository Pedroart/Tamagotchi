#!/bin/bash

SESSION_SERVICIOS="asistente"
SESSION_INTERFAZ="interfaz"
VENV="./.venv/bin/python"

declare -a SCRIPTS=(
  "stt/serviceStt.py"
  "tts/serviceTTS_piper.py"
  "llm/serviceLLM.py"
)

INTERFAZ_SCRIPT="interfaz/test.py"

# 🧹 Cierra sesiones previas si existen
tmux has-session -t $SESSION_SERVICIOS 2>/dev/null && tmux kill-session -t $SESSION_SERVICIOS
tmux has-session -t $SESSION_INTERFAZ 2>/dev/null && tmux kill-session -t $SESSION_INTERFAZ

# 🪟 Crea nueva sesión con una sola ventana
echo "🧩 Creando sesión '$SESSION_SERVICIOS' con servicios en paneles..."
tmux new-session -d -s $SESSION_SERVICIOS -n servicios "$VENV ${SCRIPTS[0]}"

# 👉 Divide en paneles verticales por cada servicio extra
for i in "${!SCRIPTS[@]}"; do
  if [ $i -gt 0 ]; then
    tmux split-window -v -t $SESSION_SERVICIOS:servicios "$VENV ${SCRIPTS[$i]}"
    tmux select-layout -t $SESSION_SERVICIOS:servicios tiled
  fi
done

# 🖥️ Inicia sesión de interfaz por separado
echo "🖥️ Creando sesión '$SESSION_INTERFAZ' para la interfaz..."
tmux new-session -d -s $SESSION_INTERFAZ "$VENV $INTERFAZ_SCRIPT"

# 👉 Adjunta solo la interfaz
tmux attach -t $SESSION_INTERFAZ
