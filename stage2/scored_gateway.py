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
import sqlite3
import time

from budget_ledger import Ledger, BudgetExceeded, UNIT
from gateway_core import Gateway, GatewayError, Trial, token_digest
from receipt_polling import read_receipt
from setup_probe import full_context_bound, validate_metadata
from trial_estimator import trial_charge_estimator
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS
from openrouter_transport import TransportError, sanitize_diagnostic
from completion_wait import validate_completion_wait


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


def require_clear_setup_ledger(runtime):
    """Validate setup accounting and return its conservatively held liability.

    Read the authoritative setup ledger before every paid scored dispatch.
    Settled setup charges are already reflected in the fresh provider balance;
    Deferred terminal attempts may remain uncertain; active requests and real
    billing incidents still block. Known charges are not subtracted twice.
    """
    database = Path(runtime) / 'setup_budget.sqlite'
    if not database.exists() and not database.is_symlink():
        from historical_hold import SIDECAR, SIDECAR_V2
        from deferred_billing import POLICY
        if any((Path(runtime) / name).exists() or (Path(runtime) / name).is_symlink()
               for name in (SIDECAR, SIDECAR_V2, POLICY)):
            raise BudgetExceeded('Original setup ledger required under historical hold amendment')
        return Decimal(0)
    info = database.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise BudgetExceeded('Original setup ledger required for scored admission')
    reader = sqlite3.connect(database.absolute().as_uri() + '?mode=ro', uri=True)
    try:
        reader.execute('PRAGMA query_only=ON')
        reader.execute('BEGIN')
        from deferred_billing import validate_deferrals, deferred_request_ids, unresolved_liability_nanodollars
        entries = validate_deferrals(runtime, reader, kind='setup')
        exempt = deferred_request_ids(entries)
        unknown = reader.execute("SELECT id,reserved FROM requests WHERE state!='settled' OR charged IS NULL").fetchall()
        receipts = reader.execute("SELECT request_id FROM receipt_checks WHERE state!='verified'").fetchall()
        if (reader.execute('PRAGMA quick_check').fetchall() != [('ok',)]
                or any(identifier not in exempt for identifier, _ in unknown)
                or any(identifier not in exempt for identifier, in receipts)
                or reader.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]):
            raise BudgetExceeded('Unresolved setup billing blocks scored admission')
        return Decimal(unresolved_liability_nanodollars(reader, entries)) / UNIT
    except sqlite3.Error as exc:
        raise BudgetExceeded('Setup billing could not be verified before scored admission') from exc
    finally:
        reader.close()


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
        self.reservation_id = None
        root = Path(root).resolve()
        runtime = private_directory(root / '.runtime' / 'stage2')
        self.runtime = runtime
        try:
            # O_NOFOLLOW avoids following a replaced control-file symlink.
            # The host orchestrator separately holds scored.lock for the whole
            # trial. Do not rely on flock propagating across macOS/Colima, or
            # deadlock against that host lock on filesystems where it does.
            descriptor = os.open(runtime / 'gateway.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self.lock = os.fdopen(descriptor, 'r+')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.scored_available_balance()
            self.ledger = Ledger(runtime / 'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP,
                STAGE_CAPS, allow_estimated_trials=True, historical_hold_runtime=runtime,
                deferred_billing_runtime=runtime, deferred_billing_kind='scored')
            if self.ledger.blocking_pending(trial=trial_id) or self.ledger.blocking_receipts(trial=trial_id):
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
                self.scored_available_balance, full_context_bound, self.generate, self.receipt,
                trial_estimate=estimator or trial_charge_estimator(root),
                request_policy=settings.enforce if settings is not None else None,
                receipt_timing=receipt_timing, on_reserved=self.record_reservation)
        except BaseException:
            self.close()
            raise

    def scored_available_balance(self):
        liability = require_clear_setup_ledger(self.runtime)
        available = self.available_balance() - liability
        if available < 0:
            raise BudgetExceeded('Setup liabilities exceed available credit')
        return available

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

    def record_reservation(self, identifier):
        # Gateway invokes this under its single-flight lock, after commit and
        # before exactly one transport dispatch. Model input cannot select it.
        self.reservation_id = identifier

    def generate(self, request):
        reservation_id, self.reservation_id = self.reservation_id, None
        if reservation_id is None:
            raise RuntimeError('Committed reservation required before dispatch')
        self.sequence += 1
        self.active_prefix = f'{self.sequence:06d}'
        prefix = self.active_prefix
        identity = {'reservation_id': reservation_id, 'trial_id': self.gateway.trial.identifier,
                    'sequence': self.sequence}
        durable_json(self.evidence / (prefix + '.reservation.json'), identity)
        durable_json(self.evidence / (prefix + '.request.json'), request)
        def attach_diagnostic(diagnostic):
            if diagnostic.get('identifier_conflict'):
                raise TransportError('Conflicting response identifiers', diagnostic=diagnostic)
            if diagnostic['generation_id'] is not None:
                self.ledger.attach_generation(reservation_id, diagnostic['generation_id'])
        def response_headers(value):
            diagnostic = sanitize_diagnostic(value)
            durable_json(self.evidence / (prefix + '.response-headers.json'),
                         dict(identity, diagnostic=diagnostic))
            attach_diagnostic(diagnostic)
        started_ns, started = time.time_ns(), time.monotonic()
        status = 'error'
        try:
            # Never retry without the callback if a client violates this
            # interface: the first call might already have reached a provider.
            response = self.client.complete(request, on_response_headers=response_headers)
            status = 'ok'
        except TransportError as exc:
            if exc.diagnostic is not None:
                diagnostic = sanitize_diagnostic(exc.diagnostic)
                durable_json(self.evidence / (prefix + '.transport-error.json'), diagnostic)
                attach_diagnostic(diagnostic)
            raise
        except KeyboardInterrupt:
            status = 'interrupted'
            durable_json(self.evidence / (prefix + '.interruption.json'),
                         dict(identity, category='gateway_interrupted_outcome_unknown'))
            raise
        finally:
            durable_json(self.evidence / (prefix + '.timing.json'), {
                'started_ns': started_ns, 'ended_ns': time.time_ns(),
                'seconds': time.monotonic() - started, 'status': status})
        durable_json(self.evidence / (prefix + '.response.json'), response)
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
                    'Conflicting or invalid generation identity; reservation retained',
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


def serve(root, trial_id, stage, token_file, credential_file, socket_path, *, completion_wait_seconds):
    """Private-container entry point. The orchestrator must remove its container
    at the agent/verifier boundary, revoking the task's model access.
    No credential or token is accepted on the command line or copied to logs.
    """
    from gateway_http import make_unix_server
    from openrouter_transport import OpenRouter, load_key
    from model_protocol import read_protocol
    completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
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
    client = OpenRouter(load_key(credential_file), generation_enabled=True,
                        completion_wait_seconds=completion_wait_seconds)
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
    parser.add_argument('--completion-wait-seconds', required=True, type=float)
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.stage, args.token_file, args.credential_file, args.socket,
              completion_wait_seconds=args.completion_wait_seconds)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Do not print provider payloads, secret values or raw exception text.
        raise SystemExit('Gateway stopped: ' + type(exc).__name__) from None
