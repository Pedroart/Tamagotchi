
# ai_agent.py
# Agente "autoconsciente" (ligero) basado en eventos, con estado interno y planificación sencilla.
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Any, Optional, Tuple
import time

from event_bus import event_bus

Action = Dict[str, Any]

@dataclass
class SelfModel:
    pos: Tuple[int,int] = (2,2)
    goal: Optional[Tuple[int,int]] = None
    intent: str = "idle"       # idle|navigate|rest|social|explore
    mood: float = 0.2          # -1..+1
    energy: float = 80.0       # 0..100
    social: float = 50.0       # 0..100
    heard_last: str = ""
    last_update: float = field(default_factory=time.time)

    def decay(self, dt: float):
        # Decaimiento leve con el tiempo
        self.energy = max(0.0, self.energy - 0.5*dt)       # energía baja lentamente
        self.social = max(0.0, self.social - 0.2*dt)
        # humor baja si energía muy baja
        if self.energy < 15:
            self.mood = max(-1.0, self.mood - 0.05*dt)
        else:
            self.mood = min( 1.0, self.mood + 0.02*dt)

class BollaAgent:
    """
    - Escucha eventos (ai.heard, player.reached, world.tick).
    - Mantiene un modelo interno (estado "autoconsciente": energía, humor, metas).
    - Genera un plan de acciones (cola) y lo ejecuta paso a paso en cada tick.
    """
    def __init__(self, map_w: int, map_h: int, step_cooldown: float = 0.16):
        self.map_w = map_w
        self.map_h = map_h
        self.model = SelfModel()
        self.queue: Deque[Action] = deque()
        self.cooldown = step_cooldown
        self._t_last = 0.0

        self.busy = False
        event_bus.subscribe("player.move_start", self._on_move_start)
        event_bus.subscribe("world.tick", self.on_tick)
        event_bus.subscribe("player.reached", self.on_reached)
        event_bus.subscribe("ai.heard", self.on_heard)

        # Estado inicial visible
        event_bus.emit("ai.state", state=self.model.intent)
        
    # ---------- Event handlers ----------
    def on_heard(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        self.model.heard_last = text
        # Interpretación súper simple (puedes reemplazar por LLM)
        if self._try_parse_go_to(text):
            return
        if any(k in text.lower() for k in ("hola", "saluda", "saludo")):
            self.say("¡Hola!")
            return
        if any(k in text.lower() for k in ("siéntate","sientate","descansa","rest")):
            self.rest_mode()
            return
        # Si no entendió, responde breve
        self.say("No entendí bien, ¿a dónde quieres que vaya?")

    def _on_move_start(self, **_):
        print("[Bolla] move_start")
        self.busy = True

    def on_reached(self, *, col: int, row: int):
        self.busy = False
        self.model.pos = (col, row)
        if self.model.goal == (col, row):
            self.say(f"Llegué a {self.model.goal}")
            self.model.goal = None
            self.set_intent("idle")

    def on_tick(self, dt: float, t: float):
        
        # Actualiza estado interno
        self.model.decay(dt)

        # Si energía muy baja, entra en modo descanso
        if self.model.energy < 10 and self.model.intent != "rest":
            self.rest_mode()

        # Ejecuta una acción de la cola si pasó el cooldown
        #print(self.queue)
        self._t_last += dt
        if self.queue and self._t_last >= self.cooldown:
            self._t_last = 0.0
            self._exec_one(self.queue.popleft())
            return  # una acción por tick es suficiente

        # Si no hay plan, decide algo según su "conciencia"
        if not self.queue and not self.busy:
            #print(self.model.intent)
            #print(f"[PLAN] pos={self.model.pos}")
            if self.model.intent == "navigate" and self.model.goal is not None:
                print(self.model.goal)
                self._plan_step_towards(self.model.goal)
            elif self.model.intent == "rest":
                # Si ya está sentado reproduciendo anim, subir energía pasivamente
                self.model.energy = min(100.0, self.model.energy + 2.0*dt)
                # Si recuperó suficiente, vuelve a idle
                if self.model.energy > 40:
                    self.say("¡Listo! Me siento con energía.")
                    self.set_intent("idle")
            elif self.model.intent in ("idle", "social"):
                # comportamiento social simple: a veces saluda
                if self.model.social < 25:
                    self.say("¿Hablamos?")
                    self.model.social = min(100.0, self.model.social + 10.0)
                else:
                    # explorar suavemente hacia el centro
                    #center = (self.map_w//2, self.map_h//2)
                    #self._plan_step_towards(center, cautious=True)
                    pass

    # ---------- Planning helpers ----------
    def _exec_one(self, step: Action):
        a = step.get("action")
        if a == "face":
            event_bus.emit("player.face", direction=step["dir"])
        elif a == "step":
            event_bus.emit("ai.step", dc=step.get("dc",0), dr=step.get("dr",0))
        elif a == "anim":
            event_bus.emit("anim.play", name=step["name"], fps=step.get("fps"), loop=step.get("loop", True), restart=True)
        elif a == "say":
            event_bus.emit("ai.say", text=step.get("text",""))
        elif a == "set_state":
            self.set_intent(step.get("name", "idle"))

    def _enqueue_face(self, dir: str):
        self.queue.append({"action":"face","dir":dir})

    def _enqueue_step(self, dc: int, dr: int, repeat: int = 1):
        for _ in range(max(1, int(repeat))):
            self.queue.append({"action":"step","dc":dc,"dr":dr})

    def _plan_step_towards(self, goal: Tuple[int,int], cautious: bool=False):
        cx, cy = self.model.pos
        gx, gy = goal

        #print(f"[PLAN] pos={self.model.pos} goal={goal}")
        if (cx, cy) == (gx, gy):
            self.set_intent("idle")
            return
        
        #print(f"[PLAN] pos={self.model.pos} goal={goal}")
        # Un paso por eje prioritario (col primero)
        if gx != cx:
            dc = 1 if gx > cx else -1
            self._enqueue_face("right" if dc>0 else "left")
            self._enqueue_step(dc, 0, repeat=1)
        elif gy != cy:
            dr = 1 if gy > cy else -1
            self._enqueue_face("down" if dr>0 else "up")
            self._enqueue_step(0, dr, repeat=1)

    # ---------- High-level intents ----------
    def set_intent(self, name: str):
        self.model.intent = name
        event_bus.emit("ai.state", state=name)

    def go_to(self, col: int, row: int):
        col = max(0, min(self.map_w-1, int(col)))
        row = max(0, min(self.map_h-1, int(row)))
        self.model.goal = (col, row)
        self.set_intent("navigate")

    def rest_mode(self):
        self.queue.clear()
        self.set_intent("rest")
        # mirar hacia abajo y sentarse (si existe anim)
        self._enqueue_face("down")
        self.queue.append({"action":"anim","name":"sit_down","fps":6,"loop":True})
        self.say("Voy a descansar un poco.")

    def say(self, text: str):
        event_bus.emit("ai.say", text=text)

    # ---------- Parsing simple de órdenes en lenguaje natural ----------
    def _try_parse_go_to(self, text: str) -> bool:
        import re
        m = re.search(r"(?:ve|ir|anda|camina)\s*(?:a|al|hacia)?\s*(\d)[,;\s]+(\d)", text, flags=re.I)
        if m:
            c = int(m.group(1)); r = int(m.group(2))
            self.go_to(c, r)
            self.say(f"Voy hacia ({c},{r}).")
            return True
        return False
