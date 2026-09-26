"""Cooperative dispatch stop. Never cancel an in-progress scored attempt."""
from pathlib import Path
import signal
from scored_gateway import durable_json


class BoundaryStop:
    def __init__(self, runtime):
        self.marker = Path(runtime) / 'operator-stop-request.json'
        self.signalled = False
        self.previous = None

    def requested(self):
        if self.marker.is_symlink():
            raise ValueError('Operator stop marker must not be a symlink')
        if self.signalled and not self.marker.exists():
            # Outside the signal handler, at a dispatch check. A fresh runner
            # must not silently forget an operator's completed boundary stop.
            durable_json(self.marker, dict(source='SIGUSR1', automatic_resume=False))
        return self.signalled or self.marker.exists()

    def _receive(self, signum, frame):
        self.signalled = True

    def __enter__(self):
        self.previous = signal.signal(signal.SIGUSR1, self._receive)
        return self

    def __exit__(self, *args):
        signal.signal(signal.SIGUSR1, self.previous)
