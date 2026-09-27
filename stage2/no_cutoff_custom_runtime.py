"""Read-only identity of the separately versioned C0-NC development host."""
import json
from pathlib import Path
import sys

import host_environment
import no_cutoff_custom_policy as policy
from direct_final_runtime import (_read_bound, _dataset, _task_limits, _baseline_images,
    _images, BASELINE_CSV_SHA256)
from portable_candidate_freeze import _check_root, _digest, _regular
from portable_custom_agent import runtime_bundle
from portable_custom_study import dependencies

DEPLOYMENT = Path('/opt/uts-capstone-custom-no-cutoff-20260928')
KIND = 'current_no_cutoff_development_host_not_paid_admission'


def sources(root, document):
    policy.candidate_execution(document)
    names = (set(document['candidate']['c3_sources']) | set(document['selection_logic_sources'])
             | policy.REQUIRED_SOURCE_FILES)
    bound = {name: _digest(Path(root) / 'stage2', name) for name in sorted(names)}
    policy.source_transition(document, bound)
    return bound


def loaded_sources(root, bound):
    stage = Path(root).resolve() / 'stage2'
    if (Path(__file__).resolve() != stage / 'no_cutoff_custom_runtime.py'
            or Path(sys.prefix).resolve() != Path(root).resolve() / '.venv'):
        raise ValueError('Use the no-cutoff deployment source and its own native interpreter')
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename and Path(filename).name in bound:
            path = Path(filename)
            if path.is_symlink() or path.resolve() != stage / path.name:
                raise ValueError('Bound helper imported from another deployment')


def inspect(root, document):
    """Hash inputs and read configuration/identity, not task answers or logs."""
    root = Path(root)
    _check_root(root)
    if root.resolve() != DEPLOYMENT:
        raise ValueError('Use only the separate C0-NC deployment')
    execution = policy.candidate_execution(document)
    bound = sources(root, document)
    loaded_sources(root, bound)
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.cells(manifest['development_ids'])
    installed = dependencies()
    if policy.fingerprint(installed) != policy.fingerprint(execution['dependencies']):
        raise ValueError('The revision must preserve the selected parent dependencies')
    _regular(root, '.runtime/stage2/python-runtime.tar.gz')
    bundle = runtime_bundle(root).validate()
    if bundle.get('sha256') != policy.PYTHON_SHA256:
        raise ValueError('Original private Python runtime required')
    host = host_environment.snapshot()
    if host.get('execution_mode') != 'native_linux_x86_64':
        raise ValueError('Native Linux x86-64 qualification required')
    dataset, files = _dataset(root, bound)
    inventory = _task_limits(dataset, manifest)
    original = _baseline_images(root, manifest)
    tasks = {name: inventory[name] for name in manifest['development_ids']}
    images = _images(row['docker_image'] for row in tasks.values())
    for name, row in tasks.items():
        if (images[row['docker_image']]['id'] != original['images'][name]
                or row['agent_timeout_seconds'] != original['agent_deadlines'][name]):
            raise ValueError('Fixed-development task image or official deadline changed')
        row['image_id'] = original['images'][name]
    if sources(root, document) != bound:
        raise ValueError('Revision source changed during identity inspection')
    return dict(kind=KIND, paid_launch_ready=False,
        original_candidate_sha256=policy.fingerprint(document),
        sources=bound, sources_sha256=policy.fingerprint(bound),
        dependencies=installed, python_runtime=bundle, host_environment=host,
        model_protocol_sha256=policy.SETTINGS.fingerprint(), input_manifest_sha256=policy.INPUT_SHA256,
        development_ids=manifest['development_ids'], task_inventory=tasks,
        dataset_files_sha256=policy.fingerprint(files), baseline_csv_sha256=BASELINE_CSV_SHA256,
        baseline_results_sha256=original['results_sha256'])


def verify_current(root, document, proof, recorded):
    policy.validate_qualification(document, proof)
    if policy.fingerprint(recorded) != proof['runtime_identity_sha256']:
        raise ValueError('Native qualification must bind the recorded host identity')
    current = inspect(root, document)
    if (policy.fingerprint(current) != policy.fingerprint(recorded)
            or current['sources'] != proof['sources']
            or current['dependencies'] != proof['dependencies']
            or current['python_runtime'] != proof['python_runtime']
            or current['host_environment'] != proof.get('host_environment')):
        raise ValueError('Current no-cutoff source/runtime differs from qualification')
    for ref, image in _images([proof['gateway_image'], proof['guard_image']]).items():
        if image['id'] != ref:
            raise ValueError('Qualified gateway or guard is unavailable')
    return current
