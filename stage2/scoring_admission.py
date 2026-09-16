"""Bind paid admission to actual passed evidence and current runtime sources."""
import hashlib
import json
from pathlib import Path
import re

from gateway_policy import MODEL, ENDPOINT
from model_protocol import ModelSettings

RUNTIME_FILES = ('budget_ledger.py', 'gateway_core.py', 'gateway_policy.py',
    'gateway_http.py', 'scored_gateway.py', 'scored_accounting.py', 'model_protocol.py',
    'trial_estimator.py', 'openrouter_transport.py', 'receipt_polling.py',
    'production_compose.py', 'guarded_runtime.py', 'container_model_relay.py',
    'container_gateway_rpc.py', 'host_model_bridge.py', 'trial_execution.py',
    'scored_trial.py', 'pinned_docker.py', 'native_agents.py', 'custom_backend.py', 'custom_runner.py',
    'custom_model.py', 'custom_control.py', 'custom_jobs.py', 'custom_harbor_agent.py',
    'openhands-requirements.lock')

RUNTIME_CHECKS = {'verifier_reward_one', 'model_revoked', 'clean_status', 'billing_verified',
                  'containers_removed', 'networks_removed', 'volumes_removed',
                  'expected_reconciled_synthetic_receipts', 'runtime_images_preserved'}
LIVE_CHECKS = {'agent_created_file', 'native_tool_roundtrip', 'settings_on_wire',
               'billing_verified', 'cleanup_verified', 'trajectory_written', 'runtime_images_preserved'}


def source_hashes(root):
    return {name: hashlib.sha256((Path(root) / 'stage2' / name).read_bytes()).hexdigest()
            for name in RUNTIME_FILES}


def validate(root, document):
    root = Path(root).resolve()
    if document.get('model') != MODEL or document.get('endpoint') != ENDPOINT:
        raise ValueError('Admission model/provider mismatch')
    settings = ModelSettings(**document['settings'])
    if document.get('source_hashes') != source_hashes(root):
        raise ValueError('Runtime code changed since qualification')
    for field in ['gateway_image', 'guard_image']:
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', document.get(field, '')):
            raise ValueError('Pinned runtime images required')
    roles = {'runtime': 'synthetic_full_runner_not_benchmark_score',
             'terminus_live': 'actual_terminus_agent_live_setup_not_scored',
             'openhands_live': 'actual_openhands_agent_live_setup_not_scored',
             'custom_live': 'actual_custom_agent_live_setup_not_scored'}
    if set(document.get('proofs', {})) != set(roles):
        raise ValueError('All four runtime/live compatibility proofs required')
    for role, kind in roles.items():
        entry = document['proofs'][role]
        relative = Path(entry['path'])
        path = root / relative
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'stage2' or path.suffix != '.json' or path.is_symlink():
            raise ValueError('Invalid qualification evidence path')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Qualification evidence changed')
        evidence = json.loads(raw)
        checks = evidence.get('checks', {})
        required = RUNTIME_CHECKS if role == 'runtime' else LIVE_CHECKS
        if not required <= set(checks):
            raise ValueError('Missing required compatibility checks')
        if evidence.get('kind') != kind or evidence.get('status') != 'passed' or not checks or not all(v is True for v in checks.values()):
            raise ValueError('Qualification evidence did not pass')
        if evidence.get('model_protocol_sha256') != settings.fingerprint() or evidence.get('source_hashes') != document['source_hashes']:
            raise ValueError('Evidence used different model settings or runtime code')
        if evidence.get('gateway_image') != document['gateway_image'] or evidence.get('guard_image') != document['guard_image']:
            raise ValueError('Evidence used different runtime images')
        calls = evidence.get('live_api_calls')
        if type(calls) is not int or (calls != 0 if role == 'runtime' else calls <= 0):
            raise ValueError('Live and synthetic evidence must remain distinct')
    return settings
