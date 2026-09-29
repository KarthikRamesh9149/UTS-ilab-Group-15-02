"""Fresh current original/repeat library parity, not historical attestation.

Use under the future repeat runner's ancestor locks, after independent real
predecessor authentication. No completed collector or archive reader is called.
There is no admission route or saved-record-only authentication in this module.
"""
import json
from pathlib import Path
import platform
import subprocess

import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
import no_cutoff_final_guard as final_guard
from matched_repeat_baseline_probe import check_files, digest, regular, relative_name

ORIGINAL_ROOT = Path('/opt/uts-capstone-corrected-20260923')
FINAL_ROOT = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
ORIGINAL_FILE_SHA256 = '813b8762eae8caa6b32ccf2bee9c7fa5d0c272ff0e756b07e7251bcb2cd9e433'
FINAL_FILE_SHA256 = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
KIND = 'current_baseline_library_parity_not_historical_or_paid_admission'
LIMITATIONS = dict(historical_installed_byte_manifest_available=False,
    original_backup_contains_virtualenv=False, constructor_only_not_task_execution=True,
    library_scope='all-site-packages-files-except-bytecode-caches',
    external_scripts_stdlib_os_and_container_installation='separate-runtime-and-native-qualification',
    record_files_are_read_not_trusted_as_complete_inventory=True)


def inactive_ancestors():
    """Refuse active/stopped ancestors before loading original libraries."""
    for root, service in ((ORIGINAL_ROOT, 'uts-stage2-corrected-20260923.service'),
            (FINAL_ROOT, 'uts-stage2-custom-no-cutoff-final-20260928.service')):
        if root == FINAL_ROOT:
            final_guard.service()
        else:
            state = subprocess.run(['systemctl', 'show', service, '--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus'],
                check=True, capture_output=True, text=True).stdout
            state = dict(line.split('=', 1) for line in state.splitlines() if '=' in line)
            if state != dict(LoadState='loaded', ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'):
                raise ValueError('Completed inactive original and custom-final services required')
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            path = root / '.runtime/stage2' / name
            if path.exists() or path.is_symlink():
                raise ValueError('Persistent ancestor stop forbids repeat inspection')


def _read(root, bindings, producer):
    # The new, source-bound producer executes from stdin; old deployments are
    # never patched or made to import a new repeat module from another tree.
    program = (producer + '\nprint(json.dumps(inspect(' + repr(str(root)) + ', ' + repr(bindings) +
        '), sort_keys=True, allow_nan=False))\n')
    value = subprocess.run([str(root / '.venv/bin/python'), '-I', '-B', '-'],
        input=program, cwd=root, check=True, capture_output=True, text=True,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'DO_NOT_TRACK': '1'}, timeout=300)
    record = json.loads(value.stdout)
    expected = dict(kind='current_installed_baseline_constructor_observation', root=str(root),
        inputs=bindings, historical_installed_bytes_attested=False,
        baseline_execution_qualified=False, live_api_calls=0, paid_launch_ready=False)
    if (not isinstance(record, dict) or any(policy.fingerprint(record.get(k)) != policy.fingerprint(v)
            for k, v in expected.items())):
        raise ValueError('Unexpected installed-baseline producer result')
    library_files = record.get('library_files')
    if not isinstance(library_files, dict) or not library_files:
        raise ValueError('Installed library bytes missing')
    for name, sha in library_files.items():
        relative_name(name); policy._hash(sha)
    if not isinstance(record.get('versions'), dict) or not record['versions']:
        raise ValueError('Installed library versions missing')
    return record


def inspect(root, original, final, harness):
    """Actually reread both installations; no saved JSON shortcut."""
    policy._harness(harness)
    root = Path(root)
    if (platform.system() != 'Linux' or root != runtime.DEPLOYMENTS[harness]
            or Path(__file__).resolve() != root / 'stage2/matched_repeat_baseline.py'):
        raise ValueError('Use the distinct native repeat host inspection')
    current = runtime.sources(root, original, final)
    runtime.loaded_sources(root, current)
    inactive_ancestors()
    original_inputs = {'stage2/' + name: sha for name, sha in original['sources'].items()}
    original_inputs['.runtime/stage2/corrected-qualification.json'] = ORIGINAL_FILE_SHA256
    repeat_inputs = {'stage2/' + name: sha for name, sha in current.items()}
    repeat_inputs.update({'.runtime/stage2/' + policy.BASELINE_FILE: ORIGINAL_FILE_SHA256,
        '.runtime/stage2/' + policy.FINAL_FILE: FINAL_FILE_SHA256})
    check_files(ORIGINAL_ROOT, original_inputs)
    check_files(root, repeat_inputs)
    producer_path = regular(root, 'stage2/matched_repeat_baseline_probe.py')
    if digest(producer_path) != current['matched_repeat_baseline_probe.py']:
        raise ValueError('Current baseline inspection producer changed')
    producer = producer_path.read_text()
    observed_original = _read(ORIGINAL_ROOT, original_inputs, producer)
    observed_repeat = _read(root, repeat_inputs, producer)
    fields = ('python', 'site_relative', 'versions', 'library_files', 'controls')
    if any(policy.fingerprint(observed_original.get(k)) != policy.fingerprint(observed_repeat.get(k))
            for k in fields):
        raise ValueError('Current original/repeat installed bytes or native controls differ')
    controls = observed_original['controls']
    if (controls['model_protocol_sha256'] != policy.MODEL_SHA256
            or type(controls['terminus']['max_turns']) is not int
            or controls['terminus']['max_turns'] != 1000000
            or controls['openhands']['resolved_env'].get('MAX_ITERATIONS') != '1000000'
            or controls['openhands']['version'] != '0.62.0'
            or controls['openhands']['python_version'] != '3.12'):
        raise ValueError('Original disclosed baseline settings must be preserved')
    check_files(ORIGINAL_ROOT, original_inputs)
    check_files(root, repeat_inputs)
    inactive_ancestors()
    return dict(kind=KIND, harness=harness, experiment=policy.EXPERIMENT,
        original_qualification_sha256=policy.fingerprint(original),
        custom_final_qualification_sha256=policy.fingerprint(final),
        current_sources_sha256=policy.fingerprint(current), source_transition=policy.source_transition(original, final, current),
        original=observed_original, repeat=observed_repeat, limitations=dict(LIMITATIONS),
        paid_launch_ready=False)


def recheck(root, original, final, harness, recorded):
    """Under-lock fresh byte/constructor reread; never grants dispatch."""
    current = inspect(root, original, final, harness)
    if policy.fingerprint(current) != policy.fingerprint(recorded):
        raise ValueError('Current baseline inspection differs from the bound observation')
    return current
