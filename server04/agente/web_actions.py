# web_actions.py
import os
import time
import json
import asyncio
import threading
from typing import Set

from agente.event_bus import event_bus
from agente.logger import logger

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except Exception as e:
    websockets = None
    WebSocketServerProtocol = None
    _WS_IMPORT_ERROR = e
else:
    _WS_IMPORT_ERROR = None

WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "8080"))

class WebActions:
    """
    - Se suscribe a 'ui.speak'
    - Imprime en logs lo que llega
    - Publica por WebSocket (broadcast) a todos los clientes conectados
    - Expone serve_forever() para correrse dentro de un hilo
    """

    def __init__(self):
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: websockets.server.Serve | None = None
        self._clients: "Set[WebSocketServerProtocol]" = set()
        self._lock = threading.Lock()

    # -------------------- Event Bus --------------------
    def _on_ui_speak(self, *args, **kwargs):
        """
        Callback del event_bus para 'ui.speak'.
        Loguea y envía por WS a todos los clientes.
        """
        ts = int(time.time() * 1000)
        logger.info(f"[web_actions] ui.speak @ {ts} args={args} kwargs={kwargs}")

        data = {}
        if args and isinstance(args[0], dict):
            data = dict(args[0])  # copia defensiva
        # Merge con kwargs por si mandan campos sueltos
        data |= kwargs

        expr = data.get("expression")           # p.ej. "smile" o 4
        path = "/out_wav/"+data.get("path")

        payload = {
            "kind": "action",
            "payload": {
                "type": "sequence",
                "items": [
                    {"type": "expression", "name": expr},
                    {"type": "audio", "src": path,
                     "crossOrigin": "anonymous", "waitEnd": True}
                ]
            }
        }

        # Enviar al loop async de este servidor, de forma thread-safe.
        if self._loop:
            try:
                
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(payload),
                    self._loop
                )
            except Exception as e:
                logger.warning(f"[web_actions] fallo al programar broadcast: {e}")

    # -------------------- WebSocket --------------------
    async def _broadcast(self, data: dict):
        """
        Envía `data` (dict) a todos los clientes conectados (JSON).
        Limpia clientes desconectados.
        """
        if not self._clients:
            return

        message = json.dumps(data, ensure_ascii=False)
        stale: Set[WebSocketServerProtocol] = set()

        # Enviar en paralelo a todos
        tasks = []
        for ws in list(self._clients):
             
            peer = getattr(ws, "remote_address", None)
            print("----> 1controld de envio")  
            print(f"[bug] cliente {peer} "
                        f"close_code={getattr(ws, 'close_code', None)} "
                        f"close_reason={getattr(ws, 'close_reason', None)}") 

            tasks.append(self._safe_send(ws, message))

        print("----> 2controld de envio") 

        if tasks:
            print("----> 3controld de envio") 
            await asyncio.gather(*tasks, return_exceptions=True)

        # Limpieza
        if stale:
            with self._lock:
                for ws in stale:
                    self._clients.discard(ws)

    async def _safe_send(self, ws: WebSocketServerProtocol, msg: str):
        try:
            await ws.send(msg)
            print(f"[web_actions] enviando a un cliente")
        except Exception as e:
            logger.info(f"[web_actions] fallo enviando a un cliente: {e}")
            # marcará como stale en el próximo broadcast al ver ws.closed

    async def _ws_handler(self, websocket: WebSocketServerProtocol):
        """
        Handler por conexión. Registramos, mantenemos vivo,
        y soportamos pings/keepalive mínimos.
        """
        with self._lock:
            self._clients.add(websocket)

        peer = getattr(websocket, "remote_address", None)
        logger.info(f"[web_actions] WS conectado: {peer} (total={len(self._clients)})")

        try:
            await websocket.send(json.dumps({"kind": "hello", "from": "web_actions"}))
        except Exception:
            pass

        try:
            # No necesitamos recibir nada; solo mantener la conexión viva.
            async for incoming in websocket:
                logger.debug(f"[web_actions] recibido de {peer}: {incoming!r}")# Si en el futuro quieres aceptar comandos entrantes, parsea aquí.
                
        except Exception as e:
            logger.info(f"[web_actions] WS error con {peer}: {e}")
        finally:
            with self._lock:
                self._clients.discard(websocket)
            logger.info(f"[web_actions] WS desconectado: {peer} (total={len(self._clients)})")

    async def _start_ws(self):
        """
        Arranca el servidor websockets en el loop actual.
        """
        if _WS_IMPORT_ERROR:
            raise RuntimeError(
                f"No se pudo importar 'websockets': {_WS_IMPORT_ERROR}. "
                "Instala con: pip install websockets"
            )

        self._server = await websockets.serve(
            self._ws_handler,
            WS_HOST,
            WS_PORT,
            ping_interval=20,
            ping_timeout=20,
            max_queue=32,
        )
        logger.info(f"[web_actions] WS server escuchando en ws://{WS_HOST}:{WS_PORT}")

    async def _async_main(self):
        """
        Tarea principal asíncrona: inicia WS y espera hasta que self._running sea False.
        """
        await self._start_ws()
        logger.info("[web_actions] callback + WS activos.")

        # Loop de vida controlado por _running
        while self._running:
            # Si quieres, aquí puedes hacer housekeeping periódico
            await asyncio.sleep(0.25)

    # -------------------- Ciclo de vida --------------------
    def serve_forever(self):
        """
        Mantiene vivo el hilo, activa la suscripción y el WS server.
        Debe correrse en un hilo propio (daemon recomendado).
        """
        if _WS_IMPORT_ERROR:
            logger.error(f"[web_actions] 'websockets' no disponible: {_WS_IMPORT_ERROR}")
            return

        self._running = True

        try:
            event_bus.subscribe("ui.speak", self._on_ui_speak)
            logger.info("web_actions: suscrito a 'ui.speak'.")
        except Exception as e:
            logger.warning(f"web_actions: no se pudo suscribir a 'ui.speak': {e}")

        # Crear y fijar loop propio para este hilo
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._async_main())
        except KeyboardInterrupt:
            logger.info("web_actions: detenido por teclado.")
        except Exception as e:
            logger.error(f"[web_actions] fallo en loop: {e}")
        finally:
            # Cerrar WS y loop
            try:
                if self._server is not None:
                    self._server.close()
                    # Esperar cierre de sockets
                    self._loop.run_until_complete(self._server.wait_closed())
            except Exception:
                pass

            pending = asyncio.all_tasks(loop=self._loop)
            for task in pending:
                task.cancel()
            try:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()
            self._loop = None
            self._running = False
            logger.info("web_actions: finalizado.")

# ------------- Función pública para usar con threading.Thread -------------
_server_singleton: WebActions | None = None

def start_ws_server():
    """
    Inicia la suscripción y el servidor WebSocket (broadcast de 'ui.speak').
    Uso:
        threading.Thread(target=start_ws_server, daemon=True).start()
    """
    global _server_singleton
    if _server_singleton is not None:
        logger.info("web_actions: ya estaba iniciado; se ignora segunda llamada.")
        return
    _server_singleton = WebActions()
    _server_singleton.serve_forever()
