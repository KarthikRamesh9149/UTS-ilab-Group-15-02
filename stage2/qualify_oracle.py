"""Run frozen dev20 reference solutions without exposing them to model policy.

No model gateway, API credential or inference request is involved. Existing
attempts are preserved, including reward zero. Human-readable output contains
only task IDs, timing, infrastructure status and verifier rewards.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

from guarded_runtime import with_task_guard
from scored_gateway import durable_json, private_directory


def check_host():
    free = shutil.disk_usage('/System/Volumes/Data').free
    if free < 20_000_000_000:
        raise RuntimeError('Host free space below 20 GB')
    thermal = subprocess.check_output(['pmset', '-g', 'therm'], text=True, timeout=10)
    for key in ['CPU_Speed_Limit', 'CPU_Scheduler_Limit']:
        match = re.search(key + r'\s*=\s*(\d+)', thermal)
        if match and int(match[1]) < 100:
            raise RuntimeError('Host performance warning')
    for key in ['Thermal_Level', 'Thermal_Warning_Level']:
        match = re.search(key + r'\s*=\s*(\d+)', thermal)
        if match and int(match[1]) > 0:
            raise RuntimeError('Host thermal warning')
    pressure = int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True, timeout=10))
    if pressure >= 4:
        raise RuntimeError('Host memory pressure critical')
    return {'free_disk_bytes': free, 'memory_pressure_level': pressure, 'thermal': thermal.strip()}


def frozen_dataset(root):
    provenance = json.loads((root / 'stage2/dataset_provenance.json').read_text())
    dataset = root / provenance['dataset_path']
    expected = provenance['canonical']['file_hashes']
    actual = {str(p.relative_to(dataset)) for p in dataset.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != {row['path'] for row in expected}:
        raise ValueError('Frozen dataset file set changed')
    for row in expected:
        path = dataset / row['path']
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Frozen dataset bytes changed')
    return dataset


async def run_one(root, dataset, task_id, attempts, guard_image):
    from harbor.agents.oracle import OracleAgent
    from pinned_docker import PinnedImageDockerEnvironment as DockerEnvironment
    from harbor.models.agent.context import AgentContext
    from harbor.models.task.task import Task
    from harbor.models.trial.paths import TrialPaths
    from harbor.verifier.verifier import Verifier
    trial = attempts / task_id
    if trial.exists():
        result = trial / 'result.json'
        if result.exists():
            return json.loads(result.read_text())
        raise RuntimeError('Unfinished existing oracle attempt requires inspection: ' + task_id)
    health = check_host()
    task = Task(dataset / task_id)
    if task.has_steps or task.config.verifier.environment is not None:
        raise ValueError('Multi-step or separate verifier runtime not qualified')
    config = task.config.environment
    if config.network_mode.value not in {'public', 'none'} or task.config.agent.network_mode is not None or task.config.verifier.network_mode is not None:
        raise ValueError('Task-specific network policy requires explicit adapter support')
    trial.mkdir(mode=0o700)
    durable_json(trial / 'started.json', {'task': task_id, 'time_utc': datetime.now(timezone.utc).isoformat(), 'host': health})
    paths = TrialPaths(trial_dir=trial)
    for directory in [paths.agent_dir, paths.verifier_dir, paths.artifacts_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    compose = {'services': {'main': {'network_mode': 'none', 'cap_drop': ['NET_ADMIN', 'NET_RAW'],
                                    'security_opt': ['no-new-privileges:true']}}}
    if config.network_mode.value == 'public':
        compose = with_task_guard(compose, guard_image)
    override = trial / 'compose.json'
    durable_json(override, compose)
    name = 'uts-oracle-' + uuid.uuid4().hex[:12]
    env = DockerEnvironment(environment_dir=task.paths.environment_dir, environment_name=name,
        session_id=name, trial_paths=paths, task_env_config=config, extra_docker_compose=[override],
        # Harbor's Verifier treats Docker as mounted and therefore does not
        # download rewards. Mirror the stock Trial's explicit log mounts.
        mounts=[{'type': 'bind', 'source': str(paths.agent_dir.resolve()), 'target': '/logs/agent'},
                {'type': 'bind', 'source': str(paths.verifier_dir.resolve()), 'target': '/logs/verifier'}])
    result = {'kind': 'reference_solution_runtime_qualification_not_model_score', 'task': task_id,
        'time_utc': datetime.now(timezone.utc).isoformat(), 'live_api_calls': 0,
        'runtime_revision': 'explicit-log-mounts-v2',
        'task_limits': {'cpus': config.cpus, 'memory_mb': config.memory_mb,
                        'agent_timeout_sec': task.config.agent.timeout_sec,
                        'verifier_timeout_sec': task.config.verifier.timeout_sec},
        'status': 'started'}
    start = time.monotonic()
    try:
        await asyncio.wait_for(env.start(force_build=False), timeout=config.build_timeout_sec)
        ids = subprocess.check_output(['docker', 'ps', '-q', '--filter',
            'label=com.docker.compose.project=' + name, '--filter', 'label=com.docker.compose.service=main'], text=True).split()
        if len(ids) != 1:
            raise RuntimeError('Expected one isolated task container')
        inspected = json.loads(subprocess.check_output(['docker', 'inspect', ids[0]], text=True))[0]
        result['image_id'] = inspected['Image']
        host = inspected['HostConfig']
        if host['NanoCpus'] != int(config.cpus * 1e9) or host['Memory'] != config.memory_mb * 1024**2:
            raise RuntimeError('Task resource enforcement mismatch')
        if host['Privileged'] or host['PortBindings'] or host['CapAdd']:
            raise RuntimeError('Unexpected task privilege or host ports')
        result['resource_limits_verified'] = True
        await env.ensure_dirs(['/logs/agent', '/logs/verifier'])
        agent = OracleAgent(logs_dir=paths.agent_dir, task_dir=dataset / task_id,
                            trial_paths=paths, agent_timeout_sec=task.config.agent.timeout_sec)
        with env.with_default_user(task.config.agent.user):
            await agent.setup(env)
            await asyncio.wait_for(agent.run(task.instruction, env, AgentContext()), timeout=task.config.agent.timeout_sec)
        with env.with_default_user(task.config.verifier.user):
            verified = await asyncio.wait_for(Verifier(task, paths, env).verify(), timeout=task.config.verifier.timeout_sec)
        result['verifier'] = verified.model_dump(mode='json')
        result['status'] = 'verified'
    except Exception as exc:
        result['status'] = 'infrastructure_or_reference_failure'
        result['error_type'] = type(exc).__name__
        # Detailed local logs are not model-policy inputs and are never echoed.
        (trial / 'infrastructure-error.txt').write_text(str(exc))
    finally:
        await env.stop(delete=True)
    remaining = subprocess.check_output(['docker', 'ps', '-aq', '--filter',
        'label=com.docker.compose.project=' + name], text=True).strip()
    result['cleanup_verified'] = not remaining
    result['elapsed_seconds'] = round(time.monotonic() - start, 3)
    durable_json(trial / 'result.json', result)
    if remaining:
        raise RuntimeError('Oracle cleanup failed; do not launch next task')
    return result


async def main(task_id=None, rosetta_requalification=False):
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    runtime = private_directory(root / '.runtime/stage2')
    # Same ownership lock as scored work: never run an oracle and model trial
    # simultaneously against shared host resources.
    with (runtime / 'scored.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dataset = frozen_dataset(root)
        manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
        selected = manifest['development_ids']
        if task_id is not None:
            if task_id not in selected:
                raise ValueError('Only frozen dev20 tasks may be qualified here')
            selected = [task_id]
        # v1 omitted stock Harbor log mounts and could not collect any reward.
        # Keep its failed attempt untouched; v2 corrects only infrastructure.
        namespace = 'oracle-dev20-v2'
        if rosetta_requalification:
            translation = subprocess.check_output(
                ['colima', 'ssh', '--', 'cat', '/proc/sys/fs/binfmt_misc/rosetta'],
                text=True, timeout=20)
            if not translation.startswith('enabled\n') or 'interpreter /mnt/lima-rosetta/rosetta\n' not in translation:
                raise RuntimeError('Rosetta environment not verified')
            namespace = 'oracle-dev20-rosetta-v1'
        attempts = private_directory(runtime / namespace)
        if rosetta_requalification and not (attempts / 'environment.json').exists():
            durable_json(attempts / 'environment.json', {
                'reason': 'Host x86-64 translator changed from QEMU to Rosetta; no task or limit changes',
                'translator_registration': translation,
                'prior_attempts_preserved': 'oracle-dev20-v2',
                'time_utc': datetime.now(timezone.utc).isoformat()})
        guard_image = subprocess.check_output(['docker', 'image', 'inspect', 'uts-stage2-egress-fixture:1', '--format', '{{.Id}}'], text=True).strip()
        for identifier in selected:
            result = await run_one(root, dataset, identifier, attempts, guard_image)
            print(json.dumps(result), flush=True)
            if result['status'] != 'verified':
                break


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', help='One frozen dev20 task; omission runs the frozen sequence')
    parser.add_argument('--rosetta-requalification', action='store_true',
                        help='Separate preserved reference evidence after host translator change')
    args = parser.parse_args()
    asyncio.run(main(args.task, args.rosetta_requalification))
