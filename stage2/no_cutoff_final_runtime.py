"""Read-only final-host identity for the measured C0-NC runtime and all 89 tasks.

No container, image pull or model request is started here. This identity and
the producer-file checks cannot replace original/revision authentication or
actual native synthetic qualification of the final execution path.
"""
import json
from pathlib import Path
import sys

import host_environment
import no_cutoff_final_policy as policy
from direct_final_runtime import (_read_bound, _dataset, _task_limits, _baseline_images,
    _images, BASELINE_CSV_SHA256)
from portable_candidate_freeze import _check_root, _digest, _regular
from portable_custom_agent import runtime_bundle
from portable_custom_study import dependencies

DEPLOYMENT = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
KIND = 'current_no_cutoff_final_host_not_paid_admission'


def sources(root, document):
    execution = policy.candidate_execution(document)
    names = (set(execution['sources']) | set(document['original_candidate']['selection_logic_sources'])
        | set(document['freeze_logic_sources']) | policy.REQUIRED_SOURCE_FILES)
    bound = {name: _digest(Path(root) / 'stage2', name) for name in sorted(names)}
    policy.source_transition(document, bound)
    return bound


def loaded_sources(root, bound):
    stage = Path(root).resolve() / 'stage2'
    if (Path(__file__).resolve() != stage / 'no_cutoff_final_runtime.py'
            or Path(sys.prefix).resolve() != Path(root).resolve() / '.venv'):
        raise ValueError('Use the separate final deployment source and its own native interpreter')
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename and Path(filename).name in bound:
            path = Path(filename)
            if path.is_symlink() or path.resolve() != stage / path.name:
                raise ValueError('Bound final helper imported from another deployment')


def inspect(root, document):
    root = Path(root)
    _check_root(root)
    if root.resolve() != DEPLOYMENT:
        raise ValueError('Use only the separate no-cutoff final deployment')
    execution = policy.candidate_execution(document)
    bound = sources(root, document)
    loaded_sources(root, bound)
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    cells = policy.cells(document, manifest)
    installed = dependencies()
    if policy.fingerprint(installed) != policy.fingerprint(execution['dependencies']):
        raise ValueError('Final host must preserve the measured revision dependencies')
    _regular(root, '.runtime/stage2/python-runtime.tar.gz')
    bundle = runtime_bundle(root).validate()
    if bundle.get('sha256') != policy.PYTHON_SHA256:
        raise ValueError('Original private Python runtime required')
    host = host_environment.snapshot()
    if host.get('execution_mode') != 'native_linux_x86_64':
        raise ValueError('Native Linux x86-64 final qualification required')
    dataset, files = _dataset(root, bound)
    inventory = _task_limits(dataset, manifest)
    original = _baseline_images(root, manifest)
    tasks = {cell['task_id']: inventory[cell['task_id']] for cell in cells}
    images = _images(row['docker_image'] for row in tasks.values())
    for name, row in tasks.items():
        if (images[row['docker_image']]['id'] != original['images'][name]
                or row['agent_timeout_seconds'] != original['agent_deadlines'][name]):
            raise ValueError('Final task image or official agent deadline differs from the baseline')
        row['image_id'] = original['images'][name]
    if sources(root, document) != bound:
        raise ValueError('Final source changed during identity inspection')
    return dict(kind=KIND, paid_launch_ready=False, candidate_sha256=policy.fingerprint(document),
        original_candidate_sha256=policy.fingerprint(document['original_candidate']),
        validation_results_sha256=policy.fingerprint(document['result_bindings']),
        sources=bound, sources_sha256=policy.fingerprint(bound), dependencies=installed,
        python_runtime=bundle, host_environment=host, model_protocol_sha256=policy.SETTINGS.fingerprint(),
        input_manifest_sha256=policy.INPUT_SHA256, manifest_canonical_sha256=policy.MANIFEST_SHA256,
        cells=cells, task_inventory=tasks, dataset_files_sha256=policy.fingerprint(files),
        baseline_csv_sha256=BASELINE_CSV_SHA256, baseline_results_sha256=original['results_sha256'])


def verify_native_files(root, proof):
    """Re-read real producer bytes; checks:true fields alone are insufficient."""
    for name, sha in proof['evidence_files'].items():
        if _digest(root, name) != sha:
            raise ValueError('Recorded final native qualification output changed')
    regression = json.loads(_regular(root, proof['regression_path'] + '/regression.json').read_text())
    if policy.fingerprint(regression) != policy.fingerprint(proof['offline']):
        raise ValueError('Native final regression report differs from qualification')
    for case in proof['synthetic']:
        saved = json.loads(_regular(root, case['runtime_path'] + '/evidence.json').read_text())
        if policy.fingerprint(saved) != policy.fingerprint(case):
            raise ValueError('Native final lifecycle report differs from qualification')
        result = json.loads(_regular(root, case['runtime_path'] +
            '/.runtime/stage2/scored-trials/synthetic-nc-final-' + case['mode'] + '/result.json').read_text())
        cancelled = case['mode'] == 'cancel_setup'
        reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        if (result.get('status') != ('interrupted' if cancelled else 'verified')
                or result.get('trial_id') != 'synthetic-nc-final-' + case['mode']
                or result.get('stage') != 'final' or result.get('harness') != policy.CONDITION
                or result.get('custom_study') != policy.EXPERIMENT
                or result.get('gateway_image_id') != proof['gateway_image']
                or result.get('model_revoked') is not True
                or any(result.get(k) is not True for k in ('containers_removed', 'networks_removed', 'volumes_removed'))
                or (reward is not None if cancelled else type(reward) not in (int, float) or reward != 1)):
            raise ValueError('Actual final native result lacks required identity, verifier, revocation or cleanup')


def verify_current(root, document, proof, recorded):
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.validate_qualification(document, manifest, proof)
    if policy.fingerprint(recorded) != proof['runtime_identity_sha256']:
        raise ValueError('Final native qualification must bind the recorded host identity')
    verify_native_files(root, proof)
    current = inspect(root, document)
    if (policy.fingerprint(current) != policy.fingerprint(recorded)
            or current['sources'] != proof['sources'] or current['dependencies'] != proof['dependencies']
            or current['python_runtime'] != proof['python_runtime']
            or current['host_environment'] != proof['host_environment']):
        raise ValueError('Current final source/runtime differs from qualification')
    references = [proof['gateway_image'], proof['guard_image']]
    images = _images(references)
    if set(images) != set(references):
        raise ValueError('Both qualified final images must remain available')
    for ref, image in images.items():
        if image['id'] != ref:
            raise ValueError('Qualified final gateway or guard image is unavailable')
    return current
