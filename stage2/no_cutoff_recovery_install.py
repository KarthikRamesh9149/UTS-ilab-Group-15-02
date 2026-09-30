"""Exclusive fixed recovery installation; no qualification or task execution.

The native entry is standard-library only and receives the complete committed
source payload over pinned SSH. It copies current protected runtime bytes on
the same host, without downloading, changing old roots or reading an archive.
Every partial target is terminal. Neither installation nor inspection is paid
admission; real fresh audit/archive authentication remains in each live session.
"""
import ast
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import subprocess
import sys
import types

ROOT = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260929')
ORIGINAL = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
REPORTER = Path('/opt/uts-capstone-custom-no-cutoff-final-reporting-20260929-r4')
QUALIFICATION = '.runtime/stage2/no-cutoff-recovery-original-qualification.json'
ORIGINAL_QUALIFICATION = '.runtime/stage2/no-cutoff-final-qualification.json'
QUALIFICATION_SHA = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
MANIFEST = '.runtime/stage2/no-cutoff-recovery-manifest.json'
STATE = '.runtime/netcup/custom-no-cutoff-recovery-installation-20260929'
KIND = 'exclusive_recovery_installation_not_qualification'
WINDOW = 64 * 1024 * 1024
EARLY = ('uts-capstone', 'uts-capstone-baseline-repeat-20260921', 'uts-capstone-credit-only-20260922',
    'uts-capstone-corrected-20260923', 'uts-capstone-timeout-diagnostic-20260925',
    'uts-capstone-custom-development-20260926', 'uts-capstone-custom-portable-20260926',
    'uts-capstone-custom-deadline-20260927')
LATE = ('uts-capstone-custom-deadline-20260927-r2', 'uts-capstone-custom-no-cutoff-20260928',
    'uts-capstone-custom-no-cutoff-final-20260928')


def _sha(value): return hashlib.sha256(value).hexdigest()


def _json(value): return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _parts(name):
    if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or name.startswith('/') or any(n in ('', '.', '..') for n in name.split('/'))):
        raise ValueError('Exact installation relative path required')
    return name


def _module(name, raw):
    module = types.ModuleType(name)
    exec(compile(raw, '<committed-' + name + '>', 'exec'), module.__dict__)
    return module


def _payload(value):
    if (type(value) is not dict or set(value) != {'kind','commit','files','hashes','native','reporter'}
            or value['kind'] != KIND or type(value['commit']) is not str
            or not re.fullmatch('[a-f0-9]{40}', value['commit'])):
        raise ValueError('Fixed complete committed installation payload required')
    decoded = {}
    for key in ('hashes', 'native', 'reporter'):
        if type(value[key]) is not dict or not value[key]: raise ValueError('Complete installation bindings required')
        for name, sha in value[key].items():
            _parts(name)
            if type(sha) is not str or not re.fullmatch('[a-f0-9]{64}', sha): raise ValueError('Exact digest required')
    if type(value['files']) is not dict or set(value['files']) != set(value['hashes']):
        raise ValueError('Missing installation source/input bytes')
    for name, encoded in value['files'].items():
        if type(encoded) is not str: raise ValueError('Exact source bytes required')
        decoded[name] = base64.b64decode(encoded, validate=True)
        if _sha(decoded[name]) != value['hashes'][name]: raise ValueError('Installation payload bytes changed')
    bootstrap = _module('no_cutoff_recovery_bootstrap', decoded['stage2/no_cutoff_recovery_bootstrap.py'])
    if (bootstrap.ROOT != ROOT or bootstrap.ORIGINAL != ORIGINAL or bootstrap.QUALIFICATION != QUALIFICATION
            or bootstrap.QUALIFICATION_SHA != QUALIFICATION_SHA
            or value['hashes'].get(QUALIFICATION) != QUALIFICATION_SHA):
        raise ValueError('Original/current native roots and exact original qualification required')
    final = bootstrap.loads(decoded[QUALIFICATION])
    nodes = [n.value for n in ast.parse(decoded['stage2/no_cutoff_recovery_policy.py']).body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REQUIRED_SOURCE_FILES' for t in n.targets)]
    if (len(nodes) != 1 or not isinstance(nodes[0], ast.Call) or not isinstance(nodes[0].func, ast.Name)
            or nodes[0].func.id != 'frozenset' or len(nodes[0].args) != 1 or nodes[0].keywords):
        raise ValueError('Bound complete recovery inventory required')
    names = set(final['sources']) | ast.literal_eval(nodes[0].args[0])
    if not {'stage2/' + n for n in names} <= set(decoded): raise ValueError('Incomplete original/current inventory')
    if (decoded[MANIFEST] != decoded['stage2/input_manifest.json']
            or final['sources'].get('input_manifest.json') != value['hashes']['stage2/input_manifest.json']):
        raise ValueError('Exact raw original manifest required')
    # Seven public original outputs/anchors are required by the live handoff.
    public = 'stage2/results/custom-no-cutoff-final-20260928/'
    extra = {public + n for n in ('qualification.json','registration-c0-nc.json','lineage.json',
        'credit-policy.json','c0-nc/summary.json','c0-nc/trials.json','c0-nc/trials.csv')}
    if set(decoded) != {'stage2/' + n for n in names} | extra | {QUALIFICATION, MANIFEST}:
        raise ValueError('Unexpected installation payload or missing original publication')
    required_native = {'stage2/'+n:h for n,h in final['sources'].items()}
    required_native.update(final['evidence_files']); required_native[ORIGINAL_QUALIFICATION] = QUALIFICATION_SHA
    if any(value['native'].get(n) != h for n,h in required_native.items()):
        raise ValueError('Complete actual original source and producer inventory required')
    libraries = _module('no_cutoff_recovery_libraries', decoded['stage2/no_cutoff_recovery_libraries.py'])
    guard = _module('no_cutoff_final_guard', decoded['stage2/no_cutoff_final_guard.py'])
    if libraries.ORIGINAL != ORIGINAL or libraries.RECOVERY != ROOT or guard.ROOT != ORIGINAL:
        raise ValueError('Fixed native readers required')
    return decoded, final, bootstrap, libraries, guard


def _environment():
    return dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8',
        PYTHON_DOTENV_DISABLED='1', LITELLM_MODE='PRODUCTION', LITELLM_LOCAL_MODEL_COST_MAP='True')


def _context():
    if (platform.system() != 'Linux' or os.getuid() != 0 or os.getgid() != 0
            or not sys.flags.isolated or not sys.dont_write_bytecode
            or Path(sys.prefix).resolve() != ORIGINAL / '.venv'
            or Path(sys.executable).absolute() != ORIGINAL / '.venv/bin/python'
            or dict(os.environ) != _environment()):
        raise ValueError('Fixed original isolated stdlib-only installer required')


def _quiet(guard):
    guard.service()
    for base in (ORIGINAL, Path('/opt/uts-capstone-corrected-20260923')):
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            path = base / '.runtime/stage2' / name
            if path.exists() or path.is_symlink(): raise ValueError('Persistent native stop forbids installation')
    units = subprocess.check_output(['systemctl','list-units','--type=service','--state=active,activating',
        '--no-legend','--plain','uts-*'], text=True, timeout=15)
    if units.strip(): raise ValueError('Active native study operation forbids installation')
    for args in (('ps','-aq'),('network','ls','-q'),('volume','ls','-q')):
        if subprocess.check_output(['docker',*args,'--filter','name=uts-scored-'],
                env=dict(_environment(), DOCKER_HOST='unix:///var/run/docker.sock', DOCKER_CONFIG='/dev/null'),
                text=True,timeout=15).strip():
            raise ValueError('Owned native resources require inspection')
    roots = [str(Path('/opt') / n) for n in (*EARLY, *LATE)] + [str(ROOT), str(REPORTER)]
    for process in Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid(): continue
        try:
            cwd = os.readlink(process / 'cwd')
            command = (process / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError): continue
        # The enclosing SSH shell may contain a fixed root argument but is not
        # a project interpreter. Inspect actual cwd and executable arguments.
        if any(cwd == r or cwd.startswith(r + '/') for r in roots):
            raise ValueError('Native process remains in an execution/reporting root')
        if any(any(a.startswith((r+'/.venv/bin/').encode()) for r in roots) for a in command):
            raise ValueError('Native project interpreter already active')


def _old(value, bootstrap, libraries, guard):
    _context(); _quiet(guard)
    bootstrap.directories(ROOT.parent)
    if ROOT.exists() or ROOT.is_symlink(): raise ValueError('Existing or partial recovery root is terminal')
    bootstrap.raw(ORIGINAL, ORIGINAL_QUALIFICATION, QUALIFICATION_SHA)
    result = {}
    for base, bindings in ((ORIGINAL,value['native']),(REPORTER,value['reporter'])):
        for name, sha in bindings.items():
            libraries.read(base,name,sha); result[(str(base),name)] = libraries.identity((base/name).lstat())
    if value['native'].get(ORIGINAL_QUALIFICATION) != QUALIFICATION_SHA:
        raise ValueError('Actual original qualification must be independently reread')
    return result


def _reread(value, identities, libraries):
    for base, bindings in ((ORIGINAL,value['native']),(REPORTER,value['reporter'])):
        for name, sha in bindings.items():
            libraries.read(base,name,sha)
            if libraries.identity((base/name).lstat()) != identities[(str(base),name)]:
                raise ValueError('Original native/reporting file identity replaced')


@contextmanager
def _locked(bootstrap):
    handles = []; observations = []
    try:
        for root in (*EARLY, *LATE):
            for name in ('matrix.lock','scored.lock','gateway.lock'):
                path = ROOT.parent / root / '.runtime/stage2' / name
                parents = bootstrap.directories(path.parent,private=True)
                fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                handles.append(fd); info = os.fstat(fd); bootstrap.acl(path)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_gid != os.getgid()
                        or stat.S_IMODE(info.st_mode) != 0o600): raise ValueError('Private existing lock required')
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                observations.append((path,fd,bootstrap.identity(info),parents))
        def check():
            for path,fd,identity,parents in observations:
                if (bootstrap.identity(os.fstat(fd)) != identity or bootstrap.identity(path.lstat()) != identity
                        or bootstrap.directories(path.parent,private=True) != parents):
                    raise ValueError('Installation ancestor lock changed')
                second = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                try:
                    try: fcntl.flock(second,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    except BlockingIOError: pass
                    else: raise ValueError('Installation ancestor lock no longer held')
                finally: os.close(second)
        check(); yield check; check()
    finally:
        for fd in reversed(handles): os.close(fd)


def _tree(base, relative, libraries, *, python_links=False):
    """Hash actual current files; inspect no task payload or secret text."""
    folder = base / _parts(relative)
    libraries.protected(base,relative+'/unused-selector')
    files = {}; links = {}; directories = []
    for current, children, names in os.walk(folder,followlinks=False):
        current = Path(current); directories.append(current.relative_to(base).as_posix())
        libraries.protected(base,current.relative_to(base).as_posix()+'/unused-selector')
        for name in children + names:
            path = current/name
            if not path.is_symlink(): continue
            relative_name = path.relative_to(base).as_posix()
            if not python_links: raise ValueError('Symlink in installation input tree')
            info = path.lstat(); libraries.acl(path)
            if info.st_uid != os.getuid() or info.st_gid != os.getgid() or info.st_nlink != 1:
                raise ValueError('Unowned interpreter link')
            if relative_name == '.venv/lib64' and os.readlink(path) == 'lib': target = 'lib'
            elif (relative_name.startswith('.venv/bin/python')
                    and re.fullmatch(r'python(?:3(?:\.12)?)?',path.name)
                    and path.resolve() == Path(sys.executable).resolve()):
                target = os.readlink(path)
                if Path(target).is_absolute() and Path(target).is_relative_to(base):
                    target = str(ROOT / Path(target).relative_to(base))
            else: raise ValueError('Only fixed interpreter aliases may be linked')
            links[relative_name] = dict(target=target,original=os.readlink(path),identity=libraries.identity(info))
        children[:] = sorted(n for n in children if n != '__pycache__' and not (current/n).is_symlink())
        for name in sorted(names):
            path = current/name
            if path.is_symlink() or name.endswith(('.pyc','.pyo')): continue
            relative_name = path.relative_to(base).as_posix()
            digest = libraries.read(base,relative_name)
            files[relative_name] = dict(sha256=digest,identity=libraries.identity(path.lstat()),mode=stat.S_IMODE(path.stat().st_mode))
    if not directories: raise ValueError('Actual installation tree missing')
    return dict(files=files,links=links,directories=sorted(directories))


def _sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def _mkdir(path,bootstrap):
    if path == ROOT: bootstrap.directories(path, private=True); return
    if path.exists(): bootstrap.directories(path); return
    _mkdir(path.parent,bootstrap) if not path.parent.exists() else bootstrap.directories(path.parent)
    path.mkdir(mode=0o700); _sync(path.parent); bootstrap.directories(path,private=True)


def _write(name,raw,bootstrap,mode=0o600):
    path=ROOT/_parts(name); _mkdir(path.parent,bootstrap)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno())
        identity = bootstrap.identity(os.fstat(out.fileno()))
    _sync(path.parent)
    if bootstrap.identity(path.lstat()) != identity: raise ValueError('Exclusive installation output replaced')
    return identity


def _copy(name,expected,bootstrap,libraries):
    libraries.read(ORIGINAL,name,expected['sha256'])
    source=ORIGINAL/name; target=ROOT/name
    if libraries.identity(source.lstat()) != expected['identity']: raise ValueError('Original copy identity replaced')
    _mkdir(target.parent,bootstrap)
    with os.fdopen(os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as inp:
        if libraries.identity(os.fstat(inp.fileno())) != expected['identity']: raise ValueError('Original copy replaced')
        with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,expected['mode']),'wb') as out:
            while chunk:=inp.read(1024*1024): out.write(chunk)
            out.flush(); os.fsync(out.fileno())
            identity = libraries.identity(os.fstat(out.fileno()))
        if libraries.identity(os.fstat(inp.fileno())) != expected['identity']: raise ValueError('Original copy changed')
    _sync(target.parent); libraries.read(ROOT,name,expected['sha256'])
    libraries.read(ORIGINAL,name,expected['sha256'])
    if libraries.identity(source.lstat()) != expected['identity']: raise ValueError('Original copy replaced')
    if libraries.identity(target.lstat()) != identity: raise ValueError('New copy replaced')
    return identity


def _installed(decoded,trees,created,bootstrap,libraries):
    expected = set(created)
    directories = {''}
    for name in expected:
        directories.update(p.as_posix() for p in Path(name).parents if p.as_posix() != '.')
    for tree in trees: directories.update(tree['directories'])
    actual = set(); actual_directories = set()
    for current, children, names in os.walk(ROOT,followlinks=False):
        current = Path(current); relative=current.relative_to(ROOT).as_posix()
        actual_directories.add('' if relative == '.' else relative)
        bootstrap.directories(current)
        for name in children+names:
            path=current/name
            if path.is_symlink(): actual.add(path.relative_to(ROOT).as_posix())
        children[:]=[n for n in children if not (current/n).is_symlink()]
        actual.update((current/n).relative_to(ROOT).as_posix() for n in names)
    if actual != expected or actual_directories != directories:
        raise ValueError('Exact newly installed file/directory inventory required')
    for name,identity in created.items():
        if libraries.identity((ROOT/name).lstat()) != identity:
            raise ValueError('New installation output identity replaced')
    for name,raw in decoded.items(): libraries.read(ROOT,name,_sha(raw))
    for tree in trees:
        for name,item in tree['files'].items(): libraries.read(ROOT,name,item['sha256'])
        for name,item in tree['links'].items():
            if not (ROOT/name).is_symlink() or os.readlink(ROOT/name) != item['target']:
                raise ValueError('Installed interpreter alias changed')


def _runtime(bootstrap,libraries,decoded):
    provenance=bootstrap.loads(decoded['stage2/dataset_provenance.json'])
    dataset=_parts(provenance['dataset_path'])
    if not dataset.startswith('.cache/'): raise ValueError('Original canonical dataset required')
    records=[_tree(ORIGINAL,'.venv',libraries,python_links=True),_tree(ORIGINAL,dataset,libraries),
        _tree(ORIGINAL,'.cache/stage2-tokenizer',libraries)]
    dataset_files=records[1]['files']
    expected={dataset+'/'+n['path']:n['sha256'] for n in provenance['canonical']['file_hashes']}
    if {n:v['sha256'] for n,v in dataset_files.items()} != expected:
        raise ValueError('Complete canonical dataset bytes required')
    for name in ('.runtime/stage2/python-runtime.tar.gz','.env'):
        digest=libraries.read(ORIGINAL,name); path=ORIGINAL/name; info=path.lstat()
        if stat.S_IMODE(info.st_mode) != 0o600: raise ValueError('Private native input required')
        records.append(dict(files={name:dict(sha256=digest,identity=libraries.identity(info),mode=0o600)},links={},directories=[]))
    return dataset, records


def _interpreter(bootstrap):
    target = Path(sys.executable).resolve(strict=True)
    raw, identity = bootstrap.raw(target.parent, target.name)
    if target != (ORIGINAL / '.venv/bin/python').resolve(strict=True) or not identity[2] & 0o111:
        raise ValueError('Actual original interpreter target identity required')
    return str(target), _sha(raw), identity


def _install(value):
    decoded,final,bootstrap,libraries,guard=_payload(value)
    old=_old(value,bootstrap,libraries,guard)
    interpreter = _interpreter(bootstrap)
    dataset,trees=_runtime(bootstrap,libraries,decoded)
    if trees[-2]['files']['.runtime/stage2/python-runtime.tar.gz']['sha256'] != final['python_runtime']['sha256']:
        raise ValueError('Exact original Python distribution required')
    with _locked(bootstrap) as locks:
        # Fresh real absence is checked again immediately before exclusive creation.
        if _old(value,bootstrap,libraries,guard) != old: raise ValueError('Native evidence replaced before installation')
        if _runtime(bootstrap,libraries,decoded) != (dataset,trees): raise ValueError('Current native inputs drifted')
        if _interpreter(bootstrap) != interpreter: raise ValueError('Original interpreter target changed')
        locks(); ROOT.mkdir(mode=0o700); _sync(ROOT.parent)
        original_root_identity=bootstrap.directories(ROOT,private=True)
        created = {}
        try:
            created['installation-intent.json'] = _write('installation-intent.json',_json(dict(kind=KIND,commit=value['commit'],
                started_utc=datetime.now(timezone.utc).isoformat(),automatic_resume=False,paid_launch_ready=False)),bootstrap)
            for name,raw in sorted(decoded.items()): created[name] = _write(name,raw,bootstrap)
            for tree in trees:
                for name in tree['directories']: _mkdir(ROOT/name,bootstrap)
                for name,item in tree['files'].items(): created[name] = _copy(name,item,bootstrap,libraries)
                for name,item in tree['links'].items():
                    target=ROOT/name; _mkdir(target.parent,bootstrap)
                    os.symlink(item['target'],target); _sync(target.parent)
                    created[name] = libraries.identity(target.lstat())
            for name in ('matrix.lock','scored.lock','gateway.lock'):
                created['.runtime/stage2/'+name] = _write('.runtime/stage2/'+name,b'',bootstrap)
            created['source-commit.txt'] = _write('source-commit.txt',(value['commit']+'\n').encode(),bootstrap)
            _quiet(guard); locks(); _reread(value,old,libraries)
            if _runtime(bootstrap,libraries,decoded) != (dataset,trees): raise ValueError('Original runtime changed during copy')
            if _interpreter(bootstrap) != interpreter: raise ValueError('Original interpreter target changed during copy')
            _installed(decoded,trees,created,bootstrap,libraries)
            if bootstrap.directories(ROOT,private=True) != original_root_identity: raise ValueError('Installed root replaced')
            result=dict(kind=KIND,commit=value['commit'],root=str(ROOT),sources_and_inputs=len(decoded),
                copied_current_files=sum(len(t['files']) for t in trees),precreated_locks=3,
                original_roots_unchanged=True,historical_installed_bytes_attested=False,
                installed_utc=datetime.now(timezone.utc).isoformat(),paid_launch_ready=False,
                recovery_execution_qualified=False,automatic_resume=False)
            # Private detailed inventory is never returned or published; .env
            # stays on the native host and is never included in a source payload.
            created['installation-files.json'] = _write('installation-files.json',_json(dict(files=value['hashes'],runtime=[dict(
                files={n:v['sha256'] for n,v in t['files'].items()},links={n:v['target'] for n,v in t['links'].items()},
                directories=t['directories']) for t in trees])),bootstrap)
            _installed(decoded,trees,created,bootstrap,libraries)
            created['installation-result.json'] = _write('installation-result.json',_json(result),bootstrap)
            _installed(decoded,trees,created,bootstrap,libraries); locks()
            return result
        except BaseException:
            path=ROOT/'installation-failure.json'
            if not path.exists() and not path.is_symlink():
                _write('installation-failure.json',_json(dict(status='failed_or_uncertain_preserve_root',
                    automatic_resume=False,paid_launch_ready=False)),bootstrap)
            raise


def _entry(digest):
    raw=sys.stdin.buffer.read(WINDOW+1)
    if len(raw)>WINDOW or _sha(raw)!=digest: raise ValueError('Committed installation payload changed')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate installation field')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=pairs)
    result=_install(value)
    print(json.dumps(result,sort_keys=True,allow_nan=False),flush=True)


def prepare(commit):
    from no_cutoff_recovery_connection import prepare as connection_prepare, _local_identities
    from no_cutoff_recovery_session import _lock_paths
    import no_cutoff_recovery_policy as policy
    import no_cutoff_recovery_predecessor as operator
    value,_=connection_prepare(commit)
    expected=[Path('/opt')/r/'.runtime/stage2'/n for r in (*EARLY,*LATE) for n in ('matrix.lock','scored.lock','gateway.lock')]
    if [p for p in _lock_paths(ROOT) if p!=ROOT/'.runtime/stage2/matrix.lock']!=expected:
        raise ValueError('Installation must preserve the actual inherited lock order')
    launch=operator.launch; hashes=dict(value['recovery_local'])
    hashes.update(operator.export.PREREQUISITES)
    hashes.update({operator.export.DESTINATION+'/'+n:h for n,h in policy.PUBLIC_FILES.items()})
    decoded={n:launch._raw(n,h) for n,h in hashes.items()}
    decoded[QUALIFICATION]=value['bindings']['anchors'][ORIGINAL_QUALIFICATION]
    decoded[MANIFEST]=decoded['stage2/input_manifest.json']
    hashes.update({QUALIFICATION:_sha(decoded[QUALIFICATION]),MANIFEST:_sha(decoded[MANIFEST])})
    payload=dict(kind=KIND,commit=commit,files={n:base64.b64encode(raw).decode() for n,raw in decoded.items()},
        hashes=hashes,native=value['bindings']['native'],reporter=value['bindings']['reporting'])
    _payload(payload); operator._current(value)
    return value,payload,_local_identities(value)


def deploy(commit):
    """ONE actual installation. Existing/partial state never restarts."""
    import no_cutoff_recovery_connection as connection
    import no_cutoff_recovery_predecessor as operator
    value,payload,identities=prepare(commit); launch=operator.launch
    root=launch.REPO; state=root/STATE
    if state.exists() or state.is_symlink(): raise ValueError('Existing installation state requires inspection')
    # Reuse the actual independently checked pinned SSH prefix. Never append a
    # second interpreter or drop a host-key/identity/destination option.
    fixed=connection.command('0'*32,connection.prepare(commit)[1],commit)
    source=launch._raw('stage2/no_cutoff_recovery_install.py',payload['hashes']['stage2/no_cutoff_recovery_install.py'])
    raw=_json(payload); program=('import base64\nexec(compile(base64.b64decode('+repr(base64.b64encode(source).decode())+
        '),"<committed-recovery-installer>","exec"))\ntry:\n _entry('+repr(_sha(raw))+')\n'
        'except BaseException:\n raise SystemExit("Recovery installation failed; preserve all partial evidence") from None\n')
    args=fixed[:-1]+[shlex.join(['/usr/bin/env','-i',*(k+'='+v for k,v in _environment().items()),
        str(ORIGINAL/'.venv/bin/python'),'-I','-B','-c',program])]
    parents=operator.receiver._parents(); state.mkdir(mode=0o700); operator.receiver._sync(state.parent)
    state_identity=(parents,operator.receiver._directory_id(state))
    from scored_gateway import durable_json
    durable_json(state/'intent.json',dict(kind=KIND,commit=commit,payload_sha256=_sha(raw),automatic_resume=False))
    intent=(launch._raw(STATE+'/intent.json'),connection.boot.identity((state/'intent.json').lstat()))
    try:
        operator._current(value)
        operator.receiver._state(state,state_identity)
        if connection._local_identities(value)!=identities or operator.receiver._parents()!=parents:
            raise ValueError('Local committed installer inputs replaced')
        result=subprocess.run(args,input=raw,capture_output=True,timeout=1800,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        if result.returncode or len(result.stdout)>16384: raise ValueError('Uncertain native installation; inspect without retry')
        observed=connection.boot.loads(result.stdout)
        if (observed.get('kind')!=KIND or observed.get('commit')!=commit or observed.get('root')!=str(ROOT)
                or observed.get('paid_launch_ready') is not False or observed.get('recovery_execution_qualified') is not False):
            raise ValueError('Exact non-admitting installation result required')
        operator._current(value)
        if connection._local_identities(value)!=identities: raise ValueError('Local inputs replaced during installation')
        operator.receiver._state(state,state_identity)
        if (intent!=(launch._raw(STATE+'/intent.json'),connection.boot.identity((state/'intent.json').lstat()))
                or {p.name for p in state.iterdir()}!={'intent.json'}):
            raise ValueError('Installation operator evidence replaced')
        durable_json(state/'result.json',observed); return observed
    except BaseException:
        operator.receiver._state(state,state_identity)
        durable_json(state/'failure.json',dict(status='uncertain_inspect_native_without_retry',automatic_resume=False))
        raise
