
from agente.event_bus import event_bus
from agente.voice import _voice_worker
import threading, time, asyncio
from agente.answer import _answer_worker
from agente.microfono import _microfono_worker
from agente.nucleo import Nucleo
from agente.web_actions import start_ws_server

def _start_workers():
  threading.Thread(target=start_ws_server, daemon=True).start()
  threading.Thread(target=_answer_worker, daemon=True).start()
  threading.Thread(target=_voice_worker, daemon=True).start()
  threading.Thread(target=_microfono_worker, daemon=True).start()
  


def test_microfono_10s():
  print("🎤 Encendiendo microfono por 10s...")
  event_bus.emit("speak.flag")   # activa el micrófono

  time.sleep(10)

  print("🔇 Apagando microfono...")
  event_bus.emit("speak.flag")   # desactiva el micrófono

  # Opcional: hacer que la voz lea un mensaje de prueba
  event_bus.emit("voice.speak", "La prueba de micrófono ha terminado", "hablar", "normal")

  print("✅ Prueba completada")

if __name__ == "__main__":
  # Activa trazas opcionales ANTES de crear/usar el player
  event_bus.enable_trace("sprite.play", "sprite.default", "sprite.get", "sprite.state")

  nucleo = Nucleo()

  _start_workers()

  test_microfono_10s()

      # Mantener proceso vivo
  try:
      while True:
          time.sleep(1)
  except KeyboardInterrupt:
      print("👋 Saliendo por Ctrl+C")