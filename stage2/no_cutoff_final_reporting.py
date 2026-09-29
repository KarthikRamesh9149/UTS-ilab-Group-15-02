"""Fixed Mac-side deployment and read-only invocation of the amended reporter.

No CLI, exporter, handoff, qualification or paid dispatch. The separate backup
operator uses the fixed binary archive operation, never the JSON reply path.
Do not invoke against the native host until final89 is inactive and the full
amended reporting/backup/export/handoff route is ready. Failed or uncertain
deployment is inspected, never automatically retried or replaced.
"""
import base64
import hashlib
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import subprocess

import no_cutoff_final_archive as archive
import no_cutoff_final_guard as guard
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_transport as transport
import progress_dashboard as dashboard

REPO = Path('/Users/karthikramesh/.codex/.chatgpt-projects/g-p-6a789724c2d48191b80421978177d029/terminal-bench-progress-smoke')
COPIES = '.runtime/netcup/custom-no-cutoff-final-20260928/qualified/'
KIND = 'separate_final_reporting_operation_not_backup_or_admission'
OPERATIONS = frozenset({'deploy', 'inspect', 'collect', 'backup'})
WINDOW = 64 * 1024 * 1024  # Metadata reply/parser window, not a study limit.


def _operator():
    if (platform.system() != 'Darwin' or REPO.is_symlink() or REPO.resolve() != REPO
            or not REPO.is_dir() or Path(__file__).resolve() != REPO / 'stage2/no_cutoff_final_reporting.py'):
        raise ValueError('Use the fixed Mac operator checkout')
    for module in (archive, phase, report, guard, report.dependencies, transport, dashboard, phase.local_trace):
        if Path(module.__file__).resolve() != REPO / 'stage2' / (module.__name__ + '.py'):
            raise ValueError('Reporting helper imported from another checkout')


def _git(*args):
    try:
        result = subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Could not check committed reporting sources') from None
    if result.returncode:
        raise ValueError('Could not check committed reporting sources')
    return result.stdout


def _raw(name, expected=None):
    path = phase._path(REPO, name)
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK),'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid()
                    or before.st_mode & (0o077 if name.startswith('.runtime/') else 0o022)
                    or before.st_size > WINDOW):
                raise ValueError('Protected regular operator source/metadata required')
            raw = stream.read(WINDOW + 1); after = os.fstat(stream.fileno())
        def identity(s):
            return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if identity(before) != identity(after) or identity(after) != identity(path.lstat()):
            raise ValueError('Operator bytes changed while preparing reporting')
    except OSError:
        raise ValueError('Required operator evidence unavailable') from None
    if len(raw)>WINDOW or expected is not None and hashlib.sha256(raw).hexdigest()!=phase._hash(expected):
        raise ValueError('Exact operator bytes required')
    return raw


def _bindings():
    """Actual local byte reads only. No native audit, SSH or archive read."""
    _operator()
    local = {}; anchors = {}
    for name, expected in archive.anchor_hashes().items():
        copy = (COPIES + 'no-cutoff-final-matrix.json' if name.endswith('/no-cutoff-final-matrix.json')
            else COPIES + name if name.startswith(phase.RT) else name)
        anchors[name] = _raw(copy, expected); local[copy] = expected
    proof, _, _, _ = archive._anchors(anchors)
    native = {'stage2/' + name: sha for name, sha in proof['sources'].items()}
    native.update({phase.RT + name: sha for name, sha in report.INPUTS.items()})
    native.update(proof['evidence_files']); native.update(report.HISTORICAL_INPUTS)
    if set(native) & set(report.dependencies.FILES):
        raise ValueError('New reporting helpers cannot be historical qualification bindings')
    native.update(report.dependencies.FILES)
    native.update(guard.REPORTING_LIBRARY_FILES)
    for name, expected in report.dependencies.FILES.items():
        _raw(name, expected); local[name] = expected
        if hashlib.sha256(_git('show', report.dependencies.ORIGINAL_COMMIT + ':' + name)).hexdigest() != expected:
            raise ValueError('Current-only helper differs from original Git source bytes')
    for name, expected in native.items():
        if name in proof['evidence_files'] or name.startswith(phase.RT) and not name.endswith('/python-runtime.tar.gz'):
            copy = COPIES + 'no-cutoff-final-matrix.json' if name.endswith('/no-cutoff-final-matrix.json') else COPIES + name
            _raw(copy, expected); local[copy] = expected
    _raw('stage2/local_trace.py', phase.FROZEN_HELPERS['local_trace.py'])
    local['stage2/local_trace.py'] = phase.FROZEN_HELPERS['local_trace.py']
    reporting = {'stage2/'+name: hashlib.sha256(_raw('stage2/'+name)).hexdigest() for name in report.REPORTING_FILES}
    local.update(reporting)
    # No project imports or network: static closure of original bound native
    # Git bytes and the current separate reporting bundle. Dynamic imports are
    # independently checked by the actual native loaded-module guards.
    raw_sources = {}
    for name, sha in native.items():
        if name.startswith('stage2/') and name.endswith('.py'):
            raw = _git('show', report.dependencies.ORIGINAL_COMMIT + ':' + name)
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError('Original Git source differs from native reporting binding')
            raw_sources[name] = raw
    raw_sources.update({n: _raw(n, h) for n, h in reporting.items() if n.endswith('.py')})
    project_names = {p.stem for p in (REPO / 'stage2').glob('*.py')}
    report.dependencies._closure(raw_sources, project_names)
    ssh_source = native.get('stage2/progress_dashboard.py')
    if ssh_source is None:
        raise ValueError('Frozen pinned SSH source is required')
    _raw('stage2/progress_dashboard.py', ssh_source)
    local['stage2/progress_dashboard.py'] = ssh_source
    return dict(native=native, reporting=reporting, local=local, anchors=anchors)


def _prepare(commit):
    if not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Exact full committed reporting revision required')
    bindings = _bindings()
    if (_git('rev-parse', 'HEAD').decode().strip() != commit
            or _git('rev-parse', 'origin/main').decode().strip() != commit):
        raise ValueError('Reporting revision must match current main and fetched origin/main')
    for name, sha in bindings['local'].items():
        if name.startswith('stage2/') and hashlib.sha256(_git('show', commit + ':' + name)).hexdigest() != sha:
            raise ValueError('Reporting and SSH sources must match the committed revision')
    return {**bindings, 'commit': commit}


def _recheck(bindings):
    for name, sha in bindings['local'].items():
        _raw(name, sha)
    if _git('rev-parse', 'HEAD').decode().strip() != bindings['commit']:
        raise ValueError('Operator revision changed across reporting operation')


# Only stdlib executes before check(). All roots, maps and operations below
# come from fresh fixed-path operator reads, never a saved caller receipt.
_BOOTSTRAP = r'''
import base64, contextlib, hashlib, json, os, stat, subprocess, sys, types
from pathlib import Path
c=CONFIG
root=Path(c['root']); reporting=Path(c['reporting'])
guard_raw=base64.b64decode(c['guard_source'],validate=True)
if hashlib.sha256(guard_raw).hexdigest()!=c['reporting_files']['stage2/no_cutoff_final_guard.py']:
 raise ValueError('Exact committed pre-import guard required')
guard_module=types.ModuleType('no_cutoff_final_guard')
guard=guard_module.__dict__
guard['__file__']=str(reporting/'stage2/no_cutoff_final_guard.py')
exec(compile(guard_raw,'<source-bound-final-guard>','exec'),guard)
dependency_raw=base64.b64decode(c['dependency_source'],validate=True)
if hashlib.sha256(dependency_raw).hexdigest()!=c['reporting_files']['stage2/no_cutoff_final_dependencies.py']:
 raise ValueError('Exact source-bound reporting dependency reader required')
dependencies={}
exec(compile(dependency_raw,'<source-bound-reporting-dependencies>','exec'),dependencies)
def fail(message): raise ValueError(message)
def path(base,name):
 guard['protected_path'](base,name)
 if base.is_symlink() or not base.is_dir() or base.resolve()!=base:
  fail('Canonical reporting/execution directory required')
 p=base
 for part in name.split('/'):
  if part in ('','.','..'): fail('Normalised bound path required')
  p/=part
  if p.is_symlink(): fail('Symlinked reporting evidence refused')
 return p
def identity(s):
 return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def read(base,name,sha,retain=False):
 protection=guard['protected_path'](base,name)
 p=path(base,name)
 with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
  before=os.fstat(f.fileno())
  guard['protected_file'](base,name,before,private=base==reporting)
  digest=hashlib.sha256(); chunks=[]
  while True:
   raw=f.read(65536)
   if not raw: break
   digest.update(raw)
   if retain:
    chunks.append(raw)
    if f.tell()>67108864: fail('Bound source/metadata parser window exceeded')
  after=os.fstat(f.fileno())
 if (identity(before)!=identity(after) or identity(after)!=identity(p.lstat()) or digest.hexdigest()!=sha
  or guard['protected_path'](base,name)!=protection):
  fail('Bound reporting evidence changed')
 return b''.join(chunks) if retain else None
def service():
 if root!=guard['ROOT'] or c['service']!=guard['SERVICE'] or c['environment']!=guard['ENVIRONMENT']:
  fail('Only the fixed final compatibility guard is permitted')
 state=guard['service']()
 for name in ('operator-stop-request.json','provider-stop.json'):
  p=path(root,'.runtime/stage2/'+name)
  if p.exists() or p.is_symlink(): fail('Persistent stop forbids completed reporting')
 return state
def inventory():
 expected={'':{'stage2'}}
 states={'.backup-intent.json','.backup-result.json','.backup-failure.json'}
 if reporting.is_dir():
  for name in states & {v.name for v in reporting.iterdir()}:
   p=path(reporting,name)
   # States are not source files or admission witnesses. They are retained
   # outside the frozen root and must remain private regular owned files.
   with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
    s=os.fstat(f.fileno())
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid() or s.st_mode & 0o077:
     fail('Private regular retained backup state required')
   expected[''].add(name)
 for name in c['reporting_files']:
  parts=name.split('/')
  for i,part in enumerate(parts): expected.setdefault('/'.join(parts[:i]),set()).add(part)
 for name,children in expected.items():
  p=path(reporting,name) if name else reporting
  st=p.stat()
  if not p.is_dir() or st.st_uid!=os.getuid() or st.st_mode & 0o077 or {v.name for v in p.iterdir()}!=children:
   fail('Exact private reporting directory inventory required')
def check(deployed=True):
 if dict(os.environ)!=c['environment']: fail('Reporting environment changed')
 guard['reporting_environment']()
 state=service()
 for name,sha in c['native_files'].items(): read(root,name,sha)
 if deployed:
  inventory()
  for name,sha in c['reporting_files'].items(): read(reporting,name,sha)
 cache=reporting/'.absent-bytecode-cache'
 if cache.exists() or cache.is_symlink(): fail('Reporting bytecode prefix must remain absent')
 return state
def loaded():
 expected={Path(name).name:(base,name,sha) for base,files in
  ((root,c['native_files']),(reporting,c['reporting_files'])) for name,sha in files.items()
  if name.startswith('stage2/') and name.endswith('.py')}
 for module in tuple(sys.modules.values()):
  filename=getattr(module,'__file__',None)
  if not filename: continue
  p=Path(filename)
  if p.name in expected:
   base,name,sha=expected[p.name]
   if p.is_symlink() or p.absolute()!=base/name or p.resolve()!=base/name:
    fail('Bound project helper imported from another deployment')
   read(base,name,sha)
  elif root/'stage2' in p.parents or reporting in p.parents:
   fail('Unbound project module imported into reporting')
def closure():
 raw={n:read(root,n,h,True) for n,h in c['native_files'].items() if n.startswith('stage2/') and n.endswith('.py')}
 for n,h in c['reporting_files'].items():
  if not n.endswith('.py'): continue
  value=base64.b64decode(c['payload'][n],validate=True) if c['operation']=='deploy' else read(reporting,n,h,True)
  if hashlib.sha256(value).hexdigest()!=h: fail('Reporting closure source changed')
  if n in raw: fail('Reporting source shadows a frozen execution module')
  raw[n]=value
 names={p.stem for p in (root/'stage2').glob('*.py')}|{Path(n).stem for n in c['reporting_files'] if n.endswith('.py')}
 dependencies['_closure'](raw,names)
def main():
 if (sys.platform!='linux' or os.getuid()!=0 or not sys.flags.isolated or not sys.dont_write_bytecode
  or dict(os.environ)!=c['environment'] or Path(sys.prefix).resolve()!=root/'.venv'):
  fail('Exact isolated final interpreter and credential-free environment required')
 if root==reporting or root in reporting.parents or reporting in root.parents:
  fail('Reporting must be separate from frozen execution')
 sys.pycache_prefix=str(reporting/'.absent-bytecode-cache')
 check(deployed=c['operation']!='deploy')
 closure()
 if c['operation']=='deploy':
  if reporting.exists() or reporting.is_symlink(): fail('Existing or partial reporting deployment must not be replaced')
  if reporting.parent.resolve()!=reporting.parent or not reporting.parent.is_dir(): fail('Canonical reporting parent required')
  # Exclusive creation only. Partial failures remain for inspection; no delete,
  # overwrite, resume, old-root write or automatic retry is provided.
  reporting.mkdir(mode=0o700)
  directories=sorted({str(Path(n).parent) for n in c['reporting_files']},key=lambda n:(n.count('/'),n))
  for name in directories: (reporting/name).mkdir(mode=0o700)
  for name,sha in c['reporting_files'].items():
   raw=base64.b64decode(c['payload'][name],validate=True)
   if hashlib.sha256(raw).hexdigest()!=sha: fail('Committed deployment payload changed')
   with os.fdopen(os.open(path(reporting,name),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:
    f.write(raw);f.flush();os.fsync(f.fileno())
  for name in [*reversed(directories),'']:
   fd=os.open(reporting/name,os.O_RDONLY|os.O_DIRECTORY)
   try: os.fsync(fd)
   finally: os.close(fd)
 state=check()
 if c['operation'] not in ('collect','backup'):
  return dict(kind=c['kind'],operation=c['operation'],operator_commit=c['commit'],
   reporting_source_files=c['reporting_files'],execution_source_set_sha256=c['source_set'],
   service=state,
   completed_final_audit=False,off_server_backup_verified=False,paid_launch_ready=False)
 os.chdir(root);sys.path[:0]=[str(reporting/'stage2'),str(root/'stage2')]
 # The report/backup must see the SAME guard and latched hook state, not a
 # second execution of its source with a fresh violation flag.
 if 'no_cutoff_final_guard' in sys.modules: fail('Unexpected preloaded reporting guard')
 sys.modules['no_cutoff_final_guard']=guard_module
 guard['install_environment_guard']()
 # Suppress incidental library output, including raw diagnostics. Only the
 # validated amended metadata reaches the SSH stdout on successful completion.
 with open(os.devnull,'w') as quiet,contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):
  import no_cutoff_final_report as audit
  import no_cutoff_final_archive as archive
  loaded();check()
  # Import fixed native readers, but never call a collector, before starting
  # the long audit. Unknown transitive imports fail before lineage/locks.
  audit._native()
  loaded();check()
  if c['operation']=='backup':
   import no_cutoff_final_backup as backup
   loaded();check()
   backup.stream()
   return None
  value=audit.collect()
  anchors={n:read(root,n,h,True) for n,h in c['anchor_files'].items()}
  archive.validate_snapshot(value,anchors)
  if value['reporting_source_files']!=c['reporting_files']: fail('Audit used another reporting bundle')
  loaded();check()
  # Actual post-return file and absence reads, not a saved leaf flag. The audit
  # itself authenticates before holding and releasing its full ancestor locks.
  for name,sha in value['supporting_file_sha256'].items(): read(root,name,sha)
  for name,children in value['directory_entries'].items():
   p=path(root,name)
   if not p.is_dir() or sorted(v.name for v in p.iterdir())!=children: fail('Evidence inventory changed after audit')
  for name in value['absent_paths']:
   if path(root,name).exists(): fail('Proven absence changed after audit')
  for base,files in value['preserved_result_files'].items():
   if base not in c['historical_roots']: fail('Historical result root changed')
   for name,sha in files.items(): read(Path(base),name,sha)
  # No native observation follows these final evidence reads. Check every
  # reporting file too, including source/tests not imported into this process.
  loaded();inventory()
  for name,sha in c['reporting_files'].items(): read(reporting,name,sha)
  guard['reporting_environment']()
 return value
try:
 value=main()
 if c['operation']!='backup':
  print(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False))
except BaseException:
 print('{"status":"reporting_operation_failed_inspect_before_retry","automatic_resume":false,"paid_launch_ready":false}',file=sys.stderr)
 raise SystemExit(1) from None
'''


def _program(bindings, operation):
    if operation not in OPERATIONS:
        raise ValueError('Only fixed reporting operations are supported')
    config = dict(root=str(report.ROOT), reporting=str(report.REPORTING), service=report.SERVICE,
        operation=operation, environment=dict(report.ENVIRONMENT), native_files=bindings['native'],
        reporting_files=bindings['reporting'], commit=bindings['commit'], kind=KIND,
        source_set=phase.SOURCE_SET, anchor_files=archive.anchor_hashes(),
        historical_roots=[str(report.BASELINE), str(report.STOPPED)])
    config['guard_source'] = base64.b64encode(guard.source(
        bindings['reporting']['stage2/no_cutoff_final_guard.py'])).decode('ascii')
    raw = Path(report.dependencies.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != bindings['reporting']['stage2/no_cutoff_final_dependencies.py']:
        raise ValueError('Current source-bound reporting dependency reader required')
    config['dependency_source'] = base64.b64encode(raw).decode('ascii')
    if operation == 'deploy':
        config['payload'] = {n: base64.b64encode(_raw(n,sha)).decode('ascii') for n,sha in bindings['reporting'].items()}
    return _BOOTSTRAP.replace('c=CONFIG', 'c=' + repr(config))


def _command():
    args = dashboard.ssh_command(REPO)
    if args[-3:] != ['root@62.83.32.126','python3','-']:
        raise ValueError('Existing pinned SSH destination/interpreter shape changed')
    remote = ['/usr/bin/env','-i', *(k+'='+v for k,v in report.ENVIRONMENT.items()),
        str(report.ROOT / '.venv/bin/python'), '-I','-B','-']
    return args[:-2] + [shlex.join(remote)]


def _invoke(commit, operation):
    if operation not in ('deploy', 'inspect', 'collect'):
        raise ValueError('Binary backup requires the exclusive fixed operator receiver')
    bindings = _prepare(commit)
    if operation == 'collect':
        return _audit(bindings)[0]
    program = _program(bindings, operation); _recheck(bindings)
    try:
        result = subprocess.run(_command(),input=program.encode(),capture_output=True,timeout=300,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Reporting connection uncertain; inspect exact deployment before another operation') from None
    _recheck(bindings)
    if result.returncode or len(result.stdout)>WINDOW:
        raise ValueError('Reporting operation refused or incomplete; inspect without retry or replacement')
    value = phase._loads(result.stdout)
    guard.validate_service(value.get('service'))
    archive._same(value, dict(kind=KIND,operation=operation,operator_commit=commit,
        reporting_source_files=bindings['reporting'],execution_source_set_sha256=phase.SOURCE_SET,
        service=value['service'],
        completed_final_audit=False,off_server_backup_verified=False,paid_launch_ready=False))
    _recheck(bindings)
    return value


def _aliases(bindings):
    values = {'<reporting-bootstrap>': 'bootstrap', '<source-bound-final-guard>': 'completion_guard',
        '<source-bound-reporting-dependencies>': 'reporting_dependencies', '<stdin>': 'transport'}
    for base, files, label in ((report.ROOT, bindings['native'], 'execution/'),
            (report.REPORTING, bindings['reporting'], 'reporting/')):
        for name in files:
            if name.endswith('.py'): values[str(base / name)] = label + name
    return values


def _audit(bindings):
    """One real audit with complete-return metadata; no saved snapshot input."""
    aliases = _aliases(bindings)
    original = _program(bindings, 'collect')
    program = transport._wrap(original, aliases)
    program_hashes = dict(original_program_sha256=transport._hash(original.encode()),
        transmitted_program_sha256=transport._hash(program.encode()))
    _recheck(bindings)
    try:
        raw, metadata = transport._exchange(program, aliases, _command(),
            {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    except transport.AuditTransportError as error:
        error.metadata = dict(error.metadata, **program_hashes)
        raise
    metadata = dict(metadata, **program_hashes)
    stage = 'operator_source_recheck'
    try:
        _recheck(bindings)
        stage = 'completed_return_validation'; transport._completed(raw, metadata)
        stage = 'snapshot_schema_validation'; value = phase._loads(raw)
        archive.validate_snapshot(value, bindings['anchors'])
        archive._same(value['reporting_source_files'], bindings['reporting'])
        stage = 'final_operator_source_recheck'; _recheck(bindings)
    except BaseException as error:
        # Preserve the real transport observations even if a later local gate
        # refuses. Never mislabel a consumed native invocation as not started.
        raise transport.AuditTransportError(dict(metadata, operator_failure_stage=stage,
            operator_error_type=transport._error_type(error), completed_final_audit_verified=False,
            native_state_requires_inspection=True)) from None
    return value, raw, metadata


def deploy(commit):
    """One exclusive separate source deployment, never overwrite or auto-retry."""
    return _invoke(commit, 'deploy')


def inspect_deployment(commit):
    """Read-only exact-byte inspection after a failed/uncertain deployment."""
    return _invoke(commit, 'inspect')


def collect(commit):
    """Fresh actual amended audit via pinned SSH, never read a saved snapshot."""
    return _invoke(commit, 'collect')
