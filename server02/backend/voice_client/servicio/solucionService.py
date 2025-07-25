import os
from dotenv import load_dotenv
from utils.EventBus import event_bus
from utils.const import SERVICE_NAME_STT
from langchain_openai import ChatOpenAI
import re
import time
from datetime import datetime, timedelta

class SolucionService:
    def __init__(self):
        self.llm = self._init_llm()
        self.buffer = ""  # guarda último parcial
        self.conversation_history = []  # memoria ligera de los últimos turnos

        self.last_comment_time = datetime.min
        
        self.comment_interval = timedelta(seconds=3) # Intervalo mínimo entre comentarios (ajústalo a tu gusto)

        self.ultimo_fragmento = ""

        # Suscribirse a eventos del STT
        event_bus.subscribe(SERVICE_NAME_STT + "_PARCIAL", self.procesar_comentarios)
        event_bus.subscribe(SERVICE_NAME_STT + "_PARCIAL", self.procesar_preliminar)
        event_bus.subscribe(SERVICE_NAME_STT + "_FINAL", self.on_final)

    def _init_llm(self):
        """Inicializa el modelo LLM desde variables de entorno"""
        load_dotenv()
        openai_key = os.getenv("OPENAI_API_KEY")

        if openai_key:
            return ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=openai_key
            )
        else:
            print("⚠️ No hay OPENAI_API_KEY, el servicio funcionará sin LLM")
            return None

    async def procesar_comentarios(self, texto: str):
        """Sólo decide si comentar (dos palabras) y emite si corresponde."""
        if not texto or not self.llm:
            return

        ahora = datetime.now()
        delta = ahora - self.last_comment_time

        if delta > self.comment_interval:
            comentario = await self._decidir_comentario(texto, int(delta.total_seconds()))
            normalizado = comentario.strip().lower().replace(".", "").replace("!", "").replace("…", "")
            if normalizado != "none":
                self.last_comment_time = ahora
                event_bus.emit("SOLUCION/FINAL",normalizado)
                print(f"🗨️ Comentario: {comentario}")


    async def procesar_preliminar(self, texto: str):
        """Sólo genera escucha activa preliminar."""
        if not texto or not self.llm:
            return

        preliminar = await self.generar_respuesta(texto, preliminar=True)
        self.ultimo_fragmento = preliminar
        print(f"🤔 Provisional: {preliminar}")
        # event_bus.emit("SOLUCION/PARCIAL", preliminar)  # si quieres


    async def on_final(self, texto: str):
        """Procesa texto final y da respuesta natural."""
        if not texto:
            return

        if not self.llm:
            return

        event_bus.emit("SOLUCION/FINAL", self.ultimo_fragmento)

        respuesta_definitiva = await self.generar_respuesta(texto, preliminar=False)

        # Emitir respuesta final
        event_bus.emit("SOLUCION/FINAL", respuesta_definitiva)
        print(f"💡 Final: {respuesta_definitiva}")

        # Limpiar buffer del último parcial
        self.buffer = ""
        self.ultimo_fragmento = ""

    async def _decidir_comentario(self, texto: str, segundos_desde_ultimo: int) -> str:
        """
        Decide si emitir un comentario breve y neutro de EXACTAMENTE UNA PALABRA corta,
        diferente a la última usada, o devolver NONE para no decir nada.
        """
        ultima = self.ultimo_comentario if hasattr(self, "ultimo_comentario") else "ninguna"
        
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente que escucha activamente. "
                    "Cuando el usuario habla, evalúa si vale la pena emitir UNA sola palabra "
                    "breve, neutra y empática. "
                    "Debes elegir SOLO entre este conjunto permitido:\n"
                    "- 'Claro'\n"
                    "- 'Bien'\n"
                    "- 'Ok'\n"
                    "- 'Vale'\n"
                    "- 'Entiendo'\n"
                    "- 'Perfecto'\n"
                    "- 'Correcto'\n\n"
                    f"No repitas la última palabra que ya usaste: '{ultima}'.\n"
                    "Si NO hace falta comentar, responde SOLO con 'NONE'.\n"
                    f"Han pasado {segundos_desde_ultimo} segundos desde el último comentario."
                )
            },
            {"role": "user", "content": texto}
        ]

        resp = await self.llm.ainvoke(messages)
        salida = resp.content.strip().splitlines()[0]

        # Normalizamos
        salida_limpia = salida.lower().replace(".", "").replace("!", "").replace("…", "")
        if salida_limpia == "none":
            return "NONE"

        # Guardamos la última para evitar repetición en el siguiente turno
        self.ultimo_comentario = salida.capitalize()

        # Retornamos UNA palabra capitalizada
        return salida.split()[0].capitalize()



    async def generar_respuesta(self, texto: str, preliminar=False) -> str:
        """
        Genera respuesta natural manteniendo contexto de la conversación.
        - preliminar=True → respuesta breve tipo escucha activa
        - preliminar=False → respuesta completa y coherente
        """

        # Construir contexto con historial
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente conversacional amable y natural. "
                    "Mantén un tono humano, breve y claro. "
                    "Recuerda el contexto de la conversación previa y responde coherentemente."
                )
            }
        ]

        # Añadir últimos turnos para memoria ligera
        messages.extend(self.conversation_history[-6:])  # últimos 3 turnos máx.

        # Añadir nuevo input del usuario
        messages.append({"role": "user", "content": texto})

        # Ajustar el comportamiento según parcial o final
        if preliminar:
            messages.append({
                "role": "system",
                "content": (
                    "El usuario aún está hablando. "
                    "Responde con una reacción breve o un pensamiento provisional, "
                    "como escucha activa. No cierres el tema todavía."
                    "Gerena un respuesta preliminar que permita empezar la conversacion"
                )
            })
        else:
            messages.append({
                "role": "system",
                "content": (
                    "El usuario ha terminado de exponer su idea. "
                    "Ahora eres el asistente: responde directamente sobre el tema planteado, "
                    "sin repetir ni hacer referencia a lo que ya dijiste antes, "
                    "ni saludar de nuevo. Mantén un tono natural, claro y coherente."
                )
            })

        try:
            resp = await self.llm.ainvoke(messages)
            respuesta = resp.content.strip()

            # Guardar turno en historial para mantener memoria
            self.conversation_history.append({"role": "user", "content": texto})
            self.conversation_history.append({"role": "assistant", "content": respuesta})

            # Limitar tamaño del historial (opcional)
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            return respuesta

        except Exception as e:
            print(f"⚠️ Error generando respuesta: {e}")
            return "(sin respuesta por ahora)"
