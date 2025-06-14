from camara import Camara
from microfono import Microfono
from interfaz import Interfaz
from agente import Agente
from gestor import Gestor
from event_bus import EventBus

bus = EventBus()
cam = Camara(bus)
mic = Microfono(bus)
ui = Interfaz(bus)
agente = Agente()
gestor = Gestor(bus, agente)

cam.start()
mic.start()
gestor.start()

try:
    ui.render_loop()
except KeyboardInterrupt:
    pass

cam.stop()
mic.stop()
gestor.stop()
ui.stop()
