"""One sequential, fixed dev20 study. Fresh trials only; no automatic replay."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from custom_python_runtime import PythonBundle
from gemini_laptop_agent import GeminiAgent
from gemini_laptop_gateway import Gateway
from gemini_laptop_logs import PrivateLog, LoggedEnvironment, ToolCallbacks
from gemini_laptop_policy import PROTOCOL, MODEL, VERSION, RESERVATION, credential, fingerprint, money, atomic_json
from local_trace import TraceSpool, PhaseRecorder
from scored_gateway import durable_json
from trial_execution import execute_phases

STUDY = 'gemini-dev20-laptop-20260930'


def environment_for(task, paths, name):
    for directory in (paths.agent_dir, paths.verifier_dir, paths.artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return DockerEnvironment(environment_dir=task.paths.environment_dir,
        environment_name=name, session_id=name, trial_paths=paths,
        task_env_config=task.config.environment,
        mounts=[{'type': 'bind', 'source': str(paths.agent_dir), 'target': '/logs/agent'},
                {'type': 'bind', 'source': str(paths.verifier_dir), 'target': '/logs/verifier'}])


def audit(environment, task):
    names = subprocess.check_output(['docker', 'ps', '-q', '--filter',
        'label=com.docker.compose.project=' + environment.session_id], text=True).split()
    if not names:
        raise RuntimeError('Task container absent')
    containers = json.loads(subprocess.check_output(['docker', 'inspect', *names]))
    if len(containers) != 1:
        raise RuntimeError('Multi-container topology requires separate qualification')
    container = containers[0]
    cfg = task.config.environment
    host = container['HostConfig']
    if host['Privileged'] or host['Memory'] != cfg.memory_mb * 1024**2 or host['NanoCpus'] != cfg.cpus * 10**9:
        raise RuntimeError('Task resource or privilege mismatch')
    if any(m['Destination'] not in {'/logs/agent', '/logs/verifier'} for m in container['Mounts']):
        raise RuntimeError('Unexpected host mount in task container')
    return dict(image_id=container['Image'], cpus=cfg.cpus, memory_mb=cfg.memory_mb,
        storage_mb_requested=cfg.storage_mb, storage_enforcement='Docker shared disk; no per-container quota',
        privileged=False, controller_key_and_socket_visible=False)


def classify(result, gateway_stop):
    if result.get('cleanup_errors') or result.get('status') not in {'verified'}:
        return 'infrastructure_failure'
    rewards = (result.get('verifier_result') or {}).get('rewards') or {}
    if rewards.get('reward') == 1:
        return 'pass'
    if gateway_stop == 'budget_stop':
        return 'budget_stop'
    if result.get('agent_error_type') not in {None, 'TimeoutError'}:
        return 'infrastructure_failure'
    return 'verifier_failure'


def report(public, registration, rows, budget, stop_reason, remaining, langfuse):
    counts = Counter(r['classification'] for r in rows)
    summary = dict(experiment=STUDY, model=MODEL, harness_version=VERSION,
        scope='new Gemini development experiment; not DeepSeek or final89',
        planned_tasks=20, started_tasks=len(rows), verified_tasks=sum(r.get('reward') in {0,1} for r in rows),
        passes=counts['pass'], verifier_failures=counts['verifier_failure'],
        infrastructure_failures=counts['infrastructure_failure'], budget_stops=counts['budget_stop'],
        unstarted_tasks=remaining, stop_reason=stop_reason, budget=budget, langfuse=langfuse,
        registration_sha256=hashlib.sha256(json.dumps(registration, sort_keys=True).encode()).hexdigest(),
        updated_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(public / 'summary.json', summary)
    atomic_json(public / 'tasks.json', rows)
    return summary


async def run(root, key_path):
    os.umask(0o077)
    private = root / '.runtime' / STUDY
    prep = json.loads((private / 'preparation.json').read_text())
    qualification = json.loads((private / 'qualification.json').read_text())
    source = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / 'stage2').glob('*.py') if not p.name.startswith('test_')}
    if qualification.get('passed') is not True or qualification.get('source_hashes') != source:
        raise RuntimeError('Successful source-bound fake qualification required')
    tasks = json.loads((root / 'stage2/input_manifest.json').read_text())['development_ids']
    if len(tasks) != 20 or len(set(tasks)) != 20:
        raise RuntimeError('Exactly twenty frozen tasks required')
    public = root / 'stage2/results' / STUDY
    public.mkdir(parents=True, exist_ok=True)
    ledger_path = private / 'ledger.json'
    if ledger_path.exists() or (private / 'registration.json').exists():
        raise RuntimeError('Study already started; do not replay')
    gateway = Gateway(credential(key_path), private)
    rows, registration, langfuse = [], {}, {'status': 'local_metadata_retained_credentials_unavailable'}
    try:
        credit = await gateway.start()
        bundle = PythonBundle(private / 'python-runtime.tar.gz', prep['python_bundle']['sha256'])
        bundle.validate()
        registration = dict(protocol=PROTOCOL, protocol_sha256=fingerprint(), task_ids=tasks,
            dataset_revision=prep['dataset_revision'], preparation=prep,
            source_hashes=source, initial_credit=credit, new_spending_limit_usd=gateway.ledger.data['cap_usd'],
            started_utc=datetime.now(timezone.utc).isoformat())
        # Public registration excludes private controller paths.
        registration['preparation'] = {k:v for k,v in prep.items() if k != 'tasks_path'}
        durable_json(private / 'registration.json', registration)
        durable_json(public / 'registration.json', registration)
        durable_json(public / 'qualification.json', qualification)
        for index, task_id in enumerate(tasks):
            await gateway.reconcile()
            current = await gateway.credit()
            if (gateway.stop_reason or gateway.ledger.known + gateway.ledger.unresolved + RESERVATION
                    > money(gateway.ledger.data['cap_usd'])
                    or gateway.ledger.unresolved + RESERVATION > money(current['available_usd'])):
                gateway.stop_reason = gateway.stop_reason or 'budget_stop'
                break
            trial_id = f'gemini-{index+1:02d}-{task_id}'
            task = Task(Path(prep['tasks_path']) / task_id)
            if task.has_steps or task.config.verifier.environment is not None:
                raise RuntimeError('Unsupported official task topology')
            paths = TrialPaths(private / 'trials' / trial_id)
            paths.trial_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            env = environment_for(task, paths, 'uts-gemini-' + uuid.uuid4().hex[:12])
            row = dict(task_id=task_id, trial_id=trial_id, classification='infrastructure_failure',
                agent_timeout_seconds=task.config.agent.timeout_sec,
                verifier_timeout_seconds=task.config.verifier.timeout_sec)
            rows.append(row)
            started = time.monotonic()
            before = len(gateway.ledger.data['requests'])
            result = {}
            try:
                await asyncio.wait_for(env.start(force_build=False), task.config.environment.build_timeout_sec)
                row['environment'] = audit(env, task)
                recorder = PhaseRecorder(TraceSpool(private / 'traces' / trial_id),
                    trial_id=trial_id, task_id=task_id, harness='C0-NC', protocol_sha256=fingerprint())
                private_log = PrivateLog(paths.trial_dir / 'private-activity.jsonl')
                observed_env = LoggedEnvironment(env, private_log)
                callbacks = ToolCallbacks(recorder, private_log)
                gateway.recorder = recorder
                agent = GeminiAgent(paths.agent_dir, gateway, bundle, task.config.agent.timeout_sec,callbacks)
                result = await execute_phases(agent=agent, environment=observed_env, task=task, paths=paths,
                    revoke_model=gateway.revoke, setup_timeout_seconds=180,
                    phase_observer=recorder, retained_result=result)
                row.update(classification=classify(result, gateway.stop_reason),
                    reward=((result.get('verifier_result') or {}).get('rewards') or {}).get('reward'),
                    status=result.get('status'), agent_error_type=result.get('agent_error_type'),
                    verifier_error_type=result.get('verifier_error_type'), cleanup_errors=result.get('cleanup_errors'),
                    phase_seconds=result.get('phase_seconds'), model_attempts=(result.get('agent_context', {}).get('metadata') or {}).get('model_attempts'))
                row['trace_errors'] = callbacks.observer.errors + gateway.trace_errors + result.get('trace_errors',[])
                gateway.recorder = None
            except BaseException as error:
                row.update(error_type=type(error).__name__)
                try:
                    await gateway.revoke()
                    await asyncio.wait_for(env.stop(delete=True), 60)
                except Exception as cleanup:
                    row['cleanup_errors'] = [type(cleanup).__name__]
                if isinstance(error, asyncio.CancelledError):
                    gateway.stop_reason = 'interrupted'
                    raise
            finally:
                row['duration_seconds'] = time.monotonic() - started
                durable_json(paths.trial_dir / 'private-result.json', result)
                requests = gateway.ledger.data['requests'][before:]
                row.update(physical_requests=len(requests),
                    known_spending_usd=str(sum((money(r['cost_usd']) for r in requests if r.get('cost_usd') is not None), Decimal(0))),
                    unresolved_requests=sum(r.get('cost_usd') is None for r in requests))
                report(public, registration, rows, gateway.ledger.report(), gateway.stop_reason,
                    tasks[len(rows):], langfuse)
                print(json.dumps(row), flush=True)
            if row.get('cleanup_errors'):
                gateway.stop_reason = 'cleanup_failure'
                break
        await gateway.reconcile()
        final_credit = await gateway.credit()
        atomic_json(public / 'request-metadata.json', gateway.ledger.data['requests'])
        budget = dict(gateway.ledger.report(), initial_credit=credit, final_credit=final_credit,
            account_usage_delta_usd=str(money(final_credit['key_usage_usd']) - money(credit['key_usage_usd'])),
            account_delta_may_include_other_key_users=True)
        if all(os.environ.get(k) for k in ('LANGFUSE_BASE_URL','LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY')):
            from local_langfuse import export
            try:
                receipts = [export(p, base_url=os.environ['LANGFUSE_BASE_URL'],
                    public_key=os.environ['LANGFUSE_PUBLIC_KEY'], secret_key=os.environ['LANGFUSE_SECRET_KEY'],
                    track='gemini-laptop') for p in (private / 'traces').iterdir()]
                langfuse = dict(status='transport_acknowledged_not_dashboard_verified', trials=len(receipts))
            except Exception as error:
                langfuse = dict(status='export_failed_local_metadata_retained', error_type=type(error).__name__)
        final = report(public, registration, rows, budget,
            gateway.stop_reason or ('twenty_attempts_complete' if len(rows) == 20 else 'stopped'),
            tasks[len(rows):], langfuse)
        print(json.dumps(final), flush=True)
    finally:
        if hasattr(gateway, 'ledger'):
            try:
                await gateway.close()
            finally:
                if registration and len(rows) < 20:
                    report(public, registration, rows, gateway.ledger.report(),
                        gateway.stop_reason or 'orchestrator_error', tasks[len(rows):], langfuse)
        elif hasattr(gateway, 'session'):
            await gateway.session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, default=Path('/run/openrouter-key'))
    args = parser.parse_args()
    lock_path = Path('.runtime') / STUDY / 'study.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        async def bounded():
            loop = asyncio.get_running_loop()
            current = asyncio.current_task()
            for signum in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(signum, current.cancel)
            await run(Path.cwd(), args.key_file)
        asyncio.run(bounded())


if __name__ == '__main__':
    main()
