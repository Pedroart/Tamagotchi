#!/bin/bash

SESSION_NAME="asistente"

# Verificar si la sesión existe
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
  echo "🛑 Cerrando servicios en la sesión '$SESSION_NAME'..."

  # Enviar Ctrl+C a cada panel para terminar los procesos
  for i in 0 1 2 3; do
    echo "  ❌ Terminando panel $i..."
    tmux send-keys -t "$SESSION_NAME:0.$i" C-c
    sleep 0.5
  done

  # Cerrar la sesión completa
  echo "🧹 Matando la sesión completa..."
  tmux kill-session -t $SESSION_NAME

else
  echo "⚠️  No hay sesión activa llamada '$SESSION_NAME'."
fi
