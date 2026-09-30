"""Pinned live completed recovery audit, ONE backup and separate public export.

The native reporter opens its own actual handoff session on the main async
task. The Mac sends the same retained ORIGINAL archive, never recreating it.
Only this separate recovery archive is written, once. No replay or restore.
"""
import asyncio
import base64
from contextlib import redirect_stdout
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import time

import no_cutoff_recovery_archive as archive
import no_cutoff_recovery_bootstrap as boot
import no_cutoff_recovery_connection as connection
import no_cutoff_recovery_files as evidence
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_report as report
import no_cutoff_recovery_service as service
import no_cutoff_recovery_session as session

BACKUP = '.runtime/netcup/custom-no-cutoff-recovery3-20260929'
EXPORT = '.runtime/netcup/custom-no-cutoff-recovery-export-20260929'
NATIVE_BACKUP = '.runtime/stage2/no-cutoff-recovery-completed-backup'
PUBLIC = 'stage2/results/custom-no-cutoff-recovery-20260929'
AUDIT_MAGIC = b'UTS-C0NC-RECOVERY3-AUDIT-1\n'
TIMEOUT = handoff.launch.transport.HANDOFF_SECONDS
OUTPUTS = ('summary.json', 'trials.json', 'trials.csv')


def _ready(files, commit, mode):
    if mode not in ('audit', 'backup') or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Exact committed reporting readiness required')
    return dict(kind='recovery_reporting_receiver_ready_not_authenticated', mode=mode,
        root=str(boot.ROOT), operator_commit=commit, bindings_sha256=policy.fingerprint(files),
        paid_launch_ready=False)


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode() + b'\n'


def _equal_audit(first, second):
    # Only collection time changes between genuine actual native audits.
    a = dict(first); b = dict(second); old = a.pop('collected_utc'); new = b.pop('collected_utc')
    policy._same(a, b)
    if datetime.fromisoformat(new.replace('Z', '+00:00')) < datetime.fromisoformat(old.replace('Z', '+00:00')):
        raise ValueError('Fresh recovery audit cannot predate the retained completed snapshot')


async def native(files, commit, mode):
    """Only the committed fixed bootstrap can enter this real live receiver."""
    if mode not in ('audit', 'backup'): raise ValueError('Fixed recovery reporting operation required')
    if Path(__file__).absolute() != boot.ROOT / 'stage2/no_cutoff_recovery_reporting.py':
        raise ValueError('Own fixed committed native reporter required')
    identities = boot.check(files); service.loaded(files)
    output = sys.__stdout__.buffer; incoming = sys.stdin.buffer
    handoff.wire.pipe_only(incoming)
    path = boot.ROOT / NATIVE_BACKUP
    if mode == 'backup' and (path.exists() or path.is_symlink()):
        raise ValueError('A previous/partial recovery backup is terminal, never recreated')
    # All actual bootstrap ancestor checks finish before the sender begins its
    # original audit. The session then waits for its post-audit header before
    # checking ancestor processes again. Readiness itself is never admission.
    output.write(service._line(_ready(files, commit, mode))); output.flush()
    created = False; state = data = inventory = inventory_state = receipt = None
    try:
        with redirect_stdout(sys.stderr), session.open_session(incoming) as active:
            live = session._live(active)
            policy._same(handoff._live(live['witness'])['header']['operator']['operator_commit'], commit)
            if mode == 'backup':
                path.mkdir(mode=0o700); service._sync(path.parent); created = True
                parent_id = boot.directories(path, private=True)
                evidence.save(path / 'intent.json', dict(kind='one_shot_separate_recovery_backup',
                    commit=commit, sources_sha256=policy.fingerprint(files), automatic_resume=False,
                    started_utc=datetime.now(timezone.utc).isoformat(), paid_launch_ready=False))
                intent = boot.raw(boot.ROOT, NATIVE_BACKUP + '/intent.json')
            data, state = report.collect(active)
            manifest = boot.loads(boot.raw(boot.ROOT, 'stage2/input_manifest.json', policy.INPUT_SHA256)[0])
            report.validate(data, manifest, live['inputs']['sources'])
            if mode == 'backup':
                inventory, inventory_state = archive.inventory(data)
                archive.framing._write(output, archive.MAGIC)
                archive.framing._metadata(output, dict(snapshot=data, inventory=inventory))
                receipt = archive.pack(output, inventory, inventory_state)
                actual, actual_state = report.collect(active); _equal_audit(data, actual)
                archive.recheck(inventory, inventory_state); report.reread(boot.ROOT, data, state)
                if (boot.directories(path, private=True) != parent_id
                        or boot.raw(boot.ROOT, NATIVE_BACKUP + '/intent.json') != intent
                        or {p.name for p in path.iterdir()} != {'intent.json'}):
                    raise ValueError('Native backup operation evidence changed')
                evidence.save(path / 'result.json', dict(receipt, automatic_resume=False, paid_launch_ready=False))
                result_identity = boot.raw(boot.ROOT, NATIVE_BACKUP + '/result.json')
        # Both real session handles must exit successfully before commitment.
        boot.check(files, identities); service.loaded(files); report.reread(boot.ROOT, data, state)
        if mode == 'backup':
            archive.recheck(inventory, inventory_state)
            if (boot.directories(path, private=True) != parent_id
                    or boot.raw(boot.ROOT, NATIVE_BACKUP + '/intent.json') != intent
                    or boot.raw(boot.ROOT, NATIVE_BACKUP + '/result.json') != result_identity
                    or {p.name for p in path.iterdir()} != {'intent.json', 'result.json'}):
                raise ValueError('Late native backup evidence changed')
            archive.framing._write(output, struct.pack('!Q', 0))
            archive.framing._metadata(output, receipt)
        else:
            archive.framing._write(output, AUDIT_MAGIC)
            archive.framing._metadata(output, data)
        archive.framing._write(output, archive.END); output.flush()
    except BaseException:
        if created:
            evidence.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_evidence',
                automatic_resume=False, paid_launch_ready=False))
        raise


def _program(files, commit, mode):
    if mode not in ('audit', 'backup'): raise ValueError('Fixed reporting operation required')
    raw = handoff.launch._raw('stage2/no_cutoff_recovery_bootstrap.py', files['stage2/no_cutoff_recovery_bootstrap.py'])
    return ('import base64,sys,types\n'
        + 'b=types.ModuleType("no_cutoff_recovery_bootstrap")\n'
        + 'b.__file__=' + repr(str(boot.ROOT / 'stage2/no_cutoff_recovery_bootstrap.py')) + '\n'
        + 'sys.modules[b.__name__]=b\n'
        + 'exec(compile(base64.b64decode(' + repr(base64.b64encode(raw).decode()) + '),b.__file__,"exec"),b.__dict__)\n'
        + 'try:\n b.reporting(' + ','.join(map(repr, (files, commit, mode))) + ')\n'
        + 'except BaseException:\n raise SystemExit("Recovery reporting failed; preserve evidence without retry") from None\n')


def _command(files, commit, mode):
    fixed = connection.command('0' * 32, files, commit)
    remote = ['/usr/bin/env', '-i', *(k + '=' + v for k, v in boot.environment().items()),
        str(boot.ROOT / '.venv/bin/python'), '-I', '-B', '-c', _program(files, commit, mode)]
    return fixed[:-1] + [shlex.join(remote)]


def _current(value, identities):
    connection.operator._current(value)
    if connection._local_identities(value) != identities:
        raise ValueError('Operator source/private/public evidence identity changed')


def _manifest(value):
    return boot.loads(handoff.launch._raw('stage2/input_manifest.json', policy.INPUT_SHA256))


def _private_bytes(path, raw):
    parent = boot.directories(path.parent, private=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as handle:
        archive.framing._write(handle, raw); handle.flush(); os.fsync(handle.fileno())
        identity = boot.identity(os.fstat(handle.fileno()))
    service._sync(path.parent)
    if boot.raw(path.parent, path.name) != (raw, identity) or boot.directories(path.parent, private=True) != parent:
        raise ValueError('Exclusive private receiver bytes changed')
    return identity


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
    value, files = connection.prepare(commit); identities = connection._local_identities(value)
    process = None
    try:
        process = subprocess.Popen(_command(files, commit, mode), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        policy._same(connection.read_reply(process.stdout), _ready(files, commit, mode))
        handoff.send(process.stdin)  # Actual fresh original audit + SAME original archive, never a saved receipt.
        process.stdin.close()
        result = _receive(process, mode, value, path=path)
        _current(value, identities)
        return result, value, identities
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill(); process.wait(timeout=30)  # Owned Mac SSH client only; no native signal.
            process.stdin.close(); process.stdout.close()


def backup(commit):
    """ONE exclusive off-server recovery archive, never another original copy."""
    value, _ = connection.prepare(commit); identities = connection._local_identities(value)
    receiver = handoff.operator.receiver; parents = receiver._parents()
    path = handoff.launch.REPO / BACKUP
    if path.exists() or path.is_symlink(): raise ValueError('Recovery backup already exists or is partial; do not repeat')
    path.mkdir(mode=0o700); receiver._sync(path.parent)
    state = (parents, receiver._directory_id(path))
    evidence.save(path / 'intent.json', dict(kind='one_shot_off_server_recovery_backup', commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False, paid_launch_ready=False))
    intent = boot.raw(path, 'intent.json')
    try:
        (data, inventory, receipt, written), capture, captured_ids = _capture(commit, 'backup', path=path)
        verified = archive.verify(path / 'evidence.tar.gz', data, inventory, receipt, _manifest(value), value['current_sources'])
        receiver._state(path, state); _current(value, identities); _current(capture, captured_ids)
        if (boot.raw(path, 'intent.json') != intent
                or {p.name for p in path.iterdir()} != {'intent.json', 'snapshot.json', 'inventory.json', 'evidence.tar.gz'}
                or boot.loads(boot.raw(path, 'snapshot.json')[0]) != data
                or boot.loads(boot.raw(path, 'inventory.json')[0]) != inventory
                or any(boot.identity((path / n).lstat()) != identity for n, identity in written.items())):
            raise ValueError('Recovery receiver evidence changed before durable completion')
        evidence.save(path / 'backup.json', dict(kind='verified_off_server_recovery_backup', receipt=receipt,
            verified=verified, snapshot_sha256=policy.fingerprint(data), inventory_sha256=policy.fingerprint(inventory),
            automatic_resume=False, paid_launch_ready=False))
        receiver._state(path, state)
        return dict(kind='recovery_backup_verified', completed=3, archive_sha256=receipt['sha256'],
            compressed_bytes=receipt['compressed_bytes'], full_runtime_restore_exercised=False, paid_launch_ready=False)
    except BaseException:
        receiver._state(path, state)
        evidence.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_recovery_backup',
            automatic_resume=False, paid_launch_ready=False))
        raise


def _read_backup(value):
    receiver = handoff.operator.receiver; path = handoff.launch.REPO / BACKUP
    state = (receiver._parents(), receiver._directory_id(path))
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
    policy._same(verified, saved['verified']); receiver._state(path, state)
    if any(boot.raw(path, n) != record for n, record in records.items()): raise ValueError('Retained backup metadata replaced')
    return data, saved


def projection(data, backup_record):
    rows = data['rows']
    summary = dict(experiment=policy.EXPERIMENT, original_experiment=policy.plan.ORIGINAL_EXPERIMENT,
        original_full89_denominator=89, separate_recovery_denominator=3,
        original_results_replaced=False, recovery_merged_into_original89=False, best_of_selection=False,
        aggregate=data['aggregate'], collected_utc=data['collected_utc'],
        qualification_sha256=data['qualification_sha256'], registration_sha256=policy.fingerprint(data['registration']),
        sources_sha256=data['sources_sha256'], snapshot_sha256=policy.fingerprint(data),
        archive_sha256=backup_record['receipt']['sha256'], completed_recovery_audit=True,
        off_server_backup_verified=True, full_runtime_restore_exercised=False,
        historical_installed_bytes_attested=False, paid_launch_ready=False)
    text = io.StringIO(newline=''); fields = sorted(ROW_FIELDS_CSV)
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator='\n'); writer.writeheader()
    for row in rows:
        flat = {k: v for k, v in row.items() if k not in ('phase_observation', 'recovery_preparation')}
        flat.update(preparation_observation_sha256=policy.fingerprint(row['recovery_preparation']),
            **{p + '_observation': row['phase_observation'][p] for p in ('setup', 'agent', 'verifier')})
        writer.writerow(flat)
    return {'summary.json': _json(summary), 'trials.json': _json(dict(experiment=policy.EXPERIMENT, rows=rows)),
        'trials.csv': text.getvalue().encode()}


ROW_FIELDS_CSV = (report.ROW_FIELDS - {'phase_observation', 'recovery_preparation'}) | {
    'preparation_observation_sha256', 'setup_observation', 'agent_observation', 'verifier_observation'}


def export(commit):
    """Fresh actual native audit + SAME recovery archive before exclusive export."""
    value, _ = connection.prepare(commit); identities = connection._local_identities(value)
    root = handoff.launch.REPO; path = root / EXPORT; receiver = handoff.operator.receiver
    parents = receiver._parents(); public = root / PUBLIC
    if path.exists() or path.is_symlink(): raise ValueError('Existing/partial recovery export cannot be repeated')
    public_identity = boot.directories(public)
    if any((public / n).exists() or (public / n).is_symlink() for n in OUTPUTS):
        raise ValueError('Recovery public outcomes are immutable')
    path.mkdir(mode=0o700); receiver._sync(path.parent)
    state = (parents, receiver._directory_id(path))
    evidence.save(path / 'intent.json', dict(kind='one_shot_separate_recovery_export', commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False))
    intent = boot.raw(path, 'intent.json')
    try:
        fresh, capture, captured_ids = _capture(commit, 'audit')
        saved, backup_record = _read_backup(value); _equal_audit(saved, fresh)
        retained = root / BACKUP
        backup_files = {n: boot.raw(retained, n) for n in ('intent.json', 'snapshot.json', 'inventory.json', 'backup.json')}
        backup_archive_id = boot.identity((retained / 'evidence.tar.gz').lstat())
        backup_directory_id = receiver._directory_id(retained)
        outputs = projection(saved, backup_record)
        _current(value, identities); _current(capture, captured_ids); receiver._state(path, state)
        if boot.directories(public) != public_identity or boot.raw(path, 'intent.json') != intent:
            raise ValueError('Recovery export directories or intent changed')
        for name, raw in outputs.items():
            fd = os.open(public / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            with os.fdopen(fd, 'wb') as handle:
                archive.framing._write(handle, raw); handle.flush(); os.fsync(handle.fileno())
        receiver._sync(public)
        bound = {PUBLIC + '/' + n: hashlib.sha256(raw).hexdigest() for n, raw in outputs.items()}
        for name, digest in bound.items(): handoff.launch._raw(name, digest)
        _current(value, identities); _current(capture, captured_ids); receiver._state(path, state)
        if (receiver._directory_id(retained) != backup_directory_id
                or {p.name for p in retained.iterdir()} != set(backup_files) | {'evidence.tar.gz'}
                or any(boot.raw(retained, n) != previous for n, previous in backup_files.items())
                or boot.identity((retained / 'evidence.tar.gz').lstat()) != backup_archive_id
                or boot.directories(public) != public_identity or boot.raw(path, 'intent.json') != intent):
            raise ValueError('Retained recovery evidence changed during public export')
        evidence.save(path / 'result.json', dict(kind='separate_recovery_allowlisted_export_complete',
            files=bound, snapshot_sha256=policy.fingerprint(saved), archive_sha256=backup_record['receipt']['sha256'],
            automatic_resume=False, paid_launch_ready=False))
        receiver._state(path, state)
        return dict(experiment=policy.EXPERIMENT, files=bound, aggregate=saved['aggregate'], paid_launch_ready=False)
    except BaseException:
        receiver._state(path, state)
        evidence.save(path / 'failure.json', dict(status='failed_or_uncertain_preserve_export', automatic_resume=False))
        raise
