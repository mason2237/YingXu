"""Single bounded worker; it never owns workspace state or writes to stdout."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4


class WorkContext:
    def __init__(self, loop, progress):
        self.stop = Event()
        self.key = uuid4().hex
        self.loop = loop
        self.callback = progress
        self._last = 0
        self._phase = None

    def report(self, done, total, message, phase):
        now = monotonic()
        if not self.stop.is_set() and (phase != self._phase or done == total or now - self._last >= .08):
            self._last, self._phase = now, phase
            self.loop.progress(self.key, lambda: self.callback(done, total, message, phase))


class ThreadTasks:
    def __init__(self, loop):
        self.loop = loop
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='workspace')
        self.active = None

    def start(self, work, progress, complete, failed):
        if self.active is not None:
            raise RuntimeError('Task runner already occupied')
        context = WorkContext(self.loop, progress)
        self.active = context
        future = self.pool.submit(work, context)

        def finished(result):
            def deliver():
                self.active = None
                try:
                    value = result.result()
                except Exception as error:
                    failed(error)
                else:
                    complete(value)
            self.loop.post(deliver)

        future.add_done_callback(finished)
        return context

    def close(self):
        if self.active:
            self.active.stop.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
