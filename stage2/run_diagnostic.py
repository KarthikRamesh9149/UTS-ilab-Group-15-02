"""One preregistered diagnostic block after freezing, not another selection round."""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path

from finalist_freeze import verify
from matrix_resume import completed_cell
from native_agents import agent_factory
from qualification_review import assess
from scored_gateway import private_directory, durable_json
from scored_trial import run_trial
from scoring_admission import validate


async def run(root, freeze, review):
    root = Path(root).resolve()
    verify(root, freeze)
    admission = freeze['admission']
    settings = validate(root, admission)
    diagnostic = freeze['selection']['diagnostic']
    if diagnostic is None:
        raise ValueError('Frozen diagnostic required')
    tasks = json.loads((root / 'stage2/input_manifest.json').read_text())['development_ids']
    if len(tasks) != 20 or len(set(tasks)) != 20:
        raise ValueError('Frozen dev20 required')
    cells = [dict(trial_id=f'dev-diagnostic-{index:02d}-{task}', task_id=task,
                  stage='development', harness=diagnostic['condition'], parent=diagnostic['parent'])
             for index, task in enumerate(tasks)]
    runtime = private_directory(root / '.runtime/stage2')
    fd = os.open(runtime / 'matrix.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if assess(root, admission, review).get('paid_expansion_allowed') is not True:
            raise ValueError('Qualification has not cleared expansion')
        descriptor = {'kind': 'frozen_diagnostic_not_selection', 'freeze': freeze,
                      'review': review, 'cells': cells}
        path = runtime / 'diagnostic-block.json'
        if path.is_symlink():
            raise ValueError('Unsafe diagnostic descriptor')
        if path.exists():
            if json.loads(path.read_text()) != descriptor:
                raise ValueError('Diagnostic configuration changed')
        else:
            if any((runtime / 'scored-trials' / cell['trial_id']).exists() for cell in cells):
                raise ValueError('Existing diagnostic attempts lack registration')
            durable_json(path, descriptor)
        results = []
        for cell in cells:
            verify(root, freeze)
            if assess(root, admission, review).get('paid_expansion_allowed') is not True:
                raise ValueError('Qualification no longer clears expansion')
            row = completed_cell(root, cell, settings)
            if row is None:
                await run_trial(root=root, trial_id=cell['trial_id'], task_id=cell['task_id'],
                    stage='development', agent_factory=agent_factory(cell['harness'], settings,
                        custom_max_model_calls=freeze['custom_max_model_calls'], parent=cell['parent']),
                    gateway_image=admission['gateway_image'], guard_image=admission['guard_image'],
                    setup_timeout_seconds=admission['setup_timeout_seconds'], model_settings=settings)
                row = completed_cell(root, cell, settings)
                if row is None:
                    raise RuntimeError('Diagnostic returned without durable evidence')
            results.append(row)
            print(json.dumps({'block': 'diagnostic', 'completed': len(results),
                              'intended': 20, 'trial_id': cell['trial_id']}), flush=True)
        # Deliberately no selection call, freeze overwrite, or final run dispatch.
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--qualification-review', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(__file__).resolve().parents[1], json.loads(args.freeze.read_text()),
                    json.loads(args.qualification_review.read_text())))
