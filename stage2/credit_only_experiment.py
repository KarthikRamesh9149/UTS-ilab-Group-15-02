"""Frozen scope and evidence bindings for the distinct uncapped experiment."""
import hashlib
import json
from pathlib import Path

from credit_only_policy import EXPERIMENT, POLICY
from run_baselines import baseline_cells
from scoring_admission import source_hashes

ORIGINAL = Path('/opt/uts-capstone')
PREDECESSOR = Path('/opt/uts-capstone-baseline-repeat-20260921')
DEPLOYMENT = Path('/opt/uts-capstone-credit-only-20260922')
REGISTRATION = 'credit-only-matrix.json'
QUALIFICATION = 'credit-only-qualification.json'
CHANGED = {'gateway_http.py', 'scored_trial.py'}
ADDED = ('credit_only_policy.py', 'credit_only_gateway.py', 'credit_only_accounting.py',
         'credit_only_experiment.py', 'run_credit_only.py', 'qualify_credit_only.py',
         'credit_only_runtime_probe.py', 'test_credit_only_gateway.py', 'test_credit_only_experiment.py',
         'fixtures/Dockerfile.credit-only', 'netcup/next_baseline_credit_only_20260922.json')


def digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular evidence/source file required')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root):
    bindings = source_hashes(root)
    for name in (*ADDED, 'rerun_budget.py', 'run_baseline_repeat.py', 'input_manifest.json', 'dataset_provenance.json'):
        bindings[name] = digest(Path(root) / 'stage2' / name)
    return bindings


def cells(task_ids):
    result = baseline_cells(task_ids)
    if len(result) != 178 or len(set(task_ids)) != 89:
        raise ValueError('Exactly 89 frozen tasks for both baselines required')
    for cell in result:
        cell['trial_id'] = 'creditonly1-' + cell['trial_id']
    return result


def cleanup_complete(result):
    return all(result.get(k) is True for k in ('containers_removed', 'networks_removed', 'volumes_removed')) \
        and result.get('status') != 'cleanup_failed' and not result.get('bridge_error_type')


def coverage(runtime, intended):
    """A retained failure is not a replay opportunity; missing is not failure."""
    runtime = Path(runtime)
    expected = {cell['trial_id']: cell for cell in intended}
    completed, started, partial = {}, set(), []
    for folder in ('scored-trials', 'scored-attempts'):
        path = runtime / folder
        if path.is_symlink():
            raise ValueError('Unsafe attempt directory')
        for attempt in path.iterdir() if path.exists() else []:
            if not attempt.is_dir() or attempt.is_symlink() or attempt.name not in expected:
                raise ValueError('Unexpected attempt outside frozen matrix')
            started.add(attempt.name)
    for name in started:
        result_path = runtime / 'scored-trials' / name / 'result.json'
        if not result_path.is_file() or result_path.is_symlink():
            partial.append(name)
            continue
        result = json.loads(result_path.read_text())
        cell = expected[name]
        if result.get('trial_id') != name or result.get('task_id') != cell['task_id'] or result.get('harness') != cell['harness']:
            raise ValueError('Result does not match registered cell')
        if not cleanup_complete(result):
            raise ValueError('Previous attempt still needs cleanup: ' + name)
        completed[name] = result
    return completed, sorted(partial)


def source_invariants(root, predecessor=PREDECESSOR):
    root, predecessor = Path(root), Path(predecessor)
    prior = json.loads((predecessor / '.runtime/stage2/repeat-qualification.json').read_text())
    current = sources(root)
    if any(current.get(name) != value for name, value in prior['sources'].items() if name not in CHANGED):
        raise ValueError('Nonfinancial baseline implementation changed')
    for name in ('input_manifest.json', 'dataset_provenance.json'):
        if digest(root / 'stage2' / name) != digest(predecessor / 'stage2' / name):
            raise ValueError('Frozen benchmark task set changed')
    return current, prior


def validate_qualification(root, predecessor=PREDECESSOR):
    root = Path(root)
    proof = json.loads((root / '.runtime/stage2' / QUALIFICATION).read_text())
    current, prior = source_invariants(root, predecessor)
    if (proof.get('experiment') != EXPERIMENT or proof.get('policy') != POLICY
            or proof.get('sources') != current or proof.get('parent_gateway') != prior['gateway_image']
            or proof.get('live_api_calls') != 0
            or proof.get('offline_passed') is not True or proof.get('synthetic_passed') is not True
            or proof.get('image_sources_match') is not True):
        raise ValueError('Current native provider-credit-only qualification required')
    for name, checksum in proof['evidence_sha256'].items():
        if name not in {'credit-only-offline-tests.json', 'credit-only-image-tests.json', 'credit-only-synthetic.json'}:
            raise ValueError('Unexpected qualification evidence')
        if digest(root / '.runtime/stage2' / name) != checksum:
            raise ValueError('Qualification evidence changed')
    if set(proof['evidence_sha256']) != {'credit-only-offline-tests.json', 'credit-only-image-tests.json', 'credit-only-synthetic.json'}:
        raise ValueError('Missing qualification evidence')
    return proof
