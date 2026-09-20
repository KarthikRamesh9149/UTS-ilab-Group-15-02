"""Native-harness compatibility sessions within the ORIGINAL $1 setup ledger.

Never a scored trial. The host must hold scored.lock across the entire runtime.
This entry point cannot create a new setup allowance or select a spending cap.
"""
from contextlib import closing
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import signal
import sqlite3

from budget_ledger import Ledger, BudgetExceeded, UNIT
from historical_hold import validate_historical_hold
from gateway_core import Gateway, Trial, token_digest
from model_protocol import ModelSettings
from scored_gateway import ScoredSession, durable_json, private_directory
from setup_probe import full_context_bound
from completion_wait import validate_completion_wait


def scored_pending_liability(runtime):
    """Read, never mutate, outstanding exposure in the separate scored ledger.

    Setup uses its original $1 ledger. Its fresh account/key balance must also
    protect scored reservations that may not yet appear in provider balances.
    This does not resolve a request or allow scored execution to resume.
    """
    path = Path(runtime) / 'scored_budget.sqlite'
    if not path.exists() and not path.is_symlink():
        return Decimal(0)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('Private regular scored ledger required')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Scored ledger integrity failure')
        if db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
            raise BudgetExceeded('Scored billing incident requires review before setup spending')
        rows = db.execute("SELECT reserved FROM requests WHERE state='pending'").fetchall()
        if any(type(row[0]) is not int or row[0] <= 0 for row in rows):
            raise ValueError('Invalid scored reservation')
        if rows and validate_historical_hold(runtime, db) is None:
            raise BudgetExceeded('Only the exact registered historical scored hold permits new setup')
        if db.execute("SELECT COUNT(*) FROM receipt_checks WHERE state='pending'").fetchone()[0]:
            raise BudgetExceeded('Unverified scored receipts block new setup spending')
    return Decimal(sum(row[0] for row in rows)) / UNIT


class NativeSetupSession(ScoredSession):
    def __init__(self, root, trial_id, token, client, *, settings, receipt_timing='post_trial'):
        if not re.fullmatch(r'setup-native-[a-zA-Z0-9_.-]{1,100}', trial_id):
            raise ValueError('Explicit native setup identity required')
        if not re.fullmatch(r'[a-f0-9]{64}', token) or not isinstance(settings, ModelSettings):
            raise ValueError('Private random trial token and explicit model settings required')
        self.ledger = self.lock = self.gateway = None
        self.closed = False
        self.client = client
        self.sequence = self.budget_stop_sequence = 0
        self.active_prefix = None
        self.reservation_id = None
        runtime = private_directory(Path(root).resolve() / '.runtime/stage2')
        self.setup_runtime = runtime
        # Require the already-existing shared account of ALL previous setup
        # work. Do not silently start another $1 allowance in a fixture folder.
        ledger_path = runtime / 'setup_budget.sqlite'
        info = ledger_path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError('Existing private setup ledger required')
        try:
            descriptor = os.open(runtime / 'gateway.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self.lock = os.fdopen(descriptor, 'r+')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.available_balance()
            self.ledger = Ledger(ledger_path, '1', '1', {'setup': '1'})
            if self.ledger.pending() or self.ledger.pending_receipts() or self.ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
                raise BudgetExceeded('Unresolved setup billing blocks dispatch')
            self.evidence = private_directory(runtime / 'native-setup-attempts') / trial_id
            self.evidence.mkdir(mode=0o700)
            durable_json(self.evidence / 'started.json', {
                'kind': 'native_harness_live_compatibility_not_scored',
                'trial_id': trial_id, 'stage': 'setup',
                'model_protocol_sha256': settings.fingerprint(),
                'aggregate_setup_cap_usd': '1', 'reservation': 'full_context_hard_bound',
                'receipt_timing': receipt_timing, 'inline_charge_source': 'openrouter_response_usage_cost'})
            self.gateway = Gateway(self.ledger, Trial(trial_id, 'setup', token_digest(token)),
                self.available_balance, full_context_bound, self.generate, self.receipt,
                request_policy=settings.enforce, receipt_timing=receipt_timing,
                on_reserved=self.record_reservation)
        except BaseException:
            self.close()
            raise

    def available_balance(self):
        # Scored gateways already account for their own pending reservations in
        # Ledger.reserve; only this separate setup ledger needs the deduction.
        available = super().available_balance() - scored_pending_liability(self.setup_runtime)
        if available < 0:
            raise BudgetExceeded('Scored liabilities exceed available credit')
        return available


def serve(root, trial_id, token_file, credential_file, socket_path, settings_file, *, completion_wait_seconds):
    """Explicit container entry point; never called by importing this module."""
    from gateway_http import make_unix_server
    from openrouter_transport import OpenRouter, load_key
    completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
    def private_text(filename):
        path = Path(filename)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError('Private regular configuration required')
        return path.read_text()
    token = private_text(token_file).strip()
    settings = ModelSettings(**json.loads(private_text(settings_file)))
    socket_path = Path(socket_path)
    private_directory(socket_path.parent)
    client = OpenRouter(load_key(credential_file), generation_enabled=True,
                        completion_wait_seconds=completion_wait_seconds)
    def interrupted(signum, frame): raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    server = None
    try:
        with NativeSetupSession(root, trial_id, token, client, settings=settings) as session:
            server = make_unix_server(lambda: session, socket_path)
            server.serve_forever()
    finally:
        if server is not None:
            server.server_close()
            socket_path.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'trial', 'token-file', 'credential-file', 'socket', 'settings-file']:
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--completion-wait-seconds', required=True, type=float)
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.token_file, args.credential_file, args.socket, args.settings_file,
              completion_wait_seconds=args.completion_wait_seconds)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Native setup gateway stopped: ' + type(exc).__name__) from None
