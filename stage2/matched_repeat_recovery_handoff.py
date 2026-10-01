"""Live recovery + unchanged original-final handoff for the first baseline.

The fixed Mac sender actually audits recovery and reads its SAME archive.
The receiver strictly verifies those bytes, observes actual completed recovery
state and rereads all supporting native files. Its witness is process/thread/
task bound, non-admitting, and must remain live under the baseline's locks.
OpenHands additionally needs its completed-Terminus reader and is refused here.
"""
import asyncio
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import threading
import weakref

import matched_repeat_amended_handoff as original
import matched_repeat_execution_bootstrap as bootstrap
import matched_repeat_composite_stream as composite
import matched_repeat_recovery_archive as stream_archive
import matched_repeat_recovery_operator as operator
import matched_repeat_runtime as runtime
import matched_repeat_stream as wire
import no_cutoff_recovery_files as evidence

KIND = 'live_completed_recovery_for_baseline_not_admission'
TRANSFER = 'completed_recovery_then_original_final_archive_v1'
_WITNESSES = weakref.WeakKeyDictionary()


class _Witness:
    __slots__=('__weakref__',)

    def __reduce__(self):
        raise TypeError('Live recovery successor witnesses cannot be saved or copied')


def _task():
    try:return asyncio.current_task()
    except RuntimeError:return None


def send(destination):
    """Fixed real captures, both actual existing archives, no backup writers."""
    wire.pipe_only(destination)
    if Path(__file__).absolute()!=operator.REPO/'stage2/matched_repeat_recovery_handoff.py':
        raise ValueError('Fixed Mac composite recovery sender required')
    commit=original.launch._git('rev-parse','HEAD').decode().strip()
    captured,document=operator.capture(commit)
    header=dict(kind=TRANSFER,schema_version=1,harness='terminus-2',operator=document)
    digest=wire.write_header(destination,header)
    receipt=captured['retained']['backup']['receipt']
    with operator.mac.opened(operator.REPO/operator.BACKUP/'evidence.tar.gz') as (source,_):
        wire.copy_archive(source,destination,receipt['compressed_bytes'],receipt['sha256'])
    operator._current(captured)
    wire.commit(destination,digest,receipt['sha256'])
    # The receiver waits for this sender's actual post-audit first byte before
    # checking ancestor processes. No competing collector is mistaken for a
    # running benchmark; the original sender/reader/archive remain unchanged.
    sent=original.send(operator.REPO,destination,'terminus-2')
    operator._current(captured)
    composite.finish(destination,operator.recovery.policy.fingerprint(document),sent)
    return dict(kind='recovery_and_original_archives_sent_not_admission',
        recovery_document_sha256=operator.recovery.policy.fingerprint(document),
        recovery_archive_sha256=receipt['sha256'],original=sent,paid_launch_ready=False)


def _context(root,harness):
    operator.recovery.policy._hash(bootstrap.RECOVERY_SOURCES_SHA)
    bootstrap.root_for(harness)
    root=Path(root)
    if (root!=runtime.DEPLOYMENTS[harness] or bootstrap.context(harness)!=root
            or Path(__file__).absolute()!=root/'stage2/matched_repeat_recovery_handoff.py'
            or threading.current_thread() is not threading.main_thread() or _task() is None):
        raise ValueError('Own isolated main-thread/current-task baseline service required')
    return root


def _inputs(root,harness):
    from matched_repeat_session import _inputs as actual_inputs
    _,_,files=actual_inputs(root)
    identities=bootstrap.check(harness,files)
    return files,identities


def _metadata(header,harness):
    recovery=operator.recovery; same=recovery.policy._same
    if type(header) is not dict or set(header)!={'kind','schema_version','harness','operator'}:
        raise ValueError('Exact composite recovery header required')
    for name,value in dict(kind=TRANSFER,schema_version=1,harness=harness).items():same(header[name],value)
    document=header['operator']
    expected={'kind','operator_commit','recovery_root','recovery_sources_sha256','fresh_audit',
        'retained','archive_sha256','paid_launch_ready'}
    if type(document) is not dict or set(document)!=expected:
        raise ValueError('Actual fixed recovery capture schema required')
    for name,value in dict(kind=operator.KIND,recovery_root=str(bootstrap.RECOVERY),
            recovery_sources_sha256=bootstrap.RECOVERY_SOURCES_SHA,paid_launch_ready=False).items():same(document[name],value)
    if not isinstance(document['operator_commit'],str) or not bootstrap.re.fullmatch('[a-f0-9]{40}',document['operator_commit']):
        raise ValueError('Full committed composite sender revision required')
    recovery.policy._hash(document['archive_sha256'])
    names={operator.BACKUP+'/'+n for n in ('intent.json','snapshot.json','inventory.json','backup.json')}
    names|={operator.mac_recovery.FAILED_BACKUP+'/'+n for n in operator.mac_recovery.FAILED_FILES}
    names|={recovery.EXPORT+'/'+n for n in ('intent.json','result.json')}
    names|={recovery.PUBLIC+'/'+n for n in recovery.OUTPUTS}
    if type(document['retained']) is not dict or set(document['retained'])!=names:
        raise ValueError('Exact original raw recovery backup/export/public bytes required')
    if any(type(v) is not str for v in document['retained'].values()):
        raise ValueError('Exact UTF-8 recovery metadata required')
    raw={n:v.encode('utf-8') for n,v in document['retained'].items()}
    for name,digest in operator.mac_recovery.FAILED_FILES.items():
        same(hashlib.sha256(raw[operator.mac_recovery.FAILED_BACKUP+'/'+name]).hexdigest(),digest)
    records={n:bootstrap.loads(v) for n,v in raw.items() if n.endswith('.json')}
    data=records[operator.BACKUP+'/snapshot.json'];inventory=records[operator.BACKUP+'/inventory.json']
    backup=records[operator.BACKUP+'/backup.json'];receipt=backup['receipt']
    if set(backup)!={'kind','receipt','verified','snapshot_sha256','inventory_sha256','automatic_resume','paid_launch_ready'}:
        raise ValueError('Exact completed recovery backup record required')
    for name,value in dict(kind='verified_off_server_recovery_backup',automatic_resume=False,paid_launch_ready=False,
            snapshot_sha256=recovery.policy.fingerprint(data),inventory_sha256=recovery.policy.fingerprint(inventory)).items():
        same(backup[name],value)
    same(document['archive_sha256'],receipt['sha256'])
    for name,kind,fields in ((operator.BACKUP+'/intent.json','one_shot_off_server_recovery_backup',
            {'kind','commit','started_utc','automatic_resume','paid_launch_ready'}),
            (recovery.EXPORT+'/intent.json','one_shot_separate_recovery_export',
            {'kind','commit','started_utc','automatic_resume'})):
        intent=records[name]
        if (set(intent)!=fields or intent.get('kind')!=kind or intent.get('automatic_resume') is not False
                or type(intent.get('commit')) is not str or not bootstrap.re.fullmatch('[a-f0-9]{40}',intent['commit'])
                or 'paid_launch_ready' in intent and intent['paid_launch_ready'] is not False):
            raise ValueError('Exact retained one-shot recovery operation intent required')
        original.archive._utc(intent['started_utc'])
    projected=recovery.projection(data,backup)
    public={recovery.PUBLIC+'/'+n:hashlib.sha256(v).hexdigest() for n,v in projected.items()}
    if any(raw[recovery.PUBLIC+'/'+n]!=value for n,value in projected.items()):
        raise ValueError('Recovery publication differs from deterministic separate outcomes')
    same(records[recovery.EXPORT+'/result.json'],dict(kind='separate_recovery_allowlisted_export_complete',
        files=public,snapshot_sha256=recovery.policy.fingerprint(data),archive_sha256=receipt['sha256'],
        automatic_resume=False,paid_launch_ready=False))
    recovery._equal_audit(data,document['fresh_audit'])
    return document,data,inventory,backup


def _backup_producer(document,backup):
    """Read the actual retained native producer, not its off-server receipt."""
    recovery=operator.recovery;root=bootstrap.RECOVERY
    relative=recovery.NATIVE_BACKUP;path=root/relative
    directory=bootstrap.directories(path,private=True)
    if {p.name for p in path.iterdir()}!={'intent.json','result.json'}:
        raise ValueError('Exact completed native recovery backup inventory required')
    records={n:evidence.read(root,relative+'/'+n) for n in ('intent.json','result.json')}
    intent=bootstrap.loads(records['intent.json'][0])
    if set(intent)!={'kind','commit','sources_sha256','automatic_resume','started_utc','paid_launch_ready'}:
        raise ValueError('Actual one-shot recovery backup producer intent required')
    original.archive._utc(intent['started_utc'])
    mac=bootstrap.loads(document['retained'][operator.BACKUP+'/intent.json'].encode())
    recovery.policy._same({n:v for n,v in intent.items() if n!='started_utc'},
        dict(kind='one_shot_separate_recovery_backup',commit=mac['commit'],
            sources_sha256=recovery.policy.fingerprint(bootstrap._recovery_files()),
            automatic_resume=False,paid_launch_ready=False))
    recovery.policy._same(bootstrap.loads(records['result.json'][0]),
        dict(backup['receipt'],automatic_resume=False,paid_launch_ready=False))
    if (bootstrap.directories(path,private=True)!=directory
            or {p.name for p in path.iterdir()}!={'intent.json','result.json'}
            or any(evidence.read(root,relative+'/'+n)!=value for n,value in records.items())):
        raise ValueError('Native recovery backup producer changed while reading')
    return dict(directory=directory,records=records)


def _actual(document,data,inventory,backup):
    """Current fixed native evidence following the genuinely fresh sender audit."""
    recovery=operator.recovery;root=bootstrap.RECOVERY
    bound=bootstrap._recovery_files()
    sources={n[7:]:h for n,h in bound.items() if n.startswith('stage2/')}
    manifest=bootstrap.loads(evidence.read(root,'stage2/input_manifest.json')[0])
    recovery.report.validate(data,manifest,sources)
    recovery.report.validate(document['fresh_audit'],manifest,sources)
    native={n:evidence.read(root,n)[0] for n in data['supporting_files']
        if n in {recovery.report.RT+p for p in (*recovery.archive.qualification_inputs(),recovery.policy.REGISTRATION_FILE)}}
    recovery.archive._anchors(data,native,manifest,sources)
    hashes,identities=evidence.capture(root,data['supporting_files'])
    if hashes!=data['supporting_files']:raise ValueError('Actual recovery evidence differs from transferred fresh audit')
    directory_ids={n:evidence.bootstrap.directories(root/n,private=True) for n in data['directory_entries']}
    state=dict(identities=identities,directory_ids=directory_ids)
    actual_inventory,inventory_state=recovery.archive.inventory(data)
    recovery.policy._same(actual_inventory,inventory)
    producer=_backup_producer(document,backup)
    # These are actual manager/procfs/resource observations, never saved flags.
    bootstrap.recovery_finished()
    for row in data['rows']:
        result=bootstrap.loads(evidence.read(root,recovery.report.RT+'scored-trials/'+row['trial_id']+'/result.json')[0])
        recovery.report.original_report._resources(result['project'])
    recovery.report.reread(root,data,state)
    recovery.archive.recheck(inventory,inventory_state)
    if _backup_producer(document,backup)!=producer:
        raise ValueError('Late native recovery backup producer identity changed')
    if bootstrap._recovery_files()!=bound:raise ValueError('Late frozen recovery source drift')
    return dict(bound=bound,state=state,sources=sources,manifest=manifest,
        inventory=inventory,inventory_state=inventory_state,producer=producer)


def invalidate(witness):
    if type(witness) is _Witness:_WITNESSES.pop(witness,None)


def _live(witness):
    if type(witness) is not _Witness or witness not in _WITNESSES:
        raise ValueError('Actual live recovery successor witness required')
    state=_WITNESSES[witness]
    if (state['pid']!=os.getpid() or state['thread']!=threading.get_ident() or state['task'] is not _task()
            or state['task'] is None or threading.current_thread() is not threading.main_thread()):
        invalidate(witness);raise ValueError('Recovery successor witness cannot cross lifetime, process, thread or task')
    return state


def recheck(witness):
    state=_live(witness)
    try:
        _context(state['root'],state['harness'])
        bootstrap.check(state['harness'],state['files'],state['identities'])
        # Actual under-lock bytes, inventories and absences; never a collector,
        # archive transfer, recursive ancestor lock or saved audit substitute.
        operator.recovery.report.reread(bootstrap.RECOVERY,state['data'],state['native']['state'])
        operator.recovery.archive.recheck(state['native']['inventory'],state['native']['inventory_state'])
        if _backup_producer(state['document'],state['backup'])!=state['native']['producer']:
            raise ValueError('Native recovery backup evidence changed under baseline locks')
        if bootstrap._recovery_files()!=state['native']['bound']:
            raise ValueError('Frozen recovery source changed under baseline locks')
        return deepcopy(state['record'])
    except BaseException:
        invalidate(witness);raise


def authenticate(root,harness,stream):
    if harness != 'terminus-2':
        raise ValueError('OpenHands must consume the real outer completed-Terminus handoff')
    return _authenticate(root,harness,stream)


def _authenticate(root,harness,stream,*,terminus_sha256=None):
    if (harness == 'openhands') != (terminus_sha256 is not None):
        raise ValueError('Exact separate completed-Terminus composite frame required')
    root=_context(root,harness);wire.pipe_only(stream)
    files,identities=_inputs(root,harness)
    header,digest=wire.read_header(stream)
    document,data,inventory,backup=_metadata(header,harness)
    # No native ancestor observation until both real sender audits have ended.
    sources=data['sources'];manifest=bootstrap.loads(evidence.read(bootstrap.RECOVERY,'stage2/input_manifest.json')[0])
    verified=stream_archive.verify_stream(stream,data,inventory,backup['receipt'],manifest,sources)
    operator.recovery.policy._same(verified,backup['verified'])
    if wire._exact(stream,len(wire.COMMIT)+64)!=wire.COMMIT+digest+bytes.fromhex(backup['receipt']['sha256']):
        raise ValueError('Missing final recovery archive sender commitment')
    digest_document=operator.recovery.policy.fingerprint(document)
    original_stream=(composite.original_frame(stream,digest_document) if terminus_sha256 is None else
        composite.original_frame(stream,digest_document,terminus_sha256=terminus_sha256))
    native=_actual(document,data,inventory,backup)
    bootstrap.check(harness,files,identities)
    record=dict(kind=KIND,harness=harness,operator_commit=document['operator_commit'],
        recovery_document_sha256=operator.recovery.policy.fingerprint(document),
        archive_sha256=backup['receipt']['sha256'],sources_sha256=bootstrap.RECOVERY_SOURCES_SHA,
        recovery_result_files={r['trial_id']:r['result_sha256'] for r in data['rows']},
        paid_launch_ready=False,full_runtime_restore_exercised=False)
    witness=_Witness()
    _WITNESSES[witness]=dict(root=root,harness=harness,pid=os.getpid(),thread=threading.get_ident(),
        task=_task(),files=files,identities=identities,document=document,data=data,backup=backup,native=native,record=record)
    try:recheck(witness)
    except BaseException:invalidate(witness);raise
    return witness,original_stream
