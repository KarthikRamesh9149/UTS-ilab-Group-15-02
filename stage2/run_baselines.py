"""Run the 178 registered final baseline cells before custom development.

These are the baseline part of the existing 267-cell final evaluation, not
extra attempts. Registration, qualification and the shared trial gateway remain
mandatory. Outcomes outside dev20 must stay out of custom development decisions.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path

from final_schedule import schedule
from matrix_resume import completed_cell
from native_agents import agent_factory
from qualification_review import assess, expansion_allowed
from scored_gateway import private_directory, durable_json
from scored_trial import run_trial
from scoring_admission import source_hashes, validate
from receipt_runtime_transition import descriptor_matches


BASELINE_ROLES = ('terminus-2', 'openhands')
REGISTRATION = 'baseline-matrix.json'
BINDING_FILES = ('run_baselines.py', 'final_schedule.py', 'input_manifest.json',
                 'dataset_provenance.json', 'budget_policy.json')


def baseline_cells(task_ids):
    """Return canonical final cells; baseline identity is custom-independent."""
    return [cell for cell in schedule(task_ids, custom_condition='C0')
            if cell['role'] in BASELINE_ROLES]


def _manifest(root):
    path = root / 'stage2/input_manifest.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError('Safe frozen task manifest required')
    manifest = json.loads(path.read_text())
    tasks, development = manifest['all_task_ids'], manifest['development_ids']
    baseline_cells(tasks)
    if (len(development) != 20 or len(set(development)) != 20
            or not set(development).issubset(tasks)):
        raise ValueError('Exactly the frozen 20 development tasks required')
    return manifest


def _bindings(root):
    hashes = dict(source_hashes(root))
    for name in BINDING_FILES:
        path = root / 'stage2' / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or unsafe baseline registration input')
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _descriptor(root, admission, review, settings):
    manifest = _manifest(root)
    return {
        'kind': 'final_baselines_registered_before_custom_freeze',
        'schema_version': 1,
        'admission': admission,
        'model_protocol_sha256': settings.fingerprint(),
        'source_hashes': _bindings(root),
        'qualification_review': review,
        'cells': baseline_cells(manifest['all_task_ids']),
        'development_task_ids': manifest['development_ids'],
        'outside_development_outcomes': 'withheld_from_custom_development_until_finalist_freeze',
        'baseline_cells': 178,
        'planned_final_cells': 267,
        'additional_baseline_attempts_authorised': False,
    }


def _existing_attempts(root, cells, *, registered, admission):
    """Reject orphan/noncanonical attempts, including gateway-only partials."""
    runtime = root / '.runtime/stage2'
    baseline_ids = {cell['trial_id'] for cell in cells}
    all_ids = {cell['trial_id'] for cell in schedule(
        _manifest(root)['all_task_ids'], custom_condition='C0')}
    custom_present = False
    for directory in ('scored-trials', 'scored-attempts'):
        folder = runtime / directory
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError('Unsafe scored attempt directory')
        if not folder.exists():
            continue
        for attempt in folder.iterdir():
            if not attempt.name.startswith('final-'):
                continue
            if not registered:
                raise ValueError('Final attempts lack original baseline registration')
            if attempt.is_symlink() or not attempt.is_dir() or attempt.name not in all_ids:
                raise ValueError('Unknown or unsafe final attempt')
            if directory == 'scored-attempts':
                trial = runtime / 'scored-trials' / attempt.name
                if trial.is_symlink() or not trial.is_dir():
                    raise ValueError('Existing gateway attempt lacks trial evidence; replay refused')
            custom_present |= attempt.name not in baseline_ids
    if custom_present:
        # The final runner owns the deeper finalist/evidence audit. This guard
        # prevents a baseline-only registration from authorising custom calls.
        path = runtime / 'final-matrix.json'
        if path.is_symlink() or not path.is_file():
            raise ValueError('Custom final attempts lack final registration')
        final = json.loads(path.read_text())
        final_cells = final.get('cells', [])
        freeze = final.get('freeze', {})
        selection = freeze.get('selection', {})
        selected = selection.get('selected')
        expected = schedule(_manifest(root)['all_task_ids'], custom_condition=selected,
                            custom_parent=selection.get('selected_parent') if selected == 'C2' else None)
        if (final.get('kind') != 'final_evaluation_started'
                or freeze.get('admission') != admission
                or final.get('baseline_registration_sha256') != hashlib.sha256(
                    (runtime / REGISTRATION).read_bytes()).hexdigest()
                or final_cells != expected
                or [cell for cell in final_cells if cell['role'] in BASELINE_ROLES] != cells):
            raise ValueError('Custom final attempts have incompatible registration')


def validate_registration(root, admission):
    """Read-only revalidation for baseline and later full-final runners.

    The caller owns matrix.lock whenever this check admits execution. Results
    are consumed separately through completed_cell, which audits durable trial
    and billing evidence and never replays an existing failed attempt.
    """
    root = Path(root).resolve()
    runtime = root / '.runtime/stage2'
    if runtime.is_symlink():
        raise ValueError('Unsafe runtime directory')
    path = runtime / REGISTRATION
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Unsafe baseline registration')
    cells = baseline_cells(_manifest(root)['all_task_ids'])
    if not path.exists():
        _existing_attempts(root, cells, registered=False, admission=admission)
        return None
    descriptor = json.loads(path.read_text())
    if not isinstance(descriptor, dict):
        raise ValueError('Invalid baseline registration')
    settings = validate(root, admission)
    review = descriptor.get('qualification_review')
    if not isinstance(review, dict) or not descriptor_matches(
            root, admission, descriptor, _descriptor(root, admission, review, settings)):
        raise ValueError('Baseline configuration or evidence changed; resume refused')
    if not expansion_allowed(root, assess(root, admission, review)):
        raise ValueError('Qualification no longer clears baseline expansion')
    _existing_attempts(root, cells, registered=True, admission=admission)
    return descriptor


async def run(root, admission, review):
    root = Path(root).resolve()
    settings = validate(root, admission)
    runtime = private_directory(root / '.runtime/stage2')
    fd = os.open(runtime / 'matrix.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not expansion_allowed(root, assess(root, admission, review)):
            raise ValueError('Qualification has not cleared baseline expansion')
        expected = _descriptor(root, admission, review, settings)
        descriptor = validate_registration(root, admission)
        if descriptor is None:
            durable_json(runtime / REGISTRATION, expected)
            descriptor = validate_registration(root, admission)
        if not descriptor_matches(root, admission, descriptor, expected):
            raise ValueError('Baseline review or registration changed; resume refused')
        results = []
        for cell in descriptor['cells']:
            if validate_registration(root, admission) != descriptor:
                raise ValueError('Baseline registration changed during execution')
            row = completed_cell(root, cell, settings)
            if row is None:
                await run_trial(root=root, trial_id=cell['trial_id'], task_id=cell['task_id'],
                    stage='final', agent_factory=agent_factory(cell['harness'], settings),
                    gateway_image=admission['gateway_image'], guard_image=admission['guard_image'],
                    setup_timeout_seconds=admission['setup_timeout_seconds'], model_settings=settings)
                row = completed_cell(root, cell, settings)
                if row is None:
                    raise RuntimeError('Baseline trial returned without durable evidence')
            results.append(row)
            # Deliberately omit rewards/costs from progress: the non-dev20
            # outcomes must not become inputs to custom policy development.
            print(json.dumps({'completed': len(results), 'intended': 178,
                              'trial_id': cell['trial_id']}), flush=True)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--qualification-review', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(__file__).resolve().parents[1], json.loads(args.admission.read_text()),
                    json.loads(args.qualification_review.read_text())))
