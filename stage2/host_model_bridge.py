"""Host agent -> private container socket, without Docker published ports.

Only the trusted host orchestrator selects the already-inspected relay container.
The task cannot invoke Docker or choose the RPC executable. No shell or upstream
credential is involved, and no failed request is retried.
"""
import json
import re
import subprocess
import threading

from budget_ledger import BudgetExceeded
from gateway_core import GatewayError
from gateway_http import make_server
from gateway_policy import MAX_BODY
from container_model_relay import MAX_RESPONSE


class ContainerGateway:
    def __init__(self, container_id, *, run=subprocess.run):
        if not re.fullmatch(r'[a-f0-9]{64}', container_id):
            raise ValueError('Full inspected container ID required')
        self.container_id = container_id
        self.run = run
        self.revoked = False

    def complete(self, token, payload):
        if self.revoked:
            raise GatewayError('Host bridge revoked')
        raw = json.dumps({'token': token, 'payload': payload}, allow_nan=False).encode()
        if len(raw) > MAX_BODY * 2:
            raise ValueError('Envelope too large')
        try:
            result = self.run(['docker', 'exec', '-i', self.container_id,
                'python', '/study/stage2/container_gateway_rpc.py'],
                input=raw, capture_output=True, timeout=120, check=False)
            if result.returncode or len(result.stdout) > MAX_RESPONSE * 2:
                raise ValueError('RPC failed')
            response = json.loads(result.stdout)
            status, body = response['status'], response['body']
            if type(status) is not int or not isinstance(body, dict):
                raise ValueError('Malformed response')
        except Exception:
            raise GatewayError('Private gateway outcome unknown; do not retry') from None
        if status == 402:
            raise BudgetExceeded('Gateway budget admission blocked')
        if status != 200:
            raise GatewayError('Private gateway rejected request; do not retry')
        return body


class HostModelBridge:
    def __init__(self, relay_container_id):
        self.gateway = ContainerGateway(relay_container_id)
        self.server = make_server(lambda: self.gateway)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.closed = False

    @property
    def base_url(self):
        return f'http://127.0.0.1:{self.server.server_address[1]}/v1'

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        if not self.closed:
            self.closed = True
            self.gateway.revoked = True
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=125)
            if self.thread.is_alive():
                raise RuntimeError('Host bridge did not stop; destroy gateway before verification')
