"""Bounded read-only receipt polling. Never retries a generation request."""
import time
from openrouter_transport import TransportError


def read_receipt(reader, identifier, *, deadline_seconds=40, max_attempts=12,
                 clock=time.monotonic, sleep=time.sleep):
    if not 0 < deadline_seconds <= 60 or not 1 <= max_attempts <= 16:
        raise ValueError('Invalid receipt polling bounds')
    deadline = clock() + deadline_seconds
    for attempt in range(max_attempts):
        try:
            return reader(identifier)
        except TransportError:
            remaining = deadline - clock()
            if attempt + 1 >= max_attempts or remaining <= 0:
                raise TransportError('Receipt unavailable; generation must not be replayed') from None
            sleep(min(.5 * 2 ** attempt, 4, remaining))
            if clock() >= deadline:
                raise TransportError('Receipt deadline reached; reservation retained') from None
    raise AssertionError('Unreachable')
