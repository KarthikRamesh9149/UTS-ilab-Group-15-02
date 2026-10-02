"""Liveness framing around the unchanged authenticated composite handoff.

Only the owner writes data or explicit completion. The heartbeat thread has no
audit, filesystem, provider or admission work. Idle timeouts bound an
unresponsive transport, not a healthy synchronous predecessor audit. Inner
commitments, real EOF, normal SSH exit and durable service acceptance remain
independent requirements. This module never retries or resumes an operation.
"""
import os
import queue
import select
import socket
import stat
import struct
import threading
import time

MAGIC = b'UTS-BASELINE-LIVENESS-20261002\n'
CHUNK = 64 * 1024
IDLE_SECONDS = 4500
HEARTBEAT_SECONDS = 30
_POLL = .05


def _identity(stream):
    if stream.closed: raise ValueError('Open owned transport descriptor required')
    value = os.fstat(stream.fileno())
    if not (stat.S_ISFIFO(value.st_mode) or stat.S_ISSOCK(value.st_mode)):
        raise ValueError('Actual pipe or socket required for baseline transport')
    # Darwin changes socket permission bits on half-close. Type/identity stay
    # fixed; the separate native Unix-path/peer checks authenticate ownership.
    return (value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode), value.st_uid, value.st_gid, value.st_nlink)


class Writer:
    """Exclusive unbuffered owned pipe, with bounded cancellable writes."""
    def __init__(self, stream, *, peer=None):
        self.stream = stream; self.identity = _identity(stream)
        self.owner = threading.get_ident(); self.lock = threading.Lock()
        self.stop = threading.Event(); self.error = None
        self.thread = None; self.entered = False; self.ended = False
        self.blocking = os.get_blocking(stream.fileno())
        self.peer = peer

    def fileno(self):
        if _identity(self.stream) != self.identity: raise ValueError('Transport descriptor changed')
        return self.stream.fileno()

    def _owner(self):
        if threading.get_ident() != self.owner: raise ValueError('Only the owning sender may write handoff data')
        if not self.entered or self.ended: raise ValueError('Active incomplete transport required')
        if self.error is not None: raise ValueError('Baseline heartbeat transport failed') from None

    def _write(self, raw, *, heartbeat=False):
        view = memoryview(raw); deadline = time.monotonic() + IDLE_SECONDS
        while view:
            if heartbeat and self.stop.is_set():
                if len(view) != len(raw): raise ValueError('Interrupted heartbeat frame')
                return
            if self.peer is not None:
                if self.peer.error is not None: raise ValueError('Baseline peer transport failed')
                deadline = max(deadline, self.peer.last_activity + IDLE_SECONDS)
            fd = self.fileno(); left = deadline - time.monotonic()
            if left <= 0: raise TimeoutError('Baseline output transport unresponsive')
            if not select.select([], [fd], [], min(_POLL, left))[1]: continue
            try: count = os.write(fd, view[:CHUNK])
            except BlockingIOError: continue
            if count <= 0: raise ValueError('Baseline pipe did not accept data')
            view = view[count:]; deadline = time.monotonic() + IDLE_SECONDS

    def _heartbeat(self):
        try:
            while not self.stop.wait(HEARTBEAT_SECONDS):
                while not self.stop.is_set():
                    if not self.lock.acquire(timeout=_POLL): continue
                    try:
                        if not self.stop.is_set(): self._write(b'H\0\0\0\0', heartbeat=True)
                    finally: self.lock.release()
                    break
        except BaseException as error:
            self.error = error; self.stop.set()

    def __enter__(self):
        if self.entered or threading.get_ident() != self.owner:
            raise ValueError('One owned transport lifetime required')
        self.entered = True
        try:
            os.set_blocking(self.fileno(), False); self._write(MAGIC)
            self.thread = threading.Thread(target=self._heartbeat, name='baseline-transport-liveness')
            self.thread.start(); return self
        except BaseException:
            self.entered = False
            os.set_blocking(self.fileno(), self.blocking)
            raise

    def write(self, raw):
        self._owner(); view = memoryview(raw); size = len(view)
        with self.lock:
            self._owner()
            while view:
                part = view[:CHUNK]
                self._write(b'D' + struct.pack('!I', len(part)) + bytes(part))
                view = view[len(part):]
        return size

    def flush(self):
        self._owner(); self.fileno()  # Writes go directly to the unbuffered FD.

    def _join(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(2)
            if self.thread.is_alive(): raise RuntimeError('Owned heartbeat thread did not stop')

    def finish(self):
        self._owner(); self._join(); self._owner()
        with self.lock: self._write(b'E\0\0\0\0')
        self.ended = True

    def __exit__(self, *exc):
        try: self._join()
        finally:
            self.entered = False
            os.set_blocking(self.fileno(), self.blocking)
        # No automatic E: an interrupted/failed sender must remain incomplete.


class Reader:
    """Strip liveness only; never invent inner bytes, commitment or EOF."""
    def __init__(self, stream, *, progress=None, cancel=None):
        self.stream = stream; self.identity = _identity(stream)
        self.started = self.ended = self.failed = False; self.buffer = b''
        self.progress = progress; self.cancel = cancel

    def fileno(self):
        if _identity(self.stream) != self.identity: raise ValueError('Transport descriptor changed')
        return self.stream.fileno()

    def _raw(self, size):
        # The consumer may spend hours authenticating the preceding archive.
        # Only an actual waiting read starts an unresponsive-input window.
        deadline = time.monotonic() + IDLE_SECONDS
        while True:
            if self.cancel is not None and self.cancel.is_set():
                raise InterruptedError('Owned transport reader cancelled')
            fd = self.fileno(); left = deadline - time.monotonic()
            if left <= 0: raise TimeoutError('Baseline input transport unresponsive')
            if not select.select([fd], [], [], min(left, _POLL))[0]: continue
            try: raw = os.read(fd, size)
            except BlockingIOError: continue
            if raw and self.progress is not None: self.progress()
            return raw

    def _exact(self, size):
        answer = bytearray()
        while len(answer) < size:
            raw = self._raw(size - len(answer))
            if not raw: raise ValueError('Truncated baseline transport')
            answer.extend(raw)
        return bytes(answer)

    def read(self, size):
        if type(size) is not int or not 0 < size <= CHUNK or self.failed:
            raise ValueError('Bounded active baseline transport read required')
        try:
            if not self.started:
                if self._exact(len(MAGIC)) != MAGIC: raise ValueError('Exact baseline transport prefix required')
                self.started = True
            while not self.buffer and not self.ended:
                frame = self._exact(5); kind = frame[:1]; count = struct.unpack('!I', frame[1:])[0]
                if kind == b'H' and count == 0: continue
                if kind == b'D' and 0 < count <= CHUNK: self.buffer = self._exact(count)
                elif kind == b'E' and count == 0:
                    if self._raw(1): raise ValueError('Bytes after baseline transport completion')
                    self.ended = True
                else: raise ValueError('Invalid baseline transport frame')
            result, self.buffer = self.buffer[:size], self.buffer[size:]
            return result
        except BaseException:
            self.failed = True; raise


def ready_line(stream, limit):
    """Read precisely one readiness line, leaving coalesced framing untouched."""
    identity = _identity(stream); result = bytearray()
    deadline = time.monotonic() + IDLE_SECONDS
    while len(result) < limit:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([stream.fileno()], [], [], left)[0]:
            raise TimeoutError('Baseline readiness unresponsive')
        if _identity(stream) != identity: raise ValueError('Readiness descriptor changed')
        raw = os.read(stream.fileno(), 1)
        if not raw: raise ValueError('Truncated baseline readiness')
        result.extend(raw)
        if raw == b'\n': return bytes(result)
    raise ValueError('Baseline readiness metadata limit exceeded')


def reply_bytes(reader, limit):
    result = bytearray()
    while len(result) < limit:
        raw = reader.read(1)
        if not raw: raise ValueError('Missing committed baseline acknowledgement')
        result.extend(raw)
        if raw == b'\n':
            if reader.read(1): raise ValueError('Extra baseline acknowledgement data')
            return bytes(result)
    raise ValueError('Baseline acknowledgement metadata limit exceeded')


class ReplyReceiver:
    """Bounded transport-only reader; the owner validates acceptance later.

    Draining reverse liveness allows a sender blocked by a legitimately busy
    native audit to distinguish a live peer from a silent connection. No
    metadata schema, source, audit, or admission checks occur in this thread.
    """
    def __init__(self, stream, limit):
        self.stream = stream; self.limit = limit; self.stop = threading.Event()
        self.last_activity = time.monotonic(); self.error = None; self.result = None
        self.thread = threading.Thread(target=self._receive, name='baseline-reply-transport')

    def _progress(self): self.last_activity = time.monotonic()

    def _receive(self):
        try:
            self.result = reply_bytes(Reader(self.stream, progress=self._progress, cancel=self.stop), self.limit)
        except BaseException as error:
            self.error = error

    def __enter__(self):
        self.thread.start(); return self

    def wait(self):
        while self.thread.is_alive(): self.thread.join(_POLL)
        if self.error is not None: raise ValueError('Incomplete baseline reply transport') from None
        if self.result is None: raise ValueError('Missing baseline reply transport')
        return self.result

    def __exit__(self, *exc):
        self.stop.set(); self.thread.join(2)
        if self.thread.is_alive(): raise RuntimeError('Owned reply reader did not stop')


class StreamReceiver:
    """Bounded reverse transport for reporting, with owner-only consumption.

    The thread strips framing and tracks actual peer bytes only. Metadata,
    archive writes, hashes and acceptance checks remain on the owning thread.
    Two chunks may be queued; reader and consumer hold at most one more each.
    """
    def __init__(self, stream):
        self.stream = stream; self.owner = threading.get_ident()
        self.stop = threading.Event(); self.done = threading.Event()
        self.pending = queue.Queue(maxsize=2); self.buffer = b''
        self.last_activity = time.monotonic(); self.error = None; self.entered = False
        self.reader = Reader(stream, progress=self._progress, cancel=self.stop)
        self.thread = threading.Thread(target=self._receive, name='baseline-report-transport')

    def _progress(self): self.last_activity = time.monotonic()

    def fileno(self): return self.reader.fileno()

    def _receive(self):
        try:
            while not self.stop.is_set():
                raw = self.reader.read(CHUNK)
                if not raw: return
                while not self.stop.is_set():
                    try: self.pending.put(raw, timeout=_POLL); break
                    except queue.Full: continue
        except BaseException as error:
            self.error = error
        finally: self.done.set()

    def __enter__(self):
        if self.entered or self.thread.ident is not None or threading.get_ident() != self.owner:
            raise ValueError('One owned reporting transport lifetime required')
        self.entered = True; self.thread.start(); return self

    def read(self, size):
        if (not self.entered or threading.get_ident() != self.owner
                or type(size) is not int or not 0 < size <= CHUNK):
            raise ValueError('Bounded owning-thread reporting read required')
        self.fileno()
        while not self.buffer:
            try: self.buffer = self.pending.get(timeout=_POLL)
            except queue.Empty:
                if not self.done.is_set(): continue
                # Completion may race the timed-out get. Once done is set the
                # producer cannot enqueue again, so drain its final bytes first.
                if not self.pending.empty(): continue
                if self.error is not None: raise ValueError('Incomplete reporting transport') from None
                return b''
        result, self.buffer = self.buffer[:size], self.buffer[size:]
        return result

    def __exit__(self, *exc):
        self.stop.set(); self.thread.join(2); self.entered = False
        if self.thread.is_alive(): raise RuntimeError('Owned reporting reader did not stop')


class Acknowledgement:
    """Socket-like owner facade; loss after durable acceptance is not a replay."""
    def __init__(self, writer, connection):
        self.writer = writer; self.connection = connection

    def sendall(self, raw):
        try: self.writer.write(raw)
        except (OSError, ValueError, RuntimeError):
            raise OSError('Baseline acknowledgement transport unavailable') from None

    def shutdown(self, how):
        if how != socket.SHUT_WR: raise ValueError('Only acknowledgement half-close is supported')
        try:
            self.writer.finish()
        except (OSError, ValueError, RuntimeError):
            raise OSError('Baseline acknowledgement completion unavailable') from None
        finally: self.connection.shutdown(socket.SHUT_WR)


def relay(incoming, outgoing, connection):
    """Bounded duplex forwarding, including peer liveness during backpressure.

    Framing and authenticated commitments are checked by the endpoints. The
    relay cannot produce an acknowledgement or heartbeat of its own.
    """
    streams = (incoming, outgoing)
    identities = tuple(_identity(s) for s in streams)
    old_blocking = tuple(os.get_blocking(s.fileno()) for s in streams)
    fd_in, fd_out = (s.fileno() for s in streams)
    original_timeout = connection.gettimeout()
    request = bytearray(); response = bytearray()
    input_ended = peer_ended = half_closed = False
    deadline = time.monotonic() + IDLE_SECONDS
    try:
        for fd in (fd_in, fd_out): os.set_blocking(fd, False)
        connection.setblocking(False)
        while not peer_ended or response:
            if tuple(_identity(s) for s in streams) != identities:
                raise ValueError('Relay transport descriptor changed')
            if input_ended and not request and not half_closed:
                connection.shutdown(socket.SHUT_WR); half_closed = True
            readers = ([] if input_ended or len(request) >= CHUNK else [fd_in])
            if not peer_ended and len(response) < CHUNK: readers.append(connection)
            writers = ([connection] if request else []) + ([fd_out] if response else [])
            left = deadline - time.monotonic()
            if left <= 0: raise TimeoutError('Duplex baseline transport unresponsive')
            ready_read, ready_write, _ = select.select(readers, writers, [], left)
            if not ready_read and not ready_write: raise TimeoutError('Duplex baseline transport unresponsive')
            for ready in ready_read:
                try:
                    raw = (os.read(fd_in, CHUNK - len(request)) if ready == fd_in
                        else connection.recv(CHUNK - len(response)))
                except BlockingIOError: continue
                if raw:
                    (request if ready == fd_in else response).extend(raw)
                    deadline = time.monotonic() + IDLE_SECONDS
                elif ready == fd_in: input_ended = True
                else:
                    if not half_closed: raise ValueError('Native peer ended before complete sender EOF')
                    peer_ended = True
            for ready in ready_write:
                data = request if ready is connection else response
                try: count = connection.send(data) if ready is connection else os.write(fd_out, data)
                except BlockingIOError: continue
                if count <= 0: raise ValueError('Relay failed to forward transport bytes')
                del data[:count]; deadline = time.monotonic() + IDLE_SECONDS
    finally:
        connection.settimeout(original_timeout)
        for stream, blocking in zip(streams, old_blocking): os.set_blocking(stream.fileno(), blocking)
