"""Private Unix-socket control channel for a no-network Apptainer sandbox.

This is runtime plumbing, not an agent, and is not yet a qualified all89 backend.
Uses only Python's standard library so the same code runs in a pinned image.
Never expose its listener over TCP or give it the upstream model credential.
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import signal
import socket
import socketserver
import stat
import struct
import subprocess
import tempfile

MAX_FRAME = 8 * 1024 * 1024
MAX_OUTPUT = 1024 * 1024


def read_exact(sock, count):
    chunks = []
    while count:
        data = sock.recv(count)
        if not data:
            raise ConnectionError('Truncated control message')
        chunks.append(data)
        count -= len(data)
    return b''.join(chunks)


def receive(sock):
    size = struct.unpack('!I', read_exact(sock, 4))[0]
    if size > MAX_FRAME:
        raise ValueError('Oversized control message')
    obj = json.loads(read_exact(sock, size))
    if not isinstance(obj, dict):
        raise ValueError('Control message must be an object')
    return obj


def send(sock, obj):
    body = json.dumps(obj).encode()
    if len(body) > MAX_FRAME:
        raise ValueError('Oversized response')
    sock.sendall(struct.pack('!I', len(body)) + body)


def validate_secret(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Token must be a private regular file')
    token = path.read_text().strip()
    if len(token) < 48:
        raise ValueError('Token is too short')
    return token


def request(socket_path, token, payload, timeout=35):
    # Retries are deliberately absent: interrupted execution is ambiguous.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(str(socket_path))
        send(conn, dict(payload, token=token))
        result = receive(conn)
    if not result.get('ok'):
        raise RuntimeError(result.get('error', 'Control request failed'))
    return result


def run_command(message):
    command = message.get('command')
    timeout = message.get('timeout_sec', 30)
    if not isinstance(command, str) or not command:
        raise ValueError('Nonempty command required')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400:
        raise ValueError('Positive bounded timeout required')
    # Clean environment: no inherited credential or host shell configuration.
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'}
    extra = message.get('env', {})
    if not isinstance(extra, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in extra.items()):
        raise ValueError('Invalid environment')
    env.update(extra)
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen(command, shell=True, executable='/bin/sh',
                                cwd=message.get('cwd', '/'), env=env,
                                stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=True)
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        size = output.tell()
        output.seek(0)
        text = output.read(MAX_OUTPUT).decode(errors='replace')
    return {'ok': True, 'return_code': proc.returncode, 'stdout': text,
            'timed_out': timed_out, 'output_bytes': size,
            'output_truncated': size > MAX_OUTPUT}


class ControlHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            message = receive(self.request)
            presented = message.pop('token', None)
            if not isinstance(presented, str) or not hmac.compare_digest(presented, self.server.token):
                send(self.request, {'ok': False, 'error': 'Unauthorised'})
                return
            action = message.get('action')
            if action == 'health':
                result = {'ok': True, 'protocol': 1, 'pid': os.getpid()}
            elif action == 'exec':
                result = run_command(message)
            else:
                raise ValueError('Unknown action')
            send(self.request, result)
        except (ValueError, ConnectionError, OSError, TypeError):
            # Never echo request data, token, environment or traceback.
            try:
                send(self.request, {'ok': False, 'error': 'Invalid or interrupted request'})
            except OSError:
                pass


def serve(socket_path, token_path):
    os.umask(0o077)
    socket_path = Path(socket_path)
    if socket_path.exists() or socket_path.is_symlink():
        raise ValueError('Refusing to replace an existing control socket')
    token = validate_secret(token_path)
    with socketserver.UnixStreamServer(str(socket_path), ControlHandler) as server:
        os.chmod(socket_path, 0o600)
        server.token = token
        server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', required=True)
    parser.add_argument('--token-file', required=True)
    opts = parser.parse_args()
    serve(opts.socket, opts.token_file)
