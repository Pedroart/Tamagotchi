# event_bus.py
from typing import Callable, Dict, List

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Suscribe una función a un evento."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, *args, **kwargs):
        """Lanza un evento y notifica a todos los suscriptores."""
        if event_name in self._listeners:
            for cb in self._listeners[event_name]:
                cb(*args, **kwargs)

# Singleton global
event_bus = EventBus()
