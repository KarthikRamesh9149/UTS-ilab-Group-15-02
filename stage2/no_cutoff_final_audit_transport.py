"""One-shot Mac connection to the unchanged installed completed-final audit.

Only collect(full_commit) is public. No deploy, backup, export, saved proof,
caller-selected root/timeout/callback or paid mode. Installed bytes stay fixed.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

import no_cutoff_final_archive as archive
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch

INSTALLED_REVISION = 'ea543e46784025f3db7a5ac54c4e8e4624893278'
DESTINATION = '.runtime/netcup/custom-no-cutoff-final89-audit-transport-20260929'
TRANSPORT_SECONDS = 1800  # Reporting connection only, never a benchmark deadline.
SAMPLE_SECONDS = 30
SOURCE_FILES = ('stage2/no_cutoff_final_audit_transport.py',
    'stage2/test_no_cutoff_final_audit_transport.py',
    'stage2/protocols/custom_final_audit_transport_20260929.md',
    'stage2/matched_repeat_policy.py')
PREFIX = b'UTS_FINAL_AUDIT_METADATA_V1 '
LINE_WINDOW = 4096
MAX_RECORDS = 128
ERROR_TYPES = frozenset({'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'AssertionError', 'RuntimeError', 'OSError', 'FileNotFoundError',
    'PermissionError', 'TimeoutError', 'TimeoutExpired', 'CalledProcessError',
    'KeyboardInterrupt', 'SystemExit', 'CancelledError', 'OtherError'})
FOOTER = '''try:
 value=main()
 if c['operation']!='backup':
  print(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False))
except BaseException:
 print('{"status":"reporting_operation_failed_inspect_before_retry","automatic_resume":false,"paid_launch_ready":false}',file=sys.stderr)
 raise SystemExit(1) from None
'''

# Periodic stack sampling, not per-call profiling. No frame locals, exception
# messages or raw logs. Original bootstrap/main definitions are byte-preserved.
WRAPPER = r'''
import hashlib, json, os, sys, threading, time
_program=PROGRAM
_aliases=ALIASES
_started=time.monotonic()
_stop=threading.Event()
_owner=threading.get_ident()
_write_lock=threading.Lock()
_allowed=ERRORS
def _type(error):
 name=type(error).__name__
 return name if name in _allowed and type(error).__module__ in (
  'builtins','subprocess','asyncio.exceptions') else 'OtherError'
def _frames(frame, traceback=False):
 result=[]; count=0
 while frame is not None and count<512:
  current=frame.tb_frame if traceback else frame
  source=_aliases.get(current.f_code.co_filename)
  line=frame.tb_lineno if traceback else current.f_lineno
  if source is not None and 0<line<=100000:
   result.append(dict(source=source,line=line))
  if len(result)==16: break
  frame=frame.tb_next if traceback else frame.f_back
  count+=1
 return result
def _errors(error):
 result=[]; seen=set(); remaining=16
 while error is not None and id(error) not in seen and len(result)<8:
  seen.add(id(error)); frames=_frames(error.__traceback__,True)[:remaining]
  remaining-=len(frames)
  result.append(dict(type=_type(error),frames=frames))
  error=error.__cause__ if error.__cause__ is not None else (
   None if error.__suppress_context__ else error.__context__)
 return result
def _emit(event,**fields):
 value=dict(event=event,elapsed_seconds=round(time.monotonic()-_started,6),**fields)
 raw=b'UTS_FINAL_AUDIT_METADATA_V1 '+json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
 if len(raw)>4096:
  if event!='failed': return
  value['exceptions']=[dict(type=v['type'],frames=[]) for v in value['exceptions']]
  raw=b'UTS_FINAL_AUDIT_METADATA_V1 '+json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
 try:
  with _write_lock:
   while raw:
    count=os.write(2,raw)
    if count<=0: return
    raw=raw[count:]
 except OSError:
  pass
def _sample():
 while not _stop.wait(INTERVAL):
  try: _emit('sample',frames=_frames(sys._current_frames().get(_owner)))
  except BaseException as error:
   _emit('sampling_unavailable',error_type=_type(error));return
_thread=None
try:
 if hashlib.sha256(_program.encode()).hexdigest()!=PROGRAM_HASH:
  raise ValueError('Original reporting bootstrap bytes changed')
 _scope={'__name__':'__main__','__file__':'<reporting-bootstrap>'}
 exec(compile(_program,'<reporting-bootstrap>','exec'),_scope)
 _ticks=0
 if sys.platform=='linux':
  with open('/proc/self/stat') as _f: _stat=_f.read()
  _ticks=int(_stat[_stat.rfind(')')+2:].split()[19])
 _emit('started',pid=os.getpid(),start_ticks=_ticks)
 _thread=threading.Thread(target=_sample,daemon=True,name='reporting-metadata-sampler')
 _thread.start()
 _value=_scope['main']()
 _stop.set();_thread.join(2)
 _raw=json.dumps(_value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
 _emit('returned',stdout_sha256=hashlib.sha256(_raw).hexdigest())
 sys.stdout.buffer.write(_raw);sys.stdout.buffer.flush()
except BaseException as _error:
 _stop.set()
 if _thread is not None: _thread.join(2)
 _emit('failed',exceptions=_errors(_error))
 raise SystemExit(1) from None
'''


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _error_type(error):
    name = type(error).__name__
    return name if name in ERROR_TYPES and type(error).__module__ in (
        'builtins', 'subprocess', 'asyncio.exceptions') else 'OtherError'


def _prepare(commit):
    bindings = launch._prepare(commit)
    if Path(__file__).resolve() != launch.REPO / SOURCE_FILES[0]:
        raise ValueError('Use the fixed source-bound Mac audit operator')
    for name, sha in bindings['reporting'].items():
        if _hash(launch._git('show', INSTALLED_REVISION + ':' + name)) != sha:
            raise ValueError('Installed reporting bundle must remain unchanged')
    local = dict(bindings['local'])
    for name in SOURCE_FILES:
        raw = launch._raw(name)
        if raw != launch._git('show', commit + ':' + name):
            raise ValueError('Current committed transport sources required')
        local[name] = _hash(raw)
    return dict(bindings, local=local)


def _aliases(bindings):
    values = {'<reporting-bootstrap>': 'bootstrap',
        '<source-bound-final-guard>': 'completion_guard', '<stdin>': 'transport'}
    for base, files, label in ((report.ROOT, bindings['native'], 'execution/'),
            (report.REPORTING, bindings['reporting'], 'reporting/')):
        for name in files:
            if name.endswith('.py'):
                values[str(base / name)] = label + name
    return values


def _program(bindings):
    original = launch._program(bindings, 'collect')
    if not original.endswith(FOOTER) or original.count(FOOTER) != 1:
        raise ValueError('Exact original reporting footer required')
    body = original[:-len(FOOTER)]
    prefix, tail = WRAPPER.split('_program=PROGRAM', 1)
    tail = tail.replace('_aliases=ALIASES', '_aliases=' + repr(_aliases(bindings)))
    tail = tail.replace('_allowed=ERRORS', '_allowed=' + repr(sorted(ERROR_TYPES)))
    tail = tail.replace('wait(INTERVAL)', 'wait(' + repr(SAMPLE_SECONDS) + ')')
    tail = tail.replace('!=PROGRAM_HASH', '!=' + repr(_hash(body.encode())))
    return prefix + '_program=' + repr(body) + tail, _hash(original.encode())


def _number(value):
    return type(value) in (int, float) and 0 <= value <= TRANSPORT_SECONDS + 60


class _Diagnostics:
    def __init__(self, aliases):
        self.sources = frozenset(aliases.values())
        self.records = []
        self.partial = bytearray()
        self.dropping = False
        self.redacted_records = 0

    def _frames(self, value):
        return (isinstance(value, list) and len(value) <= 16
            and all(isinstance(v, dict) and set(v) == {'source', 'line'}
                and v['source'] in self.sources and type(v['line']) is int
                and 0 < v['line'] <= 100000 for v in value))

    def _valid(self, value):
        if not isinstance(value, dict) or not _number(value.get('elapsed_seconds')):
            return False
        common = {'event', 'elapsed_seconds'}; event = value.get('event')
        if event == 'started':
            return (set(value) == common | {'pid', 'start_ticks'}
                and type(value['pid']) is int and value['pid'] > 0
                and type(value['start_ticks']) is int and value['start_ticks'] >= 0)
        if event == 'sample':
            return set(value) == common | {'frames'} and self._frames(value['frames'])
        if event == 'returned':
            sha = value.get('stdout_sha256')
            return (set(value) == common | {'stdout_sha256'} and isinstance(sha, str)
                and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha))
        if event == 'sampling_unavailable':
            return set(value) == common | {'error_type'} and value['error_type'] in ERROR_TYPES
        if event == 'failed':
            errors = value.get('exceptions')
            return (set(value) == common | {'exceptions'} and isinstance(errors, list)
                and 0 < len(errors) <= 8 and all(isinstance(e, dict)
                    and set(e) == {'type', 'frames'} and e['type'] in ERROR_TYPES
                    and self._frames(e['frames']) for e in errors))
        return False

    def _line(self, raw):
        try:
            if not raw.startswith(PREFIX):
                raise ValueError('Unknown diagnostics')
            value = phase._loads(raw[len(PREFIX):])
            if not self._valid(value) or len(self.records) >= MAX_RECORDS:
                raise ValueError('Unrecognised diagnostic schema')
        except (ValueError, TypeError, KeyError, UnicodeError):
            self.redacted_records += 1
            return
        self.records.append(value)
        print(json.dumps(dict(reporting_diagnostic=value), sort_keys=True), file=sys.stderr, flush=True)

    def feed(self, raw):
        for byte in raw:
            if byte == 10:
                if self.dropping: self.redacted_records += 1
                else: self._line(bytes(self.partial))
                self.partial.clear(); self.dropping = False
            elif not self.dropping:
                if len(self.partial) >= LINE_WINDOW:
                    self.partial.clear(); self.dropping = True
                else: self.partial.append(byte)

    def finish(self):
        if self.partial or self.dropping: self.redacted_records += 1
        self.partial.clear(); self.dropping = False
        return dict(records=self.records, redacted_stderr_records=self.redacted_records,
            samples_are_not_passed_checks=True)


class AuditTransportError(ValueError):
    """Allowlisted metadata only; never raw subprocess output."""
    def __init__(self, metadata):
        super().__init__('Audit incomplete; inspect retained metadata without automatic retry')
        self.metadata = metadata


def _close_client(process):
    # Only this Mac-side SSH child. Never signal a native PID, unit or study.
    for handle in (process.stdin, process.stdout, process.stderr):
        if handle is not None:
            try: handle.close()
            except OSError: pass
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)


def _exchange(program, bindings):
    started = time.monotonic(); deadline = started + TRANSPORT_SECONDS
    diagnostics = _Diagnostics(_aliases(bindings)); output = bytearray()
    process = None; status = 'transport_start'; error = None; returncode = None
    try:
        process = subprocess.Popen(launch._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        status = 'transport_send'
        receiver._send(process, program, deadline)
        status = 'transport_read'
        with selectors.DefaultSelector() as selected:
            for handle, kind in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
                os.set_blocking(handle.fileno(), False); selected.register(handle, selectors.EVENT_READ, kind)
            while selected.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status = 'transport_timeout'; raise TimeoutError('Reporting transport elapsed')
                for key, _ in selected.select(min(30, remaining)):
                    try: raw = os.read(key.fd, 65536)
                    except BlockingIOError: continue
                    if not raw:
                        selected.unregister(key.fileobj); continue
                    if key.data == 'stderr': diagnostics.feed(raw)
                    else:
                        if len(output) + len(raw) > launch.WINDOW:
                            status = 'reply_window_exceeded'
                            raise ValueError('Reporting metadata parser window exceeded')
                        output.extend(raw)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = 'transport_timeout'; raise TimeoutError('Reporting transport elapsed')
        returncode = process.wait(timeout=remaining)
        status = 'ssh_exit' if returncode else 'transport_finished'
        if returncode: raise ValueError('SSH operation did not succeed')
    except BaseException as caught:
        error = _error_type(caught)
        if time.monotonic() >= deadline or isinstance(caught, (TimeoutError, subprocess.TimeoutExpired)):
            status = 'transport_timeout'
    finally:
        if process is not None:
            try: _close_client(process)
            except (OSError, subprocess.SubprocessError):
                error = error or 'OSError'; status = 'local_client_cleanup_uncertain'
    metadata = dict(status=status, error_type=error, elapsed_seconds=round(time.monotonic()-started, 6),
        returncode=returncode, stdout_bytes=len(output), diagnostics=diagnostics.finish(),
        automatic_resume=False, native_state_requires_inspection=error is not None)
    if error is not None: raise AuditTransportError(metadata) from None
    return bytes(output), metadata


def _destination():
    path = phase._path(launch.REPO, DESTINATION)
    for parent in (launch.REPO / '.runtime', path.parent): receiver._directory(parent)
    if path.exists() or path.is_symlink():
        raise ValueError('Existing or partial audit operation forbids another attempt')
    return path


def _directory_id(folder):
    receiver._directory(folder); s = folder.lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid)


def _state(folder, identity, hashes):
    if phase._path(launch.REPO, DESTINATION) != folder or _directory_id(folder) != identity:
        raise ValueError('Audit state directory changed')
    for parent in (launch.REPO / '.runtime', folder.parent): receiver._directory(parent)
    if {p.name for p in folder.iterdir()} != set(hashes):
        raise ValueError('Exact retained audit inventory required')
    for name, sha in hashes.items(): launch._raw(DESTINATION + '/' + name, sha)


def _save(folder, identity, hashes, name, raw):
    _state(folder, identity, hashes); receiver._raw_save(folder, name, raw)
    hashes[name] = _hash(raw); _state(folder, identity, hashes)


def _reply(raw, metadata, bindings):
    if (metadata['status'] != 'transport_finished' or metadata['error_type'] is not None
            or metadata['returncode'] != 0):
        raise ValueError('Successful live reporting transport required')
    records = metadata['diagnostics']['records']
    if (not records or records[0]['event'] != 'started'
            or sum(v['event'] == 'started' for v in records) != 1
            or sum(v['event'] == 'returned' for v in records) != 1
            or any(v['event'] == 'failed' for v in records)
            or records[-1]['event'] != 'returned'
            or records[-1]['stdout_sha256'] != _hash(raw)):
        raise ValueError('Exact live completed-return metadata and output bytes required')
    data = phase._loads(raw); archive.validate_snapshot(data, bindings['anchors'])
    archive._same(data['reporting_source_files'], bindings['reporting'])
    return data


def collect(commit):
    """Make ONE actual completed audit; save only validated audit/diagnostics."""
    bindings = _prepare(commit); folder = _destination()
    launch.inspect_deployment(commit)  # Fresh actual preflight, not a collector.
    launch._recheck(bindings); _destination()
    program, original_sha = _program(bindings)
    folder.mkdir(mode=0o700); receiver._sync(folder.parent)
    identity = _directory_id(folder); hashes = {}; stage = 'intent'
    metadata = dict(status='not_started', automatic_resume=False)
    try:
        intent = dict(kind='one_shot_mac_reporting_audit_transport_v1', operator_commit=commit,
            created_utc=datetime.now(timezone.utc).isoformat(), installed_revision=INSTALLED_REVISION,
            operator_sources={n: bindings['local'][n] for n in SOURCE_FILES},
            reporting_source_files=bindings['reporting'], native_files=bindings['native'],
            original_program_sha256=original_sha, transmitted_program_sha256=_hash(program.encode()),
            transport_seconds=TRANSPORT_SECONDS, sample_seconds=SAMPLE_SECONDS,
            original_bootstrap_main_unchanged=True, automatic_resume=False, paid_launch_ready=False)
        _save(folder, identity, hashes, 'intent.json', _json(intent))
        launch._recheck(bindings); _state(folder, identity, hashes)
        stage = 'native_operation'; raw, metadata = _exchange(program, bindings)
        stage = 'local_source_recheck'; launch._recheck(bindings)
        stage = 'reply_validation'; data = _reply(raw, metadata, bindings)
        stage = 'final_source_recheck'; launch._recheck(bindings)
        stage = 'retaining_verified_output'
        _save(folder, identity, hashes, 'diagnostics.json', _json(metadata))
        _save(folder, identity, hashes, 'snapshot.json', raw)
        launch._recheck(bindings); _state(folder, identity, hashes)
        result = dict(kind='verified_completed_audit_not_backup_or_admission_v1',
            operator_commit=commit, observed_utc=datetime.now(timezone.utc).isoformat(),
            snapshot_file_sha256=hashes['snapshot.json'], diagnostics_file_sha256=hashes['diagnostics.json'],
            elapsed_seconds=metadata['elapsed_seconds'], completed_final_audit_verified=True,
            off_server_backup_verified=False, paid_launch_ready=False, automatic_resume=False,
            full89=data['aggregates']['full89'])
        _save(folder, identity, hashes, 'result.json', _json(result))
        launch._recheck(bindings); _state(folder, identity, hashes)
        return result
    except BaseException as error:
        if isinstance(error, AuditTransportError): metadata = error.metadata
        failure = dict(kind='incomplete_reporting_audit_transport_v1', stage=stage,
            error_type=_error_type(error), transport=metadata, automatic_resume=False,
            completed_final_audit_verified=False, paid_launch_ready=False,
            native_state_requires_inspection=True)
        try: _save(folder, identity, hashes, 'failure.json', _json(failure))
        except (OSError, ValueError): failure['failure_state_write_verified'] = False
        raise AuditTransportError(failure) from None
