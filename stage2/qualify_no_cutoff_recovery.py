"""One-shot native recovery qualification, only in the real live service task.

Actual image, regression and six isolated lifecycle producers are reread before
publishing qualification. This is neither registration nor paid dispatch.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import unittest
import uuid

import no_cutoff_recovery_bootstrap as bootstrap
import no_cutoff_recovery_files as files
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_probe as probe
import no_cutoff_recovery_qualification as reader
import no_cutoff_recovery_session as session

INTENT = policy.QUALIFIER_INTENT_FILE
RESULT = policy.QUALIFIER_RESULT_FILE
FAILURE = policy.QUALIFIER_FAILURE_FILE


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _error(exc):
    return type(exc).__name__ if type(exc) in (ValueError, RuntimeError, TimeoutError,
        OSError, asyncio.CancelledError, SystemExit, KeyboardInterrupt) else 'OtherException'


def _check(active, bound, identities=None):
    session.recheck(active)
    live = session._live(active)
    probe._environment(); reader.no_failure(live['root'])
    files.check(live['root'], bound, identities)
    return live


def _fresh(root):
    probe._unscored(root)
    rt = root / '.runtime/stage2'
    names = (INTENT, RESULT, FAILURE, images.INTENT, images.RESULT, images.FAILURE, images.CONFIG)
    if any((rt / n).exists() or (rt / n).is_symlink() for n in names):
        raise ValueError('Existing or partial recovery qualification is terminal, not a restart')
    if any(rt.glob('no-cutoff-recovery-rehearsal-*')) or any(rt.glob('native-no-cutoff-recovery-*')):
        raise ValueError('Earlier native recovery evidence forbids automatic repetition')


def _input(root, name, value):
    path = root / '.runtime/stage2' / name
    if path.exists() or path.is_symlink():
        actual, bound = files.private(root, name); policy._same(actual, value)
        return bound
    files.save(path, value)
    return files.private(root, name)[1]


def _network_guard(event, args):
    # Trusted tests need local fake HTTP/Unix peers. This is not an OS sandbox.
    if event == 'socket.getaddrinfo': host = args[0]
    elif event in ('socket.connect', 'socket.sendto'):
        address = args[1] if event == 'socket.connect' else args[-1]
        if not isinstance(address, tuple): return
        host = address[0]
    else: return
    if host in (None, 'localhost', b'localhost'): return
    try: allowed = ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
    except ValueError: allowed = False
    if not allowed: raise PermissionError('Recovery regressions permit only local synthetic peers')


def regression_worker(payload):
    root = bootstrap.ROOT
    bootstrap.context()
    if Path(__file__).absolute() != root / 'stage2/qualify_no_cutoff_recovery.py':
        raise ValueError('Own bound native regression producer required')
    before = bootstrap.check(payload['sources'])
    private_before = files.capture(root, payload['files'])[1]
    final = bootstrap.loads(bootstrap.raw(root, bootstrap.QUALIFICATION)[0])
    modules = policy.test_modules(final)
    policy._same(list(modules), payload['modules'])
    folder = root / payload['folder']
    if folder.parent != root / '.runtime/stage2' or not folder.name.startswith('native-no-cutoff-recovery-qualification-'):
        raise ValueError('Fixed private regression output required')
    bootstrap.directories(folder, private=True)
    temporary = folder / 'test-tmp'
    temporary.mkdir(mode=0o700)
    tempfile.tempdir = str(temporary)
    from no_cutoff_recovery_predecessor import loaded
    sources = {n.removeprefix('stage2/'): h for n, h in payload['sources'].items() if n.startswith('stage2/')}
    loaded(root, sources)
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    bootstrap.check(payload['sources'], before); files.check(root, payload['files'], private_before)
    loaded(root, sources)
    result = unittest.TextTestRunner(stream=sys.stdout).run(suite)
    report = dict(modules=list(modules), tests=result.testsRun, passed=result.wasSuccessful(),
        skipped=len(result.skipped), errors=len(result.errors), failures=len(result.failures))
    bootstrap.check(payload['sources'], before); files.check(root, payload['files'], private_before)
    loaded(root, sources)
    files.save(folder / 'regression.json', report)
    if not result.wasSuccessful() or result.skipped or result.testsRun <= 0:
        raise ValueError('Actual native recovery regressions failed; evidence retained')


def _program(active):
    live = session._live(active); root = live['root']
    name = 'stage2/no_cutoff_recovery_bootstrap.py'
    raw, _ = files.read(root, name)
    if hashlib.sha256(raw).hexdigest() != live['inputs']['files'][name]:
        raise ValueError('Actual committed pre-import bootstrap required')
    # The already-bound stdlib module is installed as the same module object
    # later imported by the worker. It independently derives the full union.
    return ('import hashlib,json,os,pathlib,sys,types\n'
        + 'SOURCE=' + repr(raw) + '\n'
        + 'b=types.ModuleType("no_cutoff_recovery_bootstrap")\n'
        + 'b.__file__=' + repr(str(root / name)) + '\n'
        + 'exec(compile(SOURCE,b.__file__,"exec"),b.__dict__)\n'
        + 'sys.pycache_prefix=str(b.ROOT/".absent-bytecode-cache")\n'
        + 'p=b.loads(sys.stdin.buffer.read(b.WINDOW+1))\n'
        + 'ids=b.check(p["sources"])\n'
        + 'if b.raw(b.ROOT,"stage2/no_cutoff_recovery_bootstrap.py")[0]!=SOURCE: raise ValueError("Bootstrap mismatch")\n'
        + 'private={n:b.raw(b.ROOT,n,h)[1] for n,h in p["files"].items()}\n'
        + 'loading=True\n'
        + 'def guard(event,args):\n'
        + ' if loading: b.no_effects(event,args)\n'
        + ' elif event=="open" and isinstance(args[0],(str,bytes,os.PathLike)):\n'
        + '  path=pathlib.Path(os.fsdecode(args[0])).resolve()\n'
        + '  if (path.name==".env" or path.name.startswith(".env.") or path.name in {".jwt_secret","id_ed25519","id_rsa"}) and not path.is_relative_to(b.ROOT/p["folder"]/"test-tmp"): raise PermissionError("Native credential read refused")\n'
        + ' if not loading and "worker" in globals(): worker._network_guard(event,args)\n'
        + 'os.chdir(b.ROOT);sys.path.insert(0,str(b.ROOT/"stage2"))\n'
        + 'sys.modules[b.__name__]=b;b.IMPORTING=True;sys.addaudithook(guard)\n'
        + 'try:\n import qualify_no_cutoff_recovery as worker\n'
        + 'finally:\n loading=False;b.IMPORTING=False\n'
        + 'if b.VIOLATION: raise ValueError("Refused regression import effect")\n'
        + 'b.check(p["sources"],ids)\n'
        + 'if private!={n:b.raw(b.ROOT,n,h)[1] for n,h in p["files"].items()}: raise ValueError("Private input changed")\n'
        + 'worker.regression_worker(p)\n')


async def _settle(task):
    while True:
        try: return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done(): return task.result()


async def _stop_regression(process):
    # Cleanup only the new owned isolated regression child group. Never an
    # existing/native benchmark service, another job or another SSH client.
    if process.returncode is not None: return
    try: os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError: pass
    try: await asyncio.wait_for(process.wait(), 10)
    except asyncio.TimeoutError:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        await process.wait()


async def _regression(active, folder, bound):
    live = _check(active, bound); root = live['root']
    payload = dict(sources=live['inputs']['files'], files=bound,
        folder=folder.relative_to(root).as_posix(), modules=list(policy.test_modules(live['inputs']['final'])))
    process = None; creation = None
    program = _program(active)
    with os.fdopen(os.open(folder / 'regression.txt',
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as log:
        try:
            creation = asyncio.create_task(asyncio.create_subprocess_exec(
                str(root / '.venv/bin/python'), '-I', '-B', '-c', program,
                cwd=root, env=bootstrap.environment(), stdin=asyncio.subprocess.PIPE,
                stdout=log, stderr=log, start_new_session=True, close_fds=True))
            process = await asyncio.shield(creation)
            await process.communicate(json.dumps(payload, allow_nan=False).encode())
            if process.returncode != 0: raise ValueError('Native regression child failed; private output retained')
        except BaseException:
            if process is None and creation is not None:
                try: process = await _settle(creation)
                except BaseException: pass
            if process is not None and process.returncode is None:
                await _settle(asyncio.create_task(_stop_regression(process)))
            raise
        finally: log.flush(); os.fsync(log.fileno())
    _check(active, bound)
    return reader._json(root, str(folder.relative_to(root)) + '/regression.json')[0]


def _proof(live, manifest, offline, cases, core, regression, binding):
    final = live['inputs']['final']; sources = live['inputs']['sources']
    predecessor = live['predecessor']['predecessor']
    return dict(schema_version=1, kind='native_separate_C0_NC_recovery_qualification',
        experiment=policy.EXPERIMENT, status='passed', condition=policy.CONDITION, parent='C0', base_parent=None,
        live_api_calls=0, paid_launch_ready=False, setup_timeout_seconds=900,
        package_command_timeout_seconds=180, preparation_source_sha256=policy.PREPARATION_SHA256,
        preparation_command_sha256=policy.COMMAND_SHA256, plan_sha256=policy.PLAN_SHA256,
        policy_sha256=policy.fingerprint(policy.POLICY), original_qualification_sha256=policy.ORIGINAL_QUALIFICATION,
        original_candidate_sha256=policy.ORIGINAL_CANDIDATE, candidate_version=policy.CANDIDATE_VERSION,
        predecessor_authentication_sha256=policy.fingerprint(predecessor),
        model_protocol_sha256=policy.MODEL_SHA256, manifest_canonical_sha256=policy.MANIFEST_SHA256,
        input_manifest_sha256=policy.INPUT_SHA256, python_runtime_sha256=policy.PYTHON_SHA256,
        execution_contract=policy.execution_contract(), dependencies=deepcopy(final['dependencies']),
        python_runtime=deepcopy(final['python_runtime']), host_environment=deepcopy(final['host_environment']),
        image_sources_match=True, sources=deepcopy(sources), sources_sha256=policy.fingerprint(sources),
        orchestration_changes=policy.source_transition(final, sources),
        runtime_identity_sha256=policy.fingerprint(live['host']), offline=offline, synthetic=cases,
        evidence_files=core, regression_path=regression, **binding)


async def qualify(active):
    live = session._live(active)
    if threading.current_thread() is not threading.main_thread() or session.handoff._task() is None:
        raise ValueError('Qualification must stay in the real service main-thread async task')
    session.recheck(active); probe._environment()
    root = live['root']; rt = root / '.runtime/stage2'
    _fresh(root); probe._owned_clear()
    folder = rt / ('native-no-cutoff-recovery-qualification-' + uuid.uuid4().hex)
    regression = folder.relative_to(root).as_posix()
    intent = dict(kind='one_shot_actual_native_recovery_qualification', experiment=policy.EXPERIMENT,
        sources_sha256=live['host']['sources_sha256'], runtime_identity_sha256=policy.fingerprint(live['host']),
        predecessor_authentication_sha256=policy.fingerprint(live['predecessor']['predecessor']),
        regression_path=regression, started_utc=_utc(), pid=os.getpid(), automatic_resume=False, paid_launch_ready=False)
    files.save(rt / INTENT, intent)
    stage = 'retain_qualification_inputs'
    try:
        folder.mkdir(mode=0o700)
        bound = files.private(root, INTENT)[1]
        raw = bootstrap.raw(root, 'stage2/input_manifest.json', policy.INPUT_SHA256)[0]
        manifest = bootstrap.loads(raw)
        # Original qualification and raw manifest are installation inputs. They
        # must already exist with their exact original bytes, never reserialised.
        for name, expected in ((policy.ORIGINAL_FILE, policy.ORIGINAL_QUALIFICATION_FILE_SHA256),
                (policy.MANIFEST_FILE, policy.INPUT_SHA256)):
            value, identity = bootstrap.raw(root, '.runtime/stage2/' + name, expected)
            bound['.runtime/stage2/' + name] = expected
        for name, value in ((policy.POLICY_FILE, policy.POLICY),
                (policy.PLAN_FILE, policy.plan.schedule(manifest)),
                (policy.PREDECESSOR_FILE, live['predecessor']['predecessor']),
                (policy.RUNTIME_FILE, live['host'])):
            bound.update(_input(root, name, value))
        identities = files.capture(root, bound)[1]
        _check(active, bound, identities)
        stage = 'qualify_gateway_image'
        images.build(active)
        binding = images.qualification_binding(active); bound.update(binding['image_evidence_files'])
        files.extend(root, bound, identities)
        stage = 'native_regressions'
        await _regression(active, folder, bound)
        _check(active, bound, identities)
        offline, core = reader._json(root, regression + '/regression.json')
        core.update(files.capture(root, [regression + '/regression.txt'])[0]); bound.update(core)
        files.extend(root, bound, identities)
        if (offline.get('modules') != list(policy.test_modules(live['inputs']['final']))
                or offline.get('passed') is not True or type(offline.get('tests')) is not int or offline['tests'] <= 0
                or any(type(offline.get(k)) is not int or offline[k] != 0 for k in ('skipped', 'errors', 'failures'))):
            raise ValueError('Actual complete native regressions required')
        cases = []
        for mode in policy.PROBE_MODES:
            stage = 'native_case_' + mode
            _check(active, bound, identities)
            await probe.probe(active, mode)
            operation = files.private(root, 'no-cutoff-recovery-rehearsal-' + mode + '.json')[0]
            relative = operation['runtime_path']
            case = reader._json(root, relative + '/evidence.json')[0]
            current = dict(binding, sources=live['inputs']['sources'], sources_sha256=live['host']['sources_sha256'])
            supporting = reader.case_files(root, case, current)
            bound.update(supporting); cases.append(case)
            files.extend(root, bound, identities)
            core.update({n: h for n, h in supporting.items() if n in {relative + '/evidence.json',
                relative + '/.runtime/stage2/scored-trials/synthetic-nc-recovery-' + mode + '/result.json'}})
            _check(active, bound, identities)
        stage = 'final_qualification_evidence'
        probe._owned_clear()
        policy._same(images.qualification_binding(active), binding)
        _check(active, bound, identities)
        proof = _proof(live, manifest, offline, cases, core, regression, binding)
        policy.validate_qualification(live['inputs']['final'], live['predecessor']['predecessor'], manifest, proof)
        files.save(rt / policy.QUALIFICATION_FILE, proof)
        bound.update(files.private(root, policy.QUALIFICATION_FILE)[1])
        files.extend(root, bound, identities)
        completed = dict(kind='actual_native_recovery_qualification_complete_not_dispatch',
            status='qualified', qualification_sha256=policy.fingerprint(proof), offline_tests=offline['tests'],
            native_cases=6, live_api_calls=0, producer_files=deepcopy(bound), completed_utc=_utc(),
            automatic_resume=False, paid_launch_ready=False)
        files.save(rt / RESULT, completed)
        verified = reader.verify(active)
        probe._owned_clear(); _check(active, bound, identities)
        _check(active, verified['files'], verified['identities'])
        return completed
    except BaseException as exc:
        session.invalidate(active)
        if not (rt / FAILURE).exists() and not (rt / FAILURE).is_symlink():
            files.save(rt / FAILURE, dict(kind='retained_native_recovery_qualification_failure',
                stage=stage,
                error_type=_error(exc), failed_utc=_utc(), automatic_resume=False, paid_launch_ready=False))
        raise
