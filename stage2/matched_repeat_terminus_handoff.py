"""Actual completed-Terminus + recovery + original archive handoff for OpenHands.

All three real sender audits end before receiver ancestor observations. Exact
original EOF is exposed only after the final commitment binding all three
documents and actual transport EOF. Native witnesses are non-admitting and
process/main-thread/task-bound; the genuine locked session must consume them.
"""
from copy import deepcopy
import os
from pathlib import Path
import threading
import weakref

import matched_repeat_terminus_predecessor as operator
import matched_repeat_recovery_handoff as recovery
import matched_repeat_archive as archive
import matched_repeat_execution_bootstrap as boot
import matched_repeat_policy as policy
import no_cutoff_recovery_files as evidence

KIND = 'live_completed_terminus_for_openhands_not_admission'
TRANSFER = 'completed_terminus_then_recovery_then_original_v1'
ROOT = boot.root_for('terminus-2')
_WITNESSES = weakref.WeakKeyDictionary()


class _Witness:
    __slots__ = ('__weakref__',)

    def __reduce__(self):
        raise TypeError('Live completed-Terminus witnesses cannot be copied or saved')


def send(destination):
    """Three genuine fresh captures, SAME archives, no caller evidence input."""
    wire = recovery.wire; wire.pipe_only(destination)
    if Path(__file__).absolute() != operator.REPO/'stage2/matched_repeat_terminus_handoff.py':
        raise ValueError('Fixed Mac OpenHands composite sender required')
    commit = recovery.original.launch._git('rev-parse', 'HEAD').decode().strip()
    captured, document = operator.capture(commit)
    header = dict(kind=TRANSFER, schema_version=1, harness='openhands', operator=document)
    digest = wire.write_header(destination, header); receipt = captured['retained']['backup']['receipt']
    with operator.mac.opened(operator.REPO/operator.reporting.BACKUP/'evidence.tar.gz') as (source, _):
        wire.copy_archive(source, destination, receipt['compressed_bytes'], receipt['sha256'])
    operator.current(captured); wire.commit(destination, digest, receipt['sha256'])
    recovered, recovery_document = recovery.operator.capture(commit)
    digest = wire.write_header(destination, dict(kind=recovery.TRANSFER, schema_version=1,
        harness='openhands', operator=recovery_document))
    recovered_receipt = recovered['retained']['backup']['receipt']
    with operator.mac.opened(operator.REPO/recovery.operator.BACKUP/'evidence.tar.gz') as (source, _):
        wire.copy_archive(source, destination, recovered_receipt['compressed_bytes'], recovered_receipt['sha256'])
    recovery.operator._current(recovered); wire.commit(destination, digest, recovered_receipt['sha256'])
    # This unmodified subframe describes ONLY the original custom-final
    # dependency in its historical wire format. It never represents an
    # OpenHands execution scope. The new receiver has its own real OH context.
    original = recovery.original.send(operator.REPO, destination, 'terminus-2')
    recovery.operator._current(recovered); operator.current(captured)
    recovery.composite.finish(destination, policy.fingerprint(recovery_document), original,
        terminus_sha256=policy.fingerprint(document))
    return dict(kind='three_actual_predecessor_archives_sent_not_admission', original=original,
        recovery_document_sha256=policy.fingerprint(recovery_document),
        recovery_archive_sha256=recovered_receipt['sha256'],
        terminus_document_sha256=policy.fingerprint(document), terminus_archive_sha256=receipt['sha256'],
        paid_launch_ready=False)


def _context(root, harness):
    root = Path(root)
    if (harness != 'openhands' or root != boot.root_for(harness) or boot.context(harness) != root
            or Path(__file__).absolute() != root/'stage2/matched_repeat_terminus_handoff.py'
            or threading.current_thread() is not threading.main_thread() or recovery._task() is None):
        raise ValueError('Own actual OpenHands main-thread async service required')
    return root


def _producer(document, backup, files):
    reporter = operator.reporting; relative = reporter.NATIVE_BACKUP
    directory = boot.directories(ROOT/relative, private=True)
    if {p.name for p in (ROOT/relative).iterdir()} != {'intent.json', 'result.json'}:
        raise ValueError('Actual completed native Terminus backup producer required')
    records = {n: evidence.read(ROOT, relative+'/'+n) for n in ('intent.json','result.json')}
    intent = boot.loads(records['intent.json'][0])
    if set(intent) != {'kind','commit','sources_sha256','automatic_resume','started_utc','paid_launch_ready'}:
        raise ValueError('Exact Terminus native backup intent required')
    recovery.original.archive._utc(intent['started_utc'])
    mac_intent = boot.loads(document['retained'][reporter.BACKUP+'/intent.json'].encode())
    archive.same({n:v for n,v in intent.items() if n != 'started_utc'}, dict(
        kind='one_shot_separate_baseline_backup', commit=mac_intent['commit'],
        sources_sha256=policy.fingerprint(files), automatic_resume=False, paid_launch_ready=False))
    archive.same(boot.loads(records['result.json'][0]), dict(backup['receipt'],
        automatic_resume=False, paid_launch_ready=False))
    if (boot.directories(ROOT/relative, private=True) != directory
            or {p.name for p in (ROOT/relative).iterdir()} != {'intent.json','result.json'}
            or any(evidence.read(ROOT, relative+'/'+n) != v for n,v in records.items())):
        raise ValueError('Native Terminus backup evidence changed')
    return dict(directory=directory, records=records)


def _actual(document, data, inventory, backup, files):
    sources = {n[7:]:h for n,h in files.items() if n.startswith('stage2/')}
    # Both deployments use this committed complete union before either freezes.
    # Future changes cannot be retroactively claimed as Terminus evidence.
    archive.same(data['sources'], sources)
    bound, identities = evidence.capture(ROOT, files)
    archive.same(bound, files)
    actual, state = archive._inventory(ROOT, data); archive.same(actual, inventory)
    producer = _producer(document, backup, files)
    # Source-bound real own-interpreter manager/procfs/producer readers. No
    # second collector or archive transfer occurs here or under later locks.
    completed = boot.terminus_finished(files)
    for row in data['rows']:
        result = boot.loads(evidence.read(ROOT, operator.reporting.report.RT+
            'scored-trials/'+row['trial_id']+'/result.json')[0])
        operator.reporting.report.original_report._resources(result['project'])
    archive.recheck(inventory, state); evidence.check(ROOT, files, identities)
    if _producer(document, backup, files) != producer:
        raise ValueError('Late Terminus backup producer replacement')
    return dict(state=state, identities=identities, producer=producer, completed=completed)


def invalidate(witness):
    if type(witness) is _Witness: _WITNESSES.pop(witness, None)


def _live(witness):
    if type(witness) is not _Witness or witness not in _WITNESSES:
        raise ValueError('Actual live completed-Terminus witness required')
    value = _WITNESSES[witness]
    if (value['pid'] != os.getpid() or value['thread'] != threading.get_ident()
            or value['task'] is None or value['task'] is not recovery._task()
            or threading.current_thread() is not threading.main_thread()):
        invalidate(witness); raise ValueError('Terminus witness cannot cross lifetime, process, thread or task')
    return value


def recheck(witness):
    value = _live(witness)
    try:
        _context(value['root'], 'openhands')
        boot.check('openhands', value['files'], value['identities'])
        evidence.check(ROOT, value['files'], value['native']['identities'])
        archive.recheck(value['inventory'], value['native']['state'])
        if _producer(value['document'], value['backup'], value['files']) != value['native']['producer']:
            raise ValueError('Retained native Terminus backup changed under successor locks')
        return deepcopy(value['record'])
    except BaseException:
        invalidate(witness); raise


def authenticate(root, harness, stream):
    """Consume three framed archives before any outer ancestor locks."""
    root = _context(root, harness); wire = recovery.wire; wire.pipe_only(stream)
    files, identities = recovery._inputs(root, harness)
    header, digest = wire.read_header(stream)
    if type(header) is not dict or set(header) != {'kind','schema_version','harness','operator'}:
        raise ValueError('Exact completed-Terminus transfer header required')
    for key,value in dict(kind=TRANSFER,schema_version=1,harness='openhands').items(): archive.same(header[key],value)
    document = header['operator']; sources = {n[7:]:h for n,h in files.items() if n.startswith('stage2/')}
    manifest = boot.loads(evidence.read(root, 'stage2/input_manifest.json')[0])
    data, inventory, backup = operator.metadata(document, manifest, sources)
    verified = archive.verify_stream(stream, data, inventory, backup['receipt'], manifest, sources)
    archive.same(verified, backup['verified'])
    trailer = wire.COMMIT + digest + bytes.fromhex(backup['receipt']['sha256'])
    if wire._exact(stream,len(trailer)) != trailer:
        raise ValueError('Exact completed-Terminus archive commitment required')
    recovered = witness = None
    try:
        # This waits for the actual ORIGINAL post-audit header before either
        # native predecessor's manager/resource observations. The original
        # reader subsequently enforces the final THREE-document commit + EOF.
        recovered, original_stream = recovery._authenticate(root, harness, stream,
            terminus_sha256=policy.fingerprint(document))
        native = _actual(document, data, inventory, backup, files)
        boot.check(harness, files, identities)
        record = dict(kind=KIND, harness=harness, operator_commit=document['operator_commit'],
            terminus_document_sha256=policy.fingerprint(document), archive_sha256=backup['receipt']['sha256'],
            sources_sha256=policy.fingerprint(sources), block=operator.block(document,manifest,sources),
            paid_launch_ready=False, full_runtime_restore_exercised=False)
        if recovery.recheck(recovered)['operator_commit'] != document['operator_commit']:
            raise ValueError('All actual successor captures require the same committed revision')
        witness = _Witness(); _WITNESSES[witness] = dict(root=root,pid=os.getpid(),thread=threading.get_ident(),
            task=recovery._task(), files=files,identities=identities,document=document,data=data,
            inventory=inventory,backup=backup,native=native,record=record,manifest=manifest)
        recheck(witness)
        return witness, recovered, original_stream
    except BaseException:
        invalidate(witness); recovery.invalidate(recovered); raise
