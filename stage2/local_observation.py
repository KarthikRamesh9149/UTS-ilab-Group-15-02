"""Passive detailed timing hooks. No prompt/output capture or cloud calls."""
import asyncio
from contextlib import contextmanager
import time


class DetailObserver:
    def __init__(self, recorder):
        self.recorder = recorder
        self.errors = []

    def emit(self, kind, started_ns, started, status, metrics):
        try:
            self.recorder(kind=kind, started_ns=started_ns, ended_ns=time.time_ns(),
                          seconds=time.monotonic() - started, status=status, metrics=metrics)
        except Exception as error:
            # Evidence admission must reject missing observations, but tracing
            # failures do not change the executed command or model response.
            self.errors.append(kind + ':' + type(error).__name__)

    @contextmanager
    def operation(self, kind, metrics=None):
        counts = dict(metrics or {})
        started_ns, started = time.time_ns(), time.monotonic()
        status = 'ok'
        try:
            yield counts
        except BaseException as error:
            status = ('interrupted' if isinstance(error, asyncio.CancelledError) else
                      'timeout' if isinstance(error, TimeoutError) else 'error')
            raise
        finally:
            self.emit(kind, started_ns, started, status, counts)
