"""Actual fresh recovery audit and SAME retained archive for a baseline sender.

The fixed recovery reader runs in its own isolated Mac interpreter because its
frozen loaded-source inventory deliberately excludes new baseline modules.
That child performs the real pinned reporting call; saved JSON is never an
alternative. This module does not install, write a backup, export or dispatch.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import matched_repeat_amended_predecessor as original
import matched_repeat_execution_bootstrap as bootstrap
import no_cutoff_recovery_reporting as recovery
import no_cutoff_recovery_mac_reporting as mac_recovery
import mac_operator_files as mac

KIND = 'actual_recovery_capture_for_baseline_not_admission'
REPO = original.launch.REPO
PYTHON = REPO / '.tools/stage2-custom/bin/python'
CACHE = REPO / '.runtime/absent-baseline-recovery-audit-bytecode'
BACKUP = mac_recovery.BACKUP


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _sources(bindings):
    """Use the separately frozen recovery union, never the baseline union."""
    # The retained qualification path is fixed; no caller-selected evidence.
    name = '.runtime/netcup/custom-no-cutoff-final-20260928/qualified/.runtime/stage2/no-cutoff-final-qualification.json'
    final = recovery.boot.loads(original.launch._raw(name, bootstrap.FINAL_SHA))
    source = original.launch._raw('stage2/no_cutoff_recovery_policy.py',
        bindings['local']['stage2/no_cutoff_recovery_policy.py'])
    names = set(final['sources']) | bootstrap._required(source)
    bound = {n:_hash(original.launch._raw('stage2/'+n,bindings['local']['stage2/'+n])) for n in names}
    if recovery.policy.fingerprint(bound) != bootstrap.RECOVERY_SOURCES_SHA:
        raise ValueError('Exact frozen recovery sources required before a baseline handoff')
    return bound


def _environment():
    return dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', LANG='C.UTF-8',
        __CF_USER_TEXT_ENCODING=f'0x{os.getuid():X}:0x0:0x0',
        PYTHON_DOTENV_DISABLED='1', LITELLM_MODE='PRODUCTION', DO_NOT_TRACK='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', TIKTOKEN_CACHE_DIR=str(
            REPO/'.tools/stage2-custom/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers'))


def _program(commit, bound, sources):
    """Fixed actual collector call, independently bound before project imports."""
    return '''import contextlib,hashlib,io,json,os,stat,subprocess,sys
from pathlib import Path
root=Path(ROOT); bound=BOUND; sources=SOURCES; commit=COMMIT
cache=Path(CACHE)
if (Path.cwd()!=root or not sys.flags.isolated or not sys.dont_write_bytecode
 or Path(sys.executable).absolute()!=Path(PYTHON) or dict(os.environ)!=ENVIRONMENT
 or cache.exists() or cache.is_symlink()): raise ValueError('Fixed isolated recovery audit child required')
sys.pycache_prefix=str(cache)
def identity(s):
 return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def current():
 observed={}
 for name,digest in bound.items():
  path=root/name
  if path.resolve()!=path: raise ValueError('Canonical committed operator path required')
  for parent in path.parents:
   s=parent.lstat()
   if not stat.S_ISDIR(s.st_mode) or s.st_uid not in {0,os.getuid()} or s.st_mode&0o022:
    raise ValueError('Protected operator ancestry required')
  with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as handle:
   s=os.fstat(handle.fileno())
   if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid() or s.st_mode&0o022:
    raise ValueError('Protected operator source/input required')
   if name.startswith('.runtime/') and stat.S_IMODE(s.st_mode)!=0o600:
    raise ValueError('Private operator input required')
   raw=handle.read()
   if identity(os.fstat(handle.fileno()))!=identity(s): raise ValueError('Changed operator input')
  if identity(path.lstat())!=identity(s) or hashlib.sha256(raw).hexdigest()!=digest:
   raise ValueError('Changed source/input bytes or identity')
  if name.startswith('stage2/') and raw!=subprocess.check_output(['git','show',commit+':'+name],cwd=root):
   raise ValueError('Committed baseline source required')
  observed[name]=identity(s)
 for ref in ('HEAD','origin/main'):
  if subprocess.check_output(['git','rev-parse',ref],cwd=root).decode().strip()!=commit:
   raise ValueError('Full committed HEAD and fetched main required')
 return observed
before=current(); importing=True; violation=False; expected_environment=dict(os.environ)
def guard(event,args):
 global violation
 denied=False
 if event=='open':
  path,mode,flags=args
  name=Path(os.fsdecode(path)).name if isinstance(path,(str,bytes,os.PathLike)) else ''
  denied=name=='.env' or name.startswith('.env.') or name in {'.jwt_secret','id_ed25519','id_rsa'}
  denied|=importing and (isinstance(mode,str) and any(c in mode for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
 if event=='os.putenv':
  key,value=(os.fsdecode(x) for x in args);denied|=expected_environment.get(key)!=value
 if event=='os.unsetenv':denied=True
 if importing:
  if event=='socket.__new__':raise RuntimeError('Import socket capability denied before creation')
  denied|=event.startswith(('socket.','subprocess.','os.exec','os.spawn','os.posix_spawn')) or event in {'os.system','os.fork','os.forkpty','os.remove','os.rename','os.rmdir','os.mkdir','os.link','os.symlink','os.truncate','os.chmod','os.chown','os.utime','shutil.copyfile'}
 if denied:
  violation=True;raise RuntimeError('Recovery audit child effect refused')
sys.addaudithook(guard);sys.path.insert(0,str(root/'stage2'))
with contextlib.redirect_stdout(io.StringIO()):
 import no_cutoff_recovery_mac_reporting as reporting
 importing=False
 if violation or current()!=before:raise ValueError('Import changed bound recovery reader')
 mac_bound={n:bound['stage2/'+n] for n in set(sources)|set(reporting.bridge.EXTRAS)}
 reporting.bridge._loaded({'bound':mac_bound})
 fresh,captured,captured_ids=reporting._capture(commit,'audit')
 reporting._current(captured,captured_ids)
 if current()!=before or violation:raise ValueError('Late audit source/input change')
 reporting.bridge._loaded({'bound':mac_bound})
print(json.dumps(fresh,sort_keys=True,allow_nan=False))
'''.replace('Path(ROOT)','Path('+repr(str(REPO))+')').replace('bound=BOUND','bound='+repr(bound)).replace(
        'sources=SOURCES','sources='+repr(sources)).replace('commit=COMMIT','commit='+repr(commit)).replace(
        'Path(CACHE)','Path('+repr(str(CACHE))+')').replace('Path(PYTHON)','Path('+repr(str(PYTHON))+')').replace(
        '!=ENVIRONMENT','!='+repr(_environment()))


def _retained(bindings, sources):
    preserved = mac_recovery._failed_backup()
    data, backup = mac_recovery._read_backup({'current_sources':sources})  # Actual SAME archive read.
    root = REPO; state = root/recovery.EXPORT
    directory = mac.directories(state,private=True)
    if {p.name for p in state.iterdir()} != {'intent.json','result.json'}:
        raise ValueError('Actual completed immutable recovery export required')
    records = {BACKUP+'/'+n:mac.raw(root/BACKUP,n)
        for n in ('intent.json','snapshot.json','inventory.json','backup.json')}
    records.update(preserved['records'])
    records.update({recovery.EXPORT+'/'+n:mac.raw(state,n) for n in ('intent.json','result.json')})
    intent = recovery.boot.loads(records[recovery.EXPORT+'/intent.json'][0])
    if (set(intent) != {'kind','commit','started_utc','automatic_resume'}
            or intent['kind'] != 'one_shot_separate_recovery_export' or intent['automatic_resume'] is not False
            or type(intent['commit']) is not str or not re.fullmatch('[a-f0-9]{40}',intent['commit'])):
        raise ValueError('Exact completed recovery export intent required')
    original.archive._utc(intent['started_utc'])
    projection = recovery.projection(data,backup); public = {}
    for name,raw in projection.items():
        relative = recovery.PUBLIC+'/'+name
        actual = original.launch._raw(relative,_hash(raw))
        if actual != original.launch._git('show',bindings['commit']+':'+relative):
            raise ValueError('Recovery public results must already be committed')
        records[relative] = (actual,recovery.boot.identity((root/relative).lstat()))
        public[relative] = _hash(raw)
    original.archive._same(recovery.boot.loads(records[recovery.EXPORT+'/result.json'][0]),dict(
        kind='separate_recovery_allowlisted_export_complete',files=public,
        snapshot_sha256=recovery.policy.fingerprint(data),archive_sha256=backup['receipt']['sha256'],
        automatic_resume=False,paid_launch_ready=False))
    if mac.directories(state,private=True) != directory or mac_recovery._failed_backup() != preserved:
        raise ValueError('Recovery export identity changed')
    return dict(data=data,backup=backup,records=records,export_directory=directory,
        failed_backup=preserved,
        archive_identity=recovery.boot.identity((root/BACKUP/'evidence.tar.gz').lstat()))


def _loaded(bindings):
    """Actual fixed Mac origins/bytes, not a native .venv admission check."""
    original.launch._operator()
    if Path(__file__).absolute() != REPO/'stage2/matched_repeat_recovery_operator.py':
        raise ValueError('Fixed Mac baseline recovery source reader required')
    return recovery.connection.operator.loaded(REPO,
        {n[7:]:h for n,h in bindings['local'].items() if n.startswith('stage2/')})


def _current(value):
    original.launch._recheck(value['bindings'])
    if _sources(value['bindings']) != value['sources'] or _retained(value['bindings'],value['sources']) != value['retained']:
        raise ValueError('Recovery source/archive/export evidence changed after actual capture')
    _loaded(value['bindings'])


def capture(commit):
    """Actual fresh fixed audit; no saved document, root, factory or callback."""
    if Path(__file__).absolute() != REPO/'stage2/matched_repeat_recovery_operator.py':
        raise ValueError('Fixed Mac baseline recovery sender required')
    bindings, _ = original._prepare(commit,'terminus-2')
    sources = _sources(bindings); retained = _retained(bindings,sources)
    value = dict(bindings=bindings,sources=sources,retained=retained)
    _current(value)
    # The child owns the existing bounded reporting transport and its cleanup.
    # No independent benchmark limit or speculative child/native signal exists.
    result = subprocess.run([str(PYTHON),'-I','-B','-c',_program(commit,bindings['local'],sources)],
        cwd=REPO,env=_environment(),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if result.returncode or len(result.stdout)>recovery.boot.WINDOW:
        raise ValueError('Actual recovery audit child failed; preserve evidence without retry')
    fresh = recovery.boot.loads(result.stdout)
    recovery.report.validate(fresh,recovery._manifest(None),sources)
    recovery._equal_audit(retained['data'],fresh)
    _current(value)
    document = dict(kind=KIND,operator_commit=commit,recovery_root=str(bootstrap.RECOVERY),
        recovery_sources_sha256=bootstrap.RECOVERY_SOURCES_SHA,fresh_audit=fresh,
        retained={n:raw.decode('utf-8') for n,(raw,_) in retained['records'].items()},
        archive_sha256=retained['backup']['receipt']['sha256'],paid_launch_ready=False)
    return value,deepcopy(document)
