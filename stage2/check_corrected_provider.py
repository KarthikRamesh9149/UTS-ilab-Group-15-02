"""Authorised real connection check, separately logged from all benchmark cells."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import tempfile

from credit_only_policy import POLICY as FINANCIAL, POLICY_FILE as FINANCIAL_FILE
from credit_only_accounting import summarise
from gateway_policy import MODEL
from model_protocol import freeze_protocol
from openrouter_transport import load_key
from retry_policy import POLICY, POLICY_FILE, SETTINGS
from retry_experiment import DEPLOYMENT, ANCESTORS, validate_qualification, sources
from retry_gateway import RetrySession
from retry_runtime import Clock, activate
from retry_transport import ObservedOpenRouter
from run_credit_only import hold
from scored_gateway import durable_json, private_directory


def check(root):
    runtime = private_directory(root / '.runtime/stage2')
    if (runtime / 'provider-check.json').exists(): raise ValueError('Preserve completed provider check')
    proof = validate_qualification(root)
    import host_environment
    if host_environment.snapshot() != proof['host_environment']: raise ValueError('Host drift')
    with ExitStack() as stack:
        for base in (*ANCESTORS, root):
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                hold(stack, base / '.runtime/stage2', name)
        folder = Path(tempfile.mkdtemp(prefix='provider-check-', dir=runtime))
        state = private_directory(folder / '.runtime/stage2')
        for name, value in ((POLICY_FILE, POLICY), (FINANCIAL_FILE, FINANCIAL)):
            durable_json(state / name, value)
        freeze_protocol(state, SETTINGS)
        token, clock = secrets.token_hex(32), Clock()
        activate(state, 'connection-check', 900, SETTINGS, clock)
        client = ObservedOpenRouter(load_key(root / '.env'), clock=clock, generation_enabled=True,
            completion_wait_seconds=900)
        status = 'failed'
        error = None
        try:
            with RetrySession(folder, 'connection-check', 'final', token, client, settings=SETTINGS, clock=clock) as session:
                response = session.complete(token, dict(model=MODEL, max_tokens=384000, temperature=1.,
                    reasoning={'effort': 'high'}, messages=[dict(role='user', content='Reply with exactly UTS_CONNECTION_OK. This is a connection test; no explanation is needed.')]))
                if response['choices'][0]['message'].get('content', '').strip() == 'UTS_CONNECTION_OK':
                    status = 'passed'
        except Exception as exc:
            error = type(exc).__name__
        result = dict(status=status, error_type=error, sources=sources(root),
            model_protocol_sha256=SETTINGS.fingerprint(), evidence_folder=folder.name,
            billing=summarise(state, 'connection-check'))
        durable_json(folder / 'result.json', result)
        if status == 'passed': durable_json(runtime / 'provider-check.json', result)
        print(json.dumps({key: result[key] for key in ('status', 'error_type', 'billing', 'evidence_folder')}))
        if status != 'passed': raise SystemExit('Provider connection not qualified; benchmark not started')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT: raise SystemExit('Use the separate registered deployment')
    os.umask(0o077)
    check(root)
