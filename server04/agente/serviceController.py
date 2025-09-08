import asyncio
import websockets
import json
from logger import logger



class ServiceController:
    def __init__(self, uri, name="Service"):
        """
        uri  -> ws://host:port
        name -> nombre descriptivo del servicio para logs
        """
        self.uri = uri
        self.name = name
        self.ws = None
        self._listeners = []
        

    async def connect(self):
        """Conectar al WebSocket del servicio"""
        try:
            self.ws = await websockets.connect(self.uri, max_size=50 * 1024 * 1024)
            logger.info(f"Conectado a {self.uri}")
            asyncio.create_task(self._listen_loop())
        except Exception as e:
            logger.info(f"Error conectando a {self.uri}: {e}")
            raise

    async def _listen_loop(self):
        """Escucha en bucle los mensajes entrantes del servicio"""
        try:
            async for msg in self.ws:
                logger.debug(f"Mensaje recibido: {msg[:80]}...")
                await self._notify_listeners(msg)
        except Exception as e:
            logger.info(f"Error en listener {self.uri}: {e}")

    def add_listener(self, callback):
        """
        Agregar función que se ejecuta al recibir mensaje.
        Puede ser síncrona o asíncrona.
        """
        self._listeners.append(callback)
        logger.debug(f"Listener agregado para {self.name}")

    async def _notify_listeners(self, msg):
        """Notificar a todos los listeners registrados"""
        for cb in self._listeners:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(msg)
                else:
                    cb(msg)
            except Exception as e:
                logger.info(f"Error en listener {cb.__name__}: {e}")

    async def send(self, data):
        """Enviar mensaje al servicio (acepta dict o str)"""
        if not self.ws:
            logger.warning("No conectado, no se puede enviar mensaje.")
            return
        payload = json.dumps(data) if isinstance(data, dict) else str(data)
        try:
            await self.ws.send(payload)
            logger.debug(f"Enviado a {self.name}: {payload[:80]}...")
        except Exception as e:
            logger.info(f"Error enviando a {self.uri}: {e}")

    async def close(self):
        """Cerrar conexión WebSocket"""
        if self.ws:
            await self.ws.close()
            logger.info(f"Desconectado de {self.uri}")
