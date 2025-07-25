# event_bus.py
from typing import Callable, Dict, List
import asyncio
import inspect

class EventBus:
    def __init__(self):
        self._listeners = {}

    def subscribe(self, event_name, callback):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def emit(self, event_name, *args, **kwargs):
        if event_name in self._listeners:
            for cb in self._listeners[event_name]:
                if inspect.iscoroutinefunction(cb):
                    # Si es async, lanzarlo como tarea
                    asyncio.create_task(cb(*args, **kwargs))
                else:
                    # Si es sync, llamarlo directo
                    cb(*args, **kwargs)

# Singleton global
event_bus = EventBus()
