import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest

from secure_transport import MAX_FRAME, receive, request, validate_secret


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='uts-uds-', dir='/tmp')
        self.root = Path(self.temp.name)
        self.token = secrets.token_hex(32)
        self.key = self.root / 'token'
        self.key.write_text(self.token)
        self.key.chmod(0o600)
        self.sock = self.root / 'control.sock'
        self.process = subprocess.Popen([sys.executable,
            str(Path(__file__).with_name('secure_transport.py')),
            '--socket', str(self.sock), '--token-file', str(self.key)])
        for _ in range(100):
            if self.sock.exists():
                return
            if self.process.poll() is not None:
                self.fail('Server failed to start')
            time.sleep(.02)
        self.fail('Server startup timed out')

    def tearDown(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.temp.cleanup()

    def test_authenticated_health_and_private_socket(self):
        self.assertTrue(request(self.sock, self.token, {'action':'health'})['ok'])
        self.assertEqual(self.sock.stat().st_mode & 0o777, 0o600)

    def test_wrong_token_cannot_execute(self):
        marker = self.root / 'must-not-exist'
        with self.assertRaises(RuntimeError):
            request(self.sock, 'wrong', {'action':'exec','command':f'touch {marker}'})
        self.assertFalse(marker.exists())

    def test_command_and_nonzero_status(self):
        result = request(self.sock, self.token, {'action':'exec', 'command':'printf test; exit 7'})
        self.assertEqual(result['stdout'], 'test')
        self.assertEqual(result['return_code'], 7)

    def test_timeout_terminates_command(self):
        result = request(self.sock, self.token, {'action':'exec','command':'sleep 10','timeout_sec':.05})
        self.assertTrue(result['timed_out'])
        self.assertNotEqual(result['return_code'], 0)

    def test_no_inherited_secret(self):
        result = request(self.sock, self.token, {'action':'exec','command':'printf "%s" "${OPENROUTER_API_KEY-unset}"'})
        self.assertEqual(result['stdout'], 'unset')

    def test_rejects_public_token_file(self):
        self.key.chmod(0o644)
        with self.assertRaises(ValueError):
            validate_secret(self.key)

    def test_rejects_oversized_frame_before_body(self):
        first, second = socket.socketpair()
        try:
            first.sendall(struct.pack('!I', MAX_FRAME + 1))
            with self.assertRaises(ValueError):
                receive(second)
        finally:
            first.close(); second.close()


if __name__ == '__main__':
    unittest.main()
