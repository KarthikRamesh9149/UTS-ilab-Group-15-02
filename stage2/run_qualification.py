"""Sequential first-20 paid trials, gated by current compatibility evidence.

No default admission file, model switch, task substitution or retry path.
Results with genuine zero rewards are retained. Final expansion is separate.
"""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path

from native_agents import agent_factory
from qualification_gate import evaluate
from scoring_admission import validate
from scored_accounting import audit_trial
from scored_gateway import private_directory, durable_json
from scored_trial import run_trial


async def run(root, admission):
    root = Path(root).resolve()
    settings = validate(root, admission)
    runtime = private_directory(root / '.runtime/stage2')
    manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
    task_ids = manifest['development_ids']
    if len(task_ids) != 20 or len(set(task_ids)) != 20:
        raise ValueError('Frozen development manifest must have exactly 20 tasks')
    fd = os.open(runtime / 'matrix.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        results = []
        for index, task_id in enumerate(task_ids):
            validate(root, admission)  # Fail closed if source/evidence changed mid-run.
            trial_id = f'dev-terminus-2-{index:02d}-{task_id}'
            attempt = runtime / 'scored-trials' / trial_id
            if attempt.exists():
                path = attempt / 'result.json'
                if not path.is_file():
                    raise RuntimeError('Interrupted attempt requires audit, not replay: ' + trial_id)
                result = json.loads(path.read_text())
                if (result.get('trial_id'), result.get('task_id'), result.get('stage'), result.get('harness'), result.get('model_protocol_sha256')) != (
                        trial_id, task_id, 'development', 'terminus-2', settings.fingerprint()):
                    raise ValueError('Existing attempt identity mismatch')
                # Recheck durable receipts; do not rely on an old success flag.
                result['billing'] = audit_trial(runtime, trial_id, 'development')
            else:
                result = await run_trial(root=root, trial_id=trial_id, task_id=task_id,
                    stage='development', agent_factory=agent_factory('terminus-2', settings),
                    gateway_image=admission['gateway_image'], guard_image=admission['guard_image'],
                    setup_timeout_seconds=admission['setup_timeout_seconds'], model_settings=settings)
            if result.get('status') != 'verified' or result.get('billing', {}).get('billing_verified') is not True:
                raise RuntimeError('Trial infrastructure or billing requires inspection: ' + trial_id)
            if not all(result.get(key) is True for key in ['containers_removed', 'networks_removed', 'volumes_removed']):
                raise RuntimeError('Unverified cleanup; next trial not started')
            results.append(result)
            print(json.dumps({'completed': len(results), 'intended': 20, 'trial_id': trial_id,
                'reward': result.get('verifier_result', {}).get('rewards', {}),
                'cost_usd': result['billing']['charged_usd']}), flush=True)
        gate = evaluate(results, task_ids=task_ids, protocol_sha256=settings.fingerprint())
        # Explicitly pending trace review; this process never expands spending.
        output = runtime / 'terminus-qualification-pending-review.json'
        if not output.exists(): durable_json(output, gate)
        return gate


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--admission', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(Path(__file__).resolve().parents[1], json.loads(args.admission.read_text())))))
