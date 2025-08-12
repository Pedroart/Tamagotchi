# services/solucion_service.py
from __future__ import annotations
import os, asyncio, re
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, List, Dict, Any, Tuple

from dotenv import load_dotenv

# EventBus (soporta ambos layouts)
try:
    from utils.EventBus import event_bus
except Exception:
    from event_bus import event_bus

# Constantes de tu STT
try:
    from utils.const import SERVICE_NAME_STT
except Exception:
    SERVICE_NAME_STT = "STT"

# LLMs (OpenAI primero; Ollama fallback)
try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

try:
    from langchain_ollama import ChatOllama as OllamaChat
except Exception:
    try:
        from langchain_community.chat_models import ChatOllama as OllamaChat
    except Exception:
        OllamaChat = None


class SolucionService:
    """
    Servicio conversacional + controlador de movimiento:
    - Escucha STT parciales/finales.
    - Emite backchannel (palabras cortas) con throttling.
    - Genera respuesta final (LLM) si aplica.
    - CONTROL DE MOVIMIENTO: parsea "X, Y" y navega con pasos ai.step.
    - Sincroniza posición con player.spawned / player.reached.
    - Estados TTS via speech.state para no solapar voz.

    independence (modo):
      0 = mute          (no habla)
      1 = backchannel   (palabra breve ocasional)
      2 = assistant     (habla respuesta final)
      3 = autonomous    (assistant + entiende órdenes y se mueve)
    """

    ALLOWED_BACKCHANNEL = ["Claro", "Bien", "Ok", "Vale", "Entiendo", "Perfecto", "Correcto"]

    # ---------- Init ----------
    def __init__(
        self,
        independence: int = 3,
        comment_interval_sec: float = 3.0,
        barge_in: bool = False,
        map_w: int = 5,
        map_h: int = 5,
        step_cooldown: float = 0.14,
    ):
        # Conversación
        self.independence = int(independence)
        self.comment_interval = timedelta(seconds=comment_interval_sec)
        self.barge_in = bool(barge_in)
        self.conversation_history: List[Dict[str, str]] = []
        self.ultimo_fragmento: str = ""
        self.ultimo_comentario: str = "ninguna"
        self.last_comment_time: datetime = datetime.min

        # TTS
        self._speaking = False

        # Mundo / navegación
        self.map_w = int(map_w)
        self.map_h = int(map_h)
        self.pos: Tuple[int,int] = (0, 0)   # posición conocida (sincroniza con player.spawned)
        self.goal: Optional[Tuple[int,int]] = None
        self.step_q: deque[Dict[str,Any]] = deque()
        self.busy: bool = False
        self._cooldown = float(step_cooldown)
        self._t_last = 0.0

        # LLMs
        self.llm_openai = None
        self.llm_ollama = None
        self.llm = None
        self._llm_lock = asyncio.Lock()
        self._init_llms()

        # Suscripciones (STT / voz / juego)
        event_bus.subscribe(SERVICE_NAME_STT + "_PARCIAL", self._on_stt_partial)
        event_bus.subscribe(SERVICE_NAME_STT + "_FINAL",   self._on_stt_final)
        event_bus.subscribe("speech.state",                self._on_speech_state)

        event_bus.subscribe("player.spawned",              self._on_player_spawn)
        event_bus.subscribe("player.move_start",           self._on_move_start)
        event_bus.subscribe("player.reached",              self._on_player_reached)
        event_bus.subscribe("world.tick",                  self._on_tick)

        # Control externo del modo
        event_bus.subscribe("solucion.set_mode",           self._on_set_mode)
        event_bus.subscribe("solucion.shutup",             self._on_shutup)

    # ---------- LLM ----------
    def _init_llms(self):
        load_dotenv()
        key = os.getenv("OPENAI_API_KEY")
        if ChatOpenAI and key:
            self.llm_openai = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=160,
                timeout=8,
                max_retries=1,
                api_key=key,
            )
            self.llm = self.llm_openai
        if (self.llm is None) and OllamaChat:
            self.llm_ollama = OllamaChat(
                model="gemma:2b",
                temperature=0.3,
                model_kwargs={
                    "num_thread": max(1, os.cpu_count() or 1),
                    "top_p": 1.0,
                    "num_ctx": 512,
                    "num_predict": 128,
                }
            )
            self.llm = self.llm_ollama

    async def _ainvoke(self, messages: List[Dict[str, str]]) -> Optional[str]:
        if not self.llm:
            return None
        async with self._llm_lock:
            try:
                resp = await self.llm.ainvoke(messages)
                return getattr(resp, "content", None)
            except Exception:
                if self.llm is self.llm_openai and self.llm_ollama:
                    self.llm = self.llm_ollama
                    try:
                        resp = await self.llm.ainvoke(messages)
                        return getattr(resp, "content", None)
                    except Exception:
                        return None
                return None

    # ---------- Eventos de voz / STT ----------
    def _on_speech_state(self, *, state: str):
        st = (state or "").lower()
        self._speaking = (st == "speaking")

    async def _on_stt_partial(self, texto: str):
        if not texto:
            return
        self.ultimo_fragmento = texto

        if self.independence == 0:
            return

        now = datetime.now()
        if self.independence >= 1 and (now - self.last_comment_time) > self.comment_interval:
            if self.barge_in or not self._speaking:
                palabra = self._pick_backchannel()
                if palabra:
                    self.last_comment_time = now
                    event_bus.emit("SOLUCION/FINAL", palabra)  # TTS la dirá

    async def _on_stt_final(self, texto: str):
        if not texto:
            return

        # Intento rápido: coordenadas → navega
        goal = self._extract_goal(texto)
        if goal and self.independence >= 3:
            c, r = self._clamp_goal(goal)
            self.set_goal(c, r)
            event_bus.emit("ai.goal", col=c, row=r)
            if self.independence >= 2:
                event_bus.emit("SOLUCION/FINAL", f"Voy hacia ({c},{r}).")
            self.ultimo_fragmento = ""
            return

        # Si no hay orden de movimiento, genera respuesta (assistant)
        if self.independence >= 2:
            if self._speaking and not self.barge_in:
                await asyncio.sleep(0.35)
            resp = await self._generar_respuesta(texto)
            if resp:
                event_bus.emit("SOLUCION/FINAL", resp)

        self.ultimo_fragmento = ""

    # ---------- Mundo / Juego ----------
    def _on_player_spawn(self, *, col: int, row: int):
        self.pos = (int(col), int(row))

    def _on_move_start(self, **_):
        self.busy = True

    def _on_player_reached(self, *, col: int, row: int):
        self.busy = False
        self.pos = (int(col), int(row))
        if self.goal == self.pos:
            event_bus.emit("SOLUCION/FINAL", f"Llegué a {self.goal}.")
            self.goal = None

    def _on_tick(self, dt: float, t: float):
        # Ejecuta un paso de la cola cada cooldown
        self._t_last += dt
        if self.step_q and self._t_last >= self._cooldown:
            self._t_last = 0.0
            self._exec_one(self.step_q.popleft())
            return

        # Si no estoy ocupado ni tengo cola y tengo meta → planear un paso
        if not self.busy and not self.step_q and self.goal:
            self._plan_one_step_towards(self.goal)

    # ---------- Planner ----------
    def set_goal(self, col: int, row: int):
        self.goal = (col, row)

    def _clamp_goal(self, goal: Tuple[int,int]) -> Tuple[int,int]:
        c = max(0, min(self.map_w - 1, int(goal[0])))
        r = max(0, min(self.map_h - 1, int(goal[1])))
        return (c, r)

    def _plan_one_step_towards(self, goal: Tuple[int,int]):
        cx, cy = self.pos
        gx, gy = goal
        if (cx, cy) == (gx, gy):
            self.goal = None
            return
        if gx != cx:
            dc = 1 if gx > cx else -1
            self._enqueue_face("right" if dc > 0 else "left")
            self._enqueue_step(dc, 0)
        elif gy != cy:
            dr = 1 if gy > cy else -1
            self._enqueue_face("down" if dr > 0 else "up")
            self._enqueue_step(0, dr)

    def _enqueue_face(self, d: str):
        self.step_q.append({"action": "face", "dir": d})

    def _enqueue_step(self, dc: int, dr: int):
        self.step_q.append({"action": "step", "dc": dc, "dr": dr})

    def _exec_one(self, step: Dict[str,Any]):
        a = step.get("action")
        if a == "face":
            event_bus.emit("player.face", direction=step.get("dir", "down"))
        elif a == "step":
            event_bus.emit("ai.step", dc=step.get("dc", 0), dr=step.get("dr", 0))

    # ---------- Utilidades conversación ----------
    def _pick_backchannel(self) -> Optional[str]:
        for w in self.ALLOWED_BACKCHANNEL:
            if w != self.ultimo_comentario:
                self.ultimo_comentario = w
                return w
        self.ultimo_comentario = self.ALLOWED_BACKCHANNEL[0]
        return self.ultimo_comentario

    def _extract_goal(self, texto: str) -> Optional[Tuple[int,int]]:
        """
        Reconoce patrones tipo:
          "ve al 2, 3", "ir a 1,4", "muévete 0,0", "2, 2"
        """
        if not texto:
            return None
        t = texto.lower()
        m = re.search(r"(?:ve|ir|anda|camina|muevete|muévete)?\s*(?:a|al|hacia)?\s*(\d+)\s*,\s*(\d+)", t)
        if not m:
            return None
        return (int(m.group(1)), int(m.group(2)))

    async def _generar_respuesta(self, texto: str) -> str:
        sys = (
            "Eres un asistente conversacional amable y natural. "
            "Responde de forma clara y concisa, con tono humano. "
            "No repitas saludos ni lo ya dicho. "
            "Si hay instrucciones para moverse en una grilla, "
            "mantén el formato numérico 'X, Y' tal cual."
        )
        msgs = [{"role": "system", "content": sys}]
        msgs.extend(self.conversation_history[-6:])
        msgs.append({"role": "user", "content": texto})

        out = await self._ainvoke(msgs)
        if not out:
            return "(sin respuesta)"

        respuesta = out.strip()
        self.conversation_history.append({"role": "user", "content": texto})
        self.conversation_history.append({"role": "assistant", "content": respuesta})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        return respuesta

    # ---------- Control externo ----------
    def _on_set_mode(self, *, mode: int = None):
        if mode is None:
            return
        self.independence = max(0, min(3, int(mode)))
        event_bus.emit("solucion.mode", mode=self.independence)

    def _on_shutup(self, **_):
        # Si tu TTS expone 'stop', puedes emitirlo aquí:
        # event_bus.emit("tts.stop")
        pass
