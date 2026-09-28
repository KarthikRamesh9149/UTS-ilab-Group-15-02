"""Fresh audit of the 178 original corrected outcomes, not repeat admission.

authenticate takes the ancestor locks itself, so call it BEFORE the future
dispatcher's locks. The unchanged original collector does not acquire locks.
recheck only rereads files under the caller's locks; it cannot replace the
actual audit. Neither entry verifies an off-server archive, historical library
bytes, task execution of a repeat, or permission to dispatch a paid trial.
"""
from contextlib import ExitStack
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
from matched_repeat_baseline_probe import check_files, digest, regular, relative_name
from run_no_cutoff_final import lock_all as inherited_locks
from run_credit_only import hold
from run_deadline_custom import ANCESTORS, BASELINE, DIAGNOSTIC, STOPPED_CUSTOM, PREVIOUS, PRIOR_REHEARSAL
from direct_final_evidence import CURRENT as C3_ROOT
from no_cutoff_final_evidence import CURRENT as NC_ROOT

SNAPSHOT = '.runtime/netcup/corrected-final-20260925/snapshot.json'
SNAPSHOT_SHA256 = '960a119ad8a6dc009884eb2b559712e0e48f0a16711ddf9d1c57399ee0aac244'
PUBLIC = 'stage2/results/baseline-corrected-20260923'
LAUNCH_SHA256 = '0c8aafa10d744095c4551ff018065e1d6d9849e1dfe11bcf30e9e4b1ffafaaaa'
COLLECTOR_SHA256 = '5edd29a48758d8434b1c24b94e17d888532b9e43eb1c1ff032de797a064cb378'
KIND = 'fresh_original_corrected_result_audit_not_repeat_admission'
LIMITATIONS = dict(historical_installed_bytes_attested=False,
    off_server_backup_verified=False, repeat_execution_qualified=False,
    support_files='current-audit-input-bindings-not-retrospective-byte-attestation')
LOCK_ANCESTORS = (*ANCESTORS, BASELINE, DIAGNOSTIC, STOPPED_CUSTOM, PREVIOUS, PRIOR_REHEARSAL, C3_ROOT, NC_ROOT)


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
    return dict(data=data, copied=copied, original=files, sources=current)


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
    """Extend, never replace, the complete final-study ancestor lock chain."""
    policy._harness(harness)
    if Path(root) != runtime.DEPLOYMENTS[harness]:
        raise ValueError('Only a distinct matched-repeat lock root is allowed')
    extras = [baseline.FINAL_ROOT]
    if harness == 'openhands':
        extras.append(runtime.DEPLOYMENTS['terminus-2'])
    for base in (*LOCK_ANCESTORS, Path(root), *extras):
        _directory(base, '.runtime/stage2')
    inherited_locks(stack, root)  # Includes corrected, C3 r2 and measured C0-NC.
    for base in extras:
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            hold(stack, base / '.runtime/stage2', name)


def _native_program(files):
    for name, sha in files.items():
        relative_name(name); policy._hash(sha)
    if not files:
        raise ValueError('Original audit input bindings required')
    # This stdlib guard executes before the unchanged collector's first project
    # import. -I/-B and an absent cache prefix prevent reading old project pyc.
    guard = '''
import hashlib, os, sys, subprocess
from pathlib import Path
_original_root = Path(ROOT)
_original_files = BINDINGS
if ((_original_root / '.venv').is_symlink() or Path(sys.prefix).resolve() != _original_root / '.venv'
 or not sys.flags.isolated or not sys.dont_write_bytecode):
 raise ValueError('Use the original isolated interpreter')
_unused_cache = _original_root / '.runtime/unused-original-audit-bytecode'
if _unused_cache.exists() or _unused_cache.is_symlink():
 raise ValueError('Original audit cache prefix must not exist')
sys.pycache_prefix = str(_unused_cache)
def _original_check():
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
_original_check()
'''
    ancestors = [(str(baseline.ORIGINAL_ROOT), 'uts-stage2-corrected-20260923.service'),
        (str(baseline.FINAL_ROOT), 'uts-stage2-custom-no-cutoff-final-20260928.service')]
    guard = guard.replace('Path(ROOT)', 'Path(' + repr(str(baseline.ORIGINAL_ROOT)) + ')')
    guard = guard.replace('= BINDINGS', '= ' + repr(files)).replace('in ANCESTORS:', 'in ' + repr(ancestors) + ':')
    return guard + exporter.COLLECT + '\n_original_check()\n'


def _native_audit(files):
    root = baseline.ORIGINAL_ROOT
    try:
        value = subprocess.run([str(root / '.venv/bin/python'), '-I', '-B', '-'],
            input=_native_program(files), cwd=root, capture_output=True, text=True, timeout=300,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'DO_NOT_TRACK': '1'})
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


def _record(harness, anchors, support):
    return dict(kind=KIND, experiment=policy.EXPERIMENT, harness=harness,
        original_qualification_sha256=policy.ORIGINAL_QUALIFICATION_SHA256,
        custom_final_qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256,
        audit_sha256=_hash_audit(anchors['data']), snapshot_file_sha256=SNAPSHOT_SHA256,
        current_sources_sha256=policy.fingerprint(anchors['sources']),
        original_files=anchors['original'], support_files=support, copied_files=anchors['copied'],
        limitations=dict(LIMITATIONS), paid_launch_ready=False)


def authenticate(root, original, final, harness):
    """Fresh native audit under this reader's locks, before dispatcher locks."""
    root = _context(root, harness)
    anchors = _anchors(root, original, final, harness)
    runtime.loaded_sources(root, anchors['sources'])
    baseline.inactive_ancestors()  # No collector or lock acquisition while final is active.
    with ExitStack() as stack:
        lock_all(stack, root, harness)
        check_files(baseline.ORIGINAL_ROOT, anchors['original'])
        support = _support_files(baseline.ORIGINAL_ROOT, anchors['data'])
        _check(root, anchors, support)
        fresh = _native_audit(dict(anchors['original'], **support))
        exporter.validate_snapshot(fresh, [r['task_id'] for r in anchors['data']['rows']
            if r['harness'] == 'terminus-2'])
        if _hash_audit(fresh) != _hash_audit(anchors['data']):
            raise ValueError('Fresh original audit differs from all 178 retained outcomes')
        _check(root, anchors, support)
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
