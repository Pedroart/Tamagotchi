# services/tts_service.py
from __future__ import annotations
import asyncio, json, threading, time
from typing import Optional
import websockets

try:
    from utils.EventBus import event_bus
except Exception:
    from event_bus import event_bus


class TTSService:
    """
    Cliente WS para tu servidor Piper TTS.
    - Conexión persistente con reconexión.
    - Cola interna de textos a reproducir (secuencial).
    - Por defecto es fire-and-forget (rápido): no espera a 'parado'.
    - Soporta interrupción: limpia cola + envía 'stop' antes del nuevo texto.
    - Re-emite estados por EventBus: 'TTS/ESTADO'
    """
    def __init__(self, uri: str = "ws://localhost:8765", fast_fire_and_forget: bool = True):
        self.uri = uri
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False

        self.fast = fast_fire_and_forget
        self.queue: asyncio.Queue[tuple[str,str,bool]] = asyncio.Queue()  # (texto, emotion, interrupt)
        self._stop = asyncio.Event()
        self._reader_task: Optional[asyncio.Task] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._conn_task: Optional[asyncio.Task] = None

        # estado
        self._speaking = False
        self._state_event = asyncio.Event()  # set cuando 'parado'
        self._state_event.set()              # arranca en 'parado'

        # Integra con tu sistema: cuando hay respuesta final, se lee
        event_bus.subscribe("SOLUCION/FINAL", self.on_tts_request)

    # ---------- Integración EventBus ----------
    def on_tts_request(self, texto: str):
        if not texto:
            return
        # Interrumpe lo que esté sonando y habla lo nuevo
        self.enqueue(texto, emotion="neutral", interrupt=True)

    def enqueue(self, texto: str, emotion: str = "neutral", interrupt: bool = True):
        loop = asyncio.get_running_loop() if asyncio.get_event_loop().is_running() else None
        payload = (texto, emotion, interrupt)
        if loop and loop.is_running():
            self.queue.put_nowait(payload)
        else:
            # si lo llaman desde un hilo sin loop, usa call_soon_threadsafe si hay loop global
            try:
                asyncio.get_event_loop().call_soon_threadsafe(self.queue.put_nowait, payload)
            except RuntimeError:
                # sin loop: ignorar (normalmente no pasa porque arrancamos en runtime)
                pass

    # ---------- Ciclo de vida ----------
    async def start(self):
        self._stop.clear()
        if not (self._conn_task and not self._conn_task.done()):
            self._conn_task = asyncio.create_task(self._run_connection())
        if not (self._worker_task and not self._worker_task.done()):
            self._worker_task = asyncio.create_task(self._run_worker())

    async def stop(self):
        self._stop.set()
        for t in (self._worker_task, self._reader_task, self._conn_task):
            if t:
                t.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None
        self.connected = False

    # ---------- Conexión persistente ----------
    async def _run_connection(self):
        backoff = 1
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self.uri,
                    ping_interval=30, ping_timeout=30, close_timeout=3,
                    max_queue=32, max_size=8*1024*1024
                ) as ws:
                    self.ws = ws
                    self.connected = True
                    backoff = 1
                    # primer mensaje (estado/listo o ack)
                    try:
                        hello = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        self._handle_msg(hello)
                    except Exception:
                        pass

                    # lector
                    self._reader_task = asyncio.create_task(self._reader(ws))
                    event_bus.emit("TTS/ESTADO", estado="listo")

                    # espera a que lector termine
                    await self._reader_task
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.connected = False
                event_bus.emit("TTS/ESTADO", estado="parado")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 20)

        self.connected = False

    async def _reader(self, ws):
        try:
            async for msg in ws:
                self._handle_msg(msg)
        except Exception:
            pass
        finally:
            self.connected = False
            self.ws = None

    def _handle_msg(self, msg: str):
        try:
            data = json.loads(msg)
        except Exception:
            return
        estado = data.get("estado")
        if estado:
            # "listo" | "hablando" | "parado"
            event_bus.emit("TTS/ESTADO", estado=estado)
            if estado == "hablando":
                self._speaking = True
                self._state_event.clear()
            elif estado == "parado":
                self._speaking = False
                self._state_event.set()

    # ---------- Worker de reproducción ----------
    async def _run_worker(self):
        while not self._stop.is_set():
            texto, emotion, interrupt = await self.queue.get()
            try:
                await self._ensure_connected()
                if interrupt:
                    await self._send_stop()
                await self._say(texto, emotion, await_end=not self.fast)
            except Exception:
                # si algo falla, seguimos al siguiente
                pass
            finally:
                self.queue.task_done()

    async def _ensure_connected(self):
        tries = 0
        while not self.connected and not self._stop.is_set():
            tries += 1
            await asyncio.sleep(0.05 if tries < 10 else 0.2)

    async def _send_stop(self):
        if not (self.ws and self.connected):
            return
        try:
            await asyncio.wait_for(self.ws.send(json.dumps({"cmd": "stop"})), timeout=0.5)
        except Exception:
            pass
        # esperar cortito a 'parado' (no bloquear de más)
        try:
            await asyncio.wait_for(self._state_event.wait(), timeout=0.7)
        except Exception:
            pass

    async def _say(self, texto: str, emotion: str, await_end: bool):
        if not (self.ws and self.connected):
            return
        # Enviar comando
        try:
            await asyncio.wait_for(
                self.ws.send(json.dumps({"cmd": "say", "text": texto, "emotion": emotion})),
                timeout=0.7
            )
        except Exception:
            return

        if not await_end:
            # modo rápido: no esperamos el final
            return

        # modo "esperar hasta que termine de hablar"
        # 1) espera breve a detectar "hablando"
        try:
            await asyncio.wait_for(self._wait_for_speaking(), timeout=1.2)
        except Exception:
            pass
        # 2) espera a "parado"
        try:
            await asyncio.wait_for(self._state_event.wait(), timeout=30.0)
        except Exception:
            pass

    async def _wait_for_speaking(self):
        t0 = time.time()
        while time.time() - t0 < 1.2:
            if self._speaking:
                return
            await asyncio.sleep(0.02)


# ---------------- Runtime para usar con Pygame (hilo aparte) ----------------
class TTSRuntime:
    """
    Arranca TTSService en un event loop propio (hilo daemon),
    para integrarlo fácilmente con apps no-async (ej. Pygame).
    """
    def __init__(self, uri: str = "ws://localhost:8765", fast_fire_and_forget: bool = True):
        self.svc = TTSService(uri=uri, fast_fire_and_forget=fast_fire_and_forget)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.svc.start())
        self.loop.run_forever()

    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def stop(self):
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.svc.stop(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)

    # atajo para encolar desde cualquier hilo
    def say(self, text: str, emotion: str = "neutral", interrupt: bool = True):
        def _enqueue():
            self.svc.enqueue(text, emotion, interrupt)
        self.loop.call_soon_threadsafe(_enqueue)
