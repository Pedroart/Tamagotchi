# main.py
from canvas import SpritePlayer
from event_bus import event_bus
from voice import _voice_worker
import threading, time
from answer import _answer_worker

# Activa trazas opcionales
event_bus.enable_trace("sprite.play", "sprite.default", "sprite.get", "sprite.state")

player = SpritePlayer(
    assets_dir="assets",
    sheet_name="spritesheet.png",
    csv_name="anims.csv",
    default_anim="parado",  # opcional
    fps_anim=10,
)


threading.Thread(target=_answer_worker, daemon=True).start()

threading.Thread(target=_voice_worker, daemon=True).start()
# Lanza el reproductor (bloqueante; corre en el hilo principal)
# En otro hilo o callbacks puedes emitir eventos


def controller():
    pad = ("triste",1.2)
    texto = (
        "Hola a todos… qué bueno verlos, aunque confieso que no llego con mucho ánimo hoy. "
        "Sus rostros conocidos me traen un poco de calma, pero sigo sintiendo un peso difícil de soltar. "
        "Quisiera contarles lo que pasó, aunque prefiero hacerlo despacio, paso a paso, para no abrumarnos. "
        "Últimamente nada ha salido como esperábamos, y eso desgasta más de lo que imaginé. "
        "Me ilusionaba tanto con el prototipo, pero al verlo fallar una y otra vez se me fue apagando la emoción. "
        "Hace un momento volvió a aparecer una alerta en el monitor, y la verdad… me parte la tranquilidad que quedaba. "
        "Me preocupa ese aumento extraño de latencia; algo no encaja y temo que haya más problemas de fondo. "
        "Molesta pensar que lo advertimos antes, y aun así se pasó por alto el respaldo… es difícil no sentirse frustrado. "
        "Seguimos los pasos: registros, tráfico, chequeo de integridad… pero nada parece darnos una respuesta clara. "
        "Intentamos el failover y también falló… eso me duele, porque siento que todo el esfuerzo se nos escapa de las manos. "
        "Respiro hondo, aunque por dentro me pesa la idea de que la base pueda estar dañada. "
        "Aun así, trato de mantenerme en pie: quizá una verificación incremental nos devuelva un poco de esperanza. "
        "No lo sé… quiero creer que podremos restaurar la calma, pero hoy el ánimo me falta. "
        "Gracias por quedarse hasta el final; a veces, incluso en medio de la frustración, lo más valioso es no estar solo. "
        "Por ahora cierro este ciclo… me quedo quieto, intentando recuperar fuerzas, en silencio y con el corazón algo cansado."
    )
    event_bus.emit("answer.generate", pad, texto)
    time.sleep(3)
    
    event_bus.emit("answer.stop")
    event_bus.emit("voice.stop")

    event_bus.emit("answer.generate", pad, texto)
    time.sleep(3)
    
    event_bus.emit("answer.stop")
    event_bus.emit("voice.stop")
    #event_bus.emit("answer.generate", pad, texto)
    

threading.Thread(target=controller, daemon=True).start()
player.run()
