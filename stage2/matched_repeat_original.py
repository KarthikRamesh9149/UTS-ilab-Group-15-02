"""Fresh audit of the 178 original corrected outcomes, not repeat admission.

authenticate takes the ancestor locks itself, so call it BEFORE the future
dispatcher's locks. The unchanged original collector does not acquire locks.
recheck only rereads files under the caller's locks; it cannot replace the
actual audit. Neither entry verifies an off-server archive, historical library
bytes, task execution of a repeat, or permission to dispatch a paid trial.
"""
from contextlib import ExitStack
import ast
import csv
import io
import json
from pathlib import Path
import platform
import subprocess

import export_corrected as exporter
import matched_repeat_baseline as baseline
import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
import matched_repeat_locks as locks
from matched_repeat_baseline_probe import check_files, digest, regular, relative_name, environment

SNAPSHOT = '.runtime/netcup/corrected-final-20260925/snapshot.json'
SNAPSHOT_SHA256 = '960a119ad8a6dc009884eb2b559712e0e48f0a16711ddf9d1c57399ee0aac244'
PUBLIC = 'stage2/results/baseline-corrected-20260923'
LAUNCH_SHA256 = '0c8aafa10d744095c4551ff018065e1d6d9849e1dfe11bcf30e9e4b1ffafaaaa'
COLLECTOR_SHA256 = '5edd29a48758d8434b1c24b94e17d888532b9e43eb1c1ff032de797a064cb378'
KIND = 'fresh_original_corrected_result_audit_not_repeat_admission'
LIMITATIONS = dict(historical_installed_bytes_attested=False,
    off_server_backup_verified=False, repeat_execution_qualified=False,
    additional_collector_imports='current-byte-bindings-not-additions-to-original-qualification',
    support_files='current-audit-input-bindings-not-retrospective-byte-attestation')
# These unchanged helpers are reached by the original collector's imports but
# absent from its historical 84-source proof. Bind their actual current bytes
# explicitly; do not expand or rewrite that old proof or its archived snapshot.
CURRENT_COLLECTOR_IMPORTS = ('calibrate_tokenizer.py', 'extended_token_calibration.py',
    'final_schedule.py', 'setup_probe.py')


def _hash_audit(data):
    return policy.fingerprint({k: v for k, v in data.items() if k != 'collected_utc'})


def _context(root, harness):
    policy._harness(harness)
    root = Path(root)
    if (platform.system() != 'Linux' or root != runtime.DEPLOYMENTS[harness]
            or root.is_symlink() or root.resolve() != root
            or Path(__file__).resolve() != root / 'stage2/matched_repeat_original.py'):
        raise ValueError('Use the distinct native repeat deployment for the original audit')
    return root


def _anchors(root, original, final, harness):
    """Pinned local metadata only; safe to check without calling a collector."""
    policy._harness(harness)
    current = runtime.sources(root, original, final)
    copied = {'stage2/' + name: sha for name, sha in current.items()}
    copied.update({SNAPSHOT: SNAPSHOT_SHA256, PUBLIC + '/launch.json': LAUNCH_SHA256,
        PUBLIC + '/trials.csv': policy.BASELINE_CSV_SHA256,
        '.runtime/stage2/' + policy.BASELINE_FILE: baseline.ORIGINAL_FILE_SHA256,
        '.runtime/stage2/' + policy.FINAL_FILE: baseline.FINAL_FILE_SHA256})
    check_files(root, copied)
    if (current.get('export_corrected.py') != COLLECTOR_SHA256
            or Path(exporter.__file__).resolve() != Path(root).resolve() / 'stage2/export_corrected.py'
            or exporter.OUTPUT != Path(root) / PUBLIC):
        raise ValueError('Use the unchanged original collector from the bound repeat source')
    for name, value in ((policy.BASELINE_FILE, original), (policy.FINAL_FILE, final)):
        saved = json.loads(regular(root, '.runtime/stage2/' + name).read_text())
        if policy.fingerprint(saved) != policy.fingerprint(value):
            raise ValueError('Supplied qualification differs from actual copied anchor bytes')
    data = json.loads(regular(root, SNAPSHOT).read_text())
    manifest = json.loads(regular(root, 'stage2/input_manifest.json').read_text())
    policy.schedule(manifest)
    exporter.validate_snapshot(data, manifest['all_task_ids'])
    if (data['sources_sha256'] != original['sources']
            or data['qualification_sha256'] != baseline.ORIGINAL_FILE_SHA256
            or data['model_protocol_sha256'] != policy.MODEL_SHA256
            or policy.fingerprint(data['model_protocol']) != policy.MODEL_SHA256
            or any(data[k] != original[k] for k in ('gateway_image', 'guard_image'))):
        raise ValueError('Original completed audit differs from the pinned qualification')
    raw = regular(root, PUBLIC + '/trials.csv').read_text()
    rows = csv.DictReader(io.StringIO(raw))
    ordered = sorted(data['rows'], key=lambda r: (r['task_id'], r['harness']))
    if (rows.fieldnames != list(ordered[0]) or list(rows) != [
            {k: '' if v is None else str(v) for k, v in row.items()} for row in ordered]):
        raise ValueError('Preserve all 178 original outcomes and unknown costs exactly')
    files = {'stage2/' + name: sha for name, sha in original['sources'].items()}
    current_imports = {'stage2/' + name: current[name] for name in CURRENT_COLLECTOR_IMPORTS}
    if any(name in files and files[name] != sha for name, sha in current_imports.items()):
        raise ValueError('Current collector helper differs from an original bound source')
    files.update(current_imports)
    files.update({'.runtime/stage2/' + name: data[key] for name, key in (
        ('corrected-qualification.json', 'qualification_sha256'),
        ('corrected-matrix.json', 'registration_sha256'), ('provider-check.json', 'provider_check_sha256'))})
    folder = original['evidence_folder']
    if not isinstance(folder, str) or '/' in folder or not folder.startswith('qualification-'):
        raise ValueError('Exact original qualification producer folder required')
    if set(original['evidence_sha256']) != {'offline.json', 'image.json', 'synthetic.json'}:
        raise ValueError('All three original qualification producers required')
    files.update({'.runtime/stage2/' + folder + '/' + name: sha
        for name, sha in original['evidence_sha256'].items()})
    for row in data['rows']:
        name = row['trial_id']; relative_name(name)
        if '/' in name:
            raise ValueError('Original trial identity must be a single path component')
        files['.runtime/stage2/scored-trials/' + name + '/result.json'] = row['result_sha256']
    return dict(data=data, copied=copied, original=files, sources=current,
        current_collector_imports=current_imports)


def _directory(root, name):
    relative_name(name)
    path = Path(root)
    if path.is_symlink() or not path.is_dir() or path.resolve() != path:
        raise ValueError('Regular original deployment required')
    for part in Path(name).parts:
        path /= part
        if path.is_symlink() or not path.is_dir():
            raise ValueError('Regular original metadata directories required')
    return path


def _support_files(root, data):
    """Hash only audit inputs; never return request bodies or raw exchanges."""
    names = {'.runtime/stage2/' + name for name in
        ('corrected-policy.json', 'credit-only-policy.json', 'model-protocol.json')}
    for row in data['rows']:
        name = row['trial_id']
        relative_name(name)
        if '/' in name:
            raise ValueError('Single original trial identity required')
        base = '.runtime/stage2/scored-trials/' + name + '/traces'
        names.update(p.relative_to(root).as_posix() for p in _directory(root, base).glob('*.json'))
        base = '.runtime/stage2/scored-attempts/' + name
        attempts = _directory(root, base)
        stop = attempts / 'provider-stop.json'
        if stop.exists() or stop.is_symlink():
            raise ValueError('Original provider stop requires inspection')
        for pattern in ('*.request.json', '*.outcome.json', '*.transport-error.json', '*.retry.json'):
            names.update(p.relative_to(root).as_posix() for p in attempts.glob(pattern))
        lifecycle = '.runtime/stage2/retry-lifecycle/' + name + '.json'
        path = Path(root) / lifecycle
        if row['agent_error_type'] == 'TimeoutError' or path.exists() or path.is_symlink():
            names.add(lifecycle)
    return {name: digest(regular(root, name)) for name in sorted(names)}


def lock_all(stack, root, harness):
    """Use the same existing full-chain order as the later live session."""
    policy._harness(harness)
    if Path(root) != runtime.DEPLOYMENTS[harness]:
        raise ValueError('Only a distinct matched-repeat lock root is allowed')
    return locks.acquire(stack, root, harness)


def _native_environment():
    return dict(environment(baseline.ORIGINAL_ROOT),
        DOCKER_HOST='unix:///var/run/docker.sock', DOCKER_CONFIG='/dev/null')


def _native_program(files):
    for name, sha in files.items():
        relative_name(name); policy._hash(sha)
    if not files:
        raise ValueError('Original audit input bindings required')
    # This stdlib guard executes before the unchanged collector's first project
    # import. -I/-B and an absent cache prefix prevent reading old project pyc.
    guard = '''
import hashlib, importlib, os, sys, subprocess
from pathlib import Path
_original_root = Path(ROOT)
_original_files = BINDINGS
_original_environment = ENVIRONMENT
_original_importing = False
_original_violation = False
_original_socket_refusals = 0
if ((_original_root / '.venv').is_symlink() or Path(sys.prefix).resolve() != _original_root / '.venv'
 or not sys.flags.isolated or not sys.dont_write_bytecode):
 raise ValueError('Use the original isolated interpreter')
_unused_cache = _original_root / '.runtime/unused-original-audit-bytecode'
if _unused_cache.exists() or _unused_cache.is_symlink():
 raise ValueError('Original audit cache prefix must not exist')
sys.pycache_prefix = str(_unused_cache)
def _original_environment_check():
 if (_original_violation or dict(os.environ) != _original_environment
  or _unused_cache.exists() or _unused_cache.is_symlink()):
  raise ValueError('Exact credential-free original audit environment required')
def _original_event(event, args):
 global _original_violation, _original_socket_refusals
 if event == 'socket.__new__' and _original_importing:
  _original_socket_refusals += 1
  raise RuntimeError('Original audit import capability probe denied before creation')
 refused = event.startswith(('socket.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in {
  'os.system','os.fork','os.forkpty','os.remove','os.rename','os.rmdir','os.mkdir',
  'os.link','os.symlink','os.truncate','os.chmod','os.chown','os.utime','shutil.copyfile','os.unsetenv'}
 if event == 'open':
  path, mode, flags = args
  name = Path(os.fsdecode(path)).name if isinstance(path,(str,bytes,os.PathLike)) else ''
  refused |= (name == '.env' or name.startswith('.env.') or name in {'.jwt_secret','id_ed25519','id_rsa'}
   or isinstance(mode,str) and any(c in mode for c in 'wax+')
   or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
 if event == 'os.putenv':
  key, value = (os.fsdecode(v) for v in args)
  refused |= _original_environment.get(key) != value
 if event == 'subprocess.Popen':
  argv, child_environment = args[1], args[3]
  allowed = [['docker','ps','-q','--filter','name=uts-scored-']]
  for _, unit in ANCESTORS:
   allowed.append(['systemctl','show',unit,'--property=ActiveState,SubState,MainPID,ExecMainStatus'])
   allowed.append(['systemctl','show',unit,'--property=ActiveState','--property=SubState',
    '--property=MainPID','--property=ExecMainStatus'])
  refused |= (_original_importing or not isinstance(argv,(list,tuple)) or list(argv) not in allowed
   or child_environment is not None and child_environment != _original_environment)
 if refused:
  _original_violation = True
  raise ValueError('Read-only original collector effect or credential access refused')
def _original_loaded():
 base = _original_root / 'stage2'
 for name, module in list(sys.modules.items()):
  path = getattr(module,'__file__',None)
  key = 'stage2/' + name + '.py'
  if path and Path(path).parent == base and key not in _original_files:
   raise ValueError('Original collector loaded an unbound project module')
  if key in _original_files and (path is None or Path(path) != base / (name + '.py')):
   raise ValueError('Original collector module loaded from another tree')
def _original_check():
 _original_environment_check()
 for base, service in ANCESTORS:
  base = Path(base)
  if base.is_symlink() or not base.is_dir() or base.resolve() != base:
   raise ValueError('Regular inactive ancestor required')
  for name in ('operator-stop-request.json','provider-stop.json'):
   p = base / '.runtime/stage2' / name
   if p.exists() or p.is_symlink(): raise ValueError('Persistent ancestor stop')
  raw = subprocess.check_output(['systemctl','show',service,
   '--property=ActiveState,SubState,MainPID,ExecMainStatus'],text=True,timeout=8)
  state = dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
  if state != dict(ActiveState='inactive',SubState='dead',MainPID='0',ExecMainStatus='0'):
   raise ValueError('Inactive successful ancestors required before original collector')
 for name, expected in _original_files.items():
  p = _original_root
  for part in Path(name).parts:
   p /= part
   if p.is_symlink(): raise ValueError('Symlinked original audit input')
  st = p.stat()
  if not p.is_file() or (name.startswith('.runtime/') and (st.st_uid != os.getuid() or st.st_mode & 0o077)):
   raise ValueError('Private regular original audit inputs required')
  with p.open('rb') as stream:
   if hashlib.file_digest(stream,'sha256').hexdigest() != expected:
    raise ValueError('Original audit input changed')
_original_environment_check()
sys.addaudithook(_original_event)
_original_check()
sys.path.insert(0,str(_original_root / 'stage2'))
_original_importing = True
try:
 for name in PRELOAD:
  importlib.import_module(name)
finally:
 _original_importing = False
_original_environment_check()
_original_loaded()
_original_check()
'''
    ancestors = [(str(baseline.ORIGINAL_ROOT), 'uts-stage2-corrected-20260923.service'),
        (str(baseline.FINAL_ROOT), 'uts-stage2-custom-no-cutoff-final-20260928.service')]
    guard = guard.replace('Path(ROOT)', 'Path(' + repr(str(baseline.ORIGINAL_ROOT)) + ')')
    guard = guard.replace('= BINDINGS', '= ' + repr(files)).replace('in ANCESTORS:', 'in ' + repr(ancestors) + ':')
    guard = guard.replace('= ENVIRONMENT', '= ' + repr(_native_environment()))
    imports = set()
    for node in ast.parse(exporter.COLLECT).body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    preload = sorted(name for name in imports if 'stage2/' + name + '.py' in files)
    guard = guard.replace('in PRELOAD:', 'in ' + repr(preload) + ':')
    return guard + exporter.COLLECT + '\n_original_loaded()\n_original_check()\n'


def _native_audit(files):
    root = baseline.ORIGINAL_ROOT
    try:
        value = subprocess.run([str(root / '.venv/bin/python'), '-I', '-B', '-'],
            input=_native_program(files), cwd=root, capture_output=True, text=True, timeout=300,
            env=_native_environment())
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Original completed audit could not complete') from None
    if value.returncode:
        raise ValueError('Original completed audit failed; inspect retained metadata without replay')
    try:
        return json.loads(value.stdout)
    except (TypeError, ValueError):
        raise ValueError('Original collector did not return allowlisted metadata') from None


def _check(root, anchors, support):
    baseline.inactive_ancestors()
    check_files(root, anchors['copied'])
    check_files(baseline.ORIGINAL_ROOT, anchors['original'])
    if _support_files(baseline.ORIGINAL_ROOT, anchors['data']) != support:
        raise ValueError('Original supporting evidence changed during or after the audit')
    baseline.inactive_ancestors()
    # No native observation follows the final actual evidence reread.
    check_files(root, anchors['copied'])
    check_files(baseline.ORIGINAL_ROOT, anchors['original'])
    if _support_files(baseline.ORIGINAL_ROOT, anchors['data']) != support:
        raise ValueError('Original supporting evidence changed after the final service check')
    runtime.loaded_sources(root, anchors['sources'])


def _record(harness, anchors, support):
    return dict(kind=KIND, experiment=policy.EXPERIMENT, harness=harness,
        original_qualification_sha256=policy.ORIGINAL_QUALIFICATION_SHA256,
        custom_final_qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256,
        audit_sha256=_hash_audit(anchors['data']), snapshot_file_sha256=SNAPSHOT_SHA256,
        current_sources_sha256=policy.fingerprint(anchors['sources']),
        current_collector_import_files=anchors['current_collector_imports'],
        original_files=anchors['original'], support_files=support, copied_files=anchors['copied'],
        limitations=dict(LIMITATIONS), paid_launch_ready=False)


def authenticate(root, original, final, harness):
    """Fresh native audit under this reader's locks, before dispatcher locks."""
    root = _context(root, harness)
    anchors = _anchors(root, original, final, harness)
    runtime.loaded_sources(root, anchors['sources'])
    baseline.inactive_ancestors()  # No collector or lock acquisition while final is active.
    with ExitStack() as stack:
        lease = lock_all(stack, root, harness)
        check_files(baseline.ORIGINAL_ROOT, anchors['original'])
        support = _support_files(baseline.ORIGINAL_ROOT, anchors['data'])
        copied_identities = locks.file_identities(root, anchors['copied'])
        native_files = dict(anchors['original'], **support)
        native_identities = locks.file_identities(baseline.ORIGINAL_ROOT, native_files)
        _check(root, anchors, support)
        lease.recheck()
        fresh = _native_audit(native_files)
        exporter.validate_snapshot(fresh, [r['task_id'] for r in anchors['data']['rows']
            if r['harness'] == 'terminus-2'])
        if _hash_audit(fresh) != _hash_audit(anchors['data']):
            raise ValueError('Fresh original audit differs from all 178 retained outcomes')
        _check(root, anchors, support)
        lease.recheck()
        if (locks.file_identities(root, anchors['copied']) != copied_identities
                or locks.file_identities(baseline.ORIGINAL_ROOT, native_files) != native_identities):
            raise ValueError('Original audit source or evidence identity changed')
        return _record(harness, anchors, support)


def recheck(root, original, final, harness, authenticated):
    """Actual under-lock file reads, not another collector or saved-only audit."""
    root = _context(root, harness)
    anchors = _anchors(root, original, final, harness)
    runtime.loaded_sources(root, anchors['sources'])
    baseline.inactive_ancestors()
    support = _support_files(baseline.ORIGINAL_ROOT, anchors['data'])
    expected = _record(harness, anchors, support)
    if policy.fingerprint(authenticated) != policy.fingerprint(expected):
        raise ValueError('Exact fresh original audit record required; copied flags are not admission')
    _check(root, anchors, support)
    return expected
