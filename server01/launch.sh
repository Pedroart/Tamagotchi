#!/bin/bash

SESSION_SERVICIOS="asistente"
SESSION_INTERFAZ="interfaz"
VENV="./.venv/bin/python"

declare -A SCRIPTS=(
  ["STT"]="stt/serviceStt.py"
  ["TTS"]="tts/serviceTTS_piper.py"
  ["LLM"]="llm/serviceLLM.py"
)

INTERFAZ_SCRIPT="interfaz/test.py"

# 🧹 Eliminar sesiones si ya existen
tmux has-session -t $SESSION_SERVICIOS 2>/dev/null && {
  echo "🛑 Cerrando sesión anterior: $SESSION_SERVICIOS"
  tmux kill-session -t $SESSION_SERVICIOS
}

tmux has-session -t $SESSION_INTERFAZ 2>/dev/null && {
  echo "🛑 Cerrando sesión anterior: $SESSION_INTERFAZ"
  tmux kill-session -t $SESSION_INTERFAZ
}

# 🚀 Crear nueva sesión para servicios en segundo plano
echo "🧩 Creando sesión '$SESSION_SERVICIOS' con servicios..."
tmux new-session -d -s $SESSION_SERVICIOS

for nombre in "${!SCRIPTS[@]}"; do
  SCRIPT=${SCRIPTS[$nombre]}
  echo "  ➕ $nombre -> $SCRIPT"
  tmux new-window -t $SESSION_SERVICIOS -n $nombre "$VENV $SCRIPT"
done

# 🚀 Crear sesión aparte para la interfaz
echo "🖥️  Creando sesión '$SESSION_INTERFAZ' para la interfaz..."
tmux new-session -d -s $SESSION_INTERFAZ "$VENV $INTERFAZ_SCRIPT"

# 👉 Mostrar solo la interfaz
tmux attach-session -t $SESSION_INTERFAZ
