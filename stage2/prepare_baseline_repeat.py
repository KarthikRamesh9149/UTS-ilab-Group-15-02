"""Freeze an explicitly authorised repeat budget after non-paid verification."""
from contextlib import ExitStack
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = Path('/opt/uts-capstone')


def main():
    from scored_gateway import durable_json
    from deferred_billing import validate_deferrals, unresolved_liability_nanodollars
    from openrouter_transport import OpenRouter, load_key
    runtime = ROOT/'.runtime/stage2'; parent_runtime = PARENT/'.runtime/stage2'
    assert ROOT != PARENT
    log = runtime/'repeat-offline-tests-final.log'
    assert log.read_text().rstrip().endswith(('OK', 'OK (skipped=1)')), 'Offline suite must pass (only optional PDF test may skip)'
    synthetic = json.loads((ROOT/'stage2/scored_runtime_probe_repeatbudgetv1.json').read_text())
    assert synthetic['status'] == 'passed' and synthetic['live_api_calls'] == 0
    assert all(synthetic['checks'].values())
    gateway = synthetic['gateway_image']
    transition = json.loads((parent_runtime/'accounting-runtime-transition-v1.json').read_text())
    old_image, new_image = json.loads(subprocess.check_output(
        ['docker', 'inspect', transition['gateway_image'], gateway], text=True))
    assert new_image['RootFS']['Layers'][:len(old_image['RootFS']['Layers'])] == old_image['RootFS']['Layers']
    assert new_image['Config'] == old_image['Config'], 'Gateway runtime configuration changed'
    names = ['study_budget.py', 'budget_ledger.py', 'scored_gateway.py', 'deferred_billing.py', 'rerun_budget.py']
    command = 'import pathlib,hashlib,json;print(json.dumps({n:hashlib.sha256((pathlib.Path("/study/stage2")/n).read_bytes()).hexdigest() for n in '+repr(names)+'}))'
    installed = json.loads(subprocess.check_output(['docker', 'run', '--rm', '--network=none',
        '--read-only', '--entrypoint', 'python', gateway, '-c', command], text=True))
    assert installed == {n:hashlib.sha256((ROOT/'stage2'/n).read_bytes()).hexdigest() for n in names}
    with ExitStack() as stack:
        for base in (parent_runtime, runtime):
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                handle = stack.enter_context(open(base/name, 'a+'))
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        capture = '''import sys,pathlib,sqlite3,hashlib,json
sys.path.insert(0,"/opt/uts-capstone/stage2")
from deferred_billing import validate_deferrals,unresolved_liability_nanodollars
r=pathlib.Path("/opt/uts-capstone/.runtime/stage2"); liability=0; hashes={}
for kind in ("setup","scored"):
 p=r/(kind+"_budget.sqlite"); db=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True);db.execute("BEGIN")
 liability+=unresolved_liability_nanodollars(db,validate_deferrals(r,db,kind=kind))
 hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest();db.close()
print(json.dumps({"liability":liability,"hashes":hashes}))'''
        original = json.loads(subprocess.check_output([str(PARENT/'.venv/bin/python'), '-c', capture], text=True))
        liability, hashes = original['liability'], original['hashes']
        client = OpenRouter(load_key(PARENT/'.env'))
        balance = min(Decimal(client.balance()), Decimal(client.key_status()['limit_remaining']))
        held = Decimal(liability)/10**9
        ceiling = balance-Decimal('1')-held
        assert ceiling >= Decimal('.106496'), 'Insufficient funded allowance for a request'
        profile = dict(experiment='baseline-repeat-20260921', authorised_utc_date='2026-09-21',
                       reserve_usd='1.00', historical_liability_usd=str(held),
                       starting_balance_usd=str(balance), ceiling_usd=str(ceiling))
        profile_path = runtime/'baseline-repeat-budget-v1.json'
        if profile_path.exists():
            assert json.loads(profile_path.read_text()) == profile, 'Prepared budget snapshot changed'
        else:
            durable_json(profile_path, profile)
    # New subprocesses actually load the active profile; this preparer retains
    # the old defaults solely for validating the original parent liabilities.
    command = [sys.executable, '-m', 'unittest', 'test_rerun_budget', 'test_baseline_repeat']
    result = subprocess.run(command, cwd=ROOT/'stage2', capture_output=True, text=True)
    (runtime/'repeat-active-budget-tests.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0, 'Active repeat budget tests failed'
    image_test = subprocess.run(['docker', 'run', '--rm', '--network=none', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m',
        '--entrypoint', 'python', '-w', '/study/stage2', '-v', f'{runtime}:/study/.runtime/stage2:ro', gateway,
        '-m', 'unittest', 'test_rerun_budget'], capture_output=True, text=True)
    (runtime/'repeat-image-budget-tests.log').write_text(image_test.stdout+image_test.stderr)
    assert image_test.returncode == 0, 'Image budget tests failed'
    from run_baseline_repeat import sources
    proof = dict(sources=sources(ROOT), offline_passed=True, budget_tests_passed=True,
                 synthetic_passed=True, gateway_parent=transition['gateway_image'],
                 gateway_image=gateway, parent_ledger_sha256=hashes,
                 evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                     log, runtime/'repeat-active-budget-tests.log', runtime/'repeat-image-budget-tests.log',
                     ROOT/'stage2/scored_runtime_probe_repeatbudgetv1.json')})
    durable_json(runtime/'repeat-qualification.json', proof)
    print(json.dumps({'status':'qualified', 'budget':profile, 'gateway_image':gateway, 'paid_calls':0}))


if __name__ == '__main__': main()
