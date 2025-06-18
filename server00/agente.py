from dotenv import load_dotenv
import os, base64, cv2
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain_core.tools import StructuredTool
from typing import Callable
from langchain_core.messages import SystemMessage
import openai
import pygame
from io import BytesIO


load_dotenv()
os.getenv("OPENAI_API_KEY")

AVAILABLE_ANIMATIONS = {
    "spellcast_down", "spellcast_left", "spellcast_right", "spellcast_up",
    "thrust_down", "thrust_left", "thrust_right", "thrust_up",
    "walk_down", "walk_left", "walk_right", "walk_up",
    "slash_down", "slash_left", "slash_right", "slash_up",
    "shoot_down", "shoot_left", "shoot_right", "shoot_up",
    "hurt", "climb",
    "idle_up",
    "jump_down", "jump_left", "jump_right", "jump_up",
    "sit_down", "sit_left", "sit_right", "sit_up",
    "emote_down", "emote_left", "emote_right", "emote_up",
    "run_down", "run_left", "run_right", "run_up",
    "watering_down", "watering_left", "watering_right", "watering_up",
    "combat_down", "combat_left", "combat_right", "combat_up",
    "1h_slash_down", "1h_slash_left", "1h_slash_right", "1h_slash_up",
    "1h_backslash_down", "1h_backslash_left", "1h_backslash_right", "1h_backslash_up",
    "1h_halfslash_down", "1h_halfslash_left", "1h_halfslash_right", "1h_halfslash_up",
}

# --- Tool base que luego envolvemos con acceso al bus ---
def make_tool_ejecutar_animacion(bus):
    def _ejecutar_animacion(name: str) -> str:
        if name not in AVAILABLE_ANIMATIONS:
            return f"Error: animación inválida '{name}'."
        bus.publish("ui/animacion", name)
        return f"Animación '{name}' ejecutada."

    return StructuredTool.from_function(
        func=_ejecutar_animacion,
        name="ejecutar_animacion",
        description="Ejecuta una animación válida: " + ", ".join(sorted(AVAILABLE_ANIMATIONS)),
    )

# --- Tool para analizar imagen (placeholder multimodal) ---
@tool
def consultar_imagen(image_b64: str) -> str:
    """Procesa una imagen enviada en base64 para analizarla con el modelo."""
    return ""  # el LLM multimodal genera la respuesta

@tool
def responder_texto(texto: str) -> str:
    """Responde con una frase clara y amigable, sin repetir el mensaje original."""
    return texto  # ahora devuelve la frase directamente, sin "Respondiendo:"

def make_tool_decir_texto(bus):

    @tool
    def decir_texto(texto: str) -> str:
        """Reproduce en voz alta un texto usando una voz sintética amigable y expresiva."""
        if not texto:
            return "Nada que decir."

        try:
            bus.publish("ia/hablando", True)
            print(f"🗣️ [tool] Hablando: {texto}")

            # Estimar duración
            palabras = len(texto.split())
            duracion_estimada = max(1.5, palabras * 0.4)

            # Animación de hablar
            bus.publish("ui/animacion", "emote_down")

            response = openai.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=texto
            )
            audio_data = response.content
            audio_buffer = BytesIO(audio_data)
            audio_buffer.name = "voz.mp3"

            pygame.mixer.music.load(audio_buffer)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)

        except Exception as e:
            print(f"❌ Error en tool decir_texto: {e}")
            return "Hubo un problema al hablar."

        finally:
            bus.publish("ia/hablando", False)
            bus.publish("ui/animacion", "idle_up")

        return "Mensaje hablado correctamente."

    return decir_texto

system_message = SystemMessage(
    content=(
        "Eres un personaje animado que interactúa con animaciones y voz.\n"
        "SIEMPRE que recibas un mensaje, primero debes ejecutar una animación usando 'ejecutar_animacion'.\n"
        "Luego debes decir algo usando 'decir_texto'.\n"
        "Nunca debes usar 'responder_texto'. Usa solo 'decir_texto'.\n"
        "Sé divertido, expresivo y amigable, como un personaje de videojuego.\n"
        "No repitas el mensaje del usuario. Responde con una frase clara y única."
    )
)

# --- Agente controlador multimodal con herramientas ---
class Agente:
    def __init__(self, bus):
        self.bus = bus
        self.llm = ChatOpenAI(temperature=0)
        self.tools = [
            make_tool_decir_texto(self.bus),
            make_tool_ejecutar_animacion(self.bus),
            consultar_imagen,
            responder_texto
        ]
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_message": system_message
            }
        )

    def procesar(self, texto: str, imagen_np=None) -> str:
        content = [{"type": "text", "text": texto}]
        '''if imagen_np is not None:
            _, enc = cv2.imencode('.jpg', imagen_np)
            b64 = base64.b64encode(enc.tobytes()).decode('utf-8')
            content.append({
                "type": "image",
                "source_type": "base64",
                "mime_type": "image/jpeg",
                "data": b64
            })'''
        msg = HumanMessage(content=content)
        resp = self.agent.invoke([msg])
        respuesta_texto = resp.get("output", "Sin respuesta")

        # 🔊 Reproducir respuesta con voz
        #self.reproducir_audio(respuesta_texto)

        return respuesta_texto

    def reproducir_audio(self, texto: str):
        if not texto:
            return

        try:
            print(f"🗣️ Sintetizando voz: {texto}")
            self.bus.publish("ia/hablando", True)
            response = openai.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=texto
            )
            audio_data = response.content
            audio_buffer = BytesIO(audio_data)
            audio_buffer.name = "voz.mp3"

            pygame.mixer.music.load(audio_buffer)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)

        except Exception as e:
            print(f"❌ Error al reproducir voz: {e}")

        finally:
            self.bus.publish("ia/hablando", False)