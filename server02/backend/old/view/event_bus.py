# event_bus.py
import asyncio, inspect, time

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
            origin = f"{fr.filename}:{fr.lineno}::{fr.function}"
            print(f"[TRACE] {time.strftime('%H:%M:%S')} {event_name} from {origin} args={args} kw={kwargs}")
        for cb in list(self._listeners.get(event_name, [])):
            if inspect.iscoroutinefunction(cb):
                asyncio.create_task(cb(*args, **kwargs))
            else:
                cb(*args, **kwargs)

event_bus = EventBus()
