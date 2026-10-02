"""Fixed Terminus completed audit, ONE backup and separate allowlisted export.

Every reporting operation consumes the actual composite recovery/original
handoff in its own main-thread async session. No saved admission, replay,
original archive recreation or caller-selected root/factory exists.
"""
import asyncio
import base64
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys

import mac_operator_files as mac
import matched_repeat_mac_archive as mac_archive
import matched_repeat_archive as archive
import matched_repeat_execution_bootstrap as boot
import matched_repeat_execution_connection as connection
import matched_repeat_execution_transport as transport
import no_cutoff_recovery_files as evidence
import matched_repeat_recovery_handoff as handoff
import matched_repeat_policy as policy
import matched_repeat_report as report
import matched_repeat_execution_service as service
import matched_repeat_session as session
import matched_repeat_public as public_projection

HARNESS = 'terminus-2'
ROOT = boot.root_for(HARNESS)
BACKUP = '.runtime/netcup/matched-repeat-terminus-2-89-20260930'
EXPORT = '.runtime/netcup/matched-repeat-terminus-2-export-20260930'
NATIVE_BACKUP = '.runtime/stage2/matched-repeat-completed-backup'
PUBLIC = 'stage2/results/matched-repeat-20260928/terminus-2'
AUDIT_MAGIC = b'UTS-MATCHED-BASELINE89-AUDIT-1\n'
TIMEOUT = handoff.original.launch.transport.HANDOFF_SECONDS
OUTPUTS = ('summary.json', 'trials.json', 'trials.csv')


def _ready(files, commit, mode):
    if mode not in ('audit', 'backup') or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Exact committed reporting readiness required')
    return dict(kind='baseline_reporting_receiver_ready_not_authenticated', mode=mode,
        root=str(ROOT), operator_commit=commit, bindings_sha256=policy.fingerprint(files),
        paid_launch_ready=False)


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode() + b'\n'


def _equal_audit(first, second):
    # Only collection time changes between genuine actual native audits.
    a = dict(first); b = dict(second); old = a.pop('collected_utc'); new = b.pop('collected_utc')
    archive.same(a, b)
    if datetime.fromisoformat(new.replace('Z', '+00:00')) < datetime.fromisoformat(old.replace('Z', '+00:00')):
        raise ValueError('Fresh baseline audit cannot predate the retained completed snapshot')


async def native(files, commit, mode):
    """Only the committed fixed bootstrap can enter this real live receiver."""
    if mode not in ('audit', 'backup'): raise ValueError('Fixed baseline reporting operation required')
    if Path(__file__).absolute() != ROOT / 'stage2/matched_repeat_reporting.py':
        raise ValueError('Own fixed committed native reporter required')
    identities = boot.check(HARNESS, files); service.loaded(HARNESS, files)
    output = sys.__stdout__.buffer; incoming = sys.stdin.buffer
    handoff.wire.pipe_only(incoming)
    path = ROOT / NATIVE_BACKUP
    if mode == 'backup' and (path.exists() or path.is_symlink()):
        raise ValueError('A previous/partial baseline backup is terminal, never recreated')
    # All actual bootstrap ancestor checks finish before the sender begins its
    # original audit. The session then waits for its post-audit header before
    # checking ancestor processes again. Readiness itself is never admission.
    output.write(service._line(_ready(files, commit, mode))); output.flush()
    created = False; state = data = inventory = inventory_state = receipt = None
    try:
        with transport.Writer(output) as framed:
            with redirect_stdout(sys.stderr), session.open_execution_session(ROOT, HARNESS, transport.Reader(incoming)) as active:
                live = session._live(active)
                archive.same(session.handoff._live(live['witness'])['header']['operator']['operator_commit'], commit)
                if mode == 'backup':
                    path.mkdir(mode=0o700); service._sync(path.parent); created = True
                    parent_id = boot.directories(path, private=True)
                    evidence.save(path / 'intent.json', dict(kind='one_shot_separate_baseline_backup',
                        commit=commit, sources_sha256=policy.fingerprint(files), automatic_resume=False,
                        started_utc=datetime.now(timezone.utc).isoformat(), paid_launch_ready=False))
                    intent = boot.raw(ROOT, NATIVE_BACKUP + '/intent.json')
                data, state = report.collect(active)
                if data['harness'] != HARNESS: raise ValueError('Exact first baseline reporter required')
                manifest = boot.loads(boot.raw(ROOT, 'stage2/input_manifest.json', policy.INPUT_SHA256)[0])
                report.validate(data, manifest, {n[7:]: h for n, h in live['files'].items() if n.startswith('stage2/')})
                if mode == 'backup':
                    inventory, inventory_state = archive.inventory(data)
                    archive.framing._write(framed, archive.MAGIC)
                    archive.framing._metadata(framed, dict(snapshot=data, inventory=inventory))
                    receipt = archive.pack(framed, inventory, inventory_state)
                    actual, actual_state = report.collect(active); _equal_audit(data, actual)
                    archive.recheck(inventory, inventory_state); report.reread(ROOT, data, state)
                    if (boot.directories(path, private=True) != parent_id
                            or boot.raw(ROOT, NATIVE_BACKUP + '/intent.json') != intent
                            or {p.name for p in path.iterdir()} != {'intent.json'}):
                        raise ValueError('Native backup operation evidence changed')
                    evidence.save(path / 'result.json', dict(receipt, automatic_resume=False, paid_launch_ready=False))
                    result_identity = boot.raw(ROOT, NATIVE_BACKUP + '/result.json')
            # Both real session handles must exit successfully before commitment.
            boot.check(HARNESS, files, identities); service.loaded(HARNESS, files); report.reread(ROOT, data, state)
            if mode == 'backup':
                archive.recheck(inventory, inventory_state)
                if (boot.directories(path, private=True) != parent_id
                        or boot.raw(ROOT, NATIVE_BACKUP + '/intent.json') != intent
                        or boot.raw(ROOT, NATIVE_BACKUP + '/result.json') != result_identity
                        or {p.name for p in path.iterdir()} != {'intent.json', 'result.json'}):
                    raise ValueError('Late native backup evidence changed')
                archive.framing._write(framed, struct.pack('!Q', 0))
                archive.framing._metadata(framed, receipt)
            else:
                archive.framing._write(framed, AUDIT_MAGIC)
                archive.framing._metadata(framed, data)
            archive.framing._write(framed, archive.END); framed.flush()
            framed.finish()
    except BaseException:
        if created:
            evidence.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_evidence',
                automatic_resume=False, paid_launch_ready=False))
        raise


def _program(files, commit, mode):
    if mode not in ('audit', 'backup'): raise ValueError('Fixed reporting operation required')
    raw = handoff.original.launch._raw('stage2/matched_repeat_execution_bootstrap.py', files['stage2/matched_repeat_execution_bootstrap.py'])
    return ('import base64,sys,types\n'
        + 'b=types.ModuleType("matched_repeat_execution_bootstrap")\n'
        + 'b.__file__=' + repr(str(ROOT / 'stage2/matched_repeat_execution_bootstrap.py')) + '\n'
        + 'sys.modules[b.__name__]=b\n'
        + 'exec(compile(base64.b64decode(' + repr(base64.b64encode(raw).decode()) + '),b.__file__,"exec"),b.__dict__)\n'
        + 'try:\n b.reporting(' + ','.join(map(repr, (HARNESS, files, commit, mode))) + ')\n'
        + 'except BaseException:\n raise SystemExit("Baseline reporting failed; preserve evidence without retry") from None\n')


def _command(files, commit, mode):
    fixed = connection.command(HARNESS, '0' * 32, files, commit, 'qualify-repeat')
    remote = ['/usr/bin/env', '-i', *(k + '=' + v for k, v in boot.environment(HARNESS).items()),
        str(ROOT / '.venv/bin/python'), '-I', '-B', '-c', _program(files, commit, mode)]
    return fixed[:-1] + [shlex.join(remote)]


def _current(value, identities):
    connection._current(value)
    if connection._identities(value['bindings']) != identities:
        raise ValueError('Operator source/private/public evidence identity changed')


def _manifest(value):
    return boot.loads(handoff.original.launch._raw('stage2/input_manifest.json', policy.INPUT_SHA256))


def _private_bytes(path, raw):
    return mac.write_bytes(path, raw)


def _parents():
    return mac.directories(handoff.original.launch.REPO/'.runtime/netcup', private=True)


def _directory_id(path):
    return mac.directories(path, private=True)


def _state(path, identity):
    if (_parents(), _directory_id(path)) != identity:
        raise ValueError('Actual protected Mac reporting ancestry changed')


def _receive(process, mode, value, *, received, path=None):
    receiver = handoff.original.receiver
    if type(received) is not transport.StreamReceiver or received.stream is not process.stdout:
        raise ValueError('Same actual owned reporting transport required')
    def exact(size): return handoff.wire._exact(received, size)
    def metadata():
        size = struct.unpack('!Q', exact(8))[0]
        if not 0 < size <= archive.original_archive.ANCHOR_WINDOW:
            raise ValueError('Backup metadata parser window exceeded')
        raw = exact(size)
        return receiver.phase._loads(raw), raw
    magic = archive.MAGIC if mode == 'backup' else AUDIT_MAGIC
    if exact(len(magic)) != magic:
        raise ValueError('Exact baseline reporting stream required')
    document, raw = metadata()
    if mode == 'backup':
        if set(document) != {'snapshot', 'inventory'}: raise ValueError('Exact baseline backup envelope required')
        data, inventory = document['snapshot'], document['inventory']
    else: data = document
    report.validate(data, _manifest(value), value['sources'])
    if data['harness'] != HARNESS: raise ValueError('Exact first baseline reporter required')
    if mode == 'backup':
        archive.validate_inventory(inventory, data)
        written = {'snapshot.json': _private_bytes(path / 'snapshot.json', _json(data)),
            'inventory.json': _private_bytes(path / 'inventory.json', _json(inventory))}
        target = path / 'evidence.tar.gz'; sha = hashlib.sha256(); size = 0
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as handle:
            while True:
                count = struct.unpack('!Q', exact(8))[0]
                if count == 0: break
                if count > archive.CHUNK: raise ValueError('Invalid baseline archive frame')
                payload = exact(count)
                archive.framing._write(handle, payload); sha.update(payload); size += count
            handle.flush(); os.fsync(handle.fileno())
            written['evidence.tar.gz'] = mac.identity(os.fstat(handle.fileno()))
        receiver._sync(path)
        receipt, _ = metadata()
        if receipt.get('sha256') != sha.hexdigest() or receipt.get('compressed_bytes') != size:
            raise ValueError('Received baseline archive differs from native commitment')
    if exact(len(archive.END)) != archive.END:
        raise ValueError('Missing post-session native reporting commitment')
    if received.read(1) or process.wait(timeout=30) != 0 or process.stdout.read(1):
        raise ValueError('Uncertain reporting SSH exit; retain evidence without retry')
    if mode == 'backup' and any(mac.identity((path / n).lstat()) != identity for n, identity in written.items()):
        raise ValueError('Received baseline evidence replaced before verification')
    return (data, inventory, receipt, written) if mode == 'backup' else data


def _capture(commit, mode, *, path=None):
    value, files = connection.prepare(commit, HARNESS); identities = connection._identities(value['bindings'])
    process = None
    try:
        process = subprocess.Popen(_command(files, commit, mode), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        archive.same(connection.read_reply(process.stdout), _ready(files, commit, mode))
        with transport.StreamReceiver(process.stdout) as received:
            with transport.Writer(process.stdin, peer=received) as outgoing:
                handoff.send(outgoing)  # Both actual fresh audits/SAME archives, never a saved receipt.
                outgoing.finish()
            process.stdin.close()
            result = _receive(process, mode, value, received=received, path=path)
        _current(value, identities)
        return result, value, identities
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill(); process.wait(timeout=30)  # Owned Mac SSH client only; no native signal.
            process.stdin.close(); process.stdout.close()


def backup(commit):
    """ONE exclusive off-server baseline archive, never another original copy."""
    value, _ = connection.prepare(commit, HARNESS); identities = connection._identities(value['bindings'])
    receiver = handoff.original.receiver; parents = _parents()
    path = handoff.original.launch.REPO / BACKUP
    if path.exists() or path.is_symlink(): raise ValueError('Baseline backup already exists or is partial; do not repeat')
    path.mkdir(mode=0o700); receiver._sync(path.parent)
    state = (parents, _directory_id(path))
    mac.save(path / 'intent.json', dict(kind='one_shot_off_server_baseline_backup', commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False, paid_launch_ready=False))
    intent = mac.raw(path, 'intent.json')
    try:
        (data, inventory, receipt, written), capture, captured_ids = _capture(commit, 'backup', path=path)
        verified = mac_archive.verify(path / 'evidence.tar.gz', data, inventory, receipt, _manifest(value), value['sources'])
        _state(path, state); _current(value, identities); _current(capture, captured_ids)
        if (mac.raw(path, 'intent.json') != intent
                or {p.name for p in path.iterdir()} != {'intent.json', 'snapshot.json', 'inventory.json', 'evidence.tar.gz'}
                or boot.loads(mac.raw(path, 'snapshot.json')[0]) != data
                or boot.loads(mac.raw(path, 'inventory.json')[0]) != inventory
                or any(mac.identity((path / n).lstat()) != identity for n, identity in written.items())):
            raise ValueError('Baseline receiver evidence changed before durable completion')
        mac.save(path / 'backup.json', dict(kind='verified_off_server_baseline_backup', receipt=receipt,
            verified=verified, snapshot_sha256=policy.fingerprint(data), inventory_sha256=policy.fingerprint(inventory),
            automatic_resume=False, paid_launch_ready=False))
        _state(path, state)
        return dict(kind='baseline_backup_verified', completed=89, harness=HARNESS, archive_sha256=receipt['sha256'],
            compressed_bytes=receipt['compressed_bytes'], full_runtime_restore_exercised=False, paid_launch_ready=False)
    except BaseException:
        _state(path, state)
        mac.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_baseline_backup',
            automatic_resume=False, paid_launch_ready=False))
        raise


def _read_backup(value):
    receiver = handoff.original.receiver; path = handoff.original.launch.REPO / BACKUP
    state = (_parents(), _directory_id(path))
    if {p.name for p in path.iterdir()} != {'intent.json', 'snapshot.json', 'inventory.json', 'evidence.tar.gz', 'backup.json'}:
        raise ValueError('Exactly one completed retained baseline backup required')
    records = {n: mac.raw(path, n) for n in ('intent.json', 'snapshot.json', 'inventory.json', 'backup.json')}
    data = boot.loads(records['snapshot.json'][0]); inventory = boot.loads(records['inventory.json'][0])
    if data.get('harness') != HARNESS: raise ValueError('Exact first baseline backup required')
    saved = boot.loads(records['backup.json'][0])
    intent = boot.loads(records['intent.json'][0])
    if (set(intent) != {'kind', 'commit', 'started_utc', 'automatic_resume', 'paid_launch_ready'}
            or intent['kind'] != 'one_shot_off_server_baseline_backup'
            or type(intent['commit']) is not str or not re.fullmatch('[a-f0-9]{40}', intent['commit'])
            or intent['automatic_resume'] is not False or intent['paid_launch_ready'] is not False):
        raise ValueError('Exact original one-shot baseline backup intent required')
    handoff.original.archive._utc(intent['started_utc'])
    if (set(saved) != {'kind', 'receipt', 'verified', 'snapshot_sha256', 'inventory_sha256',
            'automatic_resume', 'paid_launch_ready'} or saved.get('kind') != 'verified_off_server_baseline_backup'
            or saved.get('automatic_resume') is not False or saved.get('paid_launch_ready') is not False):
        raise ValueError('Actual completed baseline backup record required')
    archive.same(saved['snapshot_sha256'], policy.fingerprint(data))
    archive.same(saved['inventory_sha256'], policy.fingerprint(inventory))
    verified = mac_archive.verify(path / 'evidence.tar.gz', data, inventory, saved['receipt'],
        _manifest(value), value['sources'])
    archive.same(verified, saved['verified']); _state(path, state)
    if any(mac.raw(path, n) != record for n, record in records.items()): raise ValueError('Retained backup metadata replaced')
    return data, saved


def export(commit):
    """Fresh actual native audit + SAME baseline archive before exclusive export."""
    value, _ = connection.prepare(commit, HARNESS); identities = connection._identities(value['bindings'])
    root = handoff.original.launch.REPO; path = root / EXPORT; receiver = handoff.original.receiver
    parents = _parents(); public = root / PUBLIC
    if path.exists() or path.is_symlink(): raise ValueError('Existing/partial baseline export cannot be repeated')
    public_identity = mac.directories(public)
    if any((public / n).exists() or (public / n).is_symlink() for n in OUTPUTS):
        raise ValueError('Baseline public outcomes are immutable')
    path.mkdir(mode=0o700); receiver._sync(path.parent)
    state = (parents, _directory_id(path))
    mac.save(path / 'intent.json', dict(kind='one_shot_separate_baseline_export', commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False))
    intent = mac.raw(path, 'intent.json')
    try:
        fresh, capture, captured_ids = _capture(commit, 'audit')
        saved, backup_record = _read_backup(value); _equal_audit(saved, fresh)
        retained = root / BACKUP
        backup_files = {n: mac.raw(retained, n) for n in ('intent.json', 'snapshot.json', 'inventory.json', 'backup.json')}
        backup_archive_id = mac.identity((retained / 'evidence.tar.gz').lstat())
        backup_directory_id = _directory_id(retained)
        outputs = public_projection.projection(saved, _manifest(value), value['sources'], backup_record['verified'])
        _current(value, identities); _current(capture, captured_ids); _state(path, state)
        if mac.directories(public) != public_identity or mac.raw(path, 'intent.json') != intent:
            raise ValueError('Baseline export directories or intent changed')
        for name, raw in outputs.items():
            fd = os.open(public / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            with os.fdopen(fd, 'wb') as handle:
                archive.framing._write(handle, raw); handle.flush(); os.fsync(handle.fileno())
        receiver._sync(public)
        bound = {PUBLIC + '/' + n: hashlib.sha256(raw).hexdigest() for n, raw in outputs.items()}
        for name, digest in bound.items(): handoff.original.launch._raw(name, digest)
        _current(value, identities); _current(capture, captured_ids); _state(path, state)
        if (_directory_id(retained) != backup_directory_id
                or {p.name for p in retained.iterdir()} != set(backup_files) | {'evidence.tar.gz'}
                or any(mac.raw(retained, n) != previous for n, previous in backup_files.items())
                or mac.identity((retained / 'evidence.tar.gz').lstat()) != backup_archive_id
                or mac.directories(public) != public_identity or mac.raw(path, 'intent.json') != intent):
            raise ValueError('Retained baseline evidence changed during public export')
        mac.save(path / 'result.json', dict(kind='separate_baseline_allowlisted_export_complete',
            files=bound, snapshot_sha256=policy.fingerprint(saved), archive_sha256=backup_record['receipt']['sha256'],
            automatic_resume=False, paid_launch_ready=False))
        _state(path, state)
        return dict(experiment=policy.EXPERIMENT, files=bound, aggregate=saved['aggregate'], paid_launch_ready=False)
    except BaseException:
        _state(path, state)
        mac.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_export', automatic_resume=False))
        raise
