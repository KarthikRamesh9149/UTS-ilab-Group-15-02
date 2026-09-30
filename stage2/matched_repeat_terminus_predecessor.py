"""Actual completed-Terminus audit and SAME archive for the OpenHands sender.

This is a current, separately bound reader, not a change to the archived
original-final readers. Every capture executes the real Terminus reporter,
which itself consumes the fresh recovery/original handoffs. No saved audit,
caller root, writer, archive recreation, qualification or dispatch entry exists.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

import mac_operator_files as mac
import matched_repeat_execution_connection as connection
import matched_repeat_policy as policy
import matched_repeat_reporting as reporting

KIND = 'actual_completed_terminus_capture_for_openhands_not_admission'
REPO = connection.REPO
HARNESS = 'terminus-2'
FIELDS = frozenset({'kind', 'operator_commit', 'root', 'sources_sha256',
    'fresh_audit', 'retained', 'archive_sha256', 'paid_launch_ready'})


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _names():
    return ({reporting.BACKUP + '/' + n for n in
        ('intent.json', 'snapshot.json', 'inventory.json', 'backup.json')}
        | {reporting.EXPORT + '/' + n for n in ('intent.json', 'result.json')}
        | {reporting.PUBLIC + '/' + n for n in reporting.OUTPUTS})


def metadata(document, manifest, sources):
    """Strict schema/byte relationships only; not proof of a fresh invocation."""
    same = reporting.archive.same
    if type(document) is not dict or set(document) != FIELDS:
        raise ValueError('Exact completed-Terminus capture required')
    for key, value in dict(kind=KIND, root=str(reporting.ROOT),
            sources_sha256=policy.fingerprint(sources), paid_launch_ready=False).items():
        same(document[key], value)
    if type(document['operator_commit']) is not str or not re.fullmatch('[a-f0-9]{40}', document['operator_commit']):
        raise ValueError('Actual full committed successor operator revision required')
    policy._hash(document['archive_sha256'])
    retained = document['retained']
    if (type(retained) is not dict or set(retained) != _names()
            or any(type(v) is not str for v in retained.values())):
        raise ValueError('Exact original UTF-8 Terminus backup/export bytes required')
    raw = {n: v.encode('utf-8') for n, v in retained.items()}
    records = {n: reporting.boot.loads(v) for n, v in raw.items() if n.endswith('.json')}
    data = records[reporting.BACKUP + '/snapshot.json']
    inventory = records[reporting.BACKUP + '/inventory.json']
    backup = records[reporting.BACKUP + '/backup.json']
    for observed in (data, document['fresh_audit']):
        reporting.report.validate(observed, manifest, sources)
        if observed['harness'] != HARNESS:
            raise ValueError('Only the actual first Terminus repeat is this predecessor')
    reporting._equal_audit(data, document['fresh_audit'])
    reporting.archive.validate_inventory(inventory, data)
    if (set(backup) != {'kind', 'receipt', 'verified', 'snapshot_sha256',
            'inventory_sha256', 'automatic_resume', 'paid_launch_ready'}
            or backup['kind'] != 'verified_off_server_baseline_backup'
            or backup['automatic_resume'] is not False or backup['paid_launch_ready'] is not False):
        raise ValueError('Exact completed Terminus backup record required')
    same(backup['snapshot_sha256'], policy.fingerprint(data))
    same(backup['inventory_sha256'], policy.fingerprint(inventory))
    same(backup['receipt']['sha256'], document['archive_sha256'])
    for name, kind, fields in (
            (reporting.BACKUP + '/intent.json', 'one_shot_off_server_baseline_backup',
                {'kind', 'commit', 'started_utc', 'automatic_resume', 'paid_launch_ready'}),
            (reporting.EXPORT + '/intent.json', 'one_shot_separate_baseline_export',
                {'kind', 'commit', 'started_utc', 'automatic_resume'})):
        intent = records[name]
        if (set(intent) != fields or intent['kind'] != kind or intent['automatic_resume'] is not False
                or type(intent['commit']) is not str or not re.fullmatch('[a-f0-9]{40}', intent['commit'])
                or 'paid_launch_ready' in intent and intent['paid_launch_ready'] is not False):
            raise ValueError('Exact original one-shot Terminus operation intent required')
        reporting.handoff.original.archive._utc(intent['started_utc'])
    projection = reporting.public_projection.projection(data, manifest, sources, backup['verified'])
    public = {reporting.PUBLIC + '/' + n: _hash(v) for n, v in projection.items()}
    if any(raw[reporting.PUBLIC + '/' + n] != value for n, value in projection.items()):
        raise ValueError('Terminus public outcomes differ from the separate immutable snapshot')
    same(records[reporting.EXPORT + '/result.json'], dict(
        kind='separate_baseline_allowlisted_export_complete', files=public,
        snapshot_sha256=policy.fingerprint(data), archive_sha256=backup['receipt']['sha256'],
        automatic_resume=False, paid_launch_ready=False))
    return data, inventory, backup


def block(document, manifest, sources):
    """Exact 89-result lineage, never a score floor or standalone admission."""
    data, _, backup = metadata(document, manifest, sources)
    result = dict(experiment=policy.EXPERIMENT, harness=HARNESS,
        qualification_sha256=data['qualification_sha256'],
        registration_sha256=policy.fingerprint(data['registration']),
        sources_sha256=data['sources_sha256'],
        results_sha256={r['trial_id']: r['result_sha256'] for r in data['rows']},
        audit_sha256=policy.fingerprint({n: v for n, v in data.items() if n != 'collected_utc'}),
        archive_sha256=backup['receipt']['sha256'],
        backup_record_sha256=_hash(document['retained'][reporting.BACKUP + '/backup.json'].encode()))
    lineage = deepcopy(data['predecessors'])
    lineage['successor_harness'] = 'openhands'; lineage['blocks'].append(result)
    policy.validate_predecessors(lineage, manifest, 'openhands')
    return result


def _retained(value):
    folders = {n: mac.directories(REPO / n, private=True) for n in (reporting.BACKUP, reporting.EXPORT)}
    archive_identity = mac.identity((REPO / reporting.BACKUP / 'evidence.tar.gz').lstat())
    data, backup = reporting._read_backup(value)  # Always reads the SAME real retained archive.
    expected = {reporting.BACKUP: {'intent.json', 'snapshot.json', 'inventory.json', 'backup.json', 'evidence.tar.gz'},
        reporting.EXPORT: {'intent.json', 'result.json'}}
    if any({p.name for p in (REPO / n).iterdir()} != names for n, names in expected.items()):
        raise ValueError('Exact completed Terminus backup/export inventory required')
    records = {}
    for name in sorted(_names()):
        private = name.startswith('.runtime/')
        records[name] = mac.raw(REPO, name, private=private)
        if not private and records[name][0] != reporting.handoff.original.launch._git(
                'show', value['bindings']['commit'] + ':' + name):
            raise ValueError('Actual Terminus results must already be committed and pushed')
    document = dict(kind=KIND, operator_commit=value['bindings']['commit'], root=str(reporting.ROOT),
        sources_sha256=policy.fingerprint(value['sources']), fresh_audit=data,
        retained={n: raw.decode('utf-8') for n, (raw, _) in records.items()},
        archive_sha256=backup['receipt']['sha256'], paid_launch_ready=False)
    metadata(document, reporting._manifest(value), value['sources'])
    if any(mac.directories(REPO / n, private=True) != identity
            or {p.name for p in (REPO / n).iterdir()} != expected[n] for n, identity in folders.items()):
        raise ValueError('Terminus retained directory identity or inventory changed')
    if any(mac.raw(REPO, n, private=n.startswith('.runtime/')) != saved for n, saved in records.items()):
        raise ValueError('Terminus retained metadata or publication was replaced')
    if mac.identity((REPO / reporting.BACKUP / 'evidence.tar.gz').lstat()) != archive_identity:
        raise ValueError('The SAME retained Terminus archive was replaced')
    return dict(document=document, data=data, backup=backup, records=records, folders=folders,
        archive_identity=archive_identity)


def prepare(commit):
    """Actual retained state only; every send still needs its own fresh capture."""
    if Path(__file__).absolute() != REPO / 'stage2/matched_repeat_terminus_predecessor.py':
        raise ValueError('Fixed Mac completed-Terminus successor reader required')
    value, files = connection.prepare(commit, HARNESS)
    result = dict(value=value, files=files, retained=_retained(value))
    current(result)
    return result


def current(value):
    connection._current(value['value'])
    if _retained(value['value']) != value['retained']:
        raise ValueError('Terminus archive/export/source identity changed; no saved successor admission')
    connection._current(value['value'])


def capture(commit):
    """Execute the genuine native Terminus audit on EVERY actual capture."""
    value = prepare(commit)
    fresh, observed, identities = reporting._capture(commit, 'audit')
    reporting._current(observed, identities)
    reporting.report.validate(fresh, reporting._manifest(value['value']), value['value']['sources'])
    reporting._equal_audit(value['retained']['data'], fresh)
    current(value)
    document = dict(value['retained']['document'], fresh_audit=deepcopy(fresh))
    metadata(document, reporting._manifest(value['value']), value['value']['sources'])
    return value, deepcopy(document)
