"""Sequential, loopback-only OpenAI-compatible gateway HTTP boundary.

Host orchestrator supplies a trusted gateway factory; no live defaults. TCP is
host-loopback only. A private Unix socket supports a dedicated gateway container
without publishing host ports or giving the task upstream credentials.
"""
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import socket
import socketserver
import stat

from budget_ledger import BudgetExceeded
from gateway_core import GatewayError
from gateway_policy import MAX_BODY


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *args):
        # Request lines and error objects can contain secrets. Ledger is the
        # source of accounting evidence; do not log raw HTTP requests here.
        pass

    def reply(self, status, value):
        body = json.dumps(value, allow_nan=False,
                          default=lambda v: float(v) if isinstance(v, Decimal) else str(v)).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.connection.settimeout(10)
        if self.path != '/v1/chat/completions':
            self.reply(404, {'error': {'message':'Unknown route'}})
            return
        credentials = self.headers.get_all('Authorization', [])
        if len(credentials) != 1 or not credentials[0].startswith('Bearer '):
            self.reply(401, {'error': {'message':'Trial credential required'}})
            return
        lengths = self.headers.get_all('Content-Length', [])
        try:
            if self.headers.get('Transfer-Encoding') or len(lengths) != 1:
                raise ValueError('Unsupported framing')
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise ValueError('Invalid length')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete body')
            payload = json.loads(raw)
        except (ValueError, OSError):
            self.reply(400, {'error': {'message':'Invalid request body'}})
            return
        try:
            if self.server.gateway is None:
                # Construct ledger in the serving thread (SQLite affinity).
                self.server.gateway = self.server.factory()
            response = self.server.gateway.complete(credentials[0][7:], payload)
            self.reply(200, response)
        except BudgetExceeded:
            self.reply(402, {'error': {'message':'Budget admission blocked'}})
        except ValueError:
            self.reply(400, {'error': {'message':'Unsupported request'}})
        except GatewayError:
            self.reply(403, {'error': {'message':'Gateway request blocked; inspect host accounting'}})
        except Exception:
            self.reply(502, {'error': {'message':'Gateway outcome unavailable; do not retry automatically'}})


def make_server(factory, port=0):
    server = HTTPServer(('127.0.0.1', port), Handler)
    server.factory = factory
    server.gateway = None
    return server


class UnixHTTPServer(HTTPServer):
    address_family = socket.AF_UNIX

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'private-model-gateway'
        self.server_port = 0


def make_unix_server(factory, path):
    path = Path(path)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Socket parent must be an owned private directory')
    if path.exists() or path.is_symlink():
        raise ValueError('Refusing to replace an existing socket path')
    server = UnixHTTPServer(str(path), Handler)
    os.chmod(path, 0o600)
    server.factory = factory
    server.gateway = None
    return server
