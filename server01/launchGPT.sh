#!/bin/bash

SESSION_NAME="asistente"
VENV="./.venv/bin/python"

# Define scripts por orden
SCRIPTS_SERVICIOS=(
  "stt/serviceStt.py"
  "tts/serviceTTS_piper2.py"
  "llm/serviceLLMGPT.py"
)

SCRIPT_UI="interfaz/test.py"

# 🧹 Eliminar sesión si ya existe
tmux has-session -t $SESSION_NAME 2>/dev/null && {
  echo "🛑 Cerrando sesión anterior: $SESSION_NAME"
  tmux kill-session -t $SESSION_NAME
}

echo "🧩 Creando sesión '$SESSION_NAME' con layout servicios + interfaz..."

# Crear nueva sesión con el primer servicio (panel 0)
tmux new-session -d -s $SESSION_NAME -n main "$VENV ${SCRIPTS_SERVICIOS[0]}"

# Dividir verticalmente dos columnas: izquierda (servicios), derecha (interfaz)
tmux split-window -h -t $SESSION_NAME:0

# En el panel izquierdo (0), dividir en 3 filas para STT, TTS, LLM
tmux split-window -v -t $SESSION_NAME:0.0
tmux split-window -v -t $SESSION_NAME:0.0

# Asignar los servicios a los paneles izquierdos
tmux send-keys -t $SESSION_NAME:0.0 "$VENV ${SCRIPTS_SERVICIOS[0]}" C-m
tmux send-keys -t $SESSION_NAME:0.1 "$VENV ${SCRIPTS_SERVICIOS[1]}" C-m
tmux send-keys -t $SESSION_NAME:0.2 "$VENV ${SCRIPTS_SERVICIOS[2]}" C-m

# Ejecutar UI en el panel derecho (panel 1)
tmux send-keys -t $SESSION_NAME:0.3 "$VENV $SCRIPT_UI" C-m

# 👉 Mostrar tmux
tmux select-pane -t $SESSION_NAME:0.3
tmux attach-session -t $SESSION_NAME
