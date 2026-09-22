"""Single-flight gateway with observational accounting, never monetary gates.

No balance, price estimator, ledger, reservation or receipt reads occur in the
dispatch path. Each call is written before sending it exactly once. Missing
costs remain unknown. Transport failures stop this attempt without replay;
real credit/authentication/identity stops are exposed to the matrix separately.
"""
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import signal
import stat
import threading
import time

from completion_wait import validate_completion_wait
from credit_only_policy import MODE, require_policy
from gateway_http import Handler, make_unix_server
from gateway_policy import MODEL, prepare_request
from model_protocol import ModelSettings, read_protocol
from openrouter_transport import OpenRouter, TransportError, load_key, sanitize_diagnostic
from scored_gateway import durable_json, private_directory

ERRORS = {
    'trial_unauthorised': (401, 'Trial credential invalid or revoked'),
    'provider_credit_exhausted': (402, 'Provider rejected this request for insufficient credit'),
    'upstream_authentication': (403, 'Provider authentication or permission rejected'),
    'response_integrity': (502, 'Provider response identity did not match the frozen model'),
    'upstream_unavailable': (502, 'Provider response unavailable; request was not replayed'),
    'attempt_stopped': (409, 'This attempt has stopped; requests will not be replayed'),
}
MATRIX_STOPS = {'provider_credit_exhausted', 'upstream_authentication', 'response_integrity'}


class CreditOnlyError(RuntimeError):
    def __init__(self, code):
        if code not in ERRORS:
            raise ValueError('Unknown gateway error category')
        self.code = code
        self.http_status, message = ERRORS[code]
        super().__init__(message)


def exact_cost(value):
    """Unknown/invalid billing does not invalidate a usable completion."""
    if type(value) not in (str, int, Decimal):
        return None
    try:
        result = Decimal(value)
        return str(result) if result.is_finite() and result >= 0 else None
    except (ValueError, InvalidOperation):
        return None


def count(value):
    return value if type(value) is int and value >= 0 else None


def prepare_credit_request(payload, settings):
    request = settings.enforce(prepare_request(payload))
    # This is a financial filter, unlike frozen endpoint/model/output limits.
    request['provider'].pop('max_price', None)
    return request


def failure_code(diagnostic):
    codes = {diagnostic.get('http_status'), diagnostic.get('error_code')}
    if diagnostic.get('identifier_conflict'):
        return 'response_integrity'
    if 402 in codes or diagnostic.get('error_type') == 'payment_required':
        return 'provider_credit_exhausted'
    if codes & {401, 403} or diagnostic.get('error_type') in {'authentication', 'permission_denied'}:
        return 'upstream_authentication'
    return 'upstream_unavailable'


def diagnostic_metadata(value):
    diagnostic = sanitize_diagnostic(value)
    # The shared transport's legacy wording refers to the OLD reserving mode.
    diagnostic['billing_outcome'] = 'unknown_no_reservation'
    return diagnostic


def response_identity(response, header_id, seen):
    if not isinstance(response, dict) or response.get('model') != MODEL or response.get('provider') != 'DeepInfra':
        raise CreditOnlyError('response_integrity')
    identifier = response.get('id')
    if identifier is not None:
        if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', identifier)
                or identifier in seen or header_id is not None and identifier != header_id):
            raise CreditOnlyError('response_integrity')
        seen.add(identifier)
    choices = response.get('choices')
    if not isinstance(choices, list) or not choices or any(
            not isinstance(c, dict) or not isinstance(c.get('message'), dict)
            or c['message'].get('role') != 'assistant' for c in choices):
        raise CreditOnlyError('upstream_unavailable')
    return identifier or header_id


class PassiveSession:
    def __init__(self, root, trial_id, stage, token, client, *, settings):
        if not isinstance(settings, ModelSettings) or stage != 'final':
            raise ValueError('Frozen model settings and explicit final stage required')
        if (not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id)
                or not isinstance(token, str) or len(token) < 32):
            raise ValueError('Valid trial identifier and strong trial credential required')
        self.closed = False
        self.stopped = False
        self.lock = None
        self.mutex = threading.Lock()
        self.client = client
        self.settings = settings
        self.trial_id = trial_id
        self.sequence = 0
        self.seen = set()
        self.token_hash = hashlib.sha256(token.encode()).digest()
        self.runtime = private_directory(Path(root).resolve() / '.runtime/stage2')
        require_policy(self.runtime)
        try:
            descriptor = os.open(self.runtime / 'gateway.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self.lock = os.fdopen(descriptor, 'r+')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.evidence = private_directory(self.runtime / 'scored-attempts') / trial_id
            self.evidence.mkdir(mode=0o700)  # Never restart an existing attempt.
            durable_json(self.evidence / 'started.json', dict(trial_id=trial_id,
                stage=stage, accounting_mode=MODE, model_protocol_sha256=settings.fingerprint()))
        except BaseException:
            self.close()
            raise

    def complete(self, token, payload):
        with self.mutex:
            if self.closed or not isinstance(token, str) or not hmac.compare_digest(
                    hashlib.sha256(token.encode()).digest(), self.token_hash):
                raise CreditOnlyError('trial_unauthorised')
            if self.stopped:
                raise CreditOnlyError('attempt_stopped')
            require_policy(self.runtime)
            request = prepare_credit_request(payload, self.settings)
            self.sequence += 1
            prefix = f'{self.sequence:06d}'
            durable_json(self.evidence / (prefix + '.request.json'), request)
            started_ns, started = time.time_ns(), time.monotonic()
            outcome = dict(sequence=self.sequence, trial_id=self.trial_id,
                status='error', accepted_for_agent=False, generation_id=None,
                cost_usd=None, cost_source=None, input_tokens=None, output_tokens=None)
            headers = {}

            def received_headers(value):
                diagnostic = diagnostic_metadata(value)
                durable_json(self.evidence / (prefix + '.response-headers.json'), diagnostic)
                headers.update(diagnostic)
                if diagnostic.get('identifier_conflict'):
                    raise CreditOnlyError('response_integrity')

            try:
                # One call, no exception retry or fallback. Billing is passive.
                response = self.client.complete(request, on_response_headers=received_headers)
                durable_json(self.evidence / (prefix + '.response.json'), response)
                usage = response.get('usage') if isinstance(response, dict) else None
                usage = usage if isinstance(usage, dict) else {}
                cost = exact_cost(usage.get('cost'))
                outcome.update(cost_usd=cost,
                    cost_source='openrouter_response_usage_cost' if cost is not None else None,
                    input_tokens=count(usage.get('prompt_tokens')), output_tokens=count(usage.get('completion_tokens')))
                outcome['generation_id'] = response_identity(response, headers.get('generation_id'), self.seen)
                outcome.update(status='ok', accepted_for_agent=True)
                return response
            except BaseException as exc:
                self.stopped = True
                diagnostic = diagnostic_metadata(exc.diagnostic if isinstance(exc, TransportError) else headers)
                if isinstance(exc, TransportError):
                    durable_json(self.evidence / (prefix + '.transport-error.json'), diagnostic)
                code = exc.code if isinstance(exc, CreditOnlyError) else failure_code(diagnostic)
                outcome.update(error_code=code, generation_id=diagnostic.get('generation_id'))
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    outcome['status'] = 'interrupted'
                if code in MATRIX_STOPS:
                    durable_json(self.evidence / 'provider-stop.json', dict(
                        trial_id=self.trial_id, sequence=self.sequence, reason=code, diagnostic=diagnostic))
                if not isinstance(exc, Exception):
                    raise
                raise CreditOnlyError(code) from None
            finally:
                durable_json(self.evidence / (prefix + '.timing.json'), dict(
                    started_ns=started_ns, ended_ns=time.time_ns(), seconds=time.monotonic() - started,
                    status=outcome['status']))
                durable_json(self.evidence / (prefix + '.outcome.json'), outcome)

    def close(self):
        with self.mutex:
            self.closed = True
            if self.lock is not None:
                self.lock.close()
                self.lock = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class CreditOnlyHandler(Handler):
    def dispatch(self, token, payload):
        try:
            if self.server.gateway is None:
                self.server.gateway = self.server.factory()
            self.reply(200, self.server.gateway.complete(token, payload))
        except CreditOnlyError as exc:
            self.reply(exc.http_status, {'error': {'code': exc.code, 'message': str(exc)}})
        except ValueError:
            self.reply(400, {'error': {'code': 'invalid_request', 'message': 'Unsupported request'}})
        except Exception:
            self.reply(502, {'error': {'code': 'gateway_unavailable', 'message': 'Gateway unavailable; do not retry automatically'}})


def serve(root, trial_id, stage, token_file, credential_file, socket_path, *, completion_wait_seconds):
    completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
    runtime = Path(root) / '.runtime/stage2'
    require_policy(runtime)
    settings = read_protocol(runtime)
    token_path = Path(token_file)
    info = token_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Private regular trial credential required')
    token = token_path.read_text().strip()
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise ValueError('Random 32-byte hexadecimal trial credential required')
    socket_path = Path(socket_path)
    private_directory(socket_path.parent)
    client = OpenRouter(load_key(credential_file), generation_enabled=True,
                        completion_wait_seconds=completion_wait_seconds)
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    server = None
    try:
        with PassiveSession(root, trial_id, stage, token, client, settings=settings) as session:
            server = make_unix_server(lambda: session, socket_path, handler=CreditOnlyHandler)
            server.serve_forever()
    finally:
        if server is not None:
            server.server_close()
            socket_path.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--stage', choices=['final'], required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--credential-file', required=True)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--completion-wait-seconds', required=True, type=float)
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.stage, args.token_file, args.credential_file, args.socket,
              completion_wait_seconds=args.completion_wait_seconds)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Gateway stopped: ' + type(exc).__name__) from None
