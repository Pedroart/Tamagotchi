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

INACTIVITY_TIMEOUT     = 0.5   # segundos de silencio para flush
PARTIAL_EVAL_INTERVAL  = 1.0   # cada cuántos seg hacemos un parcial
WINDOW_SEC             = 5.0   # cuántos seg de contexto en cada parcial
SAMPLERATE             = 16000 # 16 kHz fija
CHANNELS               = 1     # mono

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AudioServer")


class AudioTransform:
    def __init__(
        self,
        model_transcription=INIT_MODEL_TRANSCRIPTION,
        device=INIT_MODEL_DEVICE,
        compute_type=INIT_MODEL_COMPUTE_TYPE,
        language=INIT_LANGUAGE,
        port=INIT_SERVER_PORT
    ):
        self.port = port
        self.language = language

        # Estado de streaming
        self.audio_buffer = io.BytesIO()
        self.last_packet_time = None
        self.partial_running = False
        self.ending = False

        # Temporizador para parciales
        self.last_partial_time = time.time()

        # Carga modelo
        logger.info(f"Cargando modelo '{model_transcription}'")
        self.model = WhisperModel(
            model_transcription,
            device=device,
            compute_type=compute_type
        )
        logger.info("Modelo cargado y listo")

    def reset_buffer(self):
        """Resetea buffer y estados."""
        self.audio_buffer = io.BytesIO()
        self.last_packet_time = None
        self.partial_running = False
        self.ending = False
        self.last_partial_time = time.time()
        logger.info("🔄 Buffer reiniciado y estados restablecidos")

    def _pcm_to_text(self, raw_data: bytes) -> str:
        """Convierte PCM int16 mono a WAV temporal y transcribe."""
        if not raw_data:
            return ""
        audio_np = np.frombuffer(raw_data, dtype=np.int16)
        wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = tmp.name
                sf.write(wav_path, audio_np, SAMPLERATE, format="WAV")
            segments, _ = self.model.transcribe(wav_path, language=self.language, vad_filter=False)
            return " ".join(seg.text for seg in segments)
        except Exception as e:
            logger.error(f"❌ Error en _pcm_to_text: {e}")
            return ""
        finally:
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)

    def transcribe_partial(self, audio_buffer: io.BytesIO) -> str:
        """Transcribe solo los últimos WINDOW_SEC segundos."""
        data = audio_buffer.getvalue()
        window_bytes = int(SAMPLERATE * CHANNELS * 2 * WINDOW_SEC)
        tail = data[-window_bytes:]
        return self._pcm_to_text(tail)

    def transcribe_final(self, audio_buffer: io.BytesIO) -> str:
        """Transcribe TODO el buffer."""
        return self._pcm_to_text(audio_buffer.getvalue())

    async def flush_if_needed(self, websocket):
        """
        Si pasó demasiado tiempo sin recibir audio, transcribe lo acumulado.
        Solo si:
          - NO estamos en END
          - NO hay un parcial en curso
          - Llevamos al menos PARTIAL_EVAL_INTERVAL seg de audio acumulado
        """
        if self.ending or self.partial_running:
            return

        if self.last_packet_time and (time.time() - self.last_packet_time) > INACTIVITY_TIMEOUT:
            # Calcula duración actual del buffer
            buf_bytes = self.audio_buffer.getbuffer().nbytes
            duration = buf_bytes / (SAMPLERATE * CHANNELS * 2)

            # Sólo flush si hay suficiente audio (> PARTIAL_EVAL_INTERVAL)
            if duration >= PARTIAL_EVAL_INTERVAL:
                logger.info("⏳ Timeout de inactividad y suficiente audio, flush final")
                await self.flush_buffer(websocket)
            else:
                logger.info(f"⚠️ Inactividad detectada pero solo {duration:.2f}s de audio (<{PARTIAL_EVAL_INTERVAL}s), no hago flush")


    async def flush_buffer(self, websocket):
        """Envía transcripción FINAL y resetea todo."""
        if self.audio_buffer.getbuffer().nbytes > 0:
            text = self.transcribe_final(self.audio_buffer)
            logger.info(f"✅ Transcripción FINAL: {text}")
            await websocket.send(text)
        self.reset_buffer()

    async def _run_partial(self, websocket):
        """Worker que genera un parcial de los últimos WINDOW_SEC segundos."""
        try:
            text = self.transcribe_partial(self.audio_buffer)
            if text.strip():
                logger.info(f"📝 Parcial: {text}")
                await websocket.send(f"(parcial) {text}")
        finally:
            self.partial_running = False
            self.last_partial_time = time.time()

    async def handle_audio(self, websocket):
        logger.info("Cliente conectado")
        self.reset_buffer()

        while True:
            try:
                # Espera con timeout para inactividad
                message = await asyncio.wait_for(websocket.recv(), timeout=0.1)

                # START
                if isinstance(message, str) and message == "__START__":
                    logger.info("⚡ START")
                    self.reset_buffer()
                    continue

                # END
                if isinstance(message, str) and message == "__END__":
                    logger.info("🏁 END")
                    self.ending = True

                    # Espera parcial en curso
                    while self.partial_running:
                        await asyncio.sleep(0.05)

                    await self.flush_buffer(websocket)
                    continue

                # Audio chunk
                self.audio_buffer.write(message)
                self.last_packet_time = time.time()

                # Logging del buffer
                buf_bytes = self.audio_buffer.getbuffer().nbytes
                duration = buf_bytes / (SAMPLERATE * CHANNELS * 2)
                logger.info(f"📥 Chunk {len(message)} B → Buffer ~{duration:.2f}s")

                # Parcial cada PARTIAL_EVAL_INTERVAL
                if (
                    not self.ending and
                    not self.partial_running and
                    time.time() - self.last_partial_time >= PARTIAL_EVAL_INTERVAL
                ):
                    self.partial_running = True
                    asyncio.create_task(self._run_partial(websocket))

            except asyncio.TimeoutError:
                # Flush por inactividad
                #await self.flush_if_needed(websocket)
                pass
            except websockets.ConnectionClosed:
                logger.info("🔌 Conexión cerrada")
                break

    async def start_server(self):
        async with websockets.serve(self.handle_audio, "0.0.0.0", self.port, max_size=50*1024*1024):
            logger.info(f"🚀 Servidor WS en ws://0.0.0.0:{self.port}")
            await asyncio.Future()

    def run(self):
        asyncio.run(self.start_server())


if __name__ == "__main__":
    audio_server = AudioTransform()
    audio_server.run()
