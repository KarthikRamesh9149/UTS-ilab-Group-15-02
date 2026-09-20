"""Explicit, sequential development blocks. Never bypass host or review gates."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path

from development_selection import select
from matrix_resume import completed_cell
from native_agents import agent_factory
from qualification_review import assess, expansion_allowed
from scored_gateway import private_directory, durable_json
from scored_trial import run_trial
from scoring_admission import validate

ORDER = ('openhands', 'C0', 'C1', 'C2')


def cells(block, tasks, parent=None):
    return [dict(trial_id=f'dev-{block}-{index:02d}-{task}', task_id=task,
                 stage='development', harness=block, **({'parent': parent} if block == 'C2' else {}))
            for index, task in enumerate(tasks)]


def limits(root):
    value = json.loads((root / 'stage2/custom_execution_limits.json').read_text())
    if (set(value) != {'max_model_calls', 'max_repair_cycles'}
            or type(value['max_model_calls']) is not int or value['max_model_calls'] <= 0
            or type(value['max_repair_cycles']) is not int or value['max_repair_cycles'] != 2):
        raise ValueError('Registered positive call limit and exactly two repairs required')
    return value


async def run(root, admission, review, block):
    root = Path(root).resolve()
    if block not in ORDER:
        raise ValueError('Unregistered development block')
    settings = validate(root, admission)
    tasks = json.loads((root / 'stage2/input_manifest.json').read_text())['development_ids']
    if len(tasks) != 20 or len(set(tasks)) != 20:
        raise ValueError('Frozen dev20 required')
    runtime = private_directory(root / '.runtime/stage2')
    fd = os.open(runtime / 'matrix.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not expansion_allowed(root, assess(root, admission, review)):
            raise ValueError('First-20 qualification has not cleared expansion')
        prior = {}
        for predecessor in ORDER[:ORDER.index(block)]:
            prior[predecessor] = [completed_cell(root, cell, settings) for cell in cells(predecessor, tasks)]
            if any(row is None for row in prior[predecessor]):
                raise ValueError('Incomplete predecessor block: ' + predecessor)
        parent = None
        if block == 'C2':
            parent = select({key: prior[key] for key in ('C0', 'C1')}, task_ids=tasks,
                            protocol=settings.fingerprint())['selected_parent']
        registered = limits(root) if block != 'openhands' else None
        for predecessor in ('C0', 'C1'):
            if predecessor not in prior:
                continue
            previous_path = runtime / 'development-blocks' / (predecessor + '.json')
            if previous_path.is_symlink() or not previous_path.is_file():
                raise ValueError('Custom predecessor lacks registered configuration')
            previous = json.loads(previous_path.read_text())
            if previous.get('limits') != registered or previous.get('admission') != admission:
                raise ValueError('Custom blocks must share limits and admission')
        scheduled = cells(block, tasks, parent)
        descriptor = {'block': block, 'cells': scheduled, 'admission': admission,
                      'qualification_review': review, 'limits': registered,
                      'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        path = private_directory(runtime / 'development-blocks') / (block + '.json')
        if path.is_symlink():
            raise ValueError('Symlinked block descriptor')
        if path.exists():
            if json.loads(path.read_text()) != descriptor:
                raise ValueError('Development configuration changed; resume refused')
        else:
            if any((runtime / 'scored-trials' / cell['trial_id']).exists() for cell in scheduled):
                raise ValueError('Existing attempts have no registered block descriptor')
            durable_json(path, descriptor)
        results = []
        for cell in scheduled:
            validate(root, admission)
            if not expansion_allowed(root, assess(root, admission, review)):
                raise ValueError('Qualification no longer clears expansion')
            if registered is not None and limits(root) != registered:
                raise ValueError('Custom limits changed during block')
            row = completed_cell(root, cell, settings)
            if row is None:
                await run_trial(root=root, trial_id=cell['trial_id'], task_id=cell['task_id'],
                    stage='development', agent_factory=agent_factory(block, settings,
                        custom_max_model_calls=registered['max_model_calls'] if registered else None,
                        parent=parent), gateway_image=admission['gateway_image'],
                    guard_image=admission['guard_image'],
                    setup_timeout_seconds=admission['setup_timeout_seconds'], model_settings=settings)
                row = completed_cell(root, cell, settings)
                if row is None:
                    raise RuntimeError('Trial returned without durable evidence')
            results.append(row)
            print(json.dumps({'block': block, 'completed': len(results), 'intended': 20,
                              'trial_id': cell['trial_id']}), flush=True)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--block', choices=ORDER, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--qualification-review', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(__file__).resolve().parents[1], json.loads(args.admission.read_text()),
                    json.loads(args.qualification_review.read_text()), args.block))
