import asyncio
import websockets
import io
import time
from faster_whisper import WhisperModel
import logging
import tempfile, os
import soundfile as sf
import numpy as np

INIT_MODEL_TRANSCRIPTION = "tiny"
INIT_MODEL_DEVICE = "cpu"
INIT_MODEL_COMPUTE_TYPE = "int8"
INIT_LANGUAGE = "es"
INIT_SERVER_PORT = 55000
INACTIVITY_TIMEOUT = 0.5  # segundos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AudioServer")

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

        # Buffer temporal de audio acumulado
        self.audio_buffer = io.BytesIO()
        self.last_packet_time = None

        # ✅ Carga el modelo una sola vez
        logger.info(f"Cargando modelo '{model_transcription}'")
        self.model = WhisperModel(
            model_transcription,
            device=device,
            compute_type=compute_type
        )
        logger.info("Modelo cargado y listo")

    def reset_buffer(self):
        """Resetea el buffer de audio"""
        self.audio_buffer = io.BytesIO()
        self.last_packet_time = None
        logger.info("🔄 Buffer reiniciado")



    def transcribe(self, audio_buffer: io.BytesIO) -> str:
        audio_buffer.seek(0)
        raw_data = audio_buffer.read()
        
        # 🚨 Necesitamos saber cómo es el PCM recibido:
        samplerate = 16000  # o el que uses en el cliente
        channels = 1        # o 2 según el origen

        # Convierte PCM a numpy para guardarlo como WAV
        audio_np = np.frombuffer(raw_data, dtype=np.int16)
        if channels > 1:
            audio_np = audio_np.reshape(-1, channels)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, audio_np, samplerate, format="WAV")
            tmp_path = tmp.name

        try:
            segments, info = self.model.transcribe(tmp_path, language=self.language, vad_filter=False)
            text = " ".join(seg.text for seg in segments)
        except Exception as e:
            logger.info(f"❌ Error al transcribir: {e}")
            text = ""
        finally:
            os.unlink(tmp_path)

        return text


    async def flush_if_needed(self, websocket):
        """
        Si pasó demasiado tiempo sin recibir audio, transcribe lo acumulado.
        """
        if self.last_packet_time and (time.time() - self.last_packet_time) > INACTIVITY_TIMEOUT:
            logger.info("⏳ Timeout de inactividad, transcribiendo...")
            await self.flush_buffer(websocket)

    async def flush_buffer(self, websocket):
        """
        Procesa el buffer acumulado y lo envía como transcripción.
        """
        if self.audio_buffer.getbuffer().nbytes > 0:
            text = self.transcribe(self.audio_buffer)
            logger.info(f"✅ Transcripción: {text}")
            await websocket.send(text)
        self.reset_buffer()

    async def handle_audio(self, websocket):
        """
        Maneja conexiones WebSocket: recibe audio, acumula y controla inicio/fin/timeout.
        """
        logger.info("Cliente conectado")
        self.reset_buffer()

        while True:
            try:
                # Esperar con timeout pequeño para poder chequear inactividad
                message = await asyncio.wait_for(websocket.recv(), timeout=0.1)

                # Comandos especiales
                if isinstance(message, str):
                    if message == "__START__":
                        logger.info("⚡ Inicio de nueva captura (START)")
                        self.reset_buffer()
                        continue
                    elif message == "__END__":
                        logger.info("🏁 Fin de captura (END)")
                        await self.flush_buffer(websocket)
                        continue

                # Audio normal
                self.audio_buffer.write(message)
                self.last_packet_time = time.time()

            except asyncio.TimeoutError:
                # Chequear si hubo inactividad
                await self.flush_if_needed(websocket)
            except websockets.ConnectionClosed:
                logger.info("🔌 Cliente desconectado")
                break

    async def start_server(self):
        """Inicia el servidor WebSocket"""
        async with websockets.serve(self.handle_audio, "0.0.0.0", self.port, max_size=50 * 1024 * 1024):
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
