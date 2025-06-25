#!/bin/bash

SESSION_NAME="asistente"
VENV="./.venv/bin/python"

declare -A SCRIPTS=(
  ["STT"]="stt/serviceStt.py"
  ["TTS"]="tts/serviceTTS_piper.py"
  ["LLM"]="llm/serviceLLM.py"
  ["INTERFAZ"]="interfaz/test.py"
)

# 🧹 Limpia sesión previa si existe
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? -eq 0 ]; then
  echo "🔁 Cerrando sesión previa de tmux..."
  tmux kill-session -t $SESSION_NAME
fi

echo "🚀 Creando sesión nueva: $SESSION_NAME"
tmux new-session -d -s $SESSION_NAME

# 🪄 Lanza cada script en una ventana separada
for nombre in "${!SCRIPTS[@]}"; do
  SCRIPT=${SCRIPTS[$nombre]}
  echo "  🧩 Añadiendo $nombre: $SCRIPT"
  tmux new-window -t $SESSION_NAME -n $nombre "$VENV $SCRIPT"
done

# 🪟 Cierra todas las ventanas excepto INTERFAZ
for nombre in "${!SCRIPTS[@]}"; do
  if [ "$nombre" != "INTERFAZ" ]; then
    tmux send-keys -t $SESSION_NAME:$nombre "clear" C-m
  fi
done

# 🖥️ Adjunta solo la vista de interfaz
tmux select-window -t $SESSION_NAME:INTERFAZ
tmux attach-session -t $SESSION_NAME
