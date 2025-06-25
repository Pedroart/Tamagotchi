#!/bin/bash

for sesion in asistente interfaz; do
  if tmux has-session -t $sesion 2>/dev/null; then
    echo "🛑 Cerrando sesión: $sesion"
    tmux kill-session -t $sesion
  else
    echo "ℹ️ No hay sesión '$sesion' activa."
  fi
done
