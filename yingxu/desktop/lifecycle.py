"""One owner loop, bounded incoming work and coalesced progress updates."""
from queue import Empty, Full, Queue
from threading import Event, Lock


class OwnerLoop:
    def __init__(self):
        self.queue = Queue(maxsize=128)
        self.stopping = Event()
        self._progress = {}
        self._lock = Lock()

    def post(self, callback):
        while not self.stopping.is_set():
            try:
                self.queue.put(callback, timeout=.1)
                return True
            except Full:
                pass
        return False

    def progress(self, key, callback):
        with self._lock:
            self._progress[key] = callback

    def tick(self):
        try:
            self.queue.get(timeout=.05)()
        except Empty:
            pass
        with self._lock:
            callbacks = list(self._progress.values())
            self._progress.clear()
        for callback in callbacks:
            callback()
