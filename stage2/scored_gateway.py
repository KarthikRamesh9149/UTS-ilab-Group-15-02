"""Production scored-gateway lifecycle, with no automatic launch or API call.

Only the trusted orchestrator constructs this session. All conditions share
one ledger and one process lock. Trial IDs are immutable, single-use attempts.
An interrupted trial cannot be restarted through this entry point.
"""
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import signal
import time

from budget_ledger import Ledger, BudgetExceeded
from gateway_core import Gateway, GatewayError, Trial, token_digest
from receipt_polling import read_receipt
from setup_probe import full_context_bound, validate_metadata
from trial_estimator import trial_charge_estimator
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS


def private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Runtime directory must be owned and private')
    return path


def durable_json(path, value):
    """Exclusive creation; never replace evidence after partial execution."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(value, handle, allow_nan=False, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class ScoredSession:
    def __init__(self, root, trial_id, stage, token, client, *, estimator=None, settings=None, receipt_timing='post_trial'):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
            raise ValueError('Invalid trial identifier')
        if stage not in {'development', 'final'} or not isinstance(token, str) or len(token) < 32:
            raise ValueError('Explicit stage and strong per-trial token required')
        self.ledger = None
        self.lock = None
        self.gateway = None
        self.closed = False
        self.client = client
        self.sequence = 0
        self.budget_stop_sequence = 0
        self.active_prefix = None
        root = Path(root).resolve()
        runtime = private_directory(root / '.runtime' / 'stage2')
        try:
            # O_NOFOLLOW avoids following a replaced control-file symlink.
            # The host orchestrator separately holds scored.lock for the whole
            # trial. Do not rely on flock propagating across macOS/Colima, or
            # deadlock against that host lock on filesystems where it does.
            descriptor = os.open(runtime / 'gateway.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self.lock = os.fdopen(descriptor, 'r+')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.available_balance()
            self.ledger = Ledger(runtime / 'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP,
                STAGE_CAPS, allow_estimated_trials=True)
            if self.ledger.pending() or self.ledger.pending_receipts():
                raise BudgetExceeded('Resolve prior pending billing before another trial')
            if self.ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
                raise BudgetExceeded('Prior billing incident blocks trial startup')
            attempts = private_directory(runtime / 'scored-attempts')
            self.evidence = attempts / trial_id
            self.evidence.mkdir(mode=0o700)  # Exists, even from a crash: never replay.
            durable_json(self.evidence / 'started.json', {
                'trial_id': trial_id, 'stage': stage, 'status': 'started',
                'model_protocol_sha256': settings.fingerprint() if settings is not None else None,
                'estimated_trial_cap_usd': TRIAL_CAP, 'aggregate_cap_usd': SCORED_CEILING,
                'receipt_timing': receipt_timing, 'inline_charge_source': 'openrouter_response_usage_cost'})
            self.gateway = Gateway(self.ledger, Trial(trial_id, stage, token_digest(token)),
                self.available_balance, full_context_bound, self.generate, self.receipt,
                trial_estimate=estimator or trial_charge_estimator(root),
                request_policy=settings.enforce if settings is not None else None,
                receipt_timing=receipt_timing)
        except BaseException:
            self.close()
            raise

    def available_balance(self):
        # Check both account and key allowance before every generation. The
        # ledger subtracts its $2 reserve; retaining it on both is conservative.
        validate_metadata(self.client.metadata())
        key = self.client.key_status()['limit_remaining']
        if key is None:
            raise BudgetExceeded('Unknown key allowance')
        key = Decimal(str(key))
        account = Decimal(str(self.client.balance()))
        if not all(v.is_finite() and v >= 0 for v in (key, account)):
            raise BudgetExceeded('Invalid available credit')
        return min(key, account)

    def generate(self, request):
        self.sequence += 1
        self.active_prefix = f'{self.sequence:06d}'
        durable_json(self.evidence / (self.active_prefix + '.request.json'), request)
        started_ns, started = time.time_ns(), time.monotonic()
        status = 'error'
        try:
            response = self.client.complete(request)  # Exactly one dispatch; no retries.
            status = 'ok'
        finally:
            durable_json(self.evidence / (self.active_prefix + '.timing.json'), {
                'started_ns': started_ns, 'ended_ns': time.time_ns(),
                'seconds': time.monotonic() - started, 'status': status})
        durable_json(self.evidence / (self.active_prefix + '.response.json'), response)
        return response

    def receipt(self, identifier):
        try:
            receipt = read_receipt(self.client.generation, identifier)
        except Exception as exc:
            durable_json(self.evidence / (self.active_prefix + '.receipt-error.json'), {
                'error_type': type(exc).__name__})
            raise
        durable_json(self.evidence / (self.active_prefix + '.receipt.json'), receipt)
        return receipt

    def complete(self, token, payload):
        if self.closed:
            raise RuntimeError('Session is closed')
        try:
            return self.gateway.complete(token, payload)
        except BudgetExceeded:
            self.budget_stop_sequence += 1
            durable_json(self.evidence / f'{self.budget_stop_sequence:06d}.budget-stop.json', {
                'trial_id': self.gateway.trial.identifier, 'stage': self.gateway.trial.stage,
                'kind': 'budget_stop', 'generation_sequence': self.sequence})
            raise
        except GatewayError as exc:
            safe = {'Unauthorised trial', 'No qualified request charge bound',
                    'No billing reconciliation reader', 'Invalid request charge bound',
                    'Upstream outcome unknown; reservation retained',
                    'Unverified response identity; reservation retained',
                    'Unverified response provider; reservation retained',
                    'Missing billing evidence; reservation retained',
                    'Invalid billing evidence; reservation retained',
                    'Inexact billing evidence; reservation retained',
                    'Billing reconciliation incomplete; reservation retained'}
            label = str(exc) if str(exc) in safe else 'Unclassified gateway failure'
            path = self.evidence / ((self.active_prefix or 'pre-dispatch') + '.gateway-error.json')
            if not path.exists():
                durable_json(path, {'error_type': 'GatewayError', 'category': label})
            raise

    def close(self):
        self.closed = True
        if self.gateway is not None:
            self.gateway.revoke()
        try:
            if self.ledger is not None:
                self.ledger.close()
                self.ledger = None
        finally:
            if self.lock is not None:
                self.lock.close()
                self.lock = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def serve(root, trial_id, stage, token_file, credential_file, socket_path):
    """Private-container entry point. The orchestrator must remove its container
    at the agent/verifier boundary, revoking the task's model access.
    No credential or token is accepted on the command line or copied to logs.
    """
    from gateway_http import make_unix_server
    from openrouter_transport import OpenRouter, load_key
    from model_protocol import read_protocol
    settings = read_protocol(Path(root) / '.runtime/stage2')
    token_path = Path(token_file)
    info = token_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Trial token file must be private and regular')
    token = token_path.read_text().strip()
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise ValueError('Expected a random 32-byte hexadecimal token')
    socket_path = Path(socket_path)
    private_directory(socket_path.parent)
    client = OpenRouter(load_key(credential_file), generation_enabled=True)
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    server = None
    try:
        with ScoredSession(root, trial_id, stage, token, client, settings=settings) as session:
            server = make_unix_server(lambda: session, socket_path)
            # Main-thread construction and serving preserve SQLite affinity.
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
    parser.add_argument('--stage', choices=['development', 'final'], required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--credential-file', required=True)
    parser.add_argument('--socket', required=True)
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.stage, args.token_file, args.credential_file, args.socket)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Do not print provider payloads, secret values or raw exception text.
        raise SystemExit('Gateway stopped: ' + type(exc).__name__) from None
