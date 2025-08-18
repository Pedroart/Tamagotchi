import json, re, csv, threading
from pathlib import Path
from time import perf_counter
from typing import Tuple, List, Dict
from queue import SimpleQueue, Empty

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.base import BaseCallbackHandler

from config import *
from event_bus import event_bus
from logger import logger


def split_text(texto: str):
    partes = re.split(r'(?<=[.!?,;:])\s+', texto)
    return [p.strip() for p in partes if p.strip()]

class StopStreaming(Exception):
    """Corte intencional del streaming (stop cooperativo)."""
    pass

class Answer:
    
    def __init__(
        self,
        base_dir: Path = None,
        assets_dir: str = "assets",
        csv_name: str = "anims.csv",
        openai_model: str = "gpt-4.1",
        temperature: float = 0.0,
    ):
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.assets_dir = assets_dir
        self.csv_name = csv_name
        self.animaciones = []
        self.inventory = ""
        self.buffer = ""
        self.scan_pos = 0
        self._resultados: List[Dict] = []
        self._oraciones_queue: "SimpleQueue[Tuple[str, Tuple[str, float]]]" = SimpleQueue()
        self._running = False
        self._cancel_stream = threading.Event()
        
        if not API_KEY_OPENAI:
            raise RuntimeError("Falta OPENAI_API_KEY en el entorno.")

        self.llm = ChatOpenAI(
            model=openai_model,
            temperature=temperature,
            api_key=API_KEY_OPENAI,
            streaming=True,
            
        )

        event_bus.subscribe("answer.generate", self.speak_calback)
        event_bus.subscribe("answer.stop", self._stop_now)

        self._load_emociones()

    # ----------------- Infra -----------------
    def _load_csv(self):
        csvp = (self.base_dir / self.assets_dir / self.csv_name).resolve()
        defs = []
        if not csvp.exists():
            return defs
        with open(csvp, newline="", encoding="utf-8") as f:
            for name, _, _, descripcion in csv.reader(f):
                defs.append((name, descripcion))
        return defs

    def _load_emociones(self):
        self.animaciones = self._load_csv()
        self.inventory = "\n".join(f"- {name}: {desc}" for name, desc in self.animaciones)

    # ----------------- Salida: emitir a voice -----------------
    def _speak(self, texto: str = "", expresion: str = "", modo: str = ""):
        """
        Emite un evento para que el subsistema de voz reproduzca y sincronice animaciones.
        Suscríbete en tu VoicePlayer con:
            unsub = event_bus.subscribe("voice.speak", handler)
        """
        event_bus.emit("voice.speak", texto=texto, expresion=expresion, modo=modo)

    # ----------------- Entrada pública -----------------
    def speak_calback(self,emocion: Tuple[str, float], texto: str):
        self._oraciones_queue.put((texto,emocion))

    def speak(self, emocion: Tuple[str, float], texto: str, use_split: bool = True) -> List[Dict]:
        """
        Entrada principal. Genera en streaming y emite cada item a 'voice.speak'.
        Retorna la lista agregada de items generados por si quieres loguearlos o testear.
        """
        # reset de resultados por invocación
        self._resultados = []
        self.buffer = ""
        self.scan_pos = 0
        nombre_emocion, intensidad = emocion
        sys_prompt = (
            "Eres un selector de animaciones para un personaje 2D.\n"
            "Entrada: una o más frases, el NOMBRE de la emoción dominante y su INTENSIDAD en [0,1].\n"
            "Tareas:\n"
            "1) Para cada frase elige EXACTAMENTE una animación del INVENTARIO.\n"
            "2) Decide el MODO entre 'once' o 'loop'.\n"
            "3) Usa la emoción (nombre) e INTENSIDAD como regla principal:\n"
            "   - Intensidad alta (>=0.70): gestos más marcados, prioridad a animaciones enfáticas o puntuales; favorece 'once' en interjecciones/sorpresas.\n"
            "   - Intensidad media (0.40–0.69): alterna entre 'once' y 'loop' según la longitud/fluidez de la frase.\n"
            "   - Intensidad baja (<0.40): gestos suaves, favorece 'loop' en discurso corrido.\n"
            "4) NO uses siempre la animación 'hablar'; incorpora variedad coherente con el INVENTARIO.\n"
            "5) Coincidencia EXACTA con el nombre de la animación del INVENTARIO es obligatoria.\n"
            "6) Salida: SOLO JSON como lista de objetos {\"texto\",\"expresion\",\"modo\"} (sin comentarios ni texto extra).\n"
            "7) Si la frase es una exclamación corta (p.ej. '¡Vaya!'/'¡Wow!'), prefiere una animación puntual con 'once'.\n"
            "8) Mantén el texto de cada objeto exactamente igual a la frase asignada (o su segmento literal).\n"
            "Ejemplo de salida: [{\"texto\":\"Hola\",\"expresion\":\"saludo\",\"modo\":\"once\"}]\n"
        )
        if use_split:
            fragmentos = split_text(texto)
            texto_prompt = "\n".join(f"- {frag}" for frag in fragmentos)
        else:
            texto_prompt = texto

        hum_prompt = (
            f"Emoción: {nombre_emocion}\n"
            f"Intensidad: {intensidad:.2f}\n"
            f"Texto:\n{texto_prompt}\n\n"
            "Inventario:\n"
            f"{self.inventory}\n\n"
            "Solo JSON."
        )

        t0 = perf_counter()
        '''
        try:
            _ = self.llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=hum_prompt),
            ])
        except StopStreaming:
            logger.info("Streaming cortado intencionalmente (StopStreaming).")
            return None
        except Exception as ex:
            logger.warning(f"LLM error inesperado: {ex}")
            return None
        '''

        try:
            for chunk in self.llm.stream([sys_prompt, hum_prompt]):
                token = getattr(chunk, "content", "") or ""
                self.on_llm_new_token(token)
        except StopStreaming:
            self._stop_worker()
            logger.info("Streaming cortado intencionalmente (StopStreaming).")
            return None
            
        t1 = perf_counter()
        logger.info(f"Tiempo total request: {t1 - t0:.2f}s")

    def on_llm_new_token(self, token: str, **kwargs):
        
        if self._cancel_stream.is_set():
            logger.info("AnswerPlayer detenido")
            raise StopStreaming
            
        self.buffer += token
        final = self.buffer.find("}", self.scan_pos)
        
        if final != -1:
            inicio = self.buffer.find("{", self.scan_pos)
            self.scan_pos = final+1
            self._emit_obj(self.buffer[inicio:final+1])

    def _emit_obj(self,s:str):
        try: 
            item = json.loads(s)
            t = (item.get("texto") or "").strip()
            e = (item.get("expresion") or "hablar").strip()
            m = (item.get("modo") or "once").strip()

            if t:
                self._speak(texto=t, expresion=e, modo=m)
                logger.info("answer.new_token")
                                  
        except Exception as ex:
            logger.info("Objeto Json no procesable")

    def run(self):
        logger.info("AnswerPlayer iniciado.")

        self._running = True

        try:
            
            while self._running:

                try:
                    texto,emocion = self._oraciones_queue.get(timeout=0.1)
                except Empty:
                    continue

                self.speak(emocion,texto)
                    
        except KeyboardInterrupt:
            logger.info("Interrupcion por teclado")
        finally:
            logger.info("AnswerPlayer finalizado.")

    def close(self):
        self._running = False

    def _stop_now(self):
        self._running = False
        self._cancel_stream.set()

    def _stop_worker(self):
        logger.info("AnswerPlayer detenido")
        try:
            while True:
                self._oraciones_queue.get_nowait()
        except Empty:
            pass
        
        self._cancel_stream.clear()

        self._running = True

AP = Answer()

def _answer_worker():
    try:
        AP.run()
    finally:
        AP.close()

# === Ejemplo de uso ===
if __name__ == "__main__":
    # Ejemplo de suscriptor minimalista del lado de voz:
    def voice_handler(texto: str, expresion: str, modo: str):
        print(f"[voice.speak] ({expresion}, {modo}) -> {texto}")

    unsub = event_bus.subscribe("voice.speak", voice_handler)

    answer = Answer()
    pad = (-0.7, 0.9, -0.4)
    txt = "Me alegra que estés aquí. Quiero contarte algo importante que pasó ayer. ¡Vaya sorpresa!"
    items = answer.speak(pad, txt, use_split=True)

    print("\nRESULTADO FINAL:", items)
    unsub()
