"""Trusted single-trial wiring; no CLI, implicit selection, or automatic retry.

The matrix must qualify and freeze an agent factory before calling this module.
No environment is started on import. The caller cannot substitute dataset bytes.
"""
import asyncio
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import uuid

from host_model_bridge import HostModelBridge
from production_compose import compose_runtime
from qualify_oracle import check_host, frozen_dataset
from scored_gateway import durable_json, private_directory
from trial_execution import execute_phases
from scored_accounting import audit_trial
from model_protocol import ModelSettings, freeze_protocol
from paid_trace import PaidTrialTrace
from post_trial_receipts import collect_receipts
from task_preparation import refresh_package_metadata
from completion_wait import completion_wait_for


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True,
                                   stderr=subprocess.PIPE, timeout=60).strip()


def service(project, name):
    ids = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project,
                 '--filter', 'label=com.docker.compose.service=' + name).split()
    if len(ids) != 1:
        raise RuntimeError('Expected exactly one owned service')
    return json.loads(docker('inspect', ids[0]))[0]


def audit_task(inspected, config, paths):
    host = inspected['HostConfig']
    if host['Privileged'] or host['CapAdd'] or host['PortBindings']:
        raise RuntimeError('Unexpected task privilege or published port')
    dropped = {cap.removeprefix('CAP_') for cap in host['CapDrop'] or []}
    if not {'NET_ADMIN', 'NET_RAW'} <= dropped or not host['NetworkMode'].startswith('container:'):
        raise RuntimeError('Task does not use the guarded namespace')
    if not any(option in {'no-new-privileges', 'no-new-privileges:true'}
               for option in host['SecurityOpt'] or []):
        raise RuntimeError('Task privilege escalation safeguard missing')
    if host['NanoCpus'] != int(config.cpus * 1e9) or host['Memory'] != config.memory_mb * 1024**2:
        raise RuntimeError('Official task resources not enforced')
    expected = {'/logs/agent': str(paths.agent_dir.resolve()),
                '/logs/verifier': str(paths.verifier_dir.resolve())}
    mounts = inspected['Mounts']
    # Harbor's other automatic bind mounts must be explicitly qualified, not
    # accepted by guessing that a new host mount is safe.
    if len(mounts) != len(expected) or any(
            mount['Type'] != 'bind' or expected.get(mount['Destination']) != mount['Source']
            for mount in mounts):
        raise RuntimeError('Unqualified task mount')


async def run_trial(*, root, trial_id, task_id, stage, agent_factory,
                    gateway_image, guard_image, setup_timeout_seconds, model_settings,
                    billing_runtime=None, billing_kind='scored'):
    """Run one qualified native agent; factory gets only task timeout, not tests.

    Factory arguments: paths, host_api_base, container_api_base, trial_token,
    agent_timeout_seconds, completion_wait_seconds. These are trusted
    orchestration values, never model input; the official deadline is unchanged.
    Billing reconciliation/selection and final protocol admission remain the
    matrix's responsibility. An interrupted attempt is retained and not resumed.
    """
    from pinned_docker import PinnedImageDockerEnvironment as DockerEnvironment
    from harbor.models.task.task import Task
    from harbor.models.trial.paths import TrialPaths
    import math
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
        raise ValueError('Invalid trial ID')
    if stage not in {'development', 'final'} or not callable(agent_factory):
        raise ValueError('Explicit stage and qualified factory required')
    if not isinstance(model_settings, ModelSettings):
        raise ValueError('Explicit shared model protocol required')
    if type(setup_timeout_seconds) not in (int, float) or not math.isfinite(setup_timeout_seconds) or setup_timeout_seconds <= 0:
        raise ValueError('Positive setup limit required')
    root = Path(root).resolve()
    runtime = private_directory(root / '.runtime/stage2')
    fd = os.open(runtime / 'scored.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        health = check_host()
        protocol_hash = freeze_protocol(runtime, model_settings)
        factory_protocol = getattr(agent_factory, 'model_protocol_sha256', protocol_hash)
        if factory_protocol != protocol_hash:
            raise ValueError('Agent factory and gateway model settings differ')
        from receipt_runtime_transition import gateway_for_trial
        gateway_image, accounting_transition = gateway_for_trial(
            root, gateway_image, guard_image, model_settings)
        manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
        allowed = manifest['development_ids' if stage == 'development' else 'all_task_ids']
        if task_id not in allowed:
            raise ValueError('Task outside frozen split')
        task = Task(frozen_dataset(root) / task_id)
        completion_wait_seconds = completion_wait_for(task.config.agent.timeout_sec)
        if task.has_steps or task.config.verifier.environment is not None:
            raise ValueError('Unqualified separate verifier or multistep runtime')
        if task.config.environment.network_mode.value != 'public' or task.config.agent.network_mode is not None or task.config.verifier.network_mode is not None:
            raise ValueError('Task network policy requires explicit adapter qualification')
        trial = private_directory(runtime / 'scored-trials') / trial_id
        trial.mkdir(mode=0o700)  # No replay, including interrupted attempts.
        paths = TrialPaths(trial_dir=trial)
        for path in [paths.agent_dir, paths.verifier_dir, paths.artifacts_dir]:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        token = secrets.token_hex(32)
        token_file = trial / 'token'
        token_fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(token_fd, 'w') as handle:
            handle.write(token)
        project = 'uts-scored-' + uuid.uuid4().hex[:12]
        result = {'trial_id': trial_id, 'task_id': task_id, 'stage': stage,
                  'harness': getattr(agent_factory, 'harness', None),
                  'started_utc': datetime.now(timezone.utc).isoformat(), 'host': health,
                  'model_protocol_sha256': protocol_hash,
                  'status': 'starting', 'project': project}
        if accounting_transition is not None:
            result['accounting_runtime_transition_sha256'] = accounting_transition
            result['gateway_image_id'] = gateway_image
        durable_json(trial / 'started.json', result)
        environment, bridge, trace = None, None, None
        try:
            compose = compose_runtime(gateway_image=gateway_image, guard_image=guard_image,
                state_dir=runtime, tokenizer_dir=root / '.cache/stage2-tokenizer',
                credential_file=root / '.env', token_file=token_file,
                trial_id=trial_id, stage=stage, uid=0, gid=0,
                completion_wait_seconds=completion_wait_seconds)
            override = trial / 'compose.json'
            durable_json(override, compose)
            environment = DockerEnvironment(environment_dir=task.paths.environment_dir,
                environment_name=project, session_id=project, trial_paths=paths,
                task_env_config=task.config.environment, extra_docker_compose=[override],
                mounts=[{'type': 'bind', 'source': str(paths.agent_dir.resolve()), 'target': '/logs/agent'},
                        {'type': 'bind', 'source': str(paths.verifier_dir.resolve()), 'target': '/logs/verifier'}])
            await asyncio.wait_for(environment.start(force_build=False),
                                   timeout=task.config.environment.build_timeout_sec)
            main = await asyncio.to_thread(service, project, 'main')
            audit_task(main, task.config.environment, paths)
            result['task_image_id'] = main['Image']
            relay = await asyncio.to_thread(service, project, 'model-relay')
            if relay['Image'] != gateway_image:
                raise RuntimeError('Unexpected relay image')
            bridge = HostModelBridge(relay['Id'], completion_wait_seconds=completion_wait_seconds)
            bridge.__enter__()
            agent = agent_factory(paths=paths, host_api_base=bridge.base_url,
                container_api_base='http://127.0.0.1:8765/v1', trial_token=token,
                agent_timeout_seconds=task.config.agent.timeout_sec,
                completion_wait_seconds=completion_wait_seconds)
            if result['harness'] in {'terminus-2', 'openhands', 'C0', 'C1', 'C2'}:
                trace = PaidTrialTrace(trial / 'traces', trial_id=trial_id, task_id=task_id,
                    harness=result['harness'], protocol_sha256=protocol_hash)
            async def revoke():
                # Stop upstream access first, even if a host request is hung.
                await environment.stop_service('model-gateway')
                gateway = await asyncio.to_thread(service, project, 'model-gateway')
                if gateway['State']['Running']:
                    raise RuntimeError('Gateway is still running')
                await asyncio.to_thread(bridge.__exit__, None, None, None)
            result.update(await execute_phases(agent=agent, environment=environment,
                task=task, paths=paths, revoke_model=revoke,
                setup_timeout_seconds=setup_timeout_seconds, phase_observer=trace,
                prepare_environment=refresh_package_metadata))
        except BaseException as exc:
            result.update(status='interrupted' if isinstance(exc, asyncio.CancelledError) else 'infrastructure_failed',
                          error_type=type(exc).__name__)
            raise
        finally:
            # Also covers construction/audit/factory failures before phases own
            # teardown. Docker down is intentionally idempotent after phases.
            try:
                if environment is not None:
                    await asyncio.wait_for(environment.stop(delete=True), timeout=60)
            except Exception as exc:
                result.update(status='cleanup_failed', teardown_error_type=type(exc).__name__)
            try:
                if bridge is not None:
                    await asyncio.to_thread(bridge.__exit__, None, None, None)
            except Exception as exc:
                result.update(status='cleanup_failed', bridge_error_type=type(exc).__name__)
            for resource, command in [('containers', ['ps', '-aq']),
                                      ('networks', ['network', 'ls', '-q']),
                                      ('volumes', ['volume', 'ls', '-q'])]:
                try:
                    result[resource + '_removed'] = not await asyncio.to_thread(
                        docker, *command, '--filter', 'label=com.docker.compose.project=' + project)
                except Exception:
                    result[resource + '_removed'] = False
                if not result[resource + '_removed']:
                    result['status'] = 'cleanup_failed'
            try:
                await asyncio.to_thread(collect_receipts, billing_runtime or runtime, trial_id, kind=billing_kind)
                result['billing'] = audit_trial(runtime, trial_id, stage)
            except Exception as exc:
                result['billing'] = {'billing_verified': False, 'error_type': type(exc).__name__}
                if result['status'] == 'verified':
                    result['status'] = 'billing_unresolved'
            if trace is not None:
                try:
                    evidence = Path(billing_runtime or runtime) / ('native-setup-attempts' if billing_kind == 'setup' else 'scored-attempts') / trial_id
                    result['trace'] = trace.finish(evidence, result['billing'])
                except Exception as exc:
                    # Preserve the actual verifier outcome; never invent spans.
                    result['trace'] = {'status': 'incomplete', 'error_type': type(exc).__name__}
            durable_json(trial / 'result.json', result)
            # Preserve the original result first. A host-only registration may
            # then carry its bounded billing uncertainty into the NEXT trial;
            # it cannot retry this attempt or turn uncertainty into a receipt.
            if result['status'] == 'billing_unresolved':
                from deferred_billing import validate_policy, register_terminal_deferral
                account_runtime = Path(billing_runtime or runtime)
                if validate_policy(account_runtime) is not None:
                    await asyncio.to_thread(register_terminal_deferral, account_runtime,
                        kind=billing_kind, trial_id=trial_id, result_path=trial / 'result.json')
        return result
