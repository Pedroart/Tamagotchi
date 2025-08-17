import asyncio
import websockets
import io
from faster_whisper import WhisperModel
import logging

INIT_MODEL_TRANSCRIPTION = "tiny"
INIT_MODEL_DEVICE = "cpu"
INIT_MODEL_COMPUTE_TYPE = "int8"
INIT_LANGUAGE = "es"
INIT_SERVER_PORT = 55000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("AudioServer")
'''
logger.info("Servidor iniciado")
logger.debug("Mensaje de depuración")
logger.info("Error al procesar")
'''


class AudioTransform:
    def __init__(
        self,
        model_transcription: str = INIT_MODEL_TRANSCRIPTION,
        device: str = INIT_MODEL_DEVICE,
        compute_type: str = INIT_MODEL_COMPUTE_TYPE,
        language: str = INIT_LANGUAGE,
        port: int = INIT_SERVER_PORT
    ):
        self.port = port
        self.language = language

        # ✅ Carga el modelo una sola vez
        logger.info(f"Cargando modelo '{model_transcription}'")
        self.model = WhisperModel(
            model_transcription,
            device=device,
            compute_type=compute_type
        )
        logger.info("Modelo cargado y listo")

    def transcribe(self, audio_buffer: io.BytesIO) -> str:
        """
        Recibe audio como BytesIO y devuelve la transcripción concatenada
        """
        segments, info = self.model.transcribe(audio_buffer, language=self.language, vad_filter=False)
        return " ".join(seg.text for seg in segments)

    async def handle_audio(self, websocket):
        """
        Maneja conexiones WebSocket: recibe bytes de audio, los transcribe y responde.
        """
        logger.info("Cliente conectado")

        async for message in websocket:
            logger.info(f"Recibido audio ({len(message)} bytes)")

            audio_buffer = io.BytesIO(message)
            text = self.transcribe(audio_buffer)

            logger.info(f"✅ Transcripción: {text}")

            # Responder al cliente
            await websocket.send(text)

    async def start_server(self):
        """Inicia el servidor WebSocket"""
        async with websockets.serve(self.handle_audio, "0.0.0.0", self.port,max_size=50 * 1024 * 1024):
            logger.info(f"🚀 Servidor WebSocket en ws://localhost:{self.port}")
            await asyncio.Future()  # Mantener vivo

    def run(self):
        """Método simple para arrancar el servicio"""
        asyncio.run(self.start_server())


if __name__ == "__main__":
    
    audio_server = AudioTransform(
        model_transcription="small",
        device="cpu",
        compute_type="int8",
        language="en",
        port=55000
    )
    audio_server.run()
