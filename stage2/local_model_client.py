"""Local-only synchronous llama.cpp client over an owned Unix socket.

No TCP, external provider fallback, automatic retries or API-key discovery.
Use from the trusted controller, not directly from task containers. A future
baseline HTTP/RPC front end must share this one trial-scoped request budget.
"""
from contextlib import nullcontext
import http.client
import json
import math
import os
from pathlib import Path
import socket
import stat
import threading

from local_study import LocalProtocol

MAX_BODY = 4 * 1024 * 1024


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__('localhost', timeout=timeout)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class LocalModelClient:
    def __init__(self, socket_path, *, protocol=None, timeout=120, observer=None):
        self.path = Path(socket_path)
        if not self.path.is_absolute() or self.path.resolve() != self.path:
            raise ValueError('Explicit non-symlink absolute Unix socket path required')
        metadata = self.path.lstat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ValueError('Owned Unix socket required')
        parent = self.path.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise ValueError('Private owned socket directory required')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Positive finite timeout required')
        self.protocol = protocol or LocalProtocol()
        if not isinstance(self.protocol, LocalProtocol):
            raise ValueError('Frozen local protocol required')
        self.timeout, self.observer = timeout, observer
        self._identity = metadata.st_dev, metadata.st_ino
        self.requests = 0
        self.revoked = False
        self._lock = threading.Lock()

    def revoke(self):
        # The lock waits for an in-flight request; no request can start after
        # revocation returns. No background retry or cached response is used.
        with self._lock:
            self.revoked = True

    def complete(self, request):
        body = dict(request)
        extra = body.pop('extra_body', {})
        if not isinstance(extra, dict) or set(extra) - {'top_k'}:
            raise ValueError('Unsupported local extra_body')
        for key, value in extra.items():
            if key in body and body[key] != value:
                raise ValueError('Conflicting local sampling settings')
            body[key] = value
        if body.get('stream', False) is not False:
            raise ValueError('This local client requires nonstreaming requests')
        self.protocol.validate_request(body)
        if not isinstance(body.get('messages'), list) or not body['messages']:
            raise ValueError('Messages required')
        encoded = json.dumps(body, allow_nan=False).encode()
        if len(encoded) > MAX_BODY:
            raise ValueError('Local request exceeds byte bound')
        with self._lock:
            if self.revoked:
                raise RuntimeError('Trial model access revoked')
            if self.requests >= self.protocol.max_model_requests:
                raise RuntimeError('Trial model request budget exhausted')
            metadata = self.path.lstat()
            if (metadata.st_dev, metadata.st_ino) != self._identity:
                raise RuntimeError('Model socket identity changed')
            self.requests += 1  # Failed attempts count too; never silently replay.
            observation = self.observer.operation('generation', {'requests': 1}) if self.observer else nullcontext({})
            with observation as metrics:
                connection = UnixConnection(str(self.path), self.timeout)
                try:
                    connection.request('POST', '/v1/chat/completions', encoded,
                                       {'Content-Type': 'application/json'})
                    response = connection.getresponse()
                    raw = response.read(MAX_BODY + 1)
                    if response.status != 200:
                        raise RuntimeError('Local model HTTP status ' + str(response.status))
                    if len(raw) > MAX_BODY:
                        raise ValueError('Local response exceeds byte bound')
                    result = json.loads(raw)
                    if result.get('model') != self.protocol.model or not result.get('choices'):
                        raise ValueError('Local response model or choices mismatch')
                    usage = result.get('usage', {})
                    for source, target in [('prompt_tokens', 'input_tokens'), ('completion_tokens', 'output_tokens')]:
                        if source in usage:
                            if type(usage[source]) is not int or usage[source] < 0:
                                raise ValueError('Invalid token usage')
                            metrics[target] = usage[source]
                    # Missing token fields stay missing, never fabricated as 0.
                    return result
                finally:
                    connection.close()
