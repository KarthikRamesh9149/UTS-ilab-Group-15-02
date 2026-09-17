"""Optional local-only LangChain/LangGraph callback. No raw data retained."""
import threading
import time
from langchain_core.callbacks import BaseCallbackHandler


class LocalGraphCallbacks(BaseCallbackHandler):
    run_inline = True

    def __init__(self, observer):
        self.observer = observer
        self.active = {}
        self.lock = threading.Lock()

    def on_chain_start(self, serialized, inputs, *, run_id, **kwargs):
        with self.lock:
            if run_id in self.active:
                self.observer.errors.append('graph:DuplicateRun')
                return
            self.active[run_id] = time.time_ns(), time.monotonic()

    def finish(self, run_id, status):
        with self.lock:
            started = self.active.pop(run_id, None)
            if started is None:
                self.observer.errors.append('graph:MissingStart')
                return
            self.observer.emit('graph', started[0], started[1], status, {})

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self.finish(run_id, 'ok')

    def on_chain_error(self, error, *, run_id, **kwargs):
        self.finish(run_id, 'timeout' if isinstance(error, TimeoutError) else 'error')
