"""Internal reporting-only transport; no deployment, audit or paid public entry.

Fixed source-bound callers supply the exact bootstrap and command. Retains the
previous metadata-only sampler without importing any project module here.
Only an owned Mac SSH client may be signalled on failure. A native audit child
is never signalled; uncertain remote work requires process/lock inspection.
"""
import hashlib
import json
import os
import selectors
import subprocess
import sys
import time

WINDOW = 64 * 1024 * 1024
BACKUP_SECONDS = 2700  # One 1800-second audit plus the 900-second archive transfer.
HANDOFF_SECONDS = 4500  # Operator audit + transfer + receiver audit; not task time.
TRANSPORT_SECONDS = 1800  # Reporting connection only, never a benchmark deadline.
SAMPLE_SECONDS = 30
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



def _wrap(original, aliases):
    if not original.endswith(FOOTER) or original.count(FOOTER) != 1:
        raise ValueError('Exact reporting footer required')
    body = original[:-len(FOOTER)]
    prefix, tail = WRAPPER.split('_program=PROGRAM', 1)
    tail = tail.replace('_aliases=ALIASES', '_aliases=' + repr(aliases))
    tail = tail.replace('_allowed=ERRORS', '_allowed=' + repr(sorted(ERROR_TYPES)))
    tail = tail.replace('wait(INTERVAL)', 'wait(' + repr(SAMPLE_SECONDS) + ')')
    tail = tail.replace('!=PROGRAM_HASH', '!=' + repr(_hash(body.encode())))
    return prefix + '_program=' + repr(body) + tail


def _loads(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise ValueError('Duplicate diagnostic field')
            result[key] = value
        return result
    def invalid(value): raise ValueError('Non-finite diagnostic number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _send(process, program, deadline):
    descriptor = process.stdin.fileno(); os.set_blocking(descriptor, False)
    remaining = memoryview(program.encode())
    try:
        with selectors.DefaultSelector() as selected:
            selected.register(process.stdin, selectors.EVENT_WRITE)
            while remaining:
                wait = deadline - time.monotonic()
                if wait <= 0 or not selected.select(min(30, wait)):
                    if time.monotonic() >= deadline: raise TimeoutError('Reporting bootstrap transport expired')
                    continue
                try: count = os.write(descriptor, remaining[:65536])
                except BlockingIOError: continue
                if count <= 0: raise ValueError('Incomplete reporting bootstrap write')
                remaining = remaining[count:]
    finally:
        process.stdin.close()


def _completed(raw, metadata):
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
            value = _loads(raw[len(PREFIX):])
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


def _close_client(process, native_child=False):
    # Only this Mac-side SSH child. Never signal a native PID, unit or study.
    for handle in (process.stdin, process.stdout, process.stderr):
        if handle is not None:
            try: handle.close()
            except OSError: pass
    if not native_child and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)


def _exchange(program, aliases, command, environment, *, cwd=None):
    started = time.monotonic(); deadline = started + TRANSPORT_SECONDS
    diagnostics = _Diagnostics(aliases); output = bytearray()
    process = None; status = 'transport_start'; error = None; returncode = None
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, env=environment, cwd=cwd)
        status = 'transport_send'
        _send(process, program, deadline)
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
                        if len(output) + len(raw) > WINDOW:
                            status = 'reply_window_exceeded'
                            raise ValueError('Reporting metadata parser window exceeded')
                        output.extend(raw)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = 'transport_timeout'; raise TimeoutError('Reporting transport elapsed')
        returncode = process.wait(timeout=remaining)
        status = 'child_exit' if returncode else 'transport_finished'
        if returncode: raise ValueError('Reporting process did not succeed')
    except BaseException as caught:
        error = _error_type(caught)
        if time.monotonic() >= deadline or isinstance(caught, (TimeoutError, subprocess.TimeoutExpired)):
            status = 'transport_timeout'
    finally:
        if process is not None:
            try: _close_client(process, native_child=cwd is not None)
            except (OSError, subprocess.SubprocessError):
                error = error or 'OSError'; status = 'local_client_cleanup_uncertain'
    metadata = dict(status=status, error_type=error, elapsed_seconds=round(time.monotonic()-started, 6),
        returncode=returncode, stdout_bytes=len(output), diagnostics=diagnostics.finish(),
        automatic_resume=False, native_state_requires_inspection=error is not None)
    if error is not None: raise AuditTransportError(metadata) from None
    return bytes(output), metadata
