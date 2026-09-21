"""Fresh 178-cell budget experiment; never resumes or replaces old scores."""
import asyncio
from contextlib import ExitStack
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from budget_ledger import Ledger, UNIT
from deferred_billing import register_policy
from model_protocol import ModelSettings, freeze_protocol
from native_agents import agent_factory
from openrouter_transport import OpenRouter, load_key
from run_baselines import baseline_cells
from scored_gateway import durable_json
from scored_trial import run_trial
from scoring_admission import source_hashes, validate
from study_budget import REPEAT_PROFILE, SCORED_CEILING, TRIAL_CAP, STAGE_CAPS, HISTORICAL_LIABILITY

PARENT = Path('/opt/uts-capstone')
CHANGED = {'study_budget.py', 'budget_ledger.py', 'scored_gateway.py', 'deferred_billing.py'}


def sources(root):
    result = source_hashes(root)
    for name in ('rerun_budget.py', 'run_baseline_repeat.py'):
        result[name] = hashlib.sha256((root/'stage2'/name).read_bytes()).hexdigest()
    return result


def cells(tasks):
    result = baseline_cells(tasks)
    for cell in result:
        cell['trial_id'] = 'repeat1-' + cell['trial_id']
    return result


async def run():
    root = Path(__file__).resolve().parents[1]
    if root == PARENT or REPEAT_PROFILE is None:
        raise ValueError('Separate root and authorised repeat budget required')
    runtime = root/'.runtime/stage2'
    os.umask(0o077)
    with ExitStack() as stack:
        # No old experiment can spend while this repeat owns the account.
        for path in (PARENT/'.runtime/stage2/matrix.lock', runtime/'matrix.lock'):
            handle = stack.enter_context(open(path, 'a+'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        parent_registration = PARENT/'.runtime/stage2/baseline-matrix.json'
        parent = json.loads(parent_registration.read_text())
        settings = validate(PARENT, parent['admission'])
        current = sources(root)
        parent_transition = json.loads((PARENT/'.runtime/stage2/accounting-runtime-transition-v1.json').read_text())
        for name, value in parent_transition['source_hashes'].items():
            if name not in CHANGED and current[name] != value:
                raise ValueError('Non-budget source changed: '+name)
        for name in ('input_manifest.json', 'dataset_provenance.json'):
            if (root/'stage2'/name).read_bytes() != (PARENT/'stage2'/name).read_bytes():
                raise ValueError('Task set changed')
        proof = json.loads((runtime/'repeat-qualification.json').read_text())
        if (proof['sources'] != current or proof['offline_passed'] is not True
                or proof['budget_tests_passed'] is not True or proof['synthetic_passed'] is not True
                or proof['gateway_parent'] != parent_transition['gateway_image']):
            raise ValueError('Current repeat qualification required')
        def verify_parent_ledgers():
            for name, expected in proof['parent_ledger_sha256'].items():
                if name not in ('setup_budget.sqlite', 'scored_budget.sqlite'):
                    raise ValueError('Unexpected parent ledger')
                if hashlib.sha256((PARENT/'.runtime/stage2'/name).read_bytes()).hexdigest() != expected:
                    raise ValueError('Parent accounting changed; repeat budget must be rechecked')
        if set(proof['parent_ledger_sha256']) != {'setup_budget.sqlite', 'scored_budget.sqlite'}:
            raise ValueError('Both parent ledgers must be bound')
        verify_parent_ledgers()
        manifest = json.loads((root/'stage2/input_manifest.json').read_text())
        intended = cells(manifest['all_task_ids'])
        descriptor = {'experiment': 'baseline-repeat-20260921', 'cells': intended,
                      'budget': REPEAT_PROFILE, 'sources': current,
                      'parent_registration_sha256': hashlib.sha256(parent_registration.read_bytes()).hexdigest(),
                      'model_protocol_sha256': settings.fingerprint(),
                      'gateway_image': proof['gateway_image'], 'guard_image': parent_transition['guard_image'],
                      'original_results_replaced': False, 'small_per_task_cap_removed': True}
        path = runtime/'baseline-repeat-matrix.json'
        if not path.exists(): durable_json(path, descriptor)
        if json.loads(path.read_text()) != descriptor: raise ValueError('Repeat registration drift')
        freeze_protocol(runtime, settings)
        # A fresh empty setup ledger makes clear that this repeat has no new
        # setup charges. Prior liabilities remain in HISTORICAL_LIABILITY.
        setup = Ledger(runtime/'setup_budget.sqlite', '1', '1', {'setup': '1'})
        setup.db.close()
        scored = Ledger(runtime/'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP, STAGE_CAPS,
                        allow_estimated_trials=True, deferred_billing_runtime=runtime)
        scored.db.close(); register_policy(runtime)
        client = OpenRouter(load_key(root/'.env'))
        completed = 0
        for cell in intended:
            verify_parent_ledgers()
            from rerun_budget import read_profile
            if read_profile(root) != REPEAT_PROFILE: raise ValueError('Repeat budget changed during execution')
            if sources(root) != current: raise ValueError('Source drift during repeat')
            result_path = runtime/'scored-trials'/cell['trial_id']/'result.json'
            if result_path.exists():
                result = json.loads(result_path.read_text())
            else:
                ledger = Ledger(runtime/'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP, STAGE_CAPS,
                                allow_estimated_trials=True, deferred_billing_runtime=runtime)
                exposure = Decimal(ledger.exposure())/UNIT; ledger.db.close()
                # Stop before scheduling an empty/no-budget trial. This is a
                # worst-case request reservation, not a charge or task score.
                fresh = min(Decimal(client.balance()), Decimal(client.key_status()['limit_remaining']))
                if exposure + Decimal('.106496') > Decimal(SCORED_CEILING) or fresh - Decimal(HISTORICAL_LIABILITY) < Decimal('1.106496'):
                    print(json.dumps({'status': 'paused_budget', 'completed': completed, 'intended': 178,
                                      'balance_usd': str(fresh), 'exposure_usd': str(exposure)}), flush=True)
                    return
                result = await run_trial(root=root, trial_id=cell['trial_id'], task_id=cell['task_id'],
                    stage='final', agent_factory=agent_factory(cell['harness'], settings),
                    gateway_image=proof['gateway_image'], guard_image=parent_transition['guard_image'],
                    setup_timeout_seconds=parent['admission']['setup_timeout_seconds'], model_settings=settings)
            if (result.get('verifier_result', {}).get('rewards', {}).get('reward') not in (0, 1)
                    or not all(result.get(k) is True for k in ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed'))):
                raise RuntimeError('Retained incomplete repeat attempt: '+cell['trial_id'])
            completed += 1
            print(json.dumps({'status': 'running' if completed < 178 else 'complete',
                              'completed': completed, 'intended': 178, 'trial_id': cell['trial_id']}), flush=True)


if __name__ == '__main__': asyncio.run(run())
