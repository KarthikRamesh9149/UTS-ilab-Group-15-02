"""One-shot native qualification inside the actual live prerequisite session.

No CLI, saved receipt, caller root/factory or paid admission exception exists.
The future trusted service must await qualify(active) in its own main-thread
async task after the real Mac handoff. Local mocked tests are not native proof.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import sys
import threading
import unittest
import uuid

import matched_repeat_images as images
import matched_repeat_policy as policy
import matched_repeat_probe as probe
import matched_repeat_session as session
from matched_repeat_baseline_probe import check_files, regular
from matched_repeat_stream import loads
from scored_gateway import durable_json

INTENT = policy.QUALIFIER_INTENT_FILE
FAILURE = policy.QUALIFIER_FAILURE_FILE
RESULT = policy.QUALIFIER_RESULT_FILE


def no_failure(root):
    rt = root / '.runtime/stage2'
    names = (FAILURE, images.FAILURE, *(f'matched-repeat-rehearsal-{m}-failure.json' for m in policy.PROBE_MODES))
    if any((rt / name).exists() or (rt / name).is_symlink() for name in names):
        raise ValueError('Retained native qualification failure forbids admission or replay')


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _bound(root, names):
    values = {}
    for name in names:
        path = regular(root, name); info = path.stat()
        if info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Owned private single-link qualifier producers required')
        values[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    check_files(root, values)
    return values


def _read(root, name):
    before = _bound(root, [name])
    value = loads(regular(root, name).read_bytes())
    check_files(root, before)
    return value, before


def _fresh(root):
    probe._unscored(root)
    rt = root / '.runtime/stage2'
    names = (INTENT, FAILURE, RESULT, images.INTENT, images.RESULT, images.FAILURE, images.CONFIG)
    if any((rt / n).exists() or (rt / n).is_symlink() for n in names):
        raise ValueError('Retained qualification or image operation requires inspection, not replay')
    if any(rt.glob('matched-repeat-rehearsal-*')) or any(rt.glob('native-matched-repeat-*')):
        raise ValueError('Earlier regression or rehearsal evidence forbids automatic qualification')


def _input(root, name, value, raw=None):
    path = root / '.runtime/stage2' / name
    if path.exists() or path.is_symlink():
        actual, files = _read(root, str(path.relative_to(root)))
        if policy.fingerprint(actual) != policy.fingerprint(value):
            raise ValueError('Existing qualification input differs from the live observations')
        if raw is not None and path.read_bytes() != raw:
            raise ValueError('Exact manifest bytes must be preserved')
        return files
    if raw is None:
        durable_json(path, value)
    else:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return _bound(root, [str(path.relative_to(root))])


def _check(active, files):
    session.recheck(active)
    state = session._live(active)
    probe._environment(); session.handoff._no_stop(state['root'])
    check_files(state['root'], files)
    return state


def _network_guard(event, args):
    # Defence in depth for trusted regression sources, not an OS sandbox.
    # Local synthetic HTTP/Unix servers are allowed; a paid provider is not.
    if event == 'socket.getaddrinfo':
        host = args[0]
    elif event in ('socket.connect', 'socket.sendto'):
        address = args[1] if event == 'socket.connect' else args[-1]
        if not isinstance(address, tuple):
            return  # Local Unix sockets used by the synthetic tests.
        host = address[0]
    else:
        return
    if host in (None, 'localhost', b'localhost'):
        return
    try:
        allowed = ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
    except ValueError:
        allowed = False
    if not allowed:
        raise PermissionError('Native regression permits only local synthetic network peers')


def _loaded(root, files):
    stage = root / 'stage2'
    names = {Path(n).name for n in files if n.startswith('stage2/') and n.endswith('.py')}
    imported = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        path = Path(filename)
        if path.name not in names and not path.is_relative_to(stage) and not path.resolve().is_relative_to(stage):
            continue
        if not path.is_relative_to(stage) or path.is_symlink() or path.resolve() != path:
            raise ValueError('Regression helper imported from another deployment')
        name = str(path.relative_to(root))
        if name not in files:
            raise ValueError('Every actual regression project import must be source-bound')
        imported[name] = files[name]
    if not imported:
        raise ValueError('Actual bound regression imports required')
    check_files(root, imported)


def regression_worker(payload):
    """Fixed child producer; receives file bindings, never a live session."""
    root = Path(payload['root']); folder = root / payload['folder']
    if (Path(sys.prefix) != root / '.venv' or sys.platform != 'linux'
            or Path(__file__).resolve() != root / 'stage2/qualify_matched_repeat.py'
            or not sys.dont_write_bytecode):
        raise ValueError('Use the exact isolated native repeat regression interpreter')
    probe._environment(); check_files(root, payload['files'])
    if policy.TEST_MODULES != tuple(payload['modules']):
        raise ValueError('Fixed bound native regression modules required')
    _loaded(root, payload['files'])
    sys.addaudithook(_network_guard)
    suite = unittest.defaultTestLoader.loadTestsFromNames(policy.TEST_MODULES)
    check_files(root, payload['files'])
    _loaded(root, payload['files'])
    result = unittest.TextTestRunner(stream=sys.stdout).run(suite)
    report = dict(tests=result.testsRun, passed=result.wasSuccessful(), skipped=len(result.skipped),
        errors=len(result.errors), failures=len(result.failures), modules=list(policy.TEST_MODULES))
    check_files(root, payload['files'])
    _loaded(root, payload['files'])
    durable_json(folder / 'regression.json', report)
    if not result.wasSuccessful() or result.skipped or result.testsRun <= 0:
        raise ValueError('Native regression failed; actual private output retained')


BOOTSTRAP = r'''
import hashlib,ipaddress,json,os,pathlib,stat,sys
def pairs(items):
 result={}
 for k,v in items:
  if k in result: raise ValueError('Duplicate native regression input')
  result[k]=v
 return result
p=json.load(sys.stdin,object_pairs_hook=pairs);root=pathlib.Path(p['root'])
if sys.platform!='linux' or pathlib.Path(sys.prefix)!=root/'.venv' or not sys.dont_write_bytecode:
 raise ValueError('Exact isolated native interpreter required before project imports')
if root.is_symlink() or root.resolve()!=root or not root.is_dir(): raise ValueError('Exact native root required')
if not isinstance(p['files'],dict) or not p['files']: raise ValueError('Native file bindings required')
folder=pathlib.PurePosixPath(p['folder'])
if str(folder)!=p['folder'] or folder.is_absolute() or '..' in folder.parts or not p['folder'].startswith('.runtime/stage2/native-matched-repeat-'):
 raise ValueError('Private native regression folder required')
current=root
for part in folder.parts:
 current/=part
 if current.is_symlink() or not current.is_dir(): raise ValueError('Regular native regression directory required')
sys.pycache_prefix=str(root/p['folder']/'absent-bytecode-cache')
if pathlib.Path(sys.pycache_prefix).exists() or pathlib.Path(sys.pycache_prefix).is_symlink(): raise ValueError('Absent bytecode cache required')
for name,sha in p['files'].items():
 if not isinstance(name,str) or str(pathlib.PurePosixPath(name))!=name or any(x in ('','..','.') for x in name.split('/')):
  raise ValueError('Normalised bound path required')
 path=root
 for part in pathlib.PurePosixPath(name).parts:
  if part in ('','..','.') or pathlib.PurePosixPath(name).is_absolute(): raise ValueError('Relative bound file required')
  path/=part
  if path.is_symlink(): raise ValueError('Symlinked native input refused')
 info=path.stat()
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1: raise ValueError('Regular single-link input required')
 if name.startswith('.runtime/') and (info.st_uid!=os.getuid() or info.st_mode&0o077): raise ValueError('Private input required')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=sha: raise ValueError('Native regression input changed')
def local_network(event,args):
 if event=='socket.getaddrinfo': host=args[0]
 elif event in ('socket.connect','socket.sendto'):
  address=args[1] if event=='socket.connect' else args[-1]
  if not isinstance(address,tuple): return
  host=address[0]
 else: return
 if host in (None,'localhost',b'localhost'): return
 try: allowed=ipaddress.ip_address(host.decode() if isinstance(host,bytes) else host).is_loopback
 except ValueError: allowed=False
 if not allowed: raise PermissionError('Native regression permits only local synthetic network peers')
sys.addaudithook(local_network)
sys.path.insert(0,str(root/'stage2'))
from qualify_matched_repeat import regression_worker
regression_worker(p)
'''


async def _settle(task):
    # Finish owned child creation/cleanup even if another cancellation arrives.
    # The original exception still propagates; no session enters this task.
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


async def _stop_regression(process):
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), 10)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


async def _regression(active, folder, files):
    state = _check(active, files); root = state['root']
    payload = dict(root=str(root), folder=str(folder.relative_to(root)),
        files=dict(state['files'], **files), modules=list(policy.TEST_MODULES))
    log = folder / 'regression.txt'
    process = None; creation = None
    with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        try:
            creation = asyncio.create_task(asyncio.create_subprocess_exec(str(root / '.venv/bin/python'), '-I', '-B', '-c', BOOTSTRAP,
                cwd=root, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                    'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}, stdin=asyncio.subprocess.PIPE,
                stdout=stream, stderr=stream, start_new_session=True, close_fds=True))
            process = await asyncio.shield(creation)
            await process.communicate(json.dumps(payload, allow_nan=False).encode())
            if process.returncode != 0:
                raise ValueError('Native regression process failed; private output retained')
        except BaseException:
            if process is None and creation is not None:
                try:
                    process = await _settle(creation)
                except BaseException:
                    pass  # Preserve the original creation/cancellation failure.
            if process is not None and process.returncode is None:
                # Only this newly spawned, owned regression process group.
                # No benchmark/service process or SSH client is signalled.
                await _settle(asyncio.create_task(_stop_regression(process)))
            raise
        finally:
            stream.flush(); os.fsync(stream.fileno())
    _check(active, files)
    return _read(root, str((folder / 'regression.json').relative_to(root)))[0]


def _case(state, mode, binding):
    root, harness = state['root'], state['harness']
    intent, intent_files = _read(root, '.runtime/stage2/matched-repeat-rehearsal-' + mode + '.json')
    relative = intent.get('runtime_path')
    if (not isinstance(relative, str) or not re.fullmatch(r'\.runtime/stage2/native-matched-repeat-'
            + harness + '-' + mode + r'-[a-zA-Z0-9_]+', relative)
            or intent.get('sources_sha256') != state['host']['sources_sha256']
            or intent.get('harness') != harness or intent.get('mode') != mode
            or intent.get('automatic_resume') is not False
            or intent.get('kind') != 'one_shot_synthetic_matched_repeat_rehearsal'
            or intent.get('paid_launch_ready') is not False
            or intent.get('image_build_sha256') != binding['image_build_sha256']):
        raise ValueError('Actual one-shot native rehearsal intent required')
    case, report_files = _read(root, relative + '/evidence.json')
    if (case.get('runtime_path') != relative or case.get('mode') != mode or case.get('harness') != harness
            or case.get('kind') != probe.KIND or case.get('status') != 'passed'
            or type(case.get('live_api_calls')) is not int or case['live_api_calls'] != 0
            or set(case.get('checks', {})) != policy.probe_checks(mode)
            or any(v is not True for v in case['checks'].values())
            or case.get('image_build_sha256') != binding['image_build_sha256']
            or case.get('image_evidence_files') != binding['image_evidence_files']
            or case.get('paid_launch_ready') is not False or case.get('repeat_execution_qualified') is not False):
        raise ValueError('Actual native rehearsal report differs from its operation')
    trial = relative + '/.runtime/stage2/scored-trials/synthetic-matched-repeat-' + harness + '-' + mode
    attempts = root / relative / '.runtime/stage2/scored-attempts' / ('synthetic-matched-repeat-' + harness + '-' + mode)
    expected = {relative + '/' + name for name in ('stage2/input_manifest.json', '.env',
        '.runtime/stage2/' + probe.fixture.FIXTURE_FILE)} | {trial + '/started.json', trial + '/result.json'}
    expected |= {str(p.relative_to(root)) for p in (root / trial / 'traces').glob('*.json')}
    expected |= {str(p.relative_to(root)) for p in attempts.glob('*.json')}
    if set(case.get('producer_files', {})) != expected:
        raise ValueError('Exact actual supporting producer inventory required')
    support = _bound(root, sorted(expected))
    if support != case['producer_files']:
        raise ValueError('Actual rehearsal supporting producer bytes changed')
    return case, dict(intent_files, **report_files, **support)


def verify_completion(active, proof):
    """Reread the one-shot operation and every real supporting producer.

    This is used by scoped admission, not a replacement for its native host,
    image and lineage readers. A copied report cannot execute a qualification.
    """
    state = session._live(active); root = state['root']
    no_failure(root)
    intent, files = _read(root, '.runtime/stage2/' + INTENT)
    expected = dict(kind='one_shot_actual_native_repeat_qualification', harness=state['harness'],
        sources_sha256=state['host']['sources_sha256'], runtime_identity_sha256=policy.fingerprint(state['host']),
        baseline_behaviour_authentication_sha256=policy.fingerprint(state['library']),
        predecessor_authentication_sha256=policy.fingerprint(state['predecessor']['predecessors']),
        regression_path=proof['regression_path'], automatic_resume=False, paid_launch_ready=False)
    if (any(policy.fingerprint(intent.get(k)) != policy.fingerprint(v) for k, v in expected.items())
            or type(intent.get('pid')) is not int or intent['pid'] <= 0
            or not isinstance(intent.get('started_utc'), str) or not intent['started_utc']):
        raise ValueError('Actual qualification operation differs from its live prerequisites')
    names = ['.runtime/stage2/' + n for n in (policy.POLICY_FILE, policy.MANIFEST_FILE,
        policy.PREDECESSOR_FILE, policy.RUNTIME_FILE, policy.QUALIFICATION_FILE)]
    files.update(_bound(root, names))
    files.update(_bound(root, proof['evidence_files']))
    files.update(_bound(root, proof['image_evidence_files']))
    binding = {k: proof[k] for k in ('image_build_sha256', 'image_evidence_files')}
    for recorded in proof['synthetic']:
        actual, supporting = _case(state, recorded['mode'], binding)
        if policy.fingerprint(actual) != policy.fingerprint(recorded):
            raise ValueError('Actual supporting rehearsal report differs from qualification')
        files.update(supporting)
    result, result_files = _read(root, '.runtime/stage2/' + RESULT)
    expected = dict(kind='actual_native_repeat_qualification_complete_not_dispatch', status='qualified',
        qualification_sha256=policy.fingerprint(proof), offline_tests=proof['offline']['tests'],
        native_cases=3, live_api_calls=0, producer_files=files, automatic_resume=False, paid_launch_ready=False)
    if (any(policy.fingerprint(result.get(k)) != policy.fingerprint(v) for k, v in expected.items())
            or not isinstance(result.get('completed_utc'), str) or not result['completed_utc']):
        raise ValueError('Actual completed qualification and all supporting bytes must agree')
    files.update(result_files)
    check_files(root, files); no_failure(root)
    return files


async def qualify(active):
    """Build and qualify once inside the service's original live async scope."""
    state = session._live(active)
    session.require_execution(active)
    if threading.current_thread() is not threading.main_thread() or session._task() is None:
        raise ValueError('Qualification stays on the service main thread and owning async task')
    session.recheck(active); probe._environment()
    root = state['root']; rt = root / '.runtime/stage2'
    _fresh(root); probe._owned_clear()
    folder = rt / ('native-matched-repeat-' + state['harness'] + '-qualification-' + uuid.uuid4().hex)
    intent = dict(kind='one_shot_actual_native_repeat_qualification', harness=state['harness'],
        sources_sha256=state['host']['sources_sha256'], runtime_identity_sha256=policy.fingerprint(state['host']),
        baseline_behaviour_authentication_sha256=policy.fingerprint(state['library']),
        predecessor_authentication_sha256=policy.fingerprint(state['predecessor']['predecessors']),
        regression_path=str(folder.relative_to(root)), started_utc=_utc(), pid=os.getpid(),
        automatic_resume=False, paid_launch_ready=False)
    durable_json(rt / INTENT, intent)
    try:
        files = _bound(root, ['.runtime/stage2/' + INTENT])
        folder.mkdir(mode=0o700)
        raw = regular(root, 'stage2/input_manifest.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != policy.INPUT_SHA256:
            raise ValueError('Exact original manifest bytes required')
        manifest = loads(raw); predecessors = deepcopy(state['predecessor']['predecessors'])
        for name, value in ((policy.POLICY_FILE, policy.POLICY), (policy.MANIFEST_FILE, manifest),
                (policy.PREDECESSOR_FILE, predecessors), (policy.RUNTIME_FILE, state['host'])):
            files.update(_input(root, name, value, raw if name == policy.MANIFEST_FILE else None))
        _check(active, files)
        images.build(active)  # The return value is not installed-image evidence.
        binding = images.qualification_binding(active); files.update(binding['image_evidence_files'])
        await _regression(active, folder, files)  # Reread actual producers below.
        offline, regression_files = _read(root, str(folder.relative_to(root)) + '/regression.json')
        regression_files.update(_bound(root, [str(folder.relative_to(root)) + '/regression.txt']))
        files.update(regression_files)
        if (offline.get('modules') != list(policy.TEST_MODULES) or offline.get('passed') is not True
                or type(offline.get('tests')) is not int or offline['tests'] <= 0
                or any(type(offline.get(k)) is not int or offline[k] != 0 for k in ('skipped', 'errors', 'failures'))):
            raise ValueError('Actual complete native regression results required')
        cases = []; core_files = dict(regression_files)
        for mode in policy.PROBE_MODES:
            _check(active, files)
            await probe.probe(active, mode)
            case, support = _case(state, mode, binding)
            files.update(support); cases.append(case)
            prefix = case['runtime_path']
            core_files.update({n: sha for n, sha in support.items() if n in {
                prefix + '/evidence.json', prefix + '/.runtime/stage2/scored-trials/'
                    + 'synthetic-matched-repeat-' + state['harness'] + '-' + mode + '/result.json'}})
            _check(active, files)
        probe._owned_clear()
        if images.qualification_binding(active) != binding:
            raise ValueError('Actual image evidence changed during qualification')
        current = _check(active, files)['host']
        proof = dict(schema_version=1, kind='native_matched_baseline_repeat_qualification',
            experiment=policy.EXPERIMENT, status='passed', harness=state['harness'], live_api_calls=0,
            paid_launch_ready=False, setup_timeout_seconds=900, policy_sha256=policy.fingerprint(policy.POLICY),
            schedule_sha256=policy.fingerprint(policy.schedule(manifest)),
            manifest_canonical_sha256=policy.MANIFEST_SHA256, input_manifest_sha256=policy.INPUT_SHA256,
            python_runtime_sha256=policy.PYTHON_SHA256, model_protocol_sha256=policy.MODEL_SHA256,
            original_baseline_csv_sha256=policy.BASELINE_CSV_SHA256,
            original_qualification_sha256=policy.fingerprint(state['original']),
            custom_final_qualification_sha256=policy.fingerprint(state['final']),
            predecessor_authentication_sha256=policy.fingerprint(predecessors),
            baseline_behaviour_authentication_sha256=policy.fingerprint(state['library']),
            runtime_identity_sha256=policy.fingerprint(current),
            inherited_baseline_turn_guards=deepcopy(policy.POLICY['inherited_baseline_turn_guards']),
            sources=deepcopy(current['sources']), sources_sha256=current['sources_sha256'],
            source_transition=deepcopy(current['source_transition']), dependencies=deepcopy(current['dependencies']),
            python_runtime=deepcopy(current['python_runtime']), host_environment=deepcopy(current['host_environment']),
            offline=offline, synthetic=cases, evidence_files=core_files,
            regression_path=str(folder.relative_to(root)), image_sources_match=True,
            qualified_utc=_utc(), **binding)
        policy.validate_qualification(state['original'], state['final'], predecessors, manifest, proof)
        session.runtime.verify_current(root, state['original'], state['final'], predecessors, proof, current)
        _check(active, files); probe._owned_clear()
        durable_json(rt / policy.QUALIFICATION_FILE, proof)
        files.update(_bound(root, ['.runtime/stage2/' + policy.QUALIFICATION_FILE]))
        result = dict(kind='actual_native_repeat_qualification_complete_not_dispatch', status='qualified',
            qualification_sha256=policy.fingerprint(proof), offline_tests=offline['tests'], native_cases=len(cases),
            live_api_calls=0, producer_files=deepcopy(files),
            completed_utc=_utc(), automatic_resume=False, paid_launch_ready=False)
        durable_json(rt / RESULT, result)
        # A retained completion record is mandatory, and any later verification
        # failure leaves FAILURE too. No later session can admit that proof.
        verified = session.verify_qualification(active)
        if verified['qualification_sha256'] != result['qualification_sha256']:
            raise ValueError('Fresh session qualification identity differs')
        _check(active, verified['qualification_operation_files']); probe._owned_clear()
        no_failure(root)
        return result
    except BaseException as exc:
        session.invalidate(active)
        if not (rt / FAILURE).exists() and not (rt / FAILURE).is_symlink():
            durable_json(rt / FAILURE, dict(kind='retained_native_repeat_qualification_failure',
                exception_type=type(exc).__name__, failed_utc=_utc(), automatic_resume=False, paid_launch_ready=False))
        raise
