"""Separately bound REPORTING-ONLY recovery after the terminal R5 producer.

The frozen R6 modules are imported from their real unchanged installation.
This new entry and its transport are independently hash-bound inline sources,
not substituted modules, a saved session, a task rerun, or a repair of R5.
"""
import base64
import hashlib
import re

SOURCE_NAMES = ('no_cutoff_recovery_reporting_repair.py',
    'no_cutoff_recovery_reporting_transport.py')
NATIVE_BACKUP = '.runtime/stage2/no-cutoff-recovery-reporting-backup-20261002'
FAILED_NATIVE = '.runtime/stage2/no-cutoff-recovery-completed-backup'
FAILED_NATIVE_FILES = {
    'intent.json': '0ec26cc18bc4c785d056c84f301f26be46e43d57fbfdf19f8e8583409ce428a6',
    'result.json': '523d83e470b6aabec86eb23246dd6be9701ce34b56a67650999e650ca738c33c',
    'failure.json': '3b0ef025906283b77084e20ca256f15c5c68287de1f035173e639d83a66a8ff0',
}


def _sources(value):
    if (type(value) is not dict or set(value) != set(SOURCE_NAMES)
            or any(type(h) is not str or not re.fullmatch('[a-f0-9]{64}', h) for h in value.values())):
        raise ValueError('Exact independently bound reporting-only sources required')
    return dict(value)


def ready(files, commit, mode, sources):
    import no_cutoff_recovery_reporting as frozen
    return dict(frozen._ready(files, commit, mode),
        reporting_only_procedure='separate_reporting_recovery_20261002',
        reporting_sources_sha256=frozen.policy.fingerprint(_sources(sources)),
        native_producer=NATIVE_BACKUP)


def preserved_native():
    """The actual failed native producer remains exact, including its failure."""
    import no_cutoff_recovery_bootstrap as boot
    path = boot.ROOT / FAILED_NATIVE
    directory = boot.directories(path, private=True)
    if {p.name for p in path.iterdir()} != set(FAILED_NATIVE_FILES):
        raise ValueError('Exact terminal R5 native producer required')
    records = {n: boot.raw(boot.ROOT, FAILED_NATIVE+'/'+n, h) for n, h in FAILED_NATIVE_FILES.items()}
    if (boot.loads(records['failure.json'][0]) != dict(
            status='failed_or_uncertain_preserve_evidence', automatic_resume=False, paid_launch_ready=False)
            or boot.directories(path, private=True) != directory
            or {p.name for p in path.iterdir()} != set(records)
            or any(boot.raw(boot.ROOT, FAILED_NATIVE+'/'+n, FAILED_NATIVE_FILES[n]) != item
                for n, item in records.items())):
        raise ValueError('Terminal R5 native producer changed')
    return dict(directory=directory, records=records)


def intent_fields(files, commit, sources):
    import no_cutoff_recovery_policy as policy
    if type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Full reporting-only operator commit required')
    return dict(kind='one_shot_reporting_only_recovery_backup', commit=commit,
        sources_sha256=policy.fingerprint(files), reporting_sources=_sources(sources),
        preserved_native_failure_files=dict(FAILED_NATIVE_FILES),
        automatic_resume=False, paid_launch_ready=False)


def retained_native(files, commit, sources, receipt):
    """Actual new producer plus exact old failure; never old receipt admission."""
    import no_cutoff_recovery_reporting as frozen
    boot = frozen.boot
    preserved = preserved_native()
    path = boot.ROOT / NATIVE_BACKUP
    directory = boot.directories(path, private=True)
    if {p.name for p in path.iterdir()} != {'intent.json', 'result.json'}:
        raise ValueError('Exact successful new reporting-only producer required')
    records = {n: boot.raw(boot.ROOT, NATIVE_BACKUP+'/'+n) for n in ('intent.json', 'result.json')}
    intent = boot.loads(records['intent.json'][0])
    expected = intent_fields(files, commit, sources)
    if set(intent) != set(expected) | {'started_utc'}:
        raise ValueError('Exact reporting-only producer intent required')
    frozen.handoff.archive._utc(intent['started_utc'])
    frozen.policy._same({n: v for n, v in intent.items() if n != 'started_utc'}, expected)
    frozen.policy._same(boot.loads(records['result.json'][0]),
        dict(receipt, automatic_resume=False, paid_launch_ready=False))
    if (boot.directories(path, private=True) != directory
            or {p.name for p in path.iterdir()} != set(records)
            or any(boot.raw(boot.ROOT, NATIVE_BACKUP+'/'+n) != item for n, item in records.items())
            or preserved_native() != preserved):
        raise ValueError('Reporting-only producer or preserved failure changed')
    return dict(directory=directory, records=records, preserved=preserved)


def program(files, commit, mode, sources):
    """Build only these exact committed entry bytes and the real frozen boot."""
    import no_cutoff_recovery_reporting as frozen
    _sources(sources)
    if mode == 'inspect':
        if type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
            raise ValueError('Full reporting-only inspection commit required')
    else:
        ready(files, commit, mode, sources)
    raw = {n: frozen.handoff.launch._raw('stage2/'+n, sources[n]) for n in SOURCE_NAMES}
    bootstrap = frozen.handoff.launch._raw('stage2/no_cutoff_recovery_bootstrap.py',
        files['stage2/no_cutoff_recovery_bootstrap.py'])
    # Two explicit non-import namespaces are bound independently. No frozen
    # sys.modules entry is removed, hidden, redirected or given different bytes.
    # Synthetic filenames identify inline code, not an invented native file.
    return ('import base64,hashlib,sys,types\n'
        + 'sources='+repr(sources)+'\n'
        + 'payloads='+repr({n: base64.b64encode(v).decode() for n, v in raw.items()})+'\n'
        + 'payloads={n:base64.b64decode(v) for n,v in payloads.items()}\n'
        + 'assert all(hashlib.sha256(v).hexdigest()==sources[n] for n,v in payloads.items())\n'
        + 'b=types.ModuleType("no_cutoff_recovery_bootstrap")\n'
        + 'b.__file__='+repr(str(frozen.boot.ROOT/'stage2/no_cutoff_recovery_bootstrap.py'))+'\n'
        + 'sys.modules[b.__name__]=b\n'
        + 'exec(compile(base64.b64decode('+repr(base64.b64encode(bootstrap).decode())+'),b.__file__,"exec"),b.__dict__)\n'
        + 'w={"__name__":"source_bound_reporting_transport"}\n'
        + 'r={"__name__":"source_bound_reporting_recovery"}\n'
        + 'exec(compile(payloads['+repr(SOURCE_NAMES[1])+'],"<reporting-transport:"+sources['+repr(SOURCE_NAMES[1])+']+">","exec"),w)\n'
        + 'exec(compile(payloads['+repr(SOURCE_NAMES[0])+'],"<reporting-recovery:"+sources['+repr(SOURCE_NAMES[0])+']+">","exec"),r)\n'
        + 'r["WIRE"]=types.SimpleNamespace(**w)\n'
        + 'try:\n r["entry"]('+','.join(map(repr, (files, commit, mode, sources)))+',payloads)\n'
        + 'except BaseException:\n raise SystemExit("Reporting-only recovery failed; preserve all evidence") from None\n')


def entry(files, commit, mode, sources, payloads):
    """Independent entry checks plus the unchanged genuine native bootstrap."""
    import os
    import sys
    import no_cutoff_recovery_bootstrap as boot
    _sources(sources)
    if (mode not in ('audit', 'backup', 'inspect') or set(payloads) != set(sources)
            or any(hashlib.sha256(v).hexdigest() != sources[n] for n, v in payloads.items())
            or entry.__code__.co_filename != '<reporting-recovery:'+sources[SOURCE_NAMES[0]]+'>'):
        raise ValueError('Exact source-bound inline reporting procedure required')
    sys.pycache_prefix = str(boot.ROOT / '.absent-bytecode-cache')
    identities = boot.check(files)
    boot.ancestors(files); boot.check(files, identities)
    os.chdir(boot.ROOT); sys.path.insert(0, str(boot.ROOT/'stage2'))
    boot.IMPORTING = True
    sys.addaudithook(boot.no_effects)
    try:
        import asyncio
        import no_cutoff_recovery_reporting as frozen
    finally:
        boot.IMPORTING = False
    if boot.VIOLATION:
        raise ValueError('Reporting import side effect refused')
    boot.ancestors(files); boot.check(files, identities); frozen.service.loaded(files)
    if mode == 'inspect':
        import json
        print(json.dumps(inspect_native(files, commit, sources, identities),sort_keys=True),flush=True)
        return
    asyncio.run(native(files, commit, mode, sources, payloads))


def no_other_processes():
    """Read-only actual root occupancy; the owning observer alone is excluded."""
    import os
    from pathlib import Path
    import no_cutoff_recovery_bootstrap as boot
    roots = (str(boot.ROOT), str(boot.ORIGINAL))
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid(): continue
        try:
            cwd = os.readlink(path/'cwd')
            if any(cwd == root or cwd.startswith(root+'/') for root in roots):
                raise ValueError('Another recovery/original-root process is present')
        except (FileNotFoundError, ProcessLookupError): pass


def inspect_native(files, commit, sources, identities):
    """Actual startup/completion/preservation only: no session or archive call."""
    import no_cutoff_recovery_reporting as frozen
    no_other_processes()
    preserved = preserved_native()
    path = frozen.boot.ROOT/NATIVE_BACKUP
    frozen.boot.directories(path.parent,private=True)
    if path.exists() or path.is_symlink(): raise ValueError('New reporting producer already exists')
    status = frozen.service.operation_status(files,commit,identities,'run-recovery')
    if (status['status'] != 'service_exited_successfully_not_completed_study_audit'
            or status['counts']['completed'] != 3 or status['counts']['active_tasks']):
        raise ValueError('Actual completed recovery service required')
    frozen.boot.check(files,identities); frozen.service.loaded(files)
    no_other_processes()
    if preserved_native()!=preserved or path.exists() or path.is_symlink():
        raise ValueError('Preservation or new producer absence changed')
    return dict(kind='read_only_reporting_recovery_inspection_not_admission',
        counts=status['counts'],observed_utc=status['observed_utc'],native_bindings=len(files),
        reporting_sources=_sources(sources),preserved_native_failure_files=dict(FAILED_NATIVE_FILES),
        new_producer_absent=True,relevant_processes=[],archive_read=False,collector=False,
        write=False,paid_launch_ready=False)


async def native(files, commit, mode, sources, payloads):
    """Fresh real audit/session, flushed stream, then post-session commitment."""
    from contextlib import redirect_stdout
    from datetime import datetime, timezone
    import struct
    import sys
    import no_cutoff_recovery_reporting as frozen
    boot, report, archive, service = frozen.boot, frozen.report, frozen.archive, frozen.service
    identities = boot.check(files); service.loaded(files)
    no_other_processes()
    preserved = preserved_native()
    path = boot.ROOT / NATIVE_BACKUP
    old = None
    if mode == 'backup':
        if path.exists() or path.is_symlink():
            raise ValueError('Reporting-only backup is one-use, including partial state')
    else:
        # An audit/export cannot borrow R5's failed result. Read the actual new
        # producer now, then recheck these same identities on normal exit.
        raw_intent = boot.loads(boot.raw(boot.ROOT, NATIVE_BACKUP+'/intent.json')[0])
        raw_result = boot.loads(boot.raw(boot.ROOT, NATIVE_BACKUP+'/result.json')[0])
        saved_receipt = {n: v for n, v in raw_result.items() if n not in ('automatic_resume', 'paid_launch_ready')}
        old = retained_native(files, raw_intent['commit'], sources, saved_receipt)
    incoming, raw_output = sys.stdin.buffer, sys.__stdout__.buffer
    frozen.handoff.wire.pipe_only(incoming)
    raw_output.write(service._line(ready(files, commit, mode, sources))); raw_output.flush()
    output = WIRE.Writer(raw_output).start()
    created = False; stage = 'handoff'
    try:
        with redirect_stdout(sys.stderr), frozen.session.open_session(incoming) as active:
            live = frozen.session._live(active)
            frozen.policy._same(frozen.handoff._live(live['witness'])['header']['operator']['operator_commit'], commit)
            stage = 'preservation'
            if preserved_native() != preserved:
                raise ValueError('R5 producer changed during original handoff')
            if mode == 'backup':
                path.mkdir(mode=0o700); service._sync(path.parent); created = True
                directory = boot.directories(path, private=True)
                frozen.evidence.save(path/'intent.json', dict(intent_fields(files, commit, sources),
                    started_utc=datetime.now(timezone.utc).isoformat()))
                intent = boot.raw(boot.ROOT, NATIVE_BACKUP+'/intent.json')
            stage = 'audit'
            data, state = report.collect(active)
            manifest = boot.loads(boot.raw(boot.ROOT, 'stage2/input_manifest.json', frozen.policy.INPUT_SHA256)[0])
            report.validate(data, manifest, live['inputs']['sources'])
            if mode == 'backup':
                stage = 'inventory'
                inventory, inventory_state = archive.inventory(data)
                archive.framing._write(output, archive.MAGIC)
                archive.framing._metadata(output, dict(snapshot=data, inventory=inventory))
                stage = 'archive'
                receipt = archive.pack(output, inventory, inventory_state)
                output.flush()  # Includes the real gzip trailer, never reconstructs it.
                stage = 'audit_recheck'
                actual, _ = report.collect(active); frozen._equal_audit(data, actual)
                archive.recheck(inventory, inventory_state); report.reread(boot.ROOT, data, state)
            stage = 'session_exit'
        # No result record exists until the REAL session has exited normally.
        stage = 'final_recheck'
        boot.check(files, identities); service.loaded(files); report.reread(boot.ROOT, data, state)
        if (preserved_native() != preserved or any(hashlib.sha256(v).hexdigest() != sources[n]
                for n, v in payloads.items())):
            raise ValueError('Late reporting source or failed-producer drift')
        if mode == 'backup':
            archive.recheck(inventory, inventory_state)
            if (boot.directories(path, private=True) != directory
                    or boot.raw(boot.ROOT, NATIVE_BACKUP+'/intent.json') != intent
                    or {p.name for p in path.iterdir()} != {'intent.json'}):
                raise ValueError('New reporting operation evidence changed')
            stage = 'commitment'
            frozen.evidence.save(path/'result.json', dict(receipt, automatic_resume=False, paid_launch_ready=False))
            retained_native(files, commit, sources, receipt)
            archive.framing._write(output, struct.pack('!Q', 0))
            archive.framing._metadata(output, receipt)
        else:
            if retained_native(files, raw_intent['commit'], sources, saved_receipt) != old:
                raise ValueError('Verified native reporting producer changed during audit')
            archive.framing._write(output, frozen.AUDIT_MAGIC)
            archive.framing._metadata(output, data)
        archive.framing._write(output, archive.END)
        output.finish()  # Liveness alone can NEVER emit this normal-exit marker.
    except BaseException as error:
        item = WIRE.diagnostic(stage, error)
        if created:
            frozen.evidence.save(path/'failure.json', dict(status='failed_or_uncertain_preserve_evidence',
                diagnostic=item, automatic_resume=False, paid_launch_ready=False))
        try: output.fail(item)
        except BaseException: pass  # Preserve the original error and durable failure.
        raise
    finally:
        output.close_heartbeat()
