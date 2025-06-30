#!/bin/bash

SESSION_NAME="asistente"
VENV="./.venv/bin/python"

declare -A SCRIPTS=(
  ["STT"]="stt/serviceStt.py"
  ["TTS"]="tts/serviceTTS_piper.py"
  ["LLM"]="llm/serviceLLM.py"
  ["UI"]="interfaz/test.py"
)

# 🧹 Eliminar sesión si ya existe
tmux has-session -t $SESSION_NAME 2>/dev/null && {
  echo "🛑 Cerrando sesión anterior: $SESSION_NAME"
  tmux kill-session -t $SESSION_NAME
}

echo "🧩 Creando sesión '$SESSION_NAME' con paneles 2x2..."

# Crear nueva sesión con el primer script
FIRST_KEY="${!SCRIPTS[@]}"  # primer key del array
FIRST_SCRIPT=${SCRIPTS[$FIRST_KEY]}
tmux new-session -d -s $SESSION_NAME -n main "$VENV $FIRST_SCRIPT"

# Dividir en 4 paneles
tmux split-window -h -t $SESSION_NAME:0         # Panel derecho
tmux split-window -v -t $SESSION_NAME:0.0       # Panel abajo izquierdo
tmux split-window -v -t $SESSION_NAME:0.1       # Panel abajo derecho

# Ejecutar scripts en cada panel
INDEX=0
for nombre in "${!SCRIPTS[@]}"; do
  SCRIPT=${SCRIPTS[$nombre]}
  echo "  ➕ Ejecutando $nombre -> $SCRIPT"
  tmux send-keys -t "$SESSION_NAME:0.$INDEX" "$VENV $SCRIPT" C-m
  ((INDEX++))
done

# Mostrar tmux
tmux attach-session -t $SESSION_NAME
