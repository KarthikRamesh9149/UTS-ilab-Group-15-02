"""Actual absence-aware predecessor transfer and native live witness.

The fixed Mac sender freshly audits, verifies the existing archive/export and
commits only after rereading its bytes. The pinned connection supplies peer
authentication: a pipe alone is not network identity or off-server proof.
Native authentication runs the actual separate reporter BEFORE caller locks;
under-lock recheck only reads actual bound bytes/inventories/absences. There is
no saved-witness, archive-write, deployment, qualification or paid entry.
"""
import asyncio
from copy import deepcopy
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import threading
import weakref

import matched_repeat_amended_predecessor as operator
import matched_repeat_baseline as baseline
import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
import matched_repeat_stream as wire
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch
from matched_repeat_baseline_probe import check_files

KIND = 'live_amended_custom_final_predecessor_not_repeat_admission'
TRANSFER_KIND = 'existing_off_server_amended_custom_final_archive_v1'
TRANSFER_FIELDS = frozenset({'kind', 'schema_version', 'harness', 'operator', 'snapshot', 'backup'})
_WITNESSES = weakref.WeakKeyDictionary()
_first = operator._first
_maps = archive._map


class _Witness:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Live amended predecessor witnesses cannot be saved or copied')


def _task():
    try: return asyncio.current_task()
    except RuntimeError: return None


def send(repo, destination, harness='terminus-2'):
    """Fresh fixed-checkout capture; only the pinned connection owns the pipe."""
    _first(harness); wire.pipe_only(destination)
    if (Path(repo) != launch.REPO
            or Path(__file__).absolute() != launch.REPO / 'stage2/matched_repeat_amended_handoff.py'):
        raise ValueError('Use the fixed Mac operator checkout')
    commit = launch._git('rev-parse', 'HEAD').decode().strip()
    captured, document = operator._capture(commit, harness)
    raw = {n: launch._raw(receiver.DESTINATION + '/' + n + '.json',
        document['local_files'][receiver.DESTINATION + '/' + n + '.json']) for n in ('snapshot', 'backup')}
    header = dict(kind=TRANSFER_KIND, schema_version=1, harness=harness, operator=document,
        snapshot=raw['snapshot'].decode('utf-8'), backup=raw['backup'].decode('utf-8'))
    operator._recheck(captured)
    header_digest = wire.write_header(destination, header)
    receipt = captured['backup']['receipt']
    with producer._open(captured['folder'], 'evidence.tar.gz') as (source, _):
        wire.copy_archive(source, destination, receipt['compressed_bytes'], receipt['sha256'])
    # Exact source, input, export, state and actual archive rereads withhold the
    # final marker on mutation. No backup is copied to another local pathname.
    operator._recheck(captured)
    wire.commit(destination, header_digest, receipt['sha256'])
    return dict(kind='amended_off_server_predecessor_bytes_sent_not_admission',
        operator_document_sha256=phase.fingerprint(document), archive_sha256=receipt['sha256'],
        paid_launch_ready=False)


def _context(root, harness):
    _first(harness); root = Path(root)
    if (platform.system() != 'Linux' or threading.current_thread() is not threading.main_thread()
            or root != runtime.DEPLOYMENTS[harness] or root.is_symlink() or root.resolve() != root
            or not root.is_dir() or Path(__file__).resolve() != root / 'stage2/matched_repeat_amended_handoff.py'):
        raise ValueError('Use the separate native repeat deployment on its main thread')
    return root


def _no_stop(root):
    baseline.inactive_ancestors()
    for base in (Path(root), baseline.FINAL_ROOT):
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            try: marker = phase._path(base, phase.RT + name)
            except ValueError:
                raise ValueError('Persistent stop or unsafe stop path forbids successor authentication') from None
            if marker.exists():
                raise ValueError('Persistent stop forbids successor authentication')


def _raw(root, name, expected=None):
    protection = phase.guard.protected_path(root, name)
    path = phase._path(root, name)
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            st = os.fstat(stream.fileno())
            private = root == report.REPORTING or name.startswith('.runtime/')
            phase.guard.protected_file(root, name, st, private=private)
            if st.st_size > archive.ANCHOR_WINDOW:
                raise ValueError('Protected regular bounded single-link metadata required')
            raw = stream.read(archive.ANCHOR_WINDOW + 1)
            after = os.fstat(stream.fileno())
        if (producer._identity(st) != producer._identity(after)
                or producer._identity(after) != producer._identity(path.lstat())
                or protection != phase.guard.protected_path(root, name)
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
    for name, sha in data['reporting_source_files'].items(): producer._digest(report.REPORTING, name, sha)
    return {n: export._hash(value) for n, value in raw.items()}


def _anchors(root, original, final, harness, header):
    _first(harness)
    if (not isinstance(header, dict) or set(header) != TRANSFER_FIELDS
            or header['kind'] != TRANSFER_KIND or type(header['schema_version']) is not int
            or header['schema_version'] != 1 or header['harness'] != harness):
        raise ValueError('Exact amended live transfer envelope required')
    document = header['operator']
    if (not isinstance(document, dict) or set(document) != operator.FIELDS
            or document['kind'] != operator.KIND or type(document['schema_version']) is not int
            or document['schema_version'] != 1 or document['successor_harness'] != harness
            or document['paid_launch_ready'] is not False
            or document['original_qualification_sha256'] != policy.ORIGINAL_QUALIFICATION_SHA256
            or not isinstance(document['operator_commit'], str)
            or not re.fullmatch('[a-f0-9]{40}', document['operator_commit'])):
        raise ValueError('Exact current amended operator capture required')
    _maps(document['local_files']); _maps(document['native_files'])
    raw = {}
    for name in ('snapshot', 'backup'):
        if not isinstance(header[name], str): raise ValueError('Exact raw UTF-8 metadata required')
        raw[name] = header[name].encode('utf-8')
        if export._hash(raw[name]) != document['local_files'].get(receiver.DESTINATION + '/' + name + '.json'):
            raise ValueError('Transferred original snapshot/backup bytes changed')
    data, backup = phase._loads(raw['snapshot']), phase._loads(raw['backup'])
    anchors = {n: _raw(report.ROOT, n, h) for n, h in archive.anchor_hashes().items()}
    archive.validate_snapshot(data, anchors)
    archive._same(final, archive._anchors(anchors)[0]); policy.anchors(original, final)
    current = runtime.sources(root, original, final); runtime.loaded_sources(root, current)
    copied = {'stage2/' + n: h for n, h in current.items()}
    for name, sha in copied.items():
        if document['local_files'].get(name) != sha:
            raise ValueError('Actual operator and native repeat source bytes differ')
    for name, value, sha in ((policy.BASELINE_FILE, original, baseline.ORIGINAL_FILE_SHA256),
            (policy.FINAL_FILE, final, baseline.FINAL_FILE_SHA256)):
        relative = phase.RT + name; actual = _raw(root, relative, sha)
        archive._same(phase._loads(actual), value); copied[relative] = sha
    for key, value in (('native_files', data['supporting_file_sha256']),
            ('reporting_source_files', data['reporting_source_files']), ('absent_paths', data['absent_paths']),
            ('directory_entries', data['directory_entries']), ('preserved_result_files', data['preserved_result_files'])):
        archive._same(document[key], value)
    expected = dict(kind='verified_mac_amended_final_backup_not_admission', operator_commit=backup.get('operator_commit'),
        snapshot_file_sha256=export._hash(raw['snapshot']), receipt=backup.get('receipt'), verification=backup.get('verification'),
        off_server_backup_verified=True, archive_export_and_handoff_integrated=False,
        full_runtime_restore_exercised=False, automatic_resume=False, paid_launch_ready=False)
    archive._same(backup, expected)
    if not isinstance(backup['operator_commit'], str) or not re.fullmatch('[a-f0-9]{40}', backup['operator_commit']):
        raise ValueError('Exact original backup operator revision required')
    archive._receipt(data, backup['receipt'])
    if document['local_files'].get(receiver.DESTINATION + '/evidence.tar.gz') != backup['receipt']['sha256']:
        raise ValueError('Existing off-server archive bytes must match the capture')
    projection = export._projection(dict(data=data, backup=backup,
        hashes={receiver.DESTINATION + '/backup.json': export._hash(raw['backup'])}))
    public = {**export.PREREQUISITES, **{export.DESTINATION + '/' + n: export._hash(v) for n, v in projection.items()}}
    for name, sha in public.items():
        if document['local_files'].get(name) != sha:
            raise ValueError('Operator public export differs from exact amended evidence')
        _raw(root, name, sha); copied[name] = sha
    manifest = phase._loads(_raw(root, 'stage2/input_manifest.json', policy.INPUT_SHA256))
    archive._same(document['predecessors'], operator._predecessors(data, backup, manifest, export._hash(raw['backup']), harness))
    native = {'stage2/' + n: h for n, h in final['sources'].items()}
    native.update({phase.RT + n: h for n, h in report.INPUTS.items()})
    native.update(final['evidence_files']); native.update(report.HISTORICAL_INPUTS)
    return dict(data=data, backup=backup, document=document, anchors=anchors, sources=current,
        copied=copied, native=native, reporting_state=_reporting(data, backup))


def _check(root, value):
    # All service observations precede final byte/inventory/absence reads.
    _no_stop(root)
    check_files(root, value['copied'])
    for name, sha in value['native'].items(): producer._digest(report.ROOT, name, sha)
    archive._same(_reporting(value['data'], value['backup']), value['reporting_state'])
    producer._recheck(value['data'])  # includes every original178/stopped-four hash
    check_files(root, value['copied'])
    archive._same(_reporting(value['data'], value['backup']), value['reporting_state'])


def _native_audit(value):
    # The trusted reporting bootstrap enforces exact isolated interpreter,
    # credential-free environment, source/deployment guard and actual collect.
    bindings = dict(native=value['native'], reporting=value['data']['reporting_source_files'],
        commit=value['document']['operator_commit'])
    try:
        response = subprocess.run([str(report.ROOT / '.venv/bin/python'), '-I', '-B', '-'],
            input=launch._program(bindings, 'collect').encode(), cwd=report.ROOT,
            capture_output=True, timeout=300, env=dict(report.ENVIRONMENT))
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Fresh amended native audit unavailable; preserve evidence without retry') from None
    if response.returncode or len(response.stdout) > archive.ANCHOR_WINDOW:
        raise ValueError('Fresh amended native audit refused or incomplete')
    return phase._loads(response.stdout)


def _record(harness, value, verified):
    return dict(kind=KIND, experiment=policy.EXPERIMENT, harness=harness,
        predecessors=deepcopy(value['document']['predecessors']),
        operator_document_sha256=phase.fingerprint(value['document']),
        current_sources_sha256=phase.fingerprint(value['sources']), copied_files=value['copied'],
        native_files=value['data']['supporting_file_sha256'], reporting_source_files=value['data']['reporting_source_files'],
        reporting_state_files=value['reporting_state'], absent_paths=value['data']['absent_paths'],
        directory_entries=value['data']['directory_entries'], preserved_result_files=value['data']['preserved_result_files'],
        streamed_backup=verified, paid_launch_ready=False, historical_installed_bytes_attested=False,
        repeat_execution_qualified=False, full_runtime_restore_exercised=False,
        transport='source-bound-pinned-SSH-required-not-descriptor-proof')


def authenticate(root, original, final, harness, stream):
    root = _context(root, harness); wire.pipe_only(stream); _no_stop(root)
    header, header_digest = wire.read_header(stream)
    value = _anchors(root, original, final, harness, header); _check(root, value)
    verified = archive.verify_stream(stream, value['data'], value['backup']['receipt'])
    archive._same(verified, value['backup']['verification'])
    trailer = wire.COMMIT + header_digest + bytes.fromhex(verified['sha256'])
    if wire._exact(stream, len(trailer)) != trailer or stream.read(1):
        raise ValueError('Exact final operator commitment and EOF required')
    _check(root, value)
    fresh = _native_audit(value)  # Takes its own locks, before the session locks.
    archive.validate_snapshot(fresh, value['anchors'])
    archive._same(operator._audit_hash(fresh), operator._audit_hash(value['data']))
    if archive._utc(fresh['collected_utc']) < archive._utc(value['data']['collected_utc']):
        raise ValueError('Fresh native audit cannot predate the retained snapshot')
    if _anchors(root, original, final, harness, header) != value:
        raise ValueError('Amended predecessor anchors changed across authentication')
    _check(root, value)
    witness = _Witness()
    _WITNESSES[witness] = dict(pid=os.getpid(), thread=threading.get_ident(), task=_task(),
        root=root, harness=harness, header=deepcopy(header), record=deepcopy(_record(harness, value, verified)))
    return witness


def _live(witness):
    if not isinstance(witness, _Witness) or witness not in _WITNESSES:
        raise ValueError('Fresh actual amended handoff required, not a saved record')
    state = _WITNESSES[witness]
    if (state['pid'] != os.getpid() or state['thread'] != threading.get_ident() or state['task'] is not _task()):
        raise ValueError('Live handoff cannot cross processes, threads or async tasks')
    return state


def describe(witness):
    return deepcopy(_live(witness)['record'])


def recheck(root, original, final, harness, witness):
    state = _live(witness)
    try:
        root = _context(root, harness)
        if root != state['root'] or harness != state['harness']:
            raise ValueError('Live predecessor belongs to another native deployment')
        value = _anchors(root, original, final, harness, state['header'])
        archive._same(_record(harness, value, state['record']['streamed_backup']), state['record'])
        _check(root, value)
        return describe(witness)
    except BaseException:
        _WITNESSES.pop(witness, None)
        raise
