"""Framed reporting liveness, not a benchmark deadline or an admission token.

Every data write is flushed, including gzip's closing trailer. Heartbeats
describe only this process/connection being alive; they never mean an audit
passed. Only an explicit final frame followed by a normal SSH exit succeeds.
"""
import json
import selectors
import struct
import threading
import time

MAGIC = b'UTS-REPORTING-RECOVERY-TRANSPORT-1\n'
CHUNK = 65536
IDLE_SECONDS = 4500
HEARTBEAT_SECONDS = 30
ERRORS = frozenset({'ValueError', 'TypeError', 'OSError', 'PermissionError',
    'FileNotFoundError', 'FileExistsError', 'TimeoutError', 'BrokenPipeError',
    'EOFError', 'RuntimeError', 'KeyboardInterrupt', 'CancelledError', 'OtherError'})
STAGES = frozenset({'bootstrap', 'preservation', 'handoff', 'audit', 'inventory',
    'archive', 'audit_recheck', 'session_exit', 'final_recheck', 'commitment'})


def diagnostic(stage, error):
    if stage not in STAGES:
        raise ValueError('Fixed reporting failure stage required')
    name = type(error).__name__
    return dict(stage=stage, error_class=name if name in ERRORS else 'OtherError')


def valid_diagnostic(value):
    return (type(value) is dict and set(value) == {'stage', 'error_class'}
        and type(value['stage']) is str and value['stage'] in STAGES
        and type(value['error_class']) is str and value['error_class'] in ERRORS)


class NativeFailure(ValueError):
    def __init__(self, value):
        if not valid_diagnostic(value):
            raise ValueError('Invalid native diagnostic')
        self.diagnostic = dict(value)
        super().__init__('Reporting-only operation failed; preserve evidence')


class Writer:
    """Only the owned heartbeat thread writes alongside the owning audit task."""
    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.error = None
        self.finished = False

    def _raw(self, raw):
        remaining = memoryview(raw)
        while remaining:
            count = self.stream.write(remaining)
            if count is None or count <= 0:
                raise BrokenPipeError('Incomplete reporting frame')
            remaining = remaining[count:]
        self.stream.flush()

    def _frame(self, tag, raw=b''):
        if self.finished or self.error is not None:
            raise BrokenPipeError('Reporting connection unavailable')
        with self.lock:
            self._raw(tag + struct.pack('!I', len(raw)) + raw)

    def _heartbeat(self):
        while not self.stop.wait(HEARTBEAT_SECONDS):
            try:
                self._frame(b'H')
            except BaseException as error:
                self.error = error
                self.stop.set()

    def start(self):
        if self.thread is not None or self.finished:
            raise ValueError('Transport cannot restart')
        self._raw(MAGIC)
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()
        return self

    def write(self, raw):
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            raise TypeError('Reporting stream requires bytes')
        for offset in range(0, len(raw), CHUNK):
            self._frame(b'D', bytes(raw[offset:offset + CHUNK]))
        return len(raw)

    def flush(self):
        with self.lock:
            if self.error is not None:
                raise BrokenPipeError('Reporting liveness failed')
            self.stream.flush()

    def close_heartbeat(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(35)
            if self.thread.is_alive():
                raise RuntimeError('Owned reporting heartbeat did not finish')

    def finish(self):
        self.close_heartbeat()
        self._frame(b'E')
        self.finished = True

    def fail(self, value):
        self.close_heartbeat()
        if not valid_diagnostic(value):
            raise ValueError('Fixed native diagnostic required')
        self._frame(b'F', json.dumps(value, sort_keys=True).encode())
        self.finished = True


class Reader:
    """Bounded frames and a rolling *unresponsive* window, never a total cutoff."""
    def __init__(self, stream):
        self.stream = stream
        self.buffer = bytearray()
        self.ended = False
        self.deadline = time.monotonic() + IDLE_SECONDS
        if self._raw(len(MAGIC)) != MAGIC:
            raise ValueError('Exact reporting transport required')

    def _raw(self, count):
        import os
        result = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(self.stream, selectors.EVENT_READ)
            while len(result) < count:
                left = self.deadline - time.monotonic()
                if left <= 0 or not selector.select(left):
                    raise TimeoutError('Reporting transport unresponsive')
                raw = os.read(self.stream.fileno(), min(CHUNK, count - len(result)))
                if not raw:
                    raise EOFError('Reporting commitment missing')
                result.extend(raw)
                self.deadline = time.monotonic() + IDLE_SECONDS
        return bytes(result)

    def _frame(self):
        if self.ended:
            raise ValueError('No frames after reporting completion')
        header = self._raw(5)
        tag, count = header[:1], struct.unpack('!I', header[1:])[0]
        if (tag not in (b'H', b'D', b'E', b'F') or count > CHUNK
                or tag in (b'H', b'E') and count != 0
                or tag == b'D' and count == 0 or tag == b'F' and not 0 < count <= 512):
            raise ValueError('Invalid reporting frame')
        raw = self._raw(count)
        if tag == b'F':
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result: raise ValueError('Duplicate diagnostic key')
                    result[key] = value
                return result
            raise NativeFailure(json.loads(raw, object_pairs_hook=pairs))
        if tag == b'E': self.ended = True
        return tag, raw

    def exact(self, count):
        if type(count) is not int or not 0 <= count <= 64 * 1024 * 1024:
            raise ValueError('Bounded reporting read required')
        while len(self.buffer) < count:
            tag, raw = self._frame()
            if tag == b'E': raise EOFError('Early reporting completion')
            if tag == b'D': self.buffer.extend(raw)
        raw = bytes(self.buffer[:count]); del self.buffer[:count]
        return raw

    def metadata(self, loads):
        count = struct.unpack('!Q', self.exact(8))[0]
        if not 0 < count <= 64 * 1024 * 1024:
            raise ValueError('Reporting metadata window exceeded')
        raw = self.exact(count)
        return loads(raw), raw

    def finish(self):
        if self.buffer: raise ValueError('Extra inner reporting data')
        while True:
            tag, _ = self._frame()
            if tag == b'E': return
            if tag != b'H': raise ValueError('Extra reporting frame before exit')
