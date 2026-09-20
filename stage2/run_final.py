"""Fresh, frozen 89-by-three evaluation; no retries or success inference."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path

from final_schedule import schedule
from finalist_freeze import verify
from matrix_resume import completed_cell
from native_agents import agent_factory
from qualification_review import assess, expansion_allowed
from scored_gateway import private_directory, durable_json
from scored_trial import run_trial
from scoring_admission import validate


def prerequisites(root, freeze, review, tasks, settings):
    runtime = root / '.runtime/stage2'
    diagnostic = freeze['selection']['diagnostic']
    if diagnostic is None or len(tasks) != 20 or len(set(tasks)) != 20:
        raise ValueError('Complete registered development required')
    diagnostic_cells = [dict(trial_id=f'dev-diagnostic-{i:02d}-{task}', task_id=task,
        stage='development', harness=diagnostic['condition'], parent=diagnostic['parent'])
        for i, task in enumerate(tasks)]
    path = runtime / 'diagnostic-block.json'
    expected = {'kind': 'frozen_diagnostic_not_selection', 'freeze': freeze,
                'review': review, 'cells': diagnostic_cells}
    if path.is_symlink() or not path.is_file() or json.loads(path.read_text()) != expected:
        raise ValueError('Matching diagnostic registration required')
    cells = [dict(trial_id=f'dev-openhands-{i:02d}-{task}', task_id=task,
                  stage='development', harness='openhands') for i, task in enumerate(tasks)] + diagnostic_cells
    hashes = {}
    for cell in cells:
        if completed_cell(root, cell, settings) is None:
            raise ValueError('Development block incomplete: ' + cell['trial_id'])
        result = runtime / 'scored-trials' / cell['trial_id'] / 'result.json'
        hashes[cell['trial_id']] = hashlib.sha256(result.read_bytes()).hexdigest()
    return hashes


async def run(root, freeze, review):
    root = Path(root).resolve()
    selected = verify(root, freeze)
    admission = freeze['admission']
    settings = validate(root, admission)
    manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
    tasks = manifest['all_task_ids']
    if not set(manifest['development_ids']).issubset(tasks):
        raise ValueError('Development tasks must belong to final benchmark')
    cells = schedule(tasks, custom_condition=selected,
                     custom_parent=freeze['selection']['selected_parent'] if selected == 'C2' else None)
    runtime = private_directory(root / '.runtime/stage2')
    fd = os.open(runtime / 'matrix.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not expansion_allowed(root, assess(root, admission, review)):
            raise ValueError('Qualification has not cleared expansion')
        evidence = prerequisites(root, freeze, review, manifest['development_ids'], settings)
        descriptor = {'kind': 'final_evaluation_started', 'freeze': freeze, 'review': review,
                      'development_evidence': evidence, 'cells': cells}
        baseline_path = runtime / 'baseline-matrix.json'
        baseline_registration = None
        if baseline_path.exists() or baseline_path.is_symlink():
            from run_baselines import validate_registration
            baseline_registration = validate_registration(root, admission)
            descriptor['baseline_registration_sha256'] = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
        path = runtime / 'final-matrix.json'
        if path.is_symlink():
            raise ValueError('Unsafe final descriptor')
        if path.exists():
            if json.loads(path.read_text()) != descriptor:
                raise ValueError('Final configuration or evidence changed; resume refused')
        else:
            baseline_ids = {cell['trial_id'] for cell in baseline_registration['cells']} if baseline_registration else set()
            for cell in cells:
                attempt = runtime / 'scored-trials' / cell['trial_id']
                if attempt.exists() or attempt.is_symlink():
                    if (cell['role'] == 'custom' or cell['trial_id'] not in baseline_ids
                            or completed_cell(root, cell, settings) is None):
                        raise ValueError('Final attempt lacks its original baseline or frozen registration')
            durable_json(path, descriptor)
        results = []
        for cell in cells:
            verify(root, freeze)
            if baseline_registration is not None:
                validate_registration(root, admission)
                if hashlib.sha256(baseline_path.read_bytes()).hexdigest() != descriptor['baseline_registration_sha256']:
                    raise ValueError('Original baseline registration changed during final run')
            if not expansion_allowed(root, assess(root, admission, review)):
                raise ValueError('Qualification no longer clears expansion')
            row = completed_cell(root, cell, settings)
            if row is None:
                await run_trial(root=root, trial_id=cell['trial_id'], task_id=cell['task_id'],
                    stage='final', agent_factory=agent_factory(cell['harness'], settings,
                        custom_max_model_calls=freeze['custom_max_model_calls'] if cell['role'] == 'custom' else None,
                        parent=cell['parent']), gateway_image=admission['gateway_image'],
                    guard_image=admission['guard_image'],
                    setup_timeout_seconds=admission['setup_timeout_seconds'], model_settings=settings)
                row = completed_cell(root, cell, settings)
                if row is None:
                    raise RuntimeError('Final trial returned without durable evidence')
            results.append(row)
            print(json.dumps({'completed': len(results), 'intended': 267,
                              'trial_id': cell['trial_id']}), flush=True)
        return results  # Analysis and success assessment are separate.


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--qualification-review', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(__file__).resolve().parents[1], json.loads(args.freeze.read_text()),
                    json.loads(args.qualification_review.read_text())))
