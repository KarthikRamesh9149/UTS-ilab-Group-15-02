"""Explicit, source-qualified accounting-only continuation of a frozen matrix.

The original admission, live proofs and baseline registration are never edited.
An additive transition must bind native offline tests, an immutable-evidence
receipt rehearsal, the replacement image and a fresh synthetic runtime check.
It cannot qualify a different model, harness policy, task, limit or provider.
"""
import hashlib
from pathlib import Path
import re

from deferred_billing import _encoded, _json, _read

TRANSITION = 'accounting-runtime-transition-v1.json'
CHANGED = frozenset({'budget_ledger.py', 'deferred_billing.py', 'run_baselines.py', 'scored_trial.py'})
ADDED = frozenset({'receipt_accounting.py', 'collect_deferred_receipts.py',
                   'receipt_runtime_transition.py', 'scoring_admission.py'})
CHECKS = {
    'offline': {'all_tests_passed', 'external_network_disabled', 'sources_unchanged'},
    'replay': {'originals_unchanged', 'unknown_reservations_unchanged',
               'exact_hold_reduction', 'idempotent_activation', 'stale_admission_rejected'},
    'gateway': {'parent_layers_preserved', 'image_configuration_unchanged',
                'image_sources_match', 'offline_accounting_matches_host'},
    'synthetic': {'verifier_reward_one', 'model_revoked', 'clean_status', 'billing_verified',
                  'containers_removed', 'networks_removed', 'volumes_removed',
                  'expected_reconciled_synthetic_receipts', 'runtime_images_preserved',
                  'host_environment_unchanged', 'runtime_sources_unchanged'},
}


def digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _artifact(runtime, entry):
    if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}:
        raise ValueError('Exact accounting qualification artifact binding required')
    relative = Path(entry['path'])
    if (relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 2
            or relative.parts[0] != 'accounting-qualification-v1' or relative.suffix != '.json'):
        raise ValueError('Private accounting qualification evidence path required')
    raw = _read(runtime / relative, runtime)
    if hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('Accounting qualification artifact changed')
    return _json(raw)


def qualified_transition(root, admission, current_sources=None):
    """Read-only; this never creates a transition or infers approval from tests."""
    from scoring_admission import source_hashes
    root = Path(root).resolve()
    runtime = root / '.runtime/stage2'
    path = runtime / TRANSITION
    if not path.exists() and not path.is_symlink():
        return None
    raw = _read(path, runtime)
    value = _json(raw)
    required = {'schema_version', 'kind', 'original_admission_sha256',
                'baseline_registration_sha256', 'source_hashes', 'gateway_image',
                'guard_image', 'host_environment', 'model_protocol_sha256', 'proofs',
                'reviewer', 'scope', 'activation_files', 'preserved_results'}
    if (not isinstance(value, dict) or set(value) != required
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'qualified_additive_receipt_accounting_transition'
            or value['scope'] != 'accounting_only_no_replay_no_model_or_limit_change'
            or not isinstance(value['reviewer'], str) or not value['reviewer'].strip()
            or value['original_admission_sha256'] != digest(admission)):
        raise ValueError('Explicit original-bound accounting transition required')
    registration_raw = _read(runtime / 'baseline-matrix.json', runtime)
    registration = _json(registration_raw)
    if (hashlib.sha256(registration_raw).hexdigest() != value['baseline_registration_sha256']
            or registration.get('admission') != admission):
        raise ValueError('Original baseline registration changed')
    current = source_hashes(root) if current_sources is None else current_sources
    original = admission['source_hashes']
    if (value['source_hashes'] != current or set(current) - set(original) != ADDED
            or set(original) - set(current)
            or not CHANGED <= set(original)
            or any(current[name] != previous for name, previous in original.items() if name not in CHANGED)):
        raise ValueError('Accounting transition cannot qualify other source changes')
    if any(registration['source_hashes'].get(name) != checksum for name, checksum in original.items()):
        raise ValueError('Original baseline and admission source bindings differ')
    for name, previous in registration['source_hashes'].items():
        if name not in CHANGED and name not in original:
            source = root / 'stage2' / name
            if (source.is_symlink() or source.parent != root / 'stage2'
                    or hashlib.sha256(source.read_bytes()).hexdigest() != previous):
                raise ValueError('Frozen non-runtime baseline input changed')
    from model_protocol import ModelSettings
    protocol = ModelSettings(**admission['settings']).fingerprint()
    if (value['host_environment'] != admission['host_environment']
            or value['model_protocol_sha256'] != protocol
            or value['guard_image'] != admission['guard_image']
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', value['gateway_image'])
            or value['gateway_image'] == admission['gateway_image']
            or set(value['proofs']) != set(CHECKS)):
        raise ValueError('Accounting transition host, protocol or image mismatch')
    for role, entry in value['proofs'].items():
        proof = _artifact(runtime, entry)
        checks = proof.get('checks', {})
        if (proof.get('status') != 'passed' or type(proof.get('live_api_calls')) is not int
                or proof['live_api_calls'] != 0 or not CHECKS[role] <= set(checks)
                or not checks or not all(item is True for item in checks.values())
                or proof.get('source_hashes') != current
                or proof.get('host_environment') != admission['host_environment']
                or proof.get('model_protocol_sha256') != protocol
                or proof.get('gateway_image') != value['gateway_image']
                or proof.get('guard_image') != value['guard_image']):
            raise ValueError('Native offline accounting qualification incomplete: ' + role)
        if role == 'offline':
            if (type(proof.get('tests_run')) is not int or proof['tests_run'] <= 0
                    or proof.get('failures') != 0 or proof.get('errors') != 0 or proof.get('skipped') != 0):
                raise ValueError('Complete native offline suite required')
        if role == 'gateway' and proof.get('parent_image') != admission['gateway_image']:
            raise ValueError('Gateway is not derived from the original qualified image')
        if role == 'replay' and (proof.get('activation_files') != value['activation_files']
                or proof.get('preserved_results') != value['preserved_results']):
            raise ValueError('Accounting replay and activation bindings differ')
        if role == 'synthetic' and proof.get('kind') != 'synthetic_full_runner_not_benchmark_score':
            raise ValueError('Synthetic runtime evidence must stay distinct from model scoring')
    if not value['activation_files'] or not value['preserved_results']:
        raise ValueError('Exact activated receipts and preserved results required')
    for relative_name, expected_hash in {**value['activation_files'], **value['preserved_results']}.items():
        relative = Path(relative_name)
        allowed = (len(relative.parts) == 2 and relative.parts[0] == 'receipt-accounting-activations-v1'
                   or len(relative.parts) == 3 and relative.parts[0] == 'scored-trials'
                   and relative.name == 'result.json')
        if not allowed or hashlib.sha256(_read(runtime / relative, runtime)).hexdigest() != expected_hash:
            raise ValueError('Accounting activation or original result changed')
    return dict(value, transition_sha256=hashlib.sha256(raw).hexdigest())


def descriptor_matches(root, admission, original, expected):
    if original == expected:
        return True
    transition = qualified_transition(root, admission)
    if transition is None:
        return False
    expected_bindings = dict(original['source_hashes'], **transition['source_hashes'])
    # Every non-source field, including all 178 cells and the review, is exact.
    return (expected.get('source_hashes') == expected_bindings
            and original == dict(expected, source_hashes=original.get('source_hashes'))
            and hashlib.sha256((Path(root) / '.runtime/stage2/baseline-matrix.json').read_bytes()).hexdigest()
            == transition['baseline_registration_sha256'])


def gateway_for_trial(root, requested_gateway, guard_image, settings):
    """Use the qualified replacement without rewriting the historical admission."""
    root = Path(root).resolve()
    runtime = root / '.runtime/stage2'
    path = runtime / TRANSITION
    if not path.exists() and not path.is_symlink():
        return requested_gateway, None
    admission = _json(_read(runtime / 'baseline-matrix.json', runtime))['admission']
    from scoring_admission import validate
    validate(root, admission)  # Also revalidate original live proofs and live host.
    transition = qualified_transition(root, admission)
    if (requested_gateway != admission['gateway_image'] or guard_image != admission['guard_image']
            or settings.fingerprint() != transition['model_protocol_sha256']):
        raise ValueError('Trial does not match the qualified accounting transition')
    return transition['gateway_image'], transition['transition_sha256']
