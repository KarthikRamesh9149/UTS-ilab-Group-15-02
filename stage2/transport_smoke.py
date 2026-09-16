"""Deterministic compute-node test; no agent, credential or model request."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

from secure_transport import request


def main(image):
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix='uts-control-', dir='/scratch'))
    control = root / 'control'
    control.mkdir(mode=0o700)
    token = secrets.token_hex(32)
    key = root / 'token'
    key.write_text(token)
    key.chmod(0o600)
    canary = root / 'host-only-canary'
    canary.write_text('must-not-be-visible')
    sock = control / 'control.sock'
    source = Path(__file__).with_name('secure_transport.py').resolve()
    args = ['apptainer', 'exec', '--cleanenv', '--containall', '--writable-tmpfs',
            '--no-mount', 'home,tmp,bind-paths,hostfs,cwd',
            '--net', '--network', 'none', '--fakeroot',
            '--bind', str(control) + ':/control',
            '--bind', str(key) + ':/run/control-token:ro',
            '--bind', str(source) + ':/run/control-server.py:ro',
            image, 'python', '/run/control-server.py',
            '--socket', '/control/control.sock', '--token-file', '/run/control-token']
    with (root / 'server.log').open('w') as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(300):
                if sock.exists():
                    break
                if process.poll() is not None:
                    raise RuntimeError('Container exited; inspect ' + str(root / 'server.log'))
                time.sleep(.1)
            checks = {}
            checks['authenticated_health'] = request(sock, token, {'action': 'health'})['ok']
            try:
                request(sock, 'wrong', {'action': 'exec', 'command': 'touch /control/unauthorised'})
                checks['reject_wrong_token'] = False
            except RuntimeError:
                checks['reject_wrong_token'] = not (control / 'unauthorised').exists()
            command = 'test ! -e /shared/homes && test ! -e ' + str(canary) + ' && test "$(id -u)" = 0 && printf fixture > /control/fixture'
            result = request(sock, token, {'action': 'exec', 'command': command})
            checks['root_and_mount_isolation'] = result['return_code'] == 0
            checks['file_roundtrip'] = (control / 'fixture').read_text() == 'fixture'
            result = request(sock, token, {'action': 'exec', 'command': 'cat /proc/net/route; cat /proc/net/tcp; cat /proc/net/tcp6'})
            # Each file has only its header: no routes or TCP endpoints.
            checks['no_routes_or_tcp_endpoints'] = len(result['stdout'].splitlines()) == 3
            checks['private_socket'] = sock.stat().st_mode & 0o777 == 0o600
            print(json.dumps({'scope': 'no-network transport fixture only', 'checks': checks,
                              'scratch': str(root)}, indent=2))
            if not all(checks.values()):
                raise RuntimeError('Transport fixture failed')
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            key.unlink()


if __name__ == '__main__':
    main(sys.argv[1])
