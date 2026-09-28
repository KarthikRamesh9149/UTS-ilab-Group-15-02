"""Live operator-to-native predecessor evidence, never paid admission.

send freshly audits and reads the existing Mac backup, then streams it through
an authenticated operator transport pipe without making another archive.
authenticate requires that pipe, independently verifies every archive binding,
and actually runs the unchanged final collector in the final interpreter.
Use it BEFORE dispatcher locks; the collector acquires its own ancestor locks.
recheck reads native files UNDER caller locks, without recursively auditing.

The process-local witness is not serialisable admission. Original-178 audit,
current installed-library parity, runtime identity, real repeat qualification,
registration and scoped dispatch remain separate mandatory prerequisites. No
SSH launcher, service, fixture, registration or paid runner is added here.
OpenHands is refused until its completed-Terminus predecessor is implemented.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import weakref

import export_no_cutoff_final as exporter
import matched_repeat_baseline as baseline
import matched_repeat_original as original_audit
import matched_repeat_policy as policy
import matched_repeat_predecessor as operator
import matched_repeat_runtime as runtime
import matched_repeat_stream as wire
from matched_repeat_baseline_probe import check_files, digest, regular, relative_name

KIND = 'live_streamed_custom_final_predecessor_not_repeat_admission'
TRANSFER_KIND = 'existing_off_server_custom_final_archive_v1'
TRANSFER_FIELDS = {'kind', 'schema_version', 'harness', 'operator', 'snapshot', 'backup'}
LIMITATIONS = dict(paid_launch_ready=False, original_178_audit='separate-required-reader',
    historical_installed_bytes_attested=False, installed_library_parity='separate-required-reader',
    repeat_execution_qualified=False, transport='requires-existing-authenticated-operator-pipe',
    off_server_archive='read-at-live-handoff-not-continuously-attested', full_runtime_restore=False)
_WITNESSES = weakref.WeakKeyDictionary()


class _Witness:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Live predecessor witnesses cannot be saved or copied')


def _first(harness):
    if harness != 'terminus-2':
        raise ValueError('OpenHands requires its additional completed-Terminus archive reader')


def _bytes_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _paths():
    return {key: operator.COMPLETED + '/' + name for key, name in
        (('snapshot', 'snapshot.json'), ('backup', 'backup.json'), ('archive', 'evidence.tar.gz'))}


def _maps(files):
    if not isinstance(files, dict) or not files:
        raise ValueError('Nonempty exact evidence bindings required')
    for name, sha in files.items():
        relative_name(name); policy._hash(sha)


def send(repo, destination, harness='terminus-2'):
    """Fresh Mac capture and existing-archive read; caller closes the pipe.

    Connect destination only to the approved native consumer over pinned SSH.
    There is no output-file mode and no saved-document-only shortcut.
    """
    _first(harness); wire.pipe_only(destination)
    repo = operator._operator(repo)
    document = operator.capture(repo, harness)
    paths = _paths()
    raw = {key: operator._regular(repo, paths[key]).read_bytes() for key in ('snapshot', 'backup')}
    if any(_bytes_sha(value) != document['local_files'][paths[key]] for key, value in raw.items()):
        raise ValueError('Off-server audit or receipt changed after fresh capture')
    backup = wire.loads(raw['backup'])
    header = dict(kind=TRANSFER_KIND, schema_version=1, harness=harness, operator=document,
        snapshot=raw['snapshot'].decode('utf-8'), backup=raw['backup'].decode('utf-8'))
    operator._check_local(repo, document['local_files'])
    header_digest = wire.write_header(destination, header)
    with operator._regular(repo, paths['archive']).open('rb') as archive:
        wire.copy_archive(archive, destination, backup['compressed_bytes'], backup['sha256'])
    # A changed source, anchor, archive or export withholds the commitment.
    operator._check_local(repo, document['local_files'])
    current = operator._anchors(repo)
    if any(document['local_files'].get(name) != sha for name, sha in current['local'].items()):
        raise ValueError('Operator source changed during the live handoff')
    wire.commit(destination, header_digest, backup['sha256'])
    return dict(kind='off_server_predecessor_bytes_sent_not_admission',
        operator_document_sha256=policy.fingerprint(document), archive_sha256=backup['sha256'],
        paid_launch_ready=False)


def _context(root, harness):
    _first(harness)
    root = Path(root)
    if (platform.system() != 'Linux' or root != runtime.DEPLOYMENTS[harness]
            or root.is_symlink() or root.resolve() != root
            or Path(__file__).resolve() != root / 'stage2/matched_repeat_handoff.py'):
        raise ValueError('Use the distinct native repeat host for the live handoff')
    return root


def _no_stop(root):
    baseline.inactive_ancestors()
    for base in (Path(root), baseline.FINAL_ROOT):
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            p = base / '.runtime/stage2' / name
            if p.exists() or p.is_symlink():
                raise ValueError('Persistent stop forbids successor authentication')


def _anchors(root, original, final, harness, header):
    """Read bound native/copy files; never execute a supplied command/path."""
    _first(harness)
    if (not isinstance(header, dict) or set(header) != TRANSFER_FIELDS
            or header['kind'] != TRANSFER_KIND or type(header['schema_version']) is not int
            or header['schema_version'] != 1 or header['harness'] != harness):
        raise ValueError('Exact live predecessor envelope required')
    document = header['operator']
    if (not isinstance(document, dict) or set(document) != operator.FIELDS
            or type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['kind'] != operator.KIND or document['successor_harness'] != harness
            or document['paid_launch_ready'] is not False
            or document['original_qualification_sha256'] != policy.ORIGINAL_QUALIFICATION_SHA256):
        raise ValueError('Exact non-admitting operator predecessor record required')
    _maps(document['local_files']); _maps(document['native_files'])
    raw = {}
    for key in ('snapshot', 'backup'):
        if not isinstance(header[key], str):
            raise ValueError('Exact UTF-8 snapshot and receipt bytes required')
        raw[key] = header[key].encode('utf-8')
        if _bytes_sha(raw[key]) != document['local_files'].get(_paths()[key]):
            raise ValueError('Transferred snapshot or receipt bytes differ from operator bindings')
    data, backup = wire.loads(raw['snapshot']), wire.loads(raw['backup'])
    current = runtime.sources(root, original, final)
    runtime.loaded_sources(root, current)
    copied = {'stage2/' + name: sha for name, sha in current.items()}
    if any(document['local_files'].get(name) != sha for name, sha in copied.items()):
        raise ValueError('Operator and native repeat source identities differ')
    copied.update({'.runtime/stage2/' + policy.BASELINE_FILE: baseline.ORIGINAL_FILE_SHA256,
        '.runtime/stage2/' + policy.FINAL_FILE: baseline.FINAL_FILE_SHA256})
    for name in ('qualification.json', 'registration-c0-nc.json', 'lineage.json', 'credit-policy.json'):
        path = operator.PUBLIC + '/' + name
        copied[path] = document['local_files'].get(path)
    _maps(copied); check_files(root, copied)
    for name, value in ((policy.BASELINE_FILE, original), (policy.FINAL_FILE, final)):
        saved = wire.loads(regular(root, '.runtime/stage2/' + name).read_bytes())
        if policy.fingerprint(saved) != policy.fingerprint(value):
            raise ValueError('Supplied qualification differs from actual copied anchor bytes')
    if (Path(exporter.__file__).resolve() != root / 'stage2/export_no_cutoff_final.py'
            or exporter.OUTPUT != root / operator.PUBLIC
            or exporter.REMOTE != str(baseline.FINAL_ROOT)):
        raise ValueError('Use the unchanged source-bound final exporter and exact final root')
    manifest = wire.loads(regular(root, 'stage2/input_manifest.json').read_bytes())
    policy.validate_predecessors(document['predecessors'], manifest, harness)
    exporter.validate_snapshot(data)
    if (data['sources'] != final['sources']
            or data['qualification_sha256'] != policy.CUSTOM_FINAL_QUALIFICATION_SHA256
            or policy.fingerprint(data['registration']) != policy.CUSTOM_FINAL_REGISTRATION_SHA256):
        raise ValueError('Transferred audit differs from actual qualified final89')
    files = exporter.expected_archive_hashes(data)
    _maps(files)
    if document['native_files'] != files:
        raise ValueError('Exact final source/input/producer/result inventory required')
    if (not isinstance(backup, dict) or set(backup) != exporter.BACKUP_FIELDS
            or any(type(backup[k]) is not int or backup[k] < 0 for k in
                ('files', 'bytes', 'excluded', 'compressed_bytes', 'verified_result_files', 'verified_bound_files'))
            or backup['verified_result_files'] != 89 or backup['verified_bound_files'] != len(files)
            or backup['private_archive_not_published'] is not True or backup['restore_test'] != exporter.RESTORE_NOTE):
        raise ValueError('Exact complete backup receipt required; flags alone are insufficient')
    policy._hash(backup['sha256'])
    if document['local_files'].get(_paths()['archive']) != backup['sha256']:
        raise ValueError('Actual archive checksum must match the operator byte inventory')
    block = dict(experiment=policy.CUSTOM_FINAL_EXPERIMENT, harness='C0-NC',
        qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256,
        registration_sha256=policy.CUSTOM_FINAL_REGISTRATION_SHA256,
        sources_sha256=policy.CUSTOM_FINAL_SOURCES_SHA256,
        results_sha256={r['trial_id']: r['result_sha256'] for r in data['rows']},
        audit_sha256=operator._audit_hash(data), archive_sha256=backup['sha256'],
        backup_record_sha256=_bytes_sha(raw['backup']))
    if document['predecessors']['blocks'] != [block]:
        raise ValueError('Predecessor declaration differs from actual retained evidence')
    return dict(data=data, backup=backup, document=document, files=files, sources=current, copied=copied)


def _support(data):
    """Current private audit-input hashes, never raw exchanges or solutions."""
    root = baseline.FINAL_ROOT; names = set()
    for row in data['rows']:
        name = row['trial_id']; relative_name(name)
        if '/' in name:
            raise ValueError('Single final trial identity required')
        base = '.runtime/stage2/scored-trials/' + name + '/traces'
        names.update(p.relative_to(root).as_posix() for p in original_audit._directory(root, base).glob('*.json'))
        base = '.runtime/stage2/scored-attempts/' + name
        folder = original_audit._directory(root, base)
        marker = folder / 'provider-stop.json'
        if marker.exists() or marker.is_symlink():
            raise ValueError('Final provider stop requires inspection')
        for pattern in ('*.request.json', '*.outcome.json', '*.transport-error.json', '*.retry.json'):
            names.update(p.relative_to(root).as_posix() for p in folder.glob(pattern))
        names.add('.runtime/stage2/retry-lifecycle/' + name + '.json')
    try:
        return {name: digest(regular(root, name)) for name in sorted(names)}
    except OSError:
        raise ValueError('Required final supporting evidence is missing or unreadable') from None


def _check(root, anchors, support):
    _no_stop(root)
    check_files(root, anchors['copied'])
    check_files(baseline.FINAL_ROOT, anchors['files'])
    if _support(anchors['data']) != support:
        raise ValueError('Final supporting evidence changed during or after the live audit')
    _no_stop(root)


def _native_program(files):
    _maps(files)
    # Reuse the unchanged operator's source-bound final collector/preflight.
    # Add native interpreter isolation and private input ownership checks.
    guard = '''
import os, sys
from pathlib import Path
_handoff_root = Path(ROOT)
_handoff_files = FILES
if (_handoff_root.resolve() != _handoff_root or (_handoff_root / '.venv').is_symlink()
 or Path(sys.prefix).resolve() != _handoff_root / '.venv'
 or not sys.flags.isolated or not sys.dont_write_bytecode):
 raise ValueError('Use the completed final isolated interpreter')
_handoff_cache = _handoff_root / '.runtime/unused-matched-handoff-bytecode'
if _handoff_cache.exists() or _handoff_cache.is_symlink():
 raise ValueError('Final audit cache prefix must not exist')
sys.pycache_prefix = str(_handoff_cache)
def _handoff_private_check():
 for name in _handoff_files:
  p = _handoff_root
  for part in Path(name).parts:
   p /= part
   if p.is_symlink(): raise ValueError('Symlinked final audit input')
  st = p.stat()
  if not p.is_file() or (name.startswith('.runtime/') and (st.st_uid != os.getuid() or st.st_mode & 0o077)):
   raise ValueError('Private owned final audit inputs required')
_handoff_private_check()
'''.replace('Path(ROOT)', 'Path(' + repr(str(baseline.FINAL_ROOT)) + ')').replace('= FILES', '= ' + repr(files))
    return guard + operator._native_program(files) + '\n_handoff_private_check()\n'


def _native_audit(files):
    root = baseline.FINAL_ROOT
    try:
        process = subprocess.run([str(root / '.venv/bin/python'), '-I', '-B', '-'],
            input=_native_program(files), cwd=root, capture_output=True, text=True, timeout=300,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'DO_NOT_TRACK': '1',
                'LITELLM_LOCAL_MODEL_COST_MAP': 'True'})
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Completed-final predecessor audit could not complete') from None
    if process.returncode:
        raise ValueError('Completed-final predecessor audit refused; preserve evidence without replay')
    return wire.loads(process.stdout)


def _record(harness, anchors, support, verified):
    return dict(kind=KIND, harness=harness, experiment=policy.EXPERIMENT,
        predecessors=deepcopy(anchors['document']['predecessors']),
        operator_document_sha256=policy.fingerprint(anchors['document']),
        current_sources_sha256=policy.fingerprint(anchors['sources']),
        native_files=anchors['files'], support_files=support, copied_files=anchors['copied'],
        streamed_backup=verified, limitations=dict(LIMITATIONS), paid_launch_ready=False)


def authenticate(root, original, final, harness, stream):
    """Verify actual streamed bytes, then freshly audit final89 BEFORE locks."""
    root = _context(root, harness)
    wire.pipe_only(stream); _no_stop(root)
    header, header_digest = wire.read_header(stream)
    anchors = _anchors(root, original, final, harness, header)
    check_files(root, anchors['copied']); check_files(baseline.FINAL_ROOT, anchors['files'])
    support = _support(anchors['data']); _check(root, anchors, support)
    verified = wire.verify_archive(stream, anchors['files'], anchors['backup'], exporter.EXCLUDED,
        exporter.RESTORE_NOTE, len(anchors['data']['rows']), header_digest)
    _check(root, anchors, support)
    fresh = _native_audit(dict(anchors['files'], **support))
    exporter.validate_snapshot(fresh)
    if operator._audit_hash(fresh) != operator._audit_hash(anchors['data']):
        raise ValueError('Fresh native final audit differs from the transferred off-server evidence')
    _check(root, anchors, support)
    if _anchors(root, original, final, harness, header) != anchors:
        raise ValueError('Predecessor anchors changed during authentication')
    witness = _Witness()
    _WITNESSES[witness] = dict(pid=os.getpid(), root=root, harness=harness,
        header=deepcopy(header), record=deepcopy(_record(harness, anchors, support, verified)))
    return witness


def _live(witness):
    if not isinstance(witness, _Witness) or witness not in _WITNESSES:
        raise ValueError('Fresh in-process streamed predecessor authentication required')
    state = _WITNESSES[witness]
    if state['pid'] != os.getpid():
        raise ValueError('Live predecessor authentication cannot cross processes')
    return state


def describe(witness):
    """Non-admitting metadata projection; never a serialised witness."""
    return deepcopy(_live(witness)['record'])


def recheck(root, original, final, harness, witness):
    """Real under-lock file reads; no archive transfer, collector or new locks."""
    root = _context(root, harness); state = _live(witness)
    if root != state['root'] or harness != state['harness']:
        raise ValueError('Live predecessor witness belongs to another repeat deployment')
    anchors = _anchors(root, original, final, harness, state['header'])
    support = _support(anchors['data'])
    expected = _record(harness, anchors, support, state['record']['streamed_backup'])
    if policy.fingerprint(expected) != policy.fingerprint(state['record']):
        raise ValueError('Predecessor bytes or supporting inventory changed after the live audit')
    _check(root, anchors, support)
    return describe(witness)
