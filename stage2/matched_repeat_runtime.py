"""Read-only identity checks for each separate matched-repeat native host.

This reader starts no tasks, containers, model calls, builds or image pulls.
It is not original-baseline library authentication, an off-server archive
attestation, native qualification or a dispatch permit. The future host must
perform those independent prerequisites and hold every ancestor lock before
using the recheck. A saved identity or checks:true document is not admission.
"""
import json
from pathlib import Path
import sys

import host_environment
import matched_repeat_policy as policy
from direct_final_runtime import _read_bound, _dataset, _task_limits, _baseline_images, _images
from portable_candidate_freeze import _check_root, _digest, _regular
from portable_custom_agent import runtime_bundle
from portable_custom_study import dependencies

DEPLOYMENTS = {harness: Path('/opt/uts-capstone-matched-repeat-' + harness + '-20260928')
    for harness in policy.HARNESSES}
KIND = 'current_matched_repeat_host_not_paid_admission'


def sources(root, original, final):
    names = set(policy.anchors(original, final)) | policy.REQUIRED_SOURCE_FILES
    stage = Path(root) / 'stage2'
    if stage.is_symlink() or not stage.is_dir():
        raise ValueError('Regular repeat source directory required')
    bound = {name: _digest(stage, name) for name in sorted(names)}
    policy.source_transition(original, final, bound)
    if not {'input_manifest.json', 'dataset_provenance.json'}.issubset(bound):
        raise ValueError('Exact dataset and manifest source inventory required')
    return bound


def loaded_sources(root, bound):
    stage = Path(root).resolve() / 'stage2'
    prefix = Path(root).resolve() / '.venv'
    if (Path(__file__).is_symlink() or Path(__file__).resolve() != stage / 'matched_repeat_runtime.py'
            or prefix.is_symlink() or Path(sys.prefix).is_symlink()
            or Path(sys.prefix).resolve() != prefix):
        raise ValueError('Use this separate repeat deployment and its own interpreter')
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename and Path(filename).name in bound:
            path = Path(filename)
            if path.is_symlink() or path.resolve() != stage / path.name:
                raise ValueError('Bound repeat helper imported from another deployment')


def inspect(root, original, final, harness):
    """Current file, version, host and image identity; never execution proof."""
    policy._harness(harness)
    root = Path(root)
    _check_root(root)
    if root.resolve() != DEPLOYMENTS[harness]:
        raise ValueError('Use the distinct deployment for this baseline repeat')
    bound = sources(root, original, final)
    loaded_sources(root, bound)
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    cells = policy.cells(manifest, harness)
    installed = dependencies()
    if policy.fingerprint(installed) != policy.fingerprint(final['dependencies']):
        raise ValueError('Repeat dependency versions differ from the qualified final host')
    _regular(root, '.runtime/stage2/python-runtime.tar.gz')
    bundle = runtime_bundle(root).validate()
    if (bundle.get('sha256') != policy.PYTHON_SHA256
            or policy.fingerprint(bundle) != policy.fingerprint(final['python_runtime'])):
        raise ValueError('Preserve the exact qualified Python archive identity')
    host = host_environment.snapshot()
    if (host.get('execution_mode') != 'native_linux_x86_64'
            or policy.fingerprint(host) != policy.fingerprint(final['host_environment'])):
        raise ValueError('Repeat host differs from the qualified native custom-final host')
    dataset, files = _dataset(root, bound)
    inventory = _task_limits(dataset, manifest)
    baseline = _baseline_images(root, manifest)
    tasks = {cell['task_id']: inventory[cell['task_id']] for cell in cells}
    references = [row['docker_image'] for row in tasks.values()]
    images = _images(references)
    if set(images) != set(references):
        raise ValueError('All 89 official task images must be locally available')
    for name, row in tasks.items():
        if (images[row['docker_image']]['id'] != baseline['images'][name]
                or row['agent_timeout_seconds'] != baseline['agent_deadlines'][name]):
            raise ValueError('Repeat task image or official deadline differs from the original baselines')
        row['image_id'] = baseline['images'][name]
    if sources(root, original, final) != bound:
        raise ValueError('Repeat source changed during identity inspection')
    return dict(kind=KIND, paid_launch_ready=False, experiment=policy.EXPERIMENT, harness=harness,
        original_qualification_sha256=policy.fingerprint(original),
        custom_final_qualification_sha256=policy.fingerprint(final),
        schedule_sha256=policy.fingerprint(policy.schedule(manifest)),
        sources=bound, sources_sha256=policy.fingerprint(bound),
        source_transition=policy.source_transition(original, final, bound),
        dependencies=installed, python_runtime=bundle, host_environment=host,
        model_protocol_sha256=policy.MODEL_SHA256, input_manifest_sha256=policy.INPUT_SHA256,
        manifest_canonical_sha256=policy.MANIFEST_SHA256, cells=cells, task_inventory=tasks,
        dataset_files_sha256=policy.fingerprint(files),
        baseline_csv_sha256=policy.BASELINE_CSV_SHA256,
        baseline_results_sha256=baseline['results_sha256'])


def verify_native_files(root, original, final, predecessors, manifest, proof):
    """Read all eight actual native producer files; do not trust report flags.

    This is an integrity recheck after a real qualifier, not a substitute for
    running the isolated native baseline lifecycle or authenticating its host.
    """
    policy.validate_qualification(original, final, predecessors, manifest, proof)
    for name, sha in proof['evidence_files'].items():
        if _digest(root, name) != sha:
            raise ValueError('Recorded repeat native producer bytes changed')
    regression = json.loads(_regular(root, proof['regression_path'] + '/regression.json').read_text())
    if policy.fingerprint(regression) != policy.fingerprint(proof['offline']):
        raise ValueError('Actual repeat regression report differs from qualification')
    harness = proof['harness']
    for case in proof['synthetic']:
        saved = json.loads(_regular(root, case['runtime_path'] + '/evidence.json').read_text())
        if policy.fingerprint(saved) != policy.fingerprint(case):
            raise ValueError('Actual repeat lifecycle report differs from qualification')
        trial_id = 'synthetic-matched-repeat-' + harness + '-' + case['mode']
        result = json.loads(_regular(root, case['runtime_path'] +
            '/.runtime/stage2/scored-trials/' + trial_id + '/result.json').read_text())
        cancelled = case['mode'] == 'cancel_setup'
        reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        if (result.get('status') != ('interrupted' if cancelled else 'verified')
                or result.get('trial_id') != trial_id or result.get('stage') != 'final'
                or result.get('harness') != harness
                or result.get('matched_repeat_experiment') != policy.EXPERIMENT
                or result.get('model_protocol_sha256') != policy.MODEL_SHA256
                or result.get('gateway_image_id') != proof['gateway_image']
                or result.get('model_revoked') is not True
                or any(result.get(k) is not True for k in ('containers_removed', 'networks_removed', 'volumes_removed'))
                or (reward is not None if cancelled else type(reward) not in (int, float) or reward != 1)):
            raise ValueError('Actual repeat result lacks identity, verifier, revocation or cleanup evidence')


def verify_current(root, original, final, predecessors, proof, recorded):
    """For use under all study locks after separate fresh authentication.

    No collector, off-server reader, lock acquisition or dispatch occurs here.
    This does not authenticate a caller-supplied predecessor or baseline proof.
    """
    manifest = json.loads(_read_bound(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    policy.validate_qualification(original, final, predecessors, manifest, proof)
    if policy.fingerprint(recorded) != proof['runtime_identity_sha256']:
        raise ValueError('Native repeat qualification must bind the recorded host identity')
    verify_native_files(root, original, final, predecessors, manifest, proof)
    current = inspect(root, original, final, proof['harness'])
    if (policy.fingerprint(current) != policy.fingerprint(recorded)
            or any(policy.fingerprint(current[k]) != policy.fingerprint(proof[k]) for k in (
                'sources', 'source_transition', 'dependencies', 'python_runtime', 'host_environment'))):
        raise ValueError('Current repeat source/runtime differs from qualification')
    references = [proof['gateway_image'], proof['guard_image']]
    images = _images(references)
    if set(images) != set(references) or any(images[ref]['id'] != ref for ref in references):
        raise ValueError('Both pinned repeat gateway and guard images must remain available')
    return current
