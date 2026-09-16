"""Native-harness compatibility sessions within the ORIGINAL $1 setup ledger.

Never a scored trial. The host must hold scored.lock across the entire runtime.
This entry point cannot create a new setup allowance or select a spending cap.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import signal

from budget_ledger import Ledger, BudgetExceeded
from gateway_core import Gateway, Trial, token_digest
from model_protocol import ModelSettings
from scored_gateway import ScoredSession, durable_json, private_directory
from setup_probe import full_context_bound


class NativeSetupSession(ScoredSession):
    def __init__(self, root, trial_id, token, client, *, settings):
        if not re.fullmatch(r'setup-native-[a-zA-Z0-9_.-]{1,100}', trial_id):
            raise ValueError('Explicit native setup identity required')
        if not re.fullmatch(r'[a-f0-9]{64}', token) or not isinstance(settings, ModelSettings):
            raise ValueError('Private random trial token and explicit model settings required')
        self.ledger = self.lock = self.gateway = None
        self.closed = False
        self.client = client
        self.sequence = self.budget_stop_sequence = 0
        self.active_prefix = None
        runtime = private_directory(Path(root).resolve() / '.runtime/stage2')
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
            if self.ledger.pending() or self.ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
                raise BudgetExceeded('Unresolved setup billing blocks dispatch')
            self.evidence = private_directory(runtime / 'native-setup-attempts') / trial_id
            self.evidence.mkdir(mode=0o700)
            durable_json(self.evidence / 'started.json', {
                'kind': 'native_harness_live_compatibility_not_scored',
                'trial_id': trial_id, 'stage': 'setup',
                'model_protocol_sha256': settings.fingerprint(),
                'aggregate_setup_cap_usd': '1', 'reservation': 'full_context_hard_bound'})
            self.gateway = Gateway(self.ledger, Trial(trial_id, 'setup', token_digest(token)),
                self.available_balance, full_context_bound, self.generate, self.receipt,
                request_policy=settings.enforce)
        except BaseException:
            self.close()
            raise


def serve(root, trial_id, token_file, credential_file, socket_path, settings_file):
    """Explicit container entry point; never called by importing this module."""
    from gateway_http import make_unix_server
    from openrouter_transport import OpenRouter, load_key
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
    client = OpenRouter(load_key(credential_file), generation_enabled=True)
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
    args = parser.parse_args()
    try:
        serve(args.root, args.trial, args.token_file, args.credential_file, args.socket, args.settings_file)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Native setup gateway stopped: ' + type(exc).__name__) from None
