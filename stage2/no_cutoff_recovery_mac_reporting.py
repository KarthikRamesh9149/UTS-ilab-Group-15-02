"""Darwin-only backup/export amendment; frozen native R6 is unchanged.

The real original-audit/archive sender executes in its own source-bound child.
A successful private backup still needs the actual native completed recovery
audit, post-session native commitment and strict same-archive verification.
No installer, qualifier, paid dispatcher, retry, extraction or replacement.
"""
from datetime import datetime, timezone
import hashlib
import os
import re
import struct
import subprocess
import time

import mac_operator_files as boot
import no_cutoff_recovery_mac_archive as archive
import no_cutoff_recovery_mac_bridge as bridge
import no_cutoff_recovery_reporting as frozen
from no_cutoff_recovery_reporting import (
    BACKUP as FAILED_BACKUP, EXPORT, PUBLIC, AUDIT_MAGIC, TIMEOUT, OUTPUTS,
    _ready, _json, _equal_audit, _command, projection,
)
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_report as report

BACKUP = '.runtime/netcup/custom-no-cutoff-recovery3-20261001-r3'
FAILED_FILES = {
    'intent.json': '7a49bd3ba8d0bd215cfb80f3cf03ec801f88bd8ca91a18f57a6ed306fedd4e5d',
    'failure.json': '9cbc70820f9403c958bd5ba879b64f60d004fd2e3f11ecfb08028e2a317ee65c',
}
FAILED_BACKUPS = {
    FAILED_BACKUP: FAILED_FILES,
    '.runtime/netcup/custom-no-cutoff-recovery3-20261001-r2': {
        'intent.json': 'c215bd13cb3b6dc5d998866936806ba5c49d356dc9b4ab5364a203632e669171',
        'failure.json': '9cbc70820f9403c958bd5ba879b64f60d004fd2e3f11ecfb08028e2a317ee65c',
    },
}

CAPTURE_STAGES = frozenset({'prepare', 'receiver_start', 'receiver_ready',
    'before_sender_recheck', 'original_sender', 'stream_receive', 'final_recheck'})
ERROR_CLASSES = frozenset({'ValueError', 'TypeError', 'OSError', 'PermissionError',
    'FileNotFoundError', 'FileExistsError', 'TimeoutError', 'TimeoutExpired',
    'BrokenPipeError', 'EOFError', 'RuntimeError', 'KeyboardInterrupt', 'CancelledError'})


def _error_class(error):
    name = type(error).__name__
    return name if name in ERROR_CLASSES else 'OtherError'


class _CaptureFailure(ValueError):
    """Fixed stage/class only; never retain a message, stack or child payload."""
    def __init__(self, stage, error):
        if stage not in CAPTURE_STAGES:
            raise ValueError('Unknown local capture stage')
        self.stage = stage; self.error_class = _error_class(error)
        super().__init__('Recovery capture failed; preserve without retry')


def _failed_backup():
    """Both actual terminal attempts, never destinations to resume or repair."""
    root = handoff.launch.REPO; directories = {}; records = {}
    for folder, files in FAILED_BACKUPS.items():
        path = root / folder
        directories[folder] = boot.directories(path, private=True)
        if {p.name for p in path.iterdir()} != set(files):
            raise ValueError('Exact retained failed recovery backup inventory required')
        records.update({folder+'/'+n: boot.raw(path, n, digest) for n, digest in files.items()})
    for folder, files in FAILED_BACKUPS.items():
        path = root / folder
        if (boot.directories(path, private=True) != directories[folder]
                or {p.name for p in path.iterdir()} != set(files)
                or any(boot.raw(path, n, files[n]) != records[folder+'/'+n] for n in files)):
            raise ValueError('Failed recovery backup bytes or identities changed')
    return dict(directories=directories, records=records)


def _prepare(commit):
    preserved = _failed_backup()
    value, files = bridge.prepare(commit)
    value = dict(value, failed_backup=preserved)
    _current(value, value['local_identities'])
    return value, files


def _parents():
    return boot.directories(handoff.launch.REPO/'.runtime/netcup', private=True)


def _directory_id(path):
    return boot.directories(path, private=True)


def _state(path, identity):
    if (_parents(), _directory_id(path)) != identity:
        raise ValueError('Darwin operator ancestry or private directory identity changed')


def _current(value, identities):
    bridge.current(value)
    if value['local_identities'] != identities or _failed_backup() != value['failed_backup']:
        raise ValueError('Exact original operator identities required')


def _manifest(value):
    return boot.loads(handoff.launch._raw('stage2/input_manifest.json', policy.INPUT_SHA256))


def _private_bytes(path, raw):
    return boot.write_bytes(path, raw)


def _receive(process, mode, value, *, path=None):
    receiver = handoff.operator.receiver
    deadline = time.monotonic() + TIMEOUT
    magic = archive.MAGIC if mode == 'backup' else AUDIT_MAGIC
    if receiver._read(process.stdout, len(magic), deadline) != magic:
        raise ValueError('Exact recovery reporting stream required')
    document, raw = receiver._metadata(process.stdout, deadline)
    if mode == 'backup':
        if set(document) != {'snapshot', 'inventory'}: raise ValueError('Exact recovery backup envelope required')
        data, inventory = document['snapshot'], document['inventory']
    else: data = document
    report.validate(data, _manifest(value), value['current_sources'])
    if mode == 'backup':
        archive.validate_inventory(inventory, data)
        written = {'snapshot.json': _private_bytes(path / 'snapshot.json', _json(data)),
            'inventory.json': _private_bytes(path / 'inventory.json', _json(inventory))}
        target = path / 'evidence.tar.gz'; sha = hashlib.sha256(); size = 0
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as handle:
            while True:
                count = struct.unpack('!Q', receiver._read(process.stdout, 8, deadline))[0]
                if count == 0: break
                if count > archive.CHUNK: raise ValueError('Invalid recovery archive frame')
                payload = receiver._read(process.stdout, count, deadline)
                archive.framing._write(handle, payload); sha.update(payload); size += count
            handle.flush(); os.fsync(handle.fileno())
            written['evidence.tar.gz'] = boot.identity(os.fstat(handle.fileno()))
        receiver._sync(path)
        receipt, _ = receiver._metadata(process.stdout, deadline)
        if receipt.get('sha256') != sha.hexdigest() or receipt.get('compressed_bytes') != size:
            raise ValueError('Received recovery archive differs from native commitment')
    if receiver._read(process.stdout, len(archive.END), deadline) != archive.END:
        raise ValueError('Missing post-session native reporting commitment')
    if process.wait(timeout=30) != 0 or process.stdout.read(1):
        raise ValueError('Uncertain reporting SSH exit; retain evidence without retry')
    if mode == 'backup' and any(boot.identity((path / n).lstat()) != identity for n, identity in written.items()):
        raise ValueError('Received recovery evidence replaced before verification')
    return (data, inventory, receipt, written) if mode == 'backup' else data


def _capture(commit, mode, *, path=None):
    process = None; stage = 'prepare'
    try:
        value, files = _prepare(commit); identities = value['local_identities']
        stage = 'receiver_start'
        process = subprocess.Popen(_command(files, commit, mode), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        stage = 'receiver_ready'
        policy._same(frozen.connection.read_reply(process.stdout), _ready(files, commit, mode))
        stage = 'before_sender_recheck'
        _current(value, identities)
        stage = 'original_sender'
        bridge.send(value, process.stdin)  # Actual fresh original audit + SAME original archive, never a saved receipt.
        process.stdin.close()
        stage = 'stream_receive'
        result = _receive(process, mode, value, path=path)
        stage = 'final_recheck'
        _current(value, identities)
        return result, value, identities
    except Exception as error:
        raise _CaptureFailure(stage, error) from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill(); process.wait(timeout=30)  # Owned Mac SSH client only; no native signal.
            process.stdin.close(); process.stdout.close()


def backup(commit):
    """ONE exclusive off-server recovery archive, never another original copy."""
    value, _ = _prepare(commit); identities = value['local_identities']
    receiver = handoff.operator.receiver; parents = _parents()
    path = handoff.launch.REPO / BACKUP
    if path.exists() or path.is_symlink(): raise ValueError('Recovery backup already exists or is partial; do not repeat')
    path.mkdir(mode=0o700); receiver._sync(path.parent)
    state = (parents, _directory_id(path))
    boot.save(path / 'intent.json', dict(kind='one_shot_off_server_recovery_backup', commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False, paid_launch_ready=False))
    intent = boot.raw(path, 'intent.json')
    stage = 'capture'
    try:
        (data, inventory, receipt, written), capture, captured_ids = _capture(commit, 'backup', path=path)
        stage = 'archive_verify'
        verified = archive.verify(path / 'evidence.tar.gz', data, inventory, receipt, _manifest(value), value['current_sources'])
        stage = 'final_evidence_recheck'
        _state(path, state); _current(value, identities); _current(capture, captured_ids)
        if (boot.raw(path, 'intent.json') != intent
                or {p.name for p in path.iterdir()} != {'intent.json', 'snapshot.json', 'inventory.json', 'evidence.tar.gz'}
                or boot.loads(boot.raw(path, 'snapshot.json')[0]) != data
                or boot.loads(boot.raw(path, 'inventory.json')[0]) != inventory
                or any(boot.identity((path / n).lstat()) != identity for n, identity in written.items())):
            raise ValueError('Recovery receiver evidence changed before durable completion')
        stage = 'durable_completion'
        boot.save(path / 'backup.json', dict(kind='verified_off_server_recovery_backup', receipt=receipt,
            verified=verified, snapshot_sha256=policy.fingerprint(data), inventory_sha256=policy.fingerprint(inventory),
            automatic_resume=False, paid_launch_ready=False))
        _state(path, state)
        return dict(kind='recovery_backup_verified', completed=3, archive_sha256=receipt['sha256'],
            compressed_bytes=receipt['compressed_bytes'], full_runtime_restore_exercised=False, paid_launch_ready=False)
    except BaseException as error:
        _state(path, state)
        diagnostic = dict(stage=stage, error_class=_error_class(error))
        if type(error) is _CaptureFailure:
            diagnostic = dict(stage='capture_'+error.stage, error_class=error.error_class)
        boot.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_recovery_backup',
            automatic_resume=False, paid_launch_ready=False, diagnostic=diagnostic))
        raise


def _read_backup(value):
    preserved = _failed_backup()
    receiver = handoff.operator.receiver; path = handoff.launch.REPO / BACKUP
    state = (_parents(), _directory_id(path))
    if {p.name for p in path.iterdir()} != {'intent.json', 'snapshot.json', 'inventory.json', 'evidence.tar.gz', 'backup.json'}:
        raise ValueError('Exactly one completed retained recovery backup required')
    records = {n: boot.raw(path, n) for n in ('intent.json', 'snapshot.json', 'inventory.json', 'backup.json')}
    data = boot.loads(records['snapshot.json'][0]); inventory = boot.loads(records['inventory.json'][0])
    saved = boot.loads(records['backup.json'][0])
    intent = boot.loads(records['intent.json'][0])
    if (set(intent) != {'kind', 'commit', 'started_utc', 'automatic_resume', 'paid_launch_ready'}
            or intent['kind'] != 'one_shot_off_server_recovery_backup'
            or type(intent['commit']) is not str or not re.fullmatch('[a-f0-9]{40}', intent['commit'])
            or intent['automatic_resume'] is not False or intent['paid_launch_ready'] is not False):
        raise ValueError('Exact original one-shot recovery backup intent required')
    handoff.archive._utc(intent['started_utc'])
    if (set(saved) != {'kind', 'receipt', 'verified', 'snapshot_sha256', 'inventory_sha256',
            'automatic_resume', 'paid_launch_ready'} or saved.get('kind') != 'verified_off_server_recovery_backup'
            or saved.get('automatic_resume') is not False or saved.get('paid_launch_ready') is not False):
        raise ValueError('Actual completed recovery backup record required')
    policy._same(saved['snapshot_sha256'], policy.fingerprint(data))
    policy._same(saved['inventory_sha256'], policy.fingerprint(inventory))
    verified = archive.verify(path / 'evidence.tar.gz', data, inventory, saved['receipt'],
        _manifest(value), value['current_sources'])
    policy._same(verified, saved['verified']); _state(path, state)
    if any(boot.raw(path, n) != record for n, record in records.items()): raise ValueError('Retained backup metadata replaced')
    if _failed_backup() != preserved: raise ValueError('Failed backup evidence changed during archive verification')
    return data, saved


def export(commit):
    """Fresh actual native audit + SAME recovery archive before exclusive export."""
    value, _ = _prepare(commit); identities = value['local_identities']
    root = handoff.launch.REPO; path = root / EXPORT; receiver = handoff.operator.receiver
    parents = _parents(); public = root / PUBLIC
    if path.exists() or path.is_symlink(): raise ValueError('Existing/partial recovery export cannot be repeated')
    public_identity = boot.directories(public)
    if any((public / n).exists() or (public / n).is_symlink() for n in OUTPUTS):
        raise ValueError('Recovery public outcomes are immutable')
    path.mkdir(mode=0o700); receiver._sync(path.parent)
    state = (parents, _directory_id(path))
    boot.save(path / 'intent.json', dict(kind='one_shot_separate_recovery_export', commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False))
    intent = boot.raw(path, 'intent.json')
    try:
        fresh, capture, captured_ids = _capture(commit, 'audit')
        saved, backup_record = _read_backup(value); _equal_audit(saved, fresh)
        retained = root / BACKUP
        backup_files = {n: boot.raw(retained, n) for n in ('intent.json', 'snapshot.json', 'inventory.json', 'backup.json')}
        backup_archive_id = boot.identity((retained / 'evidence.tar.gz').lstat())
        backup_directory_id = _directory_id(retained)
        outputs = projection(saved, backup_record)
        _current(value, identities); _current(capture, captured_ids); _state(path, state)
        if boot.directories(public) != public_identity or boot.raw(path, 'intent.json') != intent:
            raise ValueError('Recovery export directories or intent changed')
        for name, raw in outputs.items():
            fd = os.open(public / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            with os.fdopen(fd, 'wb') as handle:
                archive.framing._write(handle, raw); handle.flush(); os.fsync(handle.fileno())
        receiver._sync(public)
        bound = {PUBLIC + '/' + n: hashlib.sha256(raw).hexdigest() for n, raw in outputs.items()}
        for name, digest in bound.items(): handoff.launch._raw(name, digest)
        _current(value, identities); _current(capture, captured_ids); _state(path, state)
        if (_directory_id(retained) != backup_directory_id
                or {p.name for p in retained.iterdir()} != set(backup_files) | {'evidence.tar.gz'}
                or any(boot.raw(retained, n) != previous for n, previous in backup_files.items())
                or boot.identity((retained / 'evidence.tar.gz').lstat()) != backup_archive_id
                or boot.directories(public) != public_identity or boot.raw(path, 'intent.json') != intent):
            raise ValueError('Retained recovery evidence changed during public export')
        boot.save(path / 'result.json', dict(kind='separate_recovery_allowlisted_export_complete',
            files=bound, snapshot_sha256=policy.fingerprint(saved), archive_sha256=backup_record['receipt']['sha256'],
            automatic_resume=False, paid_launch_ready=False))
        _state(path, state)
        return dict(experiment=policy.EXPERIMENT, files=bound, aggregate=saved['aggregate'], paid_launch_ready=False)
    except BaseException:
        _state(path, state)
        boot.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_export', automatic_resume=False))
        raise
