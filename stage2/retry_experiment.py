"""Immutable identity, source bindings and full coverage for the corrected run."""
import json
from pathlib import Path
from credit_only_experiment import (ORIGINAL, PREDECESSOR, DEPLOYMENT as CLOSED_THIRD,
    sources as inherited_sources, digest, coverage, cleanup_complete)
from run_baselines import baseline_cells
from retry_policy import EXPERIMENT, SETTINGS, POLICY

DEPLOYMENT = Path('/opt/uts-capstone-corrected-20260923')
ANCESTORS = (ORIGINAL, PREDECESSOR, CLOSED_THIRD)
REGISTRATION = 'corrected-matrix.json'
QUALIFICATION = 'corrected-qualification.json'
ADDED = ('retry_policy.py', 'retry_runtime.py', 'retry_transport.py', 'retry_gateway.py',
    'rate_limit_candidate.py', 'recovery_agents.py', 'retry_experiment.py', 'run_corrected.py',
    'qualify_corrected.py', 'retry_runtime_probe.py', 'check_corrected_provider.py', 'test_retry_gateway.py',
    'test_retry_experiment.py', 'test_rate_limit_candidate.py', 'fixtures/Dockerfile.corrected')


def sources(root):
    values = inherited_sources(root)
    values.update({name: digest(Path(root) / 'stage2' / name) for name in ADDED})
    return values


def cells(task_ids):
    result = baseline_cells(task_ids)
    if len(result) != 178 or len(set(task_ids)) != 89:
        raise ValueError('Exactly 89 original tasks for each baseline required')
    for cell in result: cell['trial_id'] = 'corrected1-' + cell['trial_id']
    return result


def source_invariants(root):
    current = sources(root)
    prior = json.loads((CLOSED_THIRD / '.runtime/stage2/credit-only-qualification.json').read_text())
    if any(current.get(k) != v for k, v in prior['sources'].items()):
        raise ValueError('Previously qualified inherited source changed')
    return current, prior


def validate_qualification(root):
    root = Path(root)
    current, parent = source_invariants(root)
    proof = json.loads((root / '.runtime/stage2' / QUALIFICATION).read_text())
    if (proof.get('sources') != current or proof.get('experiment') != EXPERIMENT
            or proof.get('policy') != POLICY or proof.get('parent_gateway') != parent['gateway_image']
            or proof.get('model_protocol_sha256') != SETTINGS.fingerprint()
            or proof.get('status') != 'passed' or proof.get('live_api_calls') != 0):
        raise ValueError('Current corrected qualification required')
    evidence = proof.get('evidence_sha256', {})
    if set(evidence) != {'offline.json', 'image.json', 'synthetic.json'}:
        raise ValueError('Incomplete qualification evidence')
    folder = root / '.runtime/stage2' / proof['evidence_folder']
    if folder.parent != root / '.runtime/stage2' or not folder.name.startswith('qualification-') or folder.is_symlink():
        raise ValueError('Invalid qualification evidence folder')
    for name, expected in evidence.items():
        if digest(folder / name) != expected: raise ValueError('Qualification evidence changed')
    return proof
