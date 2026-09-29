"""Current recovery host/library identity using a live original handoff.

Call under the future owning session's full ancestor locks. This reader takes
no locks and runs no collector, archive transfer, container, build or task.
Its returned metadata is not qualification, registration or scored admission.
"""
from copy import deepcopy
from pathlib import Path
import subprocess

import host_environment
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_libraries as libraries
import no_cutoff_recovery_policy as policy
from direct_final_runtime import _dataset as _original_dataset, _task_limits, _images
from portable_custom_agent import runtime_bundle
from portable_custom_study import dependencies

KIND = 'current_recovery_C0_NC_host_not_admission'
CURRENT_ORIGINAL_HELPERS = ('calibrate_tokenizer.py', 'extended_token_calibration.py', 'setup_probe.py')
LIMITATIONS = dict(historical_installed_bytes_attested=False, original_backup_contains_virtualenv=False,
    library_scope='all-site-packages-files-except-bytecode-caches',
    external_scripts_stdlib_os_and_container_installation='separate-runtime-and-native-qualification',
    constructor_only_not_task_execution=True, locks='required-from-owning-live-session',
    native_qualification=False, paid_launch_ready=False)


def _inputs(witness):
    record = handoff.recheck(witness)
    root = handoff._live(witness)['root']
    if root != handoff._context() or Path(__file__).absolute() != root / 'stage2/no_cutoff_recovery_runtime.py':
        raise ValueError('Own recovery runtime source and live handoff required')
    final_raw = handoff._raw(root, handoff.phase.RT + policy.ORIGINAL_FILE,
        policy.ORIGINAL_QUALIFICATION_FILE_SHA256)
    final = handoff.phase._loads(final_raw); policy.original_final(final)
    bound = handoff.operator.sources(root, final)
    if policy.fingerprint(bound) != record['current_sources_sha256']:
        raise ValueError('Current source differs from actual live handoff')
    handoff.operator.loaded(root, bound)
    manifest = handoff.phase._loads(handoff._raw(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.cells(manifest)
    original = handoff.report.ROOT
    runtime_name = handoff.phase.RT + 'no-cutoff-final-runtime.json'
    runtime_sha = handoff.report.INPUTS['no-cutoff-final-runtime.json']
    old = handoff.phase._loads(handoff._raw(original, runtime_name, runtime_sha))
    policy._same(policy.fingerprint(old), final['runtime_identity_sha256'])
    for key in ('sources', 'sources_sha256', 'dependencies', 'python_runtime', 'host_environment'):
        policy._same(old[key], final[key])
    policy._same(old['candidate_sha256'], policy.ORIGINAL_CANDIDATE)
    return root, final, bound, manifest, old, record


def _library_read(root, bindings, producer):
    program = (producer + '\nprint(json.dumps(inspect(' + repr(str(root)) + ', ' + repr(bindings) +
        '), sort_keys=True, allow_nan=False))\n')
    try:
        result = subprocess.run([str(root / '.venv/bin/python'), '-I', '-B', '-'],
            input=program, cwd=root, env=libraries.environment(root), capture_output=True,
            text=True, check=True, timeout=300)
        record = handoff.phase._loads(result.stdout.encode('utf-8'))
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
        raise ValueError('Current C0-NC library inspection failed; raw diagnostics suppressed') from None
    fixed = dict(kind=libraries.KIND, root=str(root), inputs=bindings,
        historical_installed_bytes_attested=False, recovery_execution_qualified=False,
        live_api_calls=0, paid_launch_ready=False)
    if type(record) is not dict or set(record) != set(fixed) | {
            'python', 'site_relative', 'versions', 'library_files', 'controls', 'denied_socket_constructions'}:
        raise ValueError('Exact current C0-NC library observation required')
    for key, value in fixed.items(): policy._same(record[key], value)
    if type(record['versions']) is not dict or not record['versions']:
        raise ValueError('Actual installed versions missing')
    if type(record['denied_socket_constructions']) is not int or record['denied_socket_constructions'] < 0:
        raise ValueError('Actual denied socket construction count required')
    files = record['library_files']
    if type(files) is not dict or not files: raise ValueError('Actual installed file inventory required')
    for name, sha in files.items():
        libraries.relative(name); policy._hash(sha)
    libraries.relative(record['site_relative'])
    if not record['site_relative'].startswith('.venv/'):
        raise ValueError('Own virtual environment library inventory required')
    return record


def _library_parity(root, final, bound):
    old_files = {'stage2/' + n: h for n, h in final['sources'].items()}
    # These exact unchanged helpers were not in original211. Current checks
    # do not retroactively extend the qualification or historical byte claim.
    old_files.update({'stage2/' + n: bound[n] for n in CURRENT_ORIGINAL_HELPERS})
    old_files[handoff.phase.RT + 'no-cutoff-final-qualification.json'] = policy.ORIGINAL_QUALIFICATION_FILE_SHA256
    current_files = {'stage2/' + n: h for n, h in bound.items()}
    current_files[handoff.phase.RT + policy.ORIGINAL_FILE] = policy.ORIGINAL_QUALIFICATION_FILE_SHA256
    for base, files in ((handoff.report.ROOT, old_files), (root, current_files)):
        for name, sha in files.items(): handoff._raw(base, name, sha)
    producer = handoff._raw(root, 'stage2/no_cutoff_recovery_libraries.py',
        bound['no_cutoff_recovery_libraries.py']).decode('utf-8')
    original = _library_read(handoff.report.ROOT, old_files, producer)
    current = _library_read(root, current_files, producer)
    for key in ('python', 'site_relative', 'versions', 'library_files', 'controls'):
        policy._same(original[key], current[key])
    policy._same(current['python'], final['dependencies']['python'])
    for name, version in final['dependencies']['packages'].items():
        policy._same(current['versions'].get(name), version)
    controls = current['controls']
    for key, value in dict(factory_harness='C0-NC', parent='C0', base_parent=None,
            version=policy.CANDIDATE_VERSION, model_protocol_sha256=policy.MODEL_SHA256,
            python_runtime_sha256=policy.PYTHON_SHA256).items(): policy._same(controls.get(key), value)
    policy._same(controls.get('metadata', {}).get('execution_contract'), policy.execution_contract())
    if controls.get('metadata', {}).get('max_model_calls', 'missing') is not None:
        raise ValueError('No new model-call ceiling is allowed')
    for base, files in ((handoff.report.ROOT, old_files), (root, current_files)):
        for name, sha in files.items(): handoff._raw(base, name, sha)
    return dict(original=original, recovery=current, current_only_original_helpers=list(CURRENT_ORIGINAL_HELPERS))


def _library_recheck(observed):
    """Final actual inventories/bytes, after the last native observations."""
    for record in (observed['original'], observed['recovery']):
        root = Path(record['root']); site = root / record['site_relative']
        libraries.check_files(root, record['inputs'])
        policy._same(libraries.installed_tree(root, site), record['library_files'])
        lock = handoff._raw(root, 'stage2/custom-requirements.lock',
            record['inputs']['stage2/custom-requirements.lock']).decode('utf-8')
        policy._same(libraries.versions(site, lock), record['versions'])
        libraries.check_files(root, record['inputs'])
    record = observed['recovery']; root = Path(record['root'])
    libraries.loaded(root, root / record['site_relative'], record['inputs'], record['library_files'])


def _python(root):
    name = '.runtime/stage2/python-runtime.tar.gz'
    libraries.read(root, name, policy.PYTHON_SHA256)
    record = runtime_bundle(root).validate()
    libraries.read(root, name, policy.PYTHON_SHA256)
    return record


def _dataset(root, bound):
    dataset, files = _original_dataset(root, bound)
    for name, digest in files.items():
        libraries.read(root, (dataset / name).relative_to(root).as_posix(), digest)
    return dataset, files


def inspect(witness):
    """Fresh actual reads; an in-memory witness is necessary but not admission."""
    try:
        root, final, bound, manifest, old, predecessor = _inputs(witness)
        installed = dependencies(); policy._same(installed, final['dependencies'])
        python = _python(root); policy._same(python, final['python_runtime'])
        host = host_environment.snapshot(); policy._same(host, final['host_environment'])
        if host.get('execution_mode') != 'native_linux_x86_64': raise ValueError('Original native host required')
        dataset, files = _dataset(root, bound)
        policy._same(policy.fingerprint(files), old['dataset_files_sha256'])
        inventory = _task_limits(dataset, manifest)
        if set(inventory) != set(old['task_inventory']): raise ValueError('All original official configurations required')
        for task, row in inventory.items():
            policy._same(row, {k: v for k, v in old['task_inventory'][task].items() if k != 'image_id'})
        cells = policy.cells(manifest)
        tasks = {cell['task_id']: deepcopy(old['task_inventory'][cell['task_id']]) for cell in cells}
        references = list(dict.fromkeys([row['docker_image'] for row in tasks.values()] +
            [final['gateway_image'], final['guard_image']]))
        images = _images(references)
        if set(images) != set(references): raise ValueError('All actual recovery task and parent images required')
        for row in tasks.values(): policy._same(images[row['docker_image']]['id'], row['image_id'])
        for key in ('gateway_image', 'guard_image'): policy._same(images[final[key]]['id'], final[key])
        library = _library_parity(root, final, bound)
        # Last actual host/image observations precede final file/history rereads.
        policy._same(host_environment.snapshot(), host); policy._same(_images(references), images)
        policy._same(dependencies(), installed); policy._same(_python(root), python)
        dataset_after, files_after = _dataset(root, bound)
        if dataset_after != dataset or files_after != files: raise ValueError('Dataset changed during inspection')
        policy._same(_task_limits(dataset_after, manifest), inventory)
        later = _inputs(witness)
        for first, second in zip((root, final, bound, manifest, old, predecessor), later):
            if isinstance(first, Path):
                if first != second: raise ValueError('Recovery root changed')
            else: policy._same(first, second)
        _library_recheck(library)
        # Final handoff recheck above performs the last service observation.
        # No new native observation follows these actual file rereads.
        policy._same(_python(root), python)
        final_dataset, final_files = _dataset(root, bound)
        if final_dataset != dataset or final_files != files: raise ValueError('Late dataset drift')
        policy._same(_task_limits(final_dataset, manifest), inventory)
        for name, sha in bound.items(): handoff._raw(root, 'stage2/' + name, sha)
        handoff.operator.loaded(root, bound)
        return dict(kind=KIND, experiment=policy.EXPERIMENT, condition=policy.CONDITION,
            original_qualification_sha256=policy.ORIGINAL_QUALIFICATION,
            original_runtime_sha256=final['runtime_identity_sha256'], plan_sha256=policy.PLAN_SHA256,
            predecessor_sha256=policy.fingerprint(predecessor['predecessor']),
            sources=bound, sources_sha256=policy.fingerprint(bound),
            orchestration_changes=policy.source_transition(final, bound),
            dependencies=installed, python_runtime=python, host_environment=host,
            model_protocol_sha256=policy.MODEL_SHA256, input_manifest_sha256=policy.INPUT_SHA256,
            manifest_canonical_sha256=policy.MANIFEST_SHA256, cells=cells, task_inventory=tasks,
            dataset_files_sha256=policy.fingerprint(files), original_gateway_image=final['gateway_image'],
            guard_image=final['guard_image'], library_parity=library,
            limitations=deepcopy(LIMITATIONS), paid_launch_ready=False)
    except BaseException:
        handoff.invalidate(witness)
        raise


def recheck(witness, recorded):
    """Reread both installations and host, never trust a saved identity alone."""
    try:
        current = inspect(witness)
        policy._same(current, recorded)
        return current
    except BaseException:
        handoff.invalidate(witness)
        raise
