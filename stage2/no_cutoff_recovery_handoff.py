"""Recovery-specific original-evidence handoff; not a host admission scope.

The actual pinned SSH/service launcher is still required. Descriptor checks
alone are not peer identity or off-server location proof. No service, writer,
qualification, registration, task execution or archive recreation is exposed.
"""
import asyncio
from copy import deepcopy
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import threading
import weakref

import no_cutoff_recovery_predecessor as operator
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_revision as revision
import matched_repeat_stream as wire
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch

ROOT = revision.ROOT
KIND = 'live_recovery_original_evidence_not_scored_admission'
TRANSFER_KIND = 'existing_off_server_recovery_original_archive_v1'
TRANSFER_FIELDS = frozenset({'kind', 'schema_version', 'successor_experiment',
    'operator', 'snapshot', 'backup'})
_WITNESSES = weakref.WeakKeyDictionary()


class _Witness:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Recovery witnesses cannot be copied or saved')


def _task():
    try: return asyncio.current_task()
    except RuntimeError: return None


def send(destination):
    """Only the fixed Mac checkout; only the trusted launcher owns the pipe."""
    wire.pipe_only(destination)
    if Path(__file__).absolute() != launch.REPO / 'stage2/no_cutoff_recovery_handoff.py':
        raise ValueError('Use the fixed Mac recovery sender')
    commit = launch._git('rev-parse', 'HEAD').decode().strip()
    captured, document = operator._capture(commit)
    raw = {n: launch._raw(receiver.DESTINATION + '/' + n + '.json',
        document['local_files'][receiver.DESTINATION + '/' + n + '.json']) for n in ('snapshot', 'backup')}
    header = dict(kind=TRANSFER_KIND, schema_version=1, successor_experiment=policy.EXPERIMENT,
        operator=document, snapshot=raw['snapshot'].decode('utf-8'), backup=raw['backup'].decode('utf-8'))
    operator._recheck(captured)
    header_digest = wire.write_header(destination, header)
    receipt = captured['backup']['receipt']
    with producer._open(captured['folder'], 'evidence.tar.gz') as (source, _):
        wire.copy_archive(source, destination, receipt['compressed_bytes'], receipt['sha256'])
    operator._recheck(captured)
    wire.commit(destination, header_digest, receipt['sha256'])
    return dict(kind='recovery_original_bytes_sent_not_admission',
        operator_document_sha256=phase.fingerprint(document), archive_sha256=receipt['sha256'],
        paid_launch_ready=False)


def _protection(root, name):
    if root == report.ROOT:
        return phase.guard.protected_path(root, name)
    path = phase._path(root, name)
    saved = []
    # Unlike the single frozen-root compatibility exception, new recovery and
    # reporting roots must have private, non-writable-by-others ancestry.
    for directory in (root.parent, root, *reversed(path.parents)):
        if directory != root.parent and directory != root and not directory.is_relative_to(root):
            continue
        s = directory.lstat()
        if (directory.is_symlink() or directory.resolve() != directory or not stat.S_ISDIR(s.st_mode)
                or s.st_uid != os.getuid() or s.st_gid != os.getgid() or s.st_mode & 0o7022
                or directory == root and stat.S_IMODE(s.st_mode) != 0o700):
            raise ValueError('Protected private recovery/reporting ancestry required')
        phase.guard._acl(directory)
        saved.append((str(directory), phase.guard.identity(s)))
    if path.exists():
        phase.guard._acl(path)
    return tuple(saved)


def _context():
    root = ROOT
    if (platform.system() != 'Linux' or os.getuid() != 0
            or threading.current_thread() is not threading.main_thread() or _task() is None
            or Path(__file__).absolute() != root / 'stage2/no_cutoff_recovery_handoff.py'
            or Path(sys.prefix).resolve() != root / '.venv'
            or not sys.flags.isolated or not sys.dont_write_bytecode
            or sys.pycache_prefix != str(root / '.absent-bytecode-cache')
            or (root / '.absent-bytecode-cache').exists()
            or (root / '.absent-bytecode-cache').is_symlink()):
        raise ValueError('Use the isolated recovery service main-thread async task')
    for name in ('stage2', phase.RT.rstrip('/')):
        _protection(root, name)
        s = phase._path(root, name).lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_mode & 0o022:
            raise ValueError('Protected recovery source/runtime directories required')
    if stat.S_IMODE((root / phase.RT).stat().st_mode) != 0o700:
        raise ValueError('Private recovery runtime required')
    return root


def _no_stop(root):
    report.guard.service()  # Actual retained manager/procfs/protected-root proof.
    observed = revision.inspect()  # Actual trusted manager/procfs and untouched unused installation.
    for base in (root, report.ROOT, report.BASELINE):
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            relative = phase.RT + name
            _protection(base, relative)
            path = phase._path(base, relative)
            if path.exists() or path.is_symlink():
                raise ValueError('Persistent stop forbids recovery authentication')
    return observed


def _raw(root, name, expected=None):
    protection = _protection(root, name)
    path = phase._path(root, name)
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            st = os.fstat(stream.fileno())
            private = root == report.REPORTING or name.startswith('.runtime/')
            phase.guard.protected_file(root, name, st, private=private)
            if st.st_gid != os.getgid() or private and stat.S_IMODE(st.st_mode) != 0o600:
                raise ValueError('Owned group and exact private metadata mode required')
            if st.st_size > archive.ANCHOR_WINDOW:
                raise ValueError('Protected regular bounded single-link metadata required')
            raw = stream.read(archive.ANCHOR_WINDOW + 1)
            after = os.fstat(stream.fileno())
        if (producer._identity(st) != producer._identity(after)
                or producer._identity(after) != producer._identity(path.lstat())
                or protection != _protection(root, name)
                or expected is not None and export._hash(raw) != expected):
            raise ValueError('Actual metadata bytes changed')
    except OSError:
        raise ValueError('Required actual native metadata unavailable') from None
    return raw


def _reporting(data, backup):
    """Actual separate deployment plus retained successful native producer bytes."""
    expected = {'': {'stage2', producer.STATE[0], producer.STATE[1]}}
    for name in data['reporting_source_files']:
        parts = name.split('/')
        for i, part in enumerate(parts): expected.setdefault('/'.join(parts[:i]), set()).add(part)
    for name, entries in expected.items():
        path = phase._path(report.REPORTING, name) if name else report.REPORTING
        st = path.lstat()
        if (path.is_symlink() or path.resolve() != path or not stat.S_ISDIR(st.st_mode)
                or st.st_uid != os.getuid() or st.st_mode & 0o077
                or {p.name for p in path.iterdir()} != entries):
            raise ValueError('Exact private reporting deployment and successful backup state required')
    raw = {n: _raw(report.REPORTING, n) for n in producer.STATE[:2]}
    intent, result = (phase._loads(raw[n]) for n in producer.STATE[:2])
    if set(intent) != {'kind', 'created_utc', 'snapshot_sha256', 'reporting_source_files', 'automatic_resume', 'paid_launch_ready'}:
        raise ValueError('Exact retained native backup intent required')
    archive._utc(intent['created_utc'])
    archive._same({k: v for k, v in intent.items() if k != 'created_utc'},
        dict(kind='one_shot_amended_final_backup_intent', snapshot_sha256=phase.fingerprint(data),
            reporting_source_files=data['reporting_source_files'], automatic_resume=False, paid_launch_ready=False))
    archive._same(result, dict(kind='native_amended_archive_streamed_not_off_server_proof',
        receipt=backup['receipt'], automatic_resume=False, off_server_backup_verified=False, paid_launch_ready=False))
    for name, sha in data['reporting_source_files'].items(): _raw(report.REPORTING, name, sha)
    return {n: export._hash(value) for n, value in raw.items()}



def _anchors(root, header):
    if (type(header) is not dict or set(header) != TRANSFER_FIELDS
            or header['kind'] != TRANSFER_KIND or type(header['schema_version']) is not int
            or header['schema_version'] != 1 or header['successor_experiment'] != policy.EXPERIMENT):
        raise ValueError('Exact recovery transfer envelope required')
    document = header['operator']
    if (type(document) is not dict or set(document) != operator.FIELDS
            or document['kind'] != operator.KIND or type(document['schema_version']) is not int
            or document['schema_version'] != 1 or document['successor_experiment'] != policy.EXPERIMENT
            or document['paid_launch_ready'] is not False or type(document['operator_commit']) is not str
            or not re.fullmatch('[a-f0-9]{40}', document['operator_commit'])):
        raise ValueError('Exact current recovery operator capture required')
    archive._map(document['local_files']); archive._map(document['native_files'])
    raw = {}
    for name, sha in (('snapshot', policy.SNAPSHOT_SHA256), ('backup', policy.BACKUP_SHA256)):
        if type(header[name]) is not str:
            raise ValueError('Exact original UTF-8 metadata required')
        raw[name] = header[name].encode('utf-8')
        if (export._hash(raw[name]) != sha
                or document['local_files'].get(receiver.DESTINATION + '/' + name + '.json') != sha):
            raise ValueError('Transferred original snapshot/backup bytes changed')
    data, backup = phase._loads(raw['snapshot']), phase._loads(raw['backup'])
    anchors = {n: _raw(report.ROOT, n, h) for n, h in archive.anchor_hashes().items()}
    archive.validate_snapshot(data, anchors)
    final = archive._anchors(anchors)[0]
    policy.original_final(final)
    current = operator.sources(root, final)
    archive._same(current, document['current_sources'])
    operator.loaded(root, current)
    copied = {'stage2/' + n: h for n, h in current.items()}
    for name, sha in copied.items():
        if document['local_files'].get(name) != sha:
            raise ValueError('Actual operator and native recovery sources differ')
        _raw(root, name, sha)
    for name, sha in data['reporting_source_files'].items():
        if copied.get(name) != sha:
            raise ValueError('Current recovery copy differs from archived reporter bytes')
    relative = phase.RT + policy.ORIGINAL_FILE
    copied[relative] = policy.ORIGINAL_QUALIFICATION_FILE_SHA256
    archive._same(phase._loads(_raw(root, relative, copied[relative])), final)
    manifest = phase._loads(_raw(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    copied['stage2/input_manifest.json'] = policy.INPUT_SHA256
    policy.cells(manifest)
    for key in ('native_files', 'reporting_source_files', 'absent_paths', 'directory_entries', 'preserved_result_files'):
        archive._same(document[key], data['supporting_file_sha256' if key == 'native_files' else key])
    expected = dict(kind='verified_mac_amended_final_backup_not_admission', operator_commit=policy.REPORTER_COMMIT,
        snapshot_file_sha256=policy.SNAPSHOT_SHA256, receipt=backup.get('receipt'), verification=backup.get('verification'),
        off_server_backup_verified=True, archive_export_and_handoff_integrated=False,
        full_runtime_restore_exercised=False, automatic_resume=False, paid_launch_ready=False)
    archive._same(backup, expected); archive._receipt(data, backup['receipt'])
    if (backup['receipt']['sha256'] != policy.ARCHIVE_SHA256
            or document['local_files'].get(receiver.DESTINATION + '/evidence.tar.gz') != policy.ARCHIVE_SHA256):
        raise ValueError('Only the same original retained archive is accepted')
    projection = export._projection(dict(data=data, backup=backup,
        hashes={receiver.DESTINATION + '/backup.json': policy.BACKUP_SHA256}))
    if {n: export._hash(v) for n, v in projection.items()} != policy.PUBLIC_FILES:
        raise ValueError('Deterministic original public projection changed')
    public = {**export.PREREQUISITES, **{export.DESTINATION + '/' + n: h for n, h in policy.PUBLIC_FILES.items()}}
    for name, sha in public.items():
        if document['local_files'].get(name) != sha:
            raise ValueError('Operator must bind already committed original public results')
        _raw(root, name, sha); copied[name] = sha
    block = operator.predecessor(data, backup, manifest, export._hash(raw['snapshot']), export._hash(raw['backup']))
    archive._same(document['predecessor'], block)
    native = {'stage2/' + n: h for n, h in final['sources'].items()}
    native.update({phase.RT + n: h for n, h in report.INPUTS.items()})
    native.update(final['evidence_files']); native.update(report.HISTORICAL_INPUTS)
    report._merge(native, report.dependencies.FILES)
    report._merge(native, report.guard.REPORTING_LIBRARY_FILES)
    return dict(data=data, backup=backup, document=document, anchors=anchors, final=final,
        sources=current, copied=copied, native=native, reporting_state=_reporting(data, backup))


def _check(root, value, revision_state=None):
    observed = _no_stop(root)  # Last service observations precede the final evidence reads.
    if revision_state is not None and observed != revision_state:
        raise ValueError('Retained unstarted installation identity changed')
    for name, sha in value['native'].items(): producer._digest(report.ROOT, name, sha)
    archive._same(_reporting(value['data'], value['backup']), value['reporting_state'])
    producer._recheck(value['data'])  # Real files/inventories/absences/all182 historical results.
    for name, sha in value['copied'].items(): _raw(root, name, sha)
    archive._same(_reporting(value['data'], value['backup']), value['reporting_state'])
    operator.loaded(root, value['sources'])


def _native_audit(value):
    # The trusted reporting bootstrap enforces exact isolated interpreter,
    # credential-free environment, source/deployment guard and actual collect.
    bindings = dict(native=value['native'], reporting=value['data']['reporting_source_files'],
        commit=value['document']['operator_commit'])
    aliases = launch._aliases(bindings)
    program = launch.transport._wrap(launch._program(bindings, 'collect'), aliases)
    raw, metadata = launch.transport._exchange(program, aliases,
        [str(report.ROOT / '.venv/bin/python'), '-I', '-B', '-'],
        dict(report.ENVIRONMENT), cwd=report.ROOT)
    launch.transport._completed(raw, metadata)
    return phase._loads(raw)



def _record(value, verified):
    return dict(kind=KIND, experiment=policy.EXPERIMENT,
        predecessor=deepcopy(value['document']['predecessor']),
        operator_document_sha256=phase.fingerprint(value['document']),
        current_sources_sha256=phase.fingerprint(value['sources']), copied_files=value['copied'],
        native_files=value['data']['supporting_file_sha256'],
        reporting_source_files=value['data']['reporting_source_files'],
        reporting_state_files=value['reporting_state'], absent_paths=value['data']['absent_paths'],
        directory_entries=value['data']['directory_entries'],
        preserved_result_files=value['data']['preserved_result_files'], streamed_backup=verified,
        paid_launch_ready=False, historical_installed_bytes_attested=False,
        recovery_execution_qualified=False, full_runtime_restore_exercised=False,
        transport='source-bound-pinned-SSH-required-not-descriptor-proof')


def authenticate(stream):
    """Actual original audit BEFORE future full ancestor locks; no saved entry."""
    root = _context(); wire.pipe_only(stream)
    # The pinned sender cannot emit a header until its actual original audit
    # and retained-archive verification finish. Before then, its required audit
    # may legitimately occupy the original root. Bootstrap ancestor checks run
    # before receiver-ready; repeat them here after the header, before reading
    # archive bytes or acquiring locks. This header alone grants no authority.
    header, header_digest = wire.read_header(stream)
    revision_state = _no_stop(root)
    value = _anchors(root, header); _check(root, value, revision_state)
    verified = archive.verify_stream(stream, value['data'], value['backup']['receipt'])
    archive._same(verified, value['backup']['verification'])
    trailer = wire.COMMIT + header_digest + bytes.fromhex(verified['sha256'])
    if wire._exact(stream, len(trailer)) != trailer or stream.read(1):
        raise ValueError('Exact final operator commitment and EOF required')
    _check(root, value, revision_state)
    fresh = _native_audit(value)
    archive.validate_snapshot(fresh, value['anchors'])
    archive._same(operator.audit_hash(fresh), policy.AUDIT_SHA256)
    if archive._utc(fresh['collected_utc']) < archive._utc(value['data']['collected_utc']):
        raise ValueError('Fresh original audit cannot predate the retained snapshot')
    operator._same_anchored(_anchors(root, header), value)
    _check(root, value, revision_state)
    witness = _Witness()
    _WITNESSES[witness] = dict(pid=os.getpid(), thread=threading.get_ident(), task=_task(),
        root=root, header=deepcopy(header), revision=revision_state, record=deepcopy(_record(value, verified)))
    return witness


def invalidate(witness):
    _WITNESSES.pop(witness, None)


def _live(witness):
    if type(witness) is not _Witness or witness not in _WITNESSES:
        raise ValueError('Actual live recovery handoff required, not a saved record')
    state = _WITNESSES[witness]
    if (state['pid'] != os.getpid() or state['thread'] != threading.get_ident() or state['task'] is not _task()):
        invalidate(witness)
        raise ValueError('Recovery witness cannot cross processes, threads or async tasks')
    return state


def describe(witness):
    return deepcopy(_live(witness)['record'])


def recheck(witness):
    """Under caller's ancestor locks: reread only, never recursive audit/transfer."""
    state = _live(witness)
    try:
        root = _context()
        if root != state['root']: raise ValueError('Recovery deployment changed')
        value = _anchors(root, state['header'])
        archive._same(_record(value, state['record']['streamed_backup']), state['record'])
        _check(root, value, state['revision'])
        return describe(witness)
    except BaseException:
        invalidate(witness)
        raise
