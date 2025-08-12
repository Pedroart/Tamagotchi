from __future__ import annotations

import asyncio
import json
import os
from collections import deque

import websockets
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama

from services.serviceController import ServiceController
from utils.const import SERVICE_NAME_STT, SERVICE_URI_STT

# Soporta ambos layouts de event_bus
try:
    from utils.EventBus import event_bus
except Exception:
    from event_bus import event_bus


class ServiceSTT(ServiceController):
    """
    Cliente STT con conexión WebSocket persistente:
    - Mantiene socket vivo con reconexión exponencial.
    - Writer/Reader en tareas separadas (cola de salida).
    - Procesa parciales/finales -> consolida con LLM -> emite por EventBus.
    - En FINAL, además de STT_FINAL, emite ai.heard(text=...).
    """

    def __init__(self, max_parciales: int = 10):
        super().__init__(SERVICE_URI_STT, SERVICE_NAME_STT)

        # Memoria de parciales para consolidación
        self.queue: deque[str] = deque(maxlen=max_parciales)
        self.last_partial: str | None = None
        self.last_final: str | None = None

        # Infra WS persistente
        self._send_q: asyncio.Queue = asyncio.Queue()
        self._reader_task: asyncio.Task | None = None
        self._writer_task: asyncio.Task | None = None
        self._conn_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.ws = None

        # LLMs
        self.llm_openai, self.llm_ollama = self._init_llms()
        self.llm = self.llm_openai or self.llm_ollama

    # ---------------- LLMs ----------------
    def _init_llms(self):
        load_dotenv()
        openai_key = os.getenv("OPENAI_API_KEY")

        llm_openai = None
        llm_ollama = None

        if openai_key:
            self.logger.info("✅ OpenAI detectado")
            llm_openai = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=openai_key,
            )
        else:
            self.logger.warning("⚠️ No hay OPENAI_API_KEY")

        try:
            llm_ollama = ChatOllama(
                model="gemma:2b",   # ajusta al que tengas local
                temperature=0.3,
                model_kwargs={
                    "num_thread": 1,
                    "top_p": 0.3,
                    "num_ctx": 100,
                    "max_tokens": 48,
                }
            )
            self.logger.info("✅ Ollama listo")
        except Exception as e:
            self.logger.warning(f"⚠️ No se pudo inicializar Ollama: {e}")

        return llm_openai, llm_ollama

    # ------------- Conexión persistente -------------
    async def start(self):
        """Arranca la conexión persistente (si ya está, no hace nada)."""
        self._stop.clear()
        if self._conn_task is None or self._conn_task.done():
            self._conn_task = asyncio.create_task(self._run_connection())

    async def stop(self):
        """Detiene conexión y tareas asociadas."""
        self._stop.set()
        if self._conn_task:
            try:
                await self._conn_task
            except Exception:
                pass
        self._conn_task = None

    async def _run_connection(self):
        backoff = 1
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    SERVICE_URI_STT,
                    ping_interval=15,
                    ping_timeout=15,
                    max_size=50 * 1024 * 1024,
                ) as ws:
                    self.ws = ws
                    self.logger.info("🔗 Conectado al servidor STT")
                    backoff = 1

                    self._reader_task = asyncio.create_task(self._reader(ws))
                    self._writer_task = asyncio.create_task(self._writer(ws))

                    done, pending = await asyncio.wait(
                        {self._reader_task, self._writer_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                    self.logger.info("⚠️ Reader/Writer finalizados, intento reconectar...")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"❌ Conexión fallida: {e} • reintento en {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 20)

        self.logger.info("🛑 Conexión detenida")

    async def _reader(self, ws):
        try:
            async for msg in ws:
                await self._on_message(msg)
        except Exception as e:
            self.logger.warning(f"Reader terminó: {e}")

    async def _writer(self, ws):
        try:
            while not self._stop.is_set():
                msg = await self._send_q.get()
                if isinstance(msg, (bytes, bytearray)):
                    await ws.send(msg)
                else:
                    await ws.send(str(msg))
        except Exception as e:
            self.logger.warning(f"Writer terminó: {e}")

    # ------------- API pública de stream -------------
    async def start_stream(self):
        """Inicia una sesión de audio dentro de la conexión viva."""
        await self.start()
        await self._send_q.put("__START__")
        self.reset_memoria()

    async def send_audio_chunk(self, audio_bytes: bytes):
        """Encola un chunk PCM int16 mono 16kHz."""
        if not audio_bytes:
            return
        await self._send_q.put(audio_bytes)

    async def stop_stream(self):
        """Finaliza la sesión de audio (la conexión sigue viva)."""
        await self._send_q.put("__END__")

    # ------------- Procesamiento mensajes -------------
    async def _on_message(self, msg: str):
        """Espera JSON: {"type":"partial|final","text":"..."}"""
        try:
            data = json.loads(msg)
            tipo = data.get("type")
            texto = (data.get("text") or "").strip()
            if not texto:
                return

            if tipo == "partial":
                self.last_partial = await self._consolidar(texto)
                self.logger.info(f"Parcial actualizado: {self.last_partial}")
                event_bus.emit(SERVICE_NAME_STT + "_PARCIAL", self.last_partial)

            elif tipo == "final":
                self.last_final = await self._consolidar(texto)
                self.logger.info(f"Final actualizado: {self.last_final}")

                # Eventos para tu app/juego
                event_bus.emit(SERVICE_NAME_STT + "_FINAL", self.last_final)
                # Dispara al agente (Bolla) directamente
                event_bus.emit("ai.heard", text=self.last_final)

                # Reset memoria de parciales para la próxima frase
                self.reset_memoria()

        except Exception as e:
            self.logger.warning(f"Mensaje inesperado: {msg} | Error: {e}")

    # ------------- Consolidación con LLM -------------
    def reset_memoria(self):
        self.queue.clear()
        self.last_partial = None

    async def _consolidar(self, nuevo: str) -> str:
        # evita duplicar entradas idénticas
        if self.queue and self.queue[-1] == nuevo:
            return self.last_partial or nuevo

        self.queue.append(nuevo)
        contexto = "\n".join(self.queue)

        prompt = f"""
            Eres experto en reconstruir frases a partir de STT streaming (con errores/truncados).
            Tarea: devuelve el texto coherente final SIN inventar, manteniendo contenido y longitud aproximada.
            Si detectas coordenadas de posicion se dictan en este formato que es estricto "No cambies la coma": X, Y.

            Parciales (cronológicos):
            ```
            {contexto}
            ```

            Responde SOLO con el texto reconstruido.
        """.strip()

        if not self.llm:
            # Sin LLM, devuelve lo último acumulado
            return nuevo

        try:
            resp = await self.llm.ainvoke(prompt)
            return (resp.content or "").strip()
        except Exception as e:
            self.logger.warning(f"Error con LLM primario: {e}")
            if self.llm is self.llm_openai and self.llm_ollama:
                self.logger.warning("🔁 Fallback a Ollama local...")
                self.llm = self.llm_ollama
                try:
                    resp = await self.llm.ainvoke(prompt)
                    return (resp.content or "").strip()
                except Exception as e2:
                    self.logger.warning(f"❌ Fallback falló: {e2}")
            return nuevo