import json, re, csv, threading, random
from pathlib import Path
from time import perf_counter
from typing import Tuple, List, Dict
from queue import SimpleQueue, Empty

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.base import BaseCallbackHandler

import emociones
from config import *
from event_bus import event_bus
from logger import logger

class StopStreaming(Exception):
    """Corte intencional del streaming (stop cooperativo)."""
    pass

class Nucleo:
    def __init__(
        self,
        openai_model: str = "gpt-4.1",
        temperature: float = 0.0,
    ):
        if not API_KEY_OPENAI:
            raise RuntimeError("Falta OPENAI_API_KEY en el entorno.")

        self.llm = ChatOpenAI(
            model=openai_model,
            temperature=temperature,
            api_key=API_KEY_OPENAI,
            streaming=True,
        )

        random.seed(7)  # reproducibilidad del ruido

        # === Config emocional (si la usas para otros módulos) ===
        self.cfg = emociones.PADConfig(
            alpha=0.45, decay=0.04, ema=0.25,
            noise_std=0.025, noise_enabled=True,
            min_D=-0.2, max_D=0.5,
            min_A=-0.3, max_A=0.8
        )
        self.base = emociones.Baseline(P0=0.1, A0=-0.05, D0=0.0, gain_P=1.0, gain_A=0.9, gain_D=0.8)

        # === Estado de generación ===
        self._cancel_stream = threading.Event()
        self._stream_lock = threading.Lock()  # evita streams simultáneos

        self.buffer = ""
        self.respuesta_parcial = ""
        self.respuesta_final = ""

        self.preliminar_historial: List[str] = []
        self.historial: List[Dict[str, str]] = []  # {"tipo": "usuario"|"asistente", "texto": str}

        # Suscripción a eventos STT
        event_bus.subscribe("stt.partial", self._handle_partial)
        event_bus.subscribe("stt.final", self._handle_final)

    # ===================== Event Handlers =====================

    def _handle_partial(self, texto: str):
        """
        Recibe fragmentos mientras el usuario habla.
        Genera una reacción breve preliminar (escucha activa).
        """
        # Cancelar cualquier stream preliminar anterior para no superponer
        self.stop_current_generation()
        self.preliminar_historial.append(texto)
        self.generar_respuesta(texto, preliminar=True)

    def _handle_final(self, texto: str):
        """
        Al finalizar la frase del usuario:
          - Cancela generación en curso y emite la preliminar (si existe).
          - Genera respuesta final coherente con el contexto.
          - Publica la final para síntesis/reproducción.
          - Actualiza histórico y limpia parciales.
        """
        # 1) Corta el stream actual y emite la parcial acumulada (si hay)
        self.stop_current_generation()
        if self.respuesta_parcial.strip():
            event_bus.emit("answer.generate", ("feliz", 1), self.respuesta_parcial)

        # 2) Genera respuesta final
        self.generar_respuesta(texto, preliminar=False)

        # 3) Publica final
        if self.respuesta_final.strip():
            logger.info(f"Generacion de respuesta final: {self.respuesta_final}")
            event_bus.emit("answer.generate", ("feliz", 1), self.respuesta_final)

        # 4) Actualiza historial (usuario + asistente)
        if texto.strip():
            self.historial.append({"tipo": "usuario", "texto": texto})
        if self.respuesta_final.strip():
            self.historial.append({"tipo": "asistente", "texto": self.respuesta_final})

        # 5) Limpia parciales y buffers
        self.preliminar_historial.clear()
        self.respuesta_parcial = ""
        self.buffer = ""

    # ===================== Core LLM =====================

    def generar_respuesta(self, texto: str, preliminar: bool = False):
        """
        Lanza un stream de LLM. Si 'preliminar' es True, produce una respuesta
        corta de escucha activa. Si es False, produce la respuesta final.
        """
        # Garantiza exclusión mutua: un stream a la vez
        if not self._stream_lock.acquire(blocking=False):
            # Ya hay un stream corriendo: lo cancelamos y seguimos
            self.stop_current_generation()
            self._stream_lock.acquire()

        try:
            # Prepara prompts
            sys_prompt = (
                "Eres un asistente conversacional amable y natural. "
                "Mantén un tono humano, breve y claro. "
                "Recuerda el contexto de la conversación previa y responde coherentemente."
            )

            if preliminar:
                sys_prompt += (
                    " El usuario aún está hablando. Responde con una sola frase breve "
                    "(máximo 12 palabras), de escucha activa/seguimiento. "
                    "No cierres el tema, no des conclusiones, no hagas listas, "
                    "no saludes ni te despidas, no repitas texto del usuario."
                )
                fragmentos_previos = "\n".join(f"- {frag}" for frag in self.preliminar_historial[-6:])
                hum_prompt = (
                    f"Fragmento actual del usuario: {texto}\n"
                    f"Fragmentos previos recientes del usuario:\n{fragmentos_previos}\n"
                    "Tu salida debe ser UNA sola oración corta que habilite continuar."
                )
            else:
                sys_prompt += (
                    " El usuario ha terminado de exponer su idea. "
                    "Responde directamente al tema, con detalle suficiente para ayudar, "
                    "sin repetir la frase preliminar ni saludar de nuevo. "
                    "Continúa el hilo de manera natural y concreta."
                )
                contexto_hist = "\n".join(f"- {h['tipo']}: {h['texto']}" for h in self.historial[-6:])
                hum_prompt = (
                    f"Transcripción final del usuario (puede contener errores): {texto}\n"
                    f"Frase preliminar que ya se emitió: {self.respuesta_parcial}\n"
                    f"Contexto reciente de la conversación:\n{contexto_hist}\n"
                    "No repitas la preliminar; si es útil, retómala implícitamente y avanza."
                )
            # Resetea estado de cancelación y buffer
            self._cancel_stream.clear()
            self.buffer = ""

            # Inicia streaming con mensajes tipados
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=hum_prompt),
            ]

            for chunk in self.llm.stream(messages):
                # chunk suele ser un AIMessageChunk; tomamos su .content seguro
                token = getattr(chunk, "content", "") or ""
                self.on_llm_new_token(token)

            # Cierre: transfiere buffer a parcial/final
            if preliminar:
                self.respuesta_parcial = self.buffer.strip()
            else:
                self.respuesta_final = self.buffer.strip()

        except StopStreaming:
            logger.info("Streaming cortado intencionalmente (StopStreaming).")
            # No propagamos; simplemente salimos
        except Exception as ex:
            logger.exception(f"Error en generar_respuesta (preliminar={preliminar}): {ex}")
        finally:
            self._stream_lock.release()

    def on_llm_new_token(self, token: str, **kwargs):
        """
        Callback por token. Si se solicitó cancelación, aborta cooperativamente.
        """
        if self._cancel_stream.is_set():
            # Señal a lazo superior de cortar
            raise StopStreaming
        self.buffer += token

    # ===================== Control Público =====================

    def stop_current_generation(self):
        """
        Señala que cualquier stream activo debe detenerse ASAP.
        No bloquea; el corte es cooperativo.
        """
        self._cancel_stream.set()
