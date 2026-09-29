"""Exclusive fixed Mac receiver for ONE source-bound amended native backup.

Not a public exporter, saved-proof importer, restore tool or repeat admission.
Do not invoke until the entire amended export/handoff route is frozen and the
final service has completed. Partial files remain for inspection, never retry.
"""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import selectors
import stat
import struct
import subprocess
import time

import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_reporting as launch

DESTINATION = '.runtime/netcup/custom-no-cutoff-final89-c0-nc-20260928'
TRANSPORT_SECONDS = 900  # Whole transfer window, never a benchmark deadline.


def _directory(path):
    state = path.lstat()
    if (path.is_symlink() or path.resolve() != path or not stat.S_ISDIR(state.st_mode)
            or state.st_uid != os.getuid() or state.st_mode & 0o077):
        raise ValueError('Canonical private owned backup directory required')


def _destination():
    parent = phase._path(launch.REPO, '.runtime/netcup')
    for path in (parent.parent, parent): _directory(path)
    folder = phase._path(launch.REPO, DESTINATION)
    if folder.exists():
        raise ValueError('Existing or partial final backup must never be replaced or recreated')
    return folder


def _ready(handle, event, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0: raise ValueError('Backup transport expired; inspect without retry')
    with selectors.DefaultSelector() as selector:
        selector.register(handle, event)
        if not selector.select(remaining):
            raise ValueError('Backup transport expired; inspect without retry')


def _read(handle, size, deadline):
    value = bytearray()
    while len(value) < size:
        _ready(handle, selectors.EVENT_READ, deadline)
        raw = os.read(handle.fileno(), min(producer.CHUNK, size - len(value)))
        if not raw: raise ValueError('Incomplete archive transfer; retain partial bytes without retry')
        value.extend(raw)
    return bytes(value)


def _metadata(handle, deadline):
    size = struct.unpack('!Q', _read(handle, 8, deadline))[0]
    if not 0 < size <= archive.ANCHOR_WINDOW:
        raise ValueError('Backup metadata parser window exceeded')
    raw = _read(handle, size, deadline)
    return phase._loads(raw), raw


def _raw_save(folder, name, raw):
    with os.fdopen(os.open(phase._path(folder, name),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        producer._write(stream, raw); stream.flush(); os.fsync(stream.fileno())
    _sync(folder)


def _sync(folder):
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def _receive(handle, folder, bindings, deadline):
    if _read(handle, len(producer.MAGIC), deadline) != producer.MAGIC:
        raise ValueError('Exact amended archive transport required')
    data, raw = _metadata(handle, deadline)
    archive.validate_snapshot(data, bindings['anchors'])
    archive._same(data['reporting_source_files'], bindings['reporting'])
    # Preserve raw UTF-8/Python numeric bytes. Never round-trip through JS.
    _raw_save(folder, 'snapshot.json', raw)
    snapshot_hash = hashlib.sha256(raw).hexdigest()
    digest = hashlib.sha256(); compressed = 0
    with os.fdopen(os.open(phase._path(folder, 'evidence.tar.gz'),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as target:
        while True:
            size = struct.unpack('!Q', _read(handle, 8, deadline))[0]
            if size == 0: break
            if size > producer.CHUNK:
                raise ValueError('Invalid archive transport frame')
            chunk = _read(handle, size, deadline)
            producer._write(target, chunk); digest.update(chunk); compressed += size
        target.flush(); os.fsync(target.fileno())
    _sync(folder)
    receipt, _ = _metadata(handle, deadline)
    archive._receipt(data, receipt)
    if receipt['sha256'] != digest.hexdigest() or receipt['compressed_bytes'] != compressed:
        raise ValueError('Received archive bytes differ from native terminal receipt')
    if _read(handle, len(producer.END), deadline) != producer.END:
        raise ValueError('Native final reread commitment is absent')
    _ready(handle, selectors.EVENT_READ, deadline)
    if os.read(handle.fileno(), 1): raise ValueError('Trailing bytes after native backup commitment')
    return data, receipt, snapshot_hash


def _start():
    # A bound SSH program is the only producer. Never accept a path, callback,
    # file-like caller archive or saved report as a substitute for this process.
    return subprocess.Popen(launch._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})


def _send(process, program, deadline):
    fd = process.stdin.fileno(); os.set_blocking(fd, False)
    remaining = memoryview(program.encode())
    try:
        while remaining:
            _ready(process.stdin, selectors.EVENT_WRITE, deadline)
            try: count = os.write(fd, remaining[:producer.CHUNK])
            except BlockingIOError: continue
            if count <= 0: raise ValueError('Incomplete backup bootstrap write')
            remaining = remaining[count:]
    finally:
        process.stdin.close()


def backup(commit):
    """One actual native audit and streamed backup to the fixed Mac directory."""
    bindings = launch._prepare(commit)
    if Path(__file__).resolve() != launch.REPO / 'stage2/no_cutoff_final_backup_operator.py':
        raise ValueError('Use the source-bound fixed Mac backup receiver')
    folder = _destination()
    # This is a read-only deployment/inactive-service check, not a collector.
    launch.inspect_deployment(commit)
    launch._recheck(bindings); _destination()
    program = launch._program(bindings, 'backup')
    folder.mkdir(mode=0o700); _sync(folder.parent)
    process = None
    try:
        producer._save(folder, 'intent.json', dict(kind='exclusive_amended_final_backup_operator_intent',
            operator_commit=commit, created_utc=datetime.now(timezone.utc).isoformat(),
            reporting_source_files=bindings['reporting'], automatic_resume=False, paid_launch_ready=False))
        intent_sha, _ = producer._digest(folder, 'intent.json')
        launch._recheck(bindings)
        deadline = time.monotonic() + TRANSPORT_SECONDS
        process = _start(); _send(process, program, deadline)
        data, receipt, snapshot_hash = _receive(process.stdout, folder, bindings, deadline)
        remaining = deadline - time.monotonic()
        if remaining <= 0 or process.wait(timeout=remaining) != 0:
            raise ValueError('Native backup did not finish successfully; inspect without retry')
        # Re-read the actual one retained archive; never regenerate it.
        verified = archive.verify_archive(folder / 'evidence.tar.gz', data, receipt)
        launch._recheck(bindings); _directory(folder)
        producer._digest(folder, 'intent.json', intent_sha)
        producer._digest(folder, 'snapshot.json', snapshot_hash)
        producer._digest(folder, 'evidence.tar.gz', receipt['sha256'])
        if {p.name for p in folder.iterdir()} != {'intent.json', 'snapshot.json', 'evidence.tar.gz'}:
            raise ValueError('Private backup inventory changed before commitment')
        result = dict(kind='verified_mac_amended_final_backup_not_admission', operator_commit=commit,
            snapshot_file_sha256=snapshot_hash, receipt=receipt, verification=verified,
            off_server_backup_verified=True, archive_export_and_handoff_integrated=False,
            full_runtime_restore_exercised=False, automatic_resume=False, paid_launch_ready=False)
        producer._save(folder, 'backup.json', result)
        return result
    except BaseException as error:
        # Preserve partial evidence, including a receipt if a late failure
        # occurred. No native stop, overwrite, removal or automatic retry.
        producer._save(folder, 'failure.json', dict(kind='amended_backup_inspection_required',
            error_type=type(error).__name__, automatic_resume=False, paid_launch_ready=False))
        raise ValueError('Backup incomplete or uncertain; inspect retained native and Mac state before any action') from None
    finally:
        if process is not None:
            # Only this owned SSH client may be terminated. No server unit or
            # benchmark process is signalled by this reporting transport.
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
            for stream in (process.stdin, process.stdout):
                if stream is not None: stream.close()
