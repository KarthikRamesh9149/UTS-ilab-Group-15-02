"""Task-local HTTP to private model socket relay. No upstream key or retries.

Only the completion route is forwarded. This is connection plumbing, not a
command executor. Mount only the dedicated socket directory read-only, never
the gateway ledger, credential file, host home, or Docker control socket.
"""
import argparse
import http.client
from http.server import HTTPServer
import socket

from gateway_http import Handler
from gateway_policy import MAX_BODY

MAX_RESPONSE = 16 * 1024 * 1024


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout=90):
        super().__init__('private-model-gateway', timeout=timeout)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class RelayHandler(Handler):
    def do_POST(self):
        self.connection.settimeout(10)
        if self.path != '/v1/chat/completions':
            self.reply(404, {'error': {'message': 'Unknown route'}})
            return
        credentials = self.headers.get_all('Authorization', [])
        if len(credentials) != 1 or not credentials[0].startswith('Bearer '):
            self.reply(401, {'error': {'message': 'Trial credential required'}})
            return
        try:
            lengths = self.headers.get_all('Content-Length', [])
            if self.headers.get('Transfer-Encoding') or len(lengths) != 1:
                raise ValueError()
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise ValueError()
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError()
        except (ValueError, OSError):
            self.reply(400, {'error': {'message': 'Invalid request body'}})
            return
        connection = UnixConnection(self.server.socket_path)
        try:
            connection.request('POST', '/v1/chat/completions', body,
                               {'Authorization': credentials[0], 'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ValueError()
            self.send_response(response.status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(raw)
        except (OSError, ValueError, http.client.HTTPException):
            self.reply(502, {'error': {'message': 'Gateway outcome unavailable; do not retry automatically'}})
        finally:
            connection.close()


def make_relay(socket_path, port=0):
    server = HTTPServer(('127.0.0.1', port), RelayHandler)
    server.socket_path = str(socket_path)
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with make_relay(args.socket, args.port) as server:
        server.serve_forever()
