from collections import defaultdict
import threading

class EventBus:
    def __init__(self):
        self.subs = defaultdict(list)
        self.lock = threading.Lock()

    def subscribe(self, topic, callback):
        with self.lock:
            self.subs[topic].append(callback)

    def publish(self, topic, data=None):
        with self.lock:
            for callback in self.subs[topic]:
                threading.Thread(target=callback, args=(data,), daemon=True).start()
