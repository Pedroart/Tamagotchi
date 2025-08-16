from queue import SimpleQueue
from dataclasses import dataclass

try:
    import sounddevice as sd
    HAS_SD = True
except Exception:
    HAS_SD = False

from piper.voice import PiperVoice

from config import *
from event_bus import event_bus
from logger import logger

@dataclass
class Oracione:
    texto: str
    expresion: str

@dataclass
class VoiceState:
    speak: bool

class VoicePlater:
    '''
    Controla la reproduccion de audio y el envio de animaciones hacia el canvas

    Se debe enviar las horaciones con la expresion que se espera que tenga

    <Saludo, unitaria> Hola! </saludo>, <hablando, loop>como estas <hablando> <sorpresa> #NADA#(1segundo) </sorpresa>
    
    '''

    def __init__(self):
        
        self._cmd_queue: "SimpleQueue[Tuple[str, tuple, dict]]" = SimpleQueue()
        
