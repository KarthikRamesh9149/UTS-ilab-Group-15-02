"""Trial-scoped loopback front end for LocalModelClient. No cluster routing.

Native host-side clients can use its OpenAI-compatible nonstreaming endpoint.
An isolated task container cannot reach this host loopback automatically.
"""
from contextlib import contextmanager
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
from local_model_client import MAX_BODY


@contextmanager
def serve(client):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def reply(self, status, payload):
            data = json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization', '').encode(), ('Bearer ' + token).encode()):
                self.reply(401, {'error': 'Invalid trial credential'})
                return
            if self.path != '/v1/chat/completions':
                self.reply(404, {'error': 'Unsupported endpoint'})
                return
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError('Chunked requests unsupported')
                if len(self.headers.get_all('Content-Length', [])) != 1:
                    raise ValueError('One content length required')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY:
                    raise ValueError('Invalid request size')
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValueError('Incomplete request')
                body = json.loads(data)
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                response = client.complete(body)
            except (ValueError, TypeError):
                self.reply(400, {'error': 'Invalid local model request or response'})
                return
            except Exception:
                self.reply(503, {'error': 'Local model unavailable or trial access closed'})
                return
            self.reply(200, response)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port) + '/v1', token
    finally:
        client.revoke()
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
