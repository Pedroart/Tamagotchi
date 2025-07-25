import asyncio
import json
import websockets

from utils.EventBus import event_bus

class TTSService:
    def __init__(self, uri="ws://localhost:8765"):
        self.uri = uri
        self.ws = None
        self.connected = False
        self.queue = asyncio.Queue()  # cola de textos por reproducir

        # Suscripción a respuestas finales
        event_bus.subscribe("SOLUCION/FINAL", self.on_tts_request)

    def on_tts_request(self, texto: str):
        """
        Callback del EventBus cuando hay una respuesta final lista.
        Encola el texto para ser reproducido por el TTS.
        """
        if not texto:
            return
        print(f"🔔 TTSService recibió texto para reproducir: {texto[:60]}...")
        self.queue.put_nowait(texto)

    async def connect(self):
        """
        Conecta al servidor WebSocket del TTS.
        """
        if self.connected:
            return
        try:
            self.ws = await websockets.connect(self.uri)
            ready = await self.ws.recv()
            print(f"✅ Conectado al TTS: {ready}")
            self.connected = True
        except Exception as e:
            print(f"⚠️ No se pudo conectar al TTS: {e}")
            self.connected = False

    async def play_text(self, texto: str, emotion="neutral"):
        """
        Envía texto al TTS y espera que termine de hablar.
        """
        if not self.connected:
            await self.connect()
            if not self.connected:
                print("❌ No se pudo reproducir porque TTS no está conectado.")
                return

        print(f"▶️ Enviando texto al TTS ({len(texto.split())} palabras)...")

        # Enviar el texto
        await self.ws.send(json.dumps({"cmd": "say", "text": texto, "emotion": emotion}))

        start_send = asyncio.get_event_loop().time()
        t_hablando = None
        t_parado = None
        '''
        # Escuchar estados hasta que termine
        while True:
            msg = await self.ws.recv()
            data = json.loads(msg)
            estado = data.get("estado")

            if estado == "hablando":
                t_hablando = asyncio.get_event_loop().time()
                print(f"🎙️ TTS empezó a hablar a los {t_hablando - start_send:.2f}s")

            elif estado == "parado":
                t_parado = asyncio.get_event_loop().time()
                print(f"⏹ TTS terminó a los {t_parado - start_send:.2f}s")
                break

        # Métricas opcionales
        if t_hablando and t_parado:
            latencia = t_hablando - start_send
            duracion_audio = t_parado - t_hablando
            total_time = t_parado - start_send

            print(f"⏱ Latencia de síntesis: {latencia:.2f}s | "
                  f"🎧 Audio: {duracion_audio:.2f}s | "
                  f"🌐 Total: {total_time:.2f}s")
        '''
        
    async def run(self):
        """
        Bucle principal: espera textos en cola y los reproduce secuencialmente.
        """
        while True:
            texto = await self.queue.get()
            await self.play_text(texto)
