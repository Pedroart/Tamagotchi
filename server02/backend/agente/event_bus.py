# event_bus.py
import asyncio, inspect, time, os
from logger import logger

class EventBus:
    def __init__(self):
        self._listeners = {}
        self._trace = set()

    def enable_trace(self, *names):
        self._trace.update(names)

    def subscribe(self, event_name, callback):
        self._listeners.setdefault(event_name, [])
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)
        def _unsub():
            try: self._listeners[event_name].remove(callback)
            except ValueError: pass
        return _unsub

    def emit(self, event_name, *args, **kwargs):
        if event_name in self._trace:
            fr = inspect.stack()[1]
            relfile = os.path.relpath(fr.filename)  # convierte a ruta relativa
            origin = f"{relfile}:{fr.lineno}::{fr.function}"
            logger.info(f"{event_name} from {origin} args={args} kw={kwargs}")
        for cb in list(self._listeners.get(event_name, [])):
            if inspect.iscoroutinefunction(cb):
                asyncio.create_task(cb(*args, **kwargs))
            else:
                cb(*args, **kwargs)

event_bus = EventBus()
