"""Wait for an actual post-audit byte without changing archived framing.

Only the fixed live service may consume this adapter. A pipe/socket is not
peer authentication; pinned SSH and the real archived reader remain required.
No archive is saved, copied, reconstructed or treated as an admission receipt.
"""
import os

import matched_repeat_stream as wire


def _identity(stream):
    wire.pipe_only(stream)
    state = os.fstat(stream.fileno())
    return (state.st_dev, state.st_ino, state.st_mode, state.st_uid, state.st_gid)


class _Prefix:
    __slots__ = ('_stream', '_prefix', '_identity')

    def __init__(self, stream, prefix, identity):
        self._stream, self._prefix, self._identity = stream, prefix, identity

    def fileno(self):
        if _identity(self._stream) != self._identity:
            raise ValueError('Live baseline stream identity changed')
        return self._stream.fileno()

    def read(self, size=-1):
        self.fileno()
        if type(size) is not int or size < -1:
            raise ValueError('Exact stream read size required')
        if size == 0: return b''
        prefix, self._prefix = self._prefix, b''
        if size > 0 and len(prefix) == size: return prefix
        raw = self._stream.read(-1 if size == -1 else size-len(prefix))
        if not isinstance(raw, bytes): raise ValueError('Binary live baseline transport required')
        self.fileno()
        return prefix + raw


def wait_for_sender(stream):
    """One actual byte means the fixed sender's pre-header audit has ended.

    This grants no authority. The unchanged archived reader still authenticates
    the entire exact header/archive/commitment/EOF, actual native audit and
    witness; its ancestor check now occurs after the sender's required audit.
    """
    before = _identity(stream)
    first = stream.read(1)
    if first != wire.MAGIC[:1] or _identity(stream) != before:
        raise ValueError('Actual post-audit baseline header byte required')
    return _Prefix(stream, first, before)
