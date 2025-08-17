from servicio.serviceController import ServiceController
from utils.EventBus import event_bus
from utils.const import SERVICE_NAME_STT,SERVICE_URI_STT
import os
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama

from dotenv import load_dotenv
import json
from collections import deque

class ServiceSTT(ServiceController):
    def __init__(self, max_parciales=10):
        super().__init__(SERVICE_URI_STT, SERVICE_NAME_STT)

        self.last_partial = None
        self.last_final = None
        self.queue = deque(maxlen=max_parciales)

        # ✅ LLM integrado dentro de la clase
        self.llm_openai, self.llm_ollama = self._init_llms()
        self.llm = self.llm_openai or self.llm_ollama


        # Listener para procesar parciales/finales
        self.add_listener(self._service_listener)


    def _init_llms(self):
        """Inicializa ambos modelos LLM (OpenAI y Ollama si está disponible)"""
        load_dotenv()
        openai_key = os.getenv("OPENAI_API_KEY")

        llm_openai = None
        llm_ollama = None

        if openai_key:
            print("✅ OpenAI detectado.")
            llm_openai = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=openai_key
            )
        else:
            print("⚠️ No hay OPENAI_API_KEY.")

        try:
            llm_ollama = ChatOllama(
                model="gemma:2b",  # cambia según lo que tengas descargado
                temperature=0.3,
                model_kwargs={
                    "num_thread": 1,
                    "top_p": 0.3,
                    "num_ctx": 100,
                    "max_tokens": 8,
                }
            )
            print("✅ Ollama listo.")
        except Exception as e:
            print(f"⚠️ No se pudo inicializar Ollama: {e}")

        return llm_openai, llm_ollama   

    async def start_stream(self):
        """Notifica inicio de sesión STT"""
        await self.send("__START__")
        self.reset_memoria()

    async def send_audio_chunk(self, audio_bytes: bytes):
        """Envía un chunk de audio PCM int16 mono 16kHz"""
        if not self.ws:
            self.logger.info("No conectado, no se puede enviar audio.")
            return
        try:
            await self.ws.send(audio_bytes)
        except Exception as e:
            self.logger.info(f"Error enviando audio: {e}")

    async def stop_stream(self):
        """Notifica fin de sesión STT"""
        await self.send("__END__")

    async def _service_listener(self, msg: str):
        try:
            # Esperamos JSON del servidor STT: {"type":"partial|final", "text":"..."}
            data = json.loads(msg)
            tipo = data.get("type")
            texto = data.get("text", "")

            if tipo == "partial":
                self.last_partial = await self.agregar_parcial(texto)
                self.logger.info(f"Parcial actualizado: {self.last_partial}")

                event_bus.emit(SERVICE_NAME_STT+"_PARCIAL", self.last_partial)

            elif tipo == "final":
                self.last_final = await self.agregar_parcial(texto)
                
                self.logger.info(f"Final actualizado: {self.last_final}")
                event_bus.emit(SERVICE_NAME_STT+"_FINAL", self.last_final)
                self.reset_memoria

        except Exception as e:
            # ✅ ahora mostramos el error real
            self.logger.warning(f"Mensaje no JSON o inesperado: {msg} | Error: {e}")

    def reset_memoria(self):
        self.queue.clear()
        self.last_partial = None

    async def agregar_parcial(self, nuevo: str) -> str:
        
        self.queue.append(nuevo)
        contexto = "\n".join(self.queue)

        prompt = f"""
            Eres un experto en reconstruir frases a partir de transcripciones STT en tiempo real.

            Has recibido varios parciales del reconocedor de voz. 
            Algunos parciales tienen errores, palabras sueltas o frases truncadas, pero en conjunto reflejan lo que la persona dijo.

            Tu tarea es:
            1. Leer TODOS los parciales como una secuencia temporal.
            2. Identificar la intención global de lo que se dijo.
            3. Reconstruir el mensaje en un texto coherente, como si fuera una transcripción humana.
            4. Corregir errores de dictado, omitir palabras sin sentido y ordenar las ideas.
            5. NO resumas demasiado: mantén la longitud aproximada y todo el contenido útil.

            Parciales recibidos:

            ```
            {contexto}
            ```
                        
            Ahora devuelve **el texto reconstruido, fluido y coherente** que representa lo que realmente se dijo.
            """

        
        try:
            resp = await self.llm.ainvoke(prompt)
            return resp.content.strip()
        except Exception as e:
            self.logger.warning(f"Error consolidando con LLM primario: {e}")

            if self.llm is self.llm_openai and self.llm_ollama:
                self.logger.warning("🔁 Cambiando a modelo local (Ollama).")
                self.llm = self.llm_ollama
                try:
                    resp = await self.llm.ainvoke(prompt)
                    return resp.content.strip()
                except Exception as e2:
                    self.logger.warning(f"❌ Fallback también falló: {e2}")

            return nuevo  # devuelves el último parcial si todo falla

