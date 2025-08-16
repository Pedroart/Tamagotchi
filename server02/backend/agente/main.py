# main.py
from canvas import SpritePlayer
from event_bus import event_bus

# Activa trazas opcionales
event_bus.enable_trace("sprite.play", "sprite.default", "sprite.get", "sprite.state")

player = SpritePlayer(
    assets_dir="assets",
    sheet_name="spritesheet.png",
    csv_name="anims.csv",
    default_anim="parado",  # opcional
    fps_anim=10,
)

# Lanza el reproductor (bloqueante; corre en el hilo principal)
# En otro hilo o callbacks puedes emitir eventos
import threading, time
def controller():
    time.sleep(1.0)
    event_bus.emit("sprite.play", "hablar", "loop")
    time.sleep(2.0)
    event_bus.emit("sprite.play", "reir", "once")
    time.sleep(3.0)
    event_bus.emit("sprite.get")
    time.sleep(1.0)
    event_bus.emit("sprite.default")
    time.sleep(1.0)
    event_bus.emit("sprite.get")

threading.Thread(target=controller, daemon=True).start()
player.run()
