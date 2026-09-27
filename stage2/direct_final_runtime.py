"""Read-only final-host identity, not qualification or paid admission.

Only task configuration and allowlisted baseline metadata are interpreted.
Other dataset files are hashed for integrity, never used as agent input here.
No container, task, model request, image pull or registration is created.
The final runner must also authenticate the original studies, hold their
locks and require actual native synthetic qualification before dispatch.
"""
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib

import direct_final_policy as policy
import host_environment
from direct_final_evidence import ROOTS
from portable_candidate_freeze import _check_root, _digest, _regular, _source_map
from portable_custom_agent import runtime_bundle
from portable_custom_study import dependencies
from retry_experiment import DEPLOYMENT as BASELINE

KIND = 'current_final_host_identity_not_paid_admission'
BASELINE_CSV = 'stage2/results/baseline-corrected-20260923/trials.csv'
BASELINE_CSV_SHA256 = '8769a865d19bc81132166d67f85a5fb84725f2cda8f5b2a45f98b1d9993d5429'
IMAGE_ID = re.compile(r'sha256:[a-f0-9]{64}\Z')


def _read_bound(root, relative, expected):
    raw = _regular(root, relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Bound runtime or baseline metadata changed')
    return raw


def _directory(root, relative):
    # The canonical dataset lives under .cache; hidden relative roots are
    # valid, but absolute, escaping and non-normalised paths are not.
    path = PurePosixPath(relative) if isinstance(relative, str) else None
    if (path is None or not path.parts or path.is_absolute() or '..' in path.parts
            or str(path) != relative or not re.fullmatch(r'[A-Za-z0-9._/-]+', relative)):
        raise ValueError('Relative dataset directory required')
    current = Path(root)
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            raise ValueError('Regular directory within this deployment required')
    return current


def sources(root, document):
    execution = policy.candidate_execution(document)
    names = set(execution['sources']) | set(document['selection_logic_sources']) | policy.REQUIRED_SOURCE_FILES
    values = {name: _digest(Path(root) / 'stage2', name) for name in sorted(names)}
    policy.source_transition(document, values)
    # These pin the dataset location and file inventory, not just task names.
    if not {'input_manifest.json', 'dataset_provenance.json'}.issubset(values):
        raise ValueError('Original dataset and manifest sources must be bound')
    return values


def _loaded_sources(root, bindings):
    """Do not inspect one tree while executing helpers from another tree."""
    stage = (Path(root) / 'stage2').resolve()
    if Path(__file__).resolve() != stage / 'direct_final_runtime.py':
        raise ValueError('Execute the final host reader from its own deployment')
    if Path(sys.prefix).resolve() != (Path(root) / '.venv').resolve():
        raise ValueError('Use the final deployment interpreter')
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename and Path(filename).name in bindings:
            path = Path(filename)
            if path.is_symlink() or path.resolve() != stage / path.name:
                raise ValueError('A bound runtime module was loaded from another tree')


def _dataset(root, source_map):
    provenance = json.loads(_read_bound(root, 'stage2/dataset_provenance.json',
        source_map['dataset_provenance.json']))
    dataset = _directory(root, provenance['dataset_path'])
    rows = provenance['canonical']['file_hashes']
    bindings = {row['path']: row['sha256'] for row in rows}
    _source_map(bindings)
    if len(rows) != len(bindings):
        raise ValueError('Duplicate canonical dataset file')
    actual = set()
    for path in dataset.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlinked dataset content is not allowed')
        if path.is_file():
            actual.add(path.relative_to(dataset).as_posix())
    if actual != set(bindings):
        raise ValueError('Frozen dataset file inventory changed')
    for name, digest in bindings.items():
        if _digest(dataset, name) != digest:
            raise ValueError('Frozen dataset bytes changed')
    return dataset, bindings


def _task_limits(dataset, manifest):
    from harbor.models.task.config import TaskConfig
    tasks = manifest['all_task_ids']
    rows = {row['task_id']: row for row in manifest['tasks']}
    if (len(tasks) != 89 or len(set(tasks)) != 89 or len(manifest['tasks']) != 89
            or len(rows) != 89 or set(rows) != set(tasks)):
        raise ValueError('Exactly 89 original task configurations required')
    result = {}
    for task_id in tasks:
        row = rows[task_id]
        raw = _read_bound(dataset, task_id + '/task.toml', row['task_config_sha256'])
        try:
            config = TaskConfig.model_validate(tomllib.loads(raw.decode()))
        except ValueError:
            raise ValueError('Official task configuration could not be parsed') from None
        env = config.environment
        if (config.steps or config.verifier.environment is not None
                or env.network_mode.value != 'public' or env.os.value != 'linux'
                or config.agent.network_mode is not None or config.verifier.network_mode is not None
                or not env.docker_image or row['compose_present'] is not False):
            raise ValueError('Task requires unsupported execution semantics')
        for field in ('docker_image', 'cpus', 'memory_mb', 'storage_mb', 'gpus'):
            if getattr(env, field) != row[field]:
                raise ValueError('Official resource configuration differs from the manifest')
        limits = dict(agent_timeout_seconds=config.agent.timeout_sec,
            verifier_timeout_seconds=config.verifier.timeout_sec,
            build_timeout_seconds=env.build_timeout_sec)
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in limits.values()):
            raise ValueError('Positive official phase deadlines required')
        result[task_id] = dict(task_config_sha256=row['task_config_sha256'],
            docker_image=env.docker_image, cpus=env.cpus, memory_mb=env.memory_mb,
            storage_mb=env.storage_mb, gpus=env.gpus, network_mode=env.network_mode.value,
            **limits)
    return result


def _baseline_images(root, manifest):
    """Read identities only; do not return scores, failures or task content."""
    _check_root(BASELINE)
    raw = _read_bound(root, BASELINE_CSV, BASELINE_CSV_SHA256)
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    expected = {(h, t) for h in ('terminus-2', 'openhands') for t in manifest['all_task_ids']}
    seen, files, images, deadlines = set(), {}, {}, {}
    if len(rows) != 178 or len(expected) != 178:
        raise ValueError('Both completed baseline image inventories required')
    for row in rows:
        key = row['harness'], row['task_id']; name = row['trial_id']
        if (key not in expected or key in seen or name in files
                or not re.fullmatch(r'corrected1-final-(?:terminus-2|openhands)-\d{2}-[a-z0-9][a-z0-9_.-]*', name)):
            raise ValueError('Original baseline cell identity is invalid')
        _source_map({name: row['result_sha256']})
        result = json.loads(_read_bound(BASELINE,
            '.runtime/stage2/scored-trials/' + name + '/result.json', row['result_sha256']))
        if (result.get('trial_id') != name or result.get('task_id') != key[1]
                or result.get('harness') != key[0] or result.get('stage') != 'final'
                or result.get('model_protocol_sha256') != policy.SETTINGS.fingerprint()):
            raise ValueError('Baseline result identity changed')
        image = result.get('task_image_id')
        if not isinstance(image, str) or not IMAGE_ID.fullmatch(image):
            raise ValueError('Original observed task image is missing; do not invent it')
        seconds = float(row['official_agent_timeout_seconds'])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('Original official deadline is missing')
        task_id = key[1]
        if task_id in images and (images[task_id] != image or deadlines[task_id] != seconds):
            raise ValueError('Baseline harnesses used different task images or deadlines')
        seen.add(key); files[name] = row['result_sha256']
        images[task_id] = image; deadlines[task_id] = seconds
    if seen != expected:
        raise ValueError('Incomplete original baseline coverage')
    return dict(results_sha256=files, images=images, agent_deadlines=deadlines)


def _images(references):
    """Docker metadata only, no container run, build, pull or provider call."""
    references = list(references)
    if not references or any(not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_./:@-]*', r) for r in references):
        raise ValueError('Explicit local image identities required')
    template = '{"id":{{json .Id}},"os":{{json .Os}},"architecture":{{json .Architecture}}}'
    try:
        value = subprocess.run(['docker', 'image', 'inspect', '--format', template, *references],
            capture_output=True, text=True, timeout=30, check=True)
        rows = [json.loads(line) for line in value.stdout.splitlines()]
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError('Local Docker image metadata is unavailable') from None
    if (len(rows) != len(references) or any(not isinstance(row, dict)
            or set(row) != {'id', 'os', 'architecture'}
            or not isinstance(row['id'], str) or not IMAGE_ID.fullmatch(row['id'])
            or row['os'] != 'linux' or row['architecture'] != 'amd64' for row in rows)):
        raise ValueError('Pinned native Linux x86-64 image metadata required')
    return dict(zip(references, rows))


def inspect(root, document):
    """Capture the current host without claiming native qualification."""
    root = Path(root)
    _check_root(root)
    if root.resolve() in {p.resolve() for p in (*ROOTS.values(), BASELINE)}:
        raise ValueError('Use a separate final deployment')
    execution = policy.candidate_execution(document)
    bound = sources(root, document)
    _loaded_sources(root, bound)
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.cells(document, manifest)
    installed = dependencies()
    if policy.fingerprint(installed) != policy.fingerprint(execution['dependencies']):
        raise ValueError('Installed agent dependencies differ from the measured candidate')
    _regular(root, '.runtime/stage2/python-runtime.tar.gz')
    bundle = runtime_bundle(root).validate()
    host = host_environment.snapshot()
    if host.get('execution_mode') != 'native_linux_x86_64':
        raise ValueError('Final execution requires the qualified native Linux host')
    dataset, dataset_files = _dataset(root, bound)
    tasks = _task_limits(dataset, manifest)
    original = _baseline_images(root, manifest)
    current_images = _images(row['docker_image'] for row in tasks.values())
    for task_id, row in tasks.items():
        if (current_images[row['docker_image']]['id'] != original['images'][task_id]
                or row['agent_timeout_seconds'] != original['agent_deadlines'][task_id]):
            raise ValueError('Current task image or deadline differs from the baselines')
        row['image_id'] = original['images'][task_id]
    # Detect source edits during the inspection as well as before it.
    if sources(root, document) != bound:
        raise ValueError('Final source changed during runtime inspection')
    return dict(kind=KIND, paid_launch_ready=False, candidate_sha256=policy.fingerprint(document),
        model_protocol_sha256=policy.SETTINGS.fingerprint(), sources=bound,
        sources_sha256=policy.fingerprint(bound), dependencies=installed, python_runtime=bundle,
        host_environment=host, task_inventory=tasks,
        dataset_files_sha256=policy.fingerprint(dataset_files),
        baseline_csv_sha256=BASELINE_CSV_SHA256, baseline_results_sha256=original['results_sha256'])


def verify_current(root, document, proof, recorded):
    """Recheck a qualified host binding; not a replacement for the qualifier.

    The caller must already hold all study locks and must perform the separate
    original-evidence authentication. This function never dispatches a task.
    """
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.validate_qualification(proof, document, manifest)
    if policy.fingerprint(recorded) != proof['runtime_identity_sha256']:
        raise ValueError('Final qualification does not bind this host snapshot')
    current = inspect(root, document)
    if (policy.fingerprint(current) != policy.fingerprint(recorded)
            or current['sources'] != proof['sources'] or current['dependencies'] != proof['dependencies']):
        raise ValueError('Final runtime changed after qualification')
    image_ids = [proof['gateway_image'], proof['guard_image']]
    images = _images(image_ids)
    if any(images[ref]['id'] != ref for ref in image_ids):
        raise ValueError('Qualified gateway or guard image changed')
    return current
