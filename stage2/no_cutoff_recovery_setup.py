"""One-use metadata observer for the unchanged recovery preparation callback.

This component neither admits nor dispatches a trial. The future recovery host
must supply the real qualified environment, own lifecycle/locks, retain this
metadata with the new trial, and authenticate its producer. No file is written,
no command is retried, and no exception text or command output is retained here.
"""
import asyncio
from copy import deepcopy
import hashlib
import inspect
import math
import os
from pathlib import Path
import stat
import sys
import threading
import time
import types

import task_preparation as preparation

PREPARATION_SHA256 = 'fb1cf6c9e3a6ee79579de2ebcbfd0f97cac39e989000bbb77b20a00f114b6815'
COMMAND_SHA256 = 'ce4b19308a2c727d159110d218fb6a8d5492d1f3842b2156d3e9fc9500fc2d76'
SOURCE_FILES = ('no_cutoff_recovery_setup.py', 'test_no_cutoff_recovery_setup.py',
    'protocols/custom_setup_recovery_instrumentation_20260929.md')
KIND = 'recovery_preparation_observation_not_admission'
_ERROR_TYPES = (RuntimeError, TimeoutError, OSError, ConnectionError,
    ConnectionResetError, ConnectionAbortedError, BrokenPipeError,
    FileNotFoundError, PermissionError, ValueError, TypeError, AttributeError,
    KeyError, OverflowError, MemoryError, asyncio.CancelledError,
    KeyboardInterrupt, SystemExit)
_ERROR_NAMES = frozenset(t.__name__ for t in _ERROR_TYPES) | {'OtherException'}
_STAGES = frozenset({'root_context_create', 'root_context_enter',
    'command_binding', 'command_execution', 'root_context_exit', 'preparation_result'})


def _error(exc):
    # Arbitrary subclass names and messages can themselves contain private data.
    return type(exc).__name__ if type(exc) in _ERROR_TYPES else 'OtherException'


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
        info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _source(path):
    if path != path.resolve() or path.is_symlink():
        raise ValueError('Canonical source file required')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError('Regular single-link source required')
        raw = stream.read()
        if (_identity(before) != _identity(os.fstat(stream.fileno()))
                or _identity(before) != _identity(path.lstat())):
            raise ValueError('Source changed during read')
    return raw


def _bindings():
    directory = Path(__file__).resolve().parent
    if (Path(__file__).name != SOURCE_FILES[0] or Path(__file__) != directory / SOURCE_FILES[0]
            or sys.modules[__name__].__spec__.origin != str(directory / SOURCE_FILES[0])):
        raise ValueError('Use the actual canonical observer source origin')
    path = directory / 'task_preparation.py'
    raw = _source(path)
    if hashlib.sha256(raw).hexdigest() != PREPARATION_SHA256:
        raise ValueError('Keep the exact original preparation source')
    function = preparation.refresh_package_metadata
    expected = next(item for item in compile(raw, str(path), 'exec',
        dont_inherit=True, optimize=sys.flags.optimize).co_consts
        if isinstance(item, types.CodeType) and item.co_name == 'refresh_package_metadata')
    if (Path(preparation.__file__) != path or preparation.__spec__.origin != str(path)
            or not isinstance(function, types.FunctionType)
            or function.__code__ != expected or function.__globals__ is not vars(preparation)
            or function.__module__ != 'task_preparation' or function.__qualname__ != 'refresh_package_metadata'
            or function.__defaults__ is not None or function.__kwdefaults__ is not None):
        raise ValueError('Actual original preparation function and origin required')
    # Execute only this already hash-pinned, stdlib-only source in an isolated
    # namespace to compare its globals, not to perform environment preparation.
    original = {}
    exec(compile(raw, str(path), 'exec', dont_inherit=True), original)
    if any(getattr(preparation, key) != original[key] for key in
            ('COMMAND', 'SOURCE_REPAIR', 'SNAPSHOT')):
        raise ValueError('Original command or security-source controls changed')
    return {'task_preparation.py': PREPARATION_SHA256,
        **{name: hashlib.sha256(_source(directory / name)).hexdigest() for name in SOURCE_FILES}}


def _output(value, *, present):
    if not present:
        return dict(observation='missing', utf8_bytes=None, sha256=None)
    if value is None:
        return dict(observation='null', utf8_bytes=None, sha256=None)
    if type(value) is not str:
        return dict(observation='unsupported_type', utf8_bytes=None, sha256=None)
    digest, count = hashlib.sha256(), 0
    try:
        # These are UTF-8 encodings of returned text, not original wire bytes.
        # Chunking limits temporary allocation without truncating the evidence.
        for start in range(0, len(value), 16384):
            chunk = value[start:start + 16384].encode('utf-8')
            digest.update(chunk)
            count += len(chunk)
    except UnicodeEncodeError:
        return dict(observation='not_utf8_encodable', utf8_bytes=None, sha256=None)
    return dict(observation='text_utf8', utf8_bytes=count, sha256=digest.hexdigest())


def _fields(result):
    # Harbor's ExecResult stores its fields in __dict__. Do not invoke arbitrary
    # result properties, __str__, model_dump or repr for diagnostic purposes.
    absent = object()
    values = {name: inspect.getattr_static(result, name, absent)
        for name in ('return_code', 'stdout', 'stderr')}
    values = {name: value for name, value in values.items() if value is not absent}
    code = values.get('return_code')
    return dict(return_code=code if type(code) is int else None,
        return_code_observation='integer' if type(code) is int else 'unavailable',
        stdout=_output(values.get('stdout'), present='stdout' in values),
        stderr=_output(values.get('stderr'), present='stderr' in values))


class PreparationObservation:
    """Pass ``prepare`` as the existing lifecycle's prepare_environment callback.

    It is single-use on its creating process/main thread. execute_phases owns a
    setup child task, so the first callback binds that child, not its parent.
    The parent can read completed metadata afterward. This is not a dispatch
    scope or a substitute for that parent's live authenticated recovery scope.
    """
    def __init__(self):
        if threading.current_thread() is not threading.main_thread():
            raise ValueError('Preparation observer requires the main thread')
        self._pid = os.getpid()
        self._thread = threading.get_ident()
        self._sources = _bindings()
        self._used = self._done = False
        self._task = None
        self._escaping = None
        self._stage = 'root_context_create'
        self._issues = set()
        self._data = dict(kind=KIND, schema_version=1, sources=deepcopy(self._sources),
            command_sha256=COMMAND_SHA256,
            command_timeout_seconds=180, terminal=None, error_class=None,
            failure_stage=None, elapsed_seconds=None, preparation_status=None,
            command=dict(terminal='not_started', error_class=None,
                elapsed_seconds=None, return_code=None, return_code_observation='unavailable',
                stdout=_output(None, present=False), stderr=_output(None, present=False)),
            source_verified_before=False, source_verified_after=False,
            diagnostic_issues=[], observation_complete=False,
            infrastructure_category='unknown', paid_launch_ready=False,
            native_qualification=False, historical_cause_established=False)

    def __copy__(self):
        raise TypeError('Preparation observations cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('Preparation observations cannot be copied')

    def __reduce_ex__(self, protocol):
        raise TypeError('Preparation observations cannot be saved as handles')

    def _owner(self):
        if (os.getpid() != self._pid or threading.get_ident() != self._thread
                or threading.current_thread() is not threading.main_thread()):
            raise ValueError('Preparation observer lifetime changed')

    def _live(self):
        self._owner()
        if self._done or not self._used or asyncio.current_task() is not self._task:
            raise ValueError('Only the actual single preparation callback may execute')

    def _record(self, operation, *args):
        try:
            return operation(*args)
        except Exception:
            # Observability must not replace the original command/phase outcome.
            # An incomplete diagnostic is explicit and cannot pass later audit.
            self._issues.add('metadata_capture_failed')
            return None

    def _elapsed(self, started):
        value = time.monotonic() - started
        if not math.isfinite(value) or value < 0:
            raise ValueError('Monotonic elapsed time required')
        return value

    async def prepare(self, environment):
        self._owner()
        if self._used:
            raise ValueError('Preparation callback cannot be reused or retried')
        self._used = True
        self._task = asyncio.current_task()
        # This gate precedes all calls to the real environment. The caller must
        # still verify protected native sources before constructing this object.
        try:
            if _bindings() != self._sources:
                raise ValueError('Preparation observer sources changed')
            self._data['source_verified_before'] = True
        except BaseException:
            self._done = True
            self._task = None
            self._data.update(terminal='guard_refused', infrastructure_category='source_guard_refused')
            self._issues.add('source_binding_failed')
            raise
        started = time.monotonic()
        try:
            value = await preparation.refresh_package_metadata(_Environment(environment, self))
        except BaseException as exc:
            stage = self._escaping[1] if self._escaping is not None and self._escaping[0] is exc else self._stage
            self._data.update(terminal='cancelled' if isinstance(exc, asyncio.CancelledError) else 'raised',
                error_class=_error(exc), failure_stage=stage)
            raise
        else:
            self._data.update(terminal='returned', preparation_status=value['status'])
            return value
        finally:
            self._data['elapsed_seconds'] = self._record(self._elapsed, started)
            try:
                if _bindings() != self._sources:
                    raise ValueError('Preparation observer sources changed')
                self._data['source_verified_after'] = True
            except Exception:
                self._issues.add('source_binding_failed')
            self._done = True
            self._task = None
            self._escaping = None

    def metadata(self):
        self._owner()
        if not self._done:
            raise ValueError('Completed callback observation required')
        try:
            if _bindings() != self._sources:
                raise ValueError('Preparation observation source binding changed')
        except Exception:
            self._issues.add('source_binding_failed')
            raise
        value = deepcopy(self._data)
        value['diagnostic_issues'] = sorted(self._issues)
        value['infrastructure_category'] = _category(value)
        command = value['command']
        value['observation_complete'] = bool(value['source_verified_before']
            and value['source_verified_after'] and not self._issues
            and value['elapsed_seconds'] is not None
            and (command['terminal'] == 'not_started' or command['elapsed_seconds'] is not None)
            and (command['terminal'] != 'returned' or
                (command['return_code_observation'] == 'integer'
                 and all(command[n]['observation'] in {'text_utf8', 'null'} for n in ('stdout', 'stderr')))))
        validate(value)
        return value


class _Context:
    def __init__(self, context, observation):
        self.context, self.observation = context, observation

    def __enter__(self):
        self.observation._live()
        self.observation._stage = 'root_context_enter'
        return self.context.__enter__()

    def __exit__(self, kind, error, traceback):
        self.observation._live()
        self.observation._stage = 'root_context_exit'
        result = self.context.__exit__(kind, error, traceback)
        self.observation._stage = 'preparation_result'
        return result


class _Environment:
    def __init__(self, environment, observation):
        self.environment, self.observation = environment, observation

    def with_default_user(self, user):
        self.observation._live()
        if user != 'root':
            raise ValueError('Only unchanged root preparation is observed')
        self.observation._stage = 'root_context_create'
        return _Context(self.environment.with_default_user(user), self.observation)

    async def exec(self, command, *, timeout_sec):
        observation = self.observation
        observation._live()
        observation._stage = 'command_binding'
        try:
            if (type(command) is not str or hashlib.sha256(command.encode()).hexdigest() != COMMAND_SHA256
                    or type(timeout_sec) is not int or timeout_sec != 180):
                raise ValueError('Only the unchanged preparation command is observed')
            if observation._data['command']['terminal'] != 'not_started':
                raise ValueError('No automatic preparation command retries')
            if _bindings() != observation._sources:
                raise ValueError('Actual preparation source changed before command')
        except Exception as exc:
            observation._issues.add('source_binding_failed')
            observation._escaping = (exc, 'command_binding')
            raise
        observation._stage = 'command_execution'
        record = observation._data['command']
        record['terminal'] = 'running'
        started = time.monotonic()
        try:
            result = await self.environment.exec(command, timeout_sec=timeout_sec)
        except BaseException as exc:
            observation._escaping = (exc, 'command_execution')
            record.update(terminal='cancelled' if isinstance(exc, asyncio.CancelledError) else 'raised',
                error_class=_error(exc))
            record['elapsed_seconds'] = observation._record(observation._elapsed, started)
            raise
        else:
            record['elapsed_seconds'] = observation._record(observation._elapsed, started)
            record['terminal'] = 'returned'
            fields = observation._record(_fields, result)
            if fields is not None:
                record.update(fields)
            return result


def _category(value):
    if value['terminal'] == 'guard_refused':
        return 'source_guard_refused'
    stage, command = value['failure_stage'], value['command']
    if stage == 'command_binding':
        return 'source_guard_refused'
    if stage in {'root_context_create', 'root_context_enter', 'root_context_exit'}:
        return 'default_user_context_exception'
    if value['terminal'] == 'cancelled':
        return 'preparation_cancelled'
    if stage == 'command_execution' and command['terminal'] == 'raised':
        return 'command_timeout_exception' if command['error_class'] == 'TimeoutError' else 'command_execution_exception'
    if (stage == 'preparation_result' and value['error_class'] == 'RuntimeError'
            and command['terminal'] == 'returned' and command['return_code_observation'] == 'integer'
            and command['return_code'] != 0):
        return 'preparation_command_nonzero'
    if value['terminal'] == 'returned':
        return 'preparation_returned'
    return 'unknown'


def _validate(value):
    keys = {'kind', 'schema_version', 'sources', 'command_sha256', 'command_timeout_seconds',
        'terminal', 'error_class', 'failure_stage', 'elapsed_seconds', 'preparation_status',
        'command', 'source_verified_before', 'source_verified_after', 'diagnostic_issues',
        'observation_complete', 'infrastructure_category', 'paid_launch_ready',
        'native_qualification', 'historical_cause_established'}
    if type(value) is not dict or set(value) != keys or value['kind'] != KIND:
        raise ValueError('Exact non-admitting preparation metadata required')
    def sha(item):
        return type(item) is str and len(item) == 64 and set(item) <= set('0123456789abcdef')
    def seconds(item):
        return type(item) in (int, float) and math.isfinite(item) and item >= 0
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['command_timeout_seconds']) is not int or value['command_timeout_seconds'] != 180
            or type(value['sources']) is not dict or set(value['sources']) !=
                {'task_preparation.py', *SOURCE_FILES}
            or value['sources']['task_preparation.py'] != PREPARATION_SHA256
            or not all(sha(v) for v in value['sources'].values()) or value['command_sha256'] != COMMAND_SHA256
            or any(value[n] is not False for n in ('paid_launch_ready', 'native_qualification', 'historical_cause_established'))
            or any(type(value[n]) is not bool for n in ('source_verified_before', 'source_verified_after', 'observation_complete'))):
        raise ValueError('Preparation metadata bindings or authority changed')
    terminal = value['terminal']
    if (terminal not in {'returned', 'raised', 'cancelled', 'guard_refused'}
            or value['error_class'] not in _ERROR_NAMES | {None}
            or value['failure_stage'] not in _STAGES | {None}
            or (value['elapsed_seconds'] is not None and not seconds(value['elapsed_seconds']))
            or type(value['diagnostic_issues']) is not list
            or value['diagnostic_issues'] != sorted(set(value['diagnostic_issues']))
            or not set(value['diagnostic_issues']) <= {'metadata_capture_failed', 'source_binding_failed'}):
        raise ValueError('Unsupported preparation diagnostic metadata')
    if terminal in {'returned', 'guard_refused'}:
        if value['error_class'] is not None or value['failure_stage'] is not None:
            raise ValueError('A non-exception cannot fabricate exception metadata')
    elif value['error_class'] is None or value['failure_stage'] is None:
        raise ValueError('Actual exception category and stage required')
    if ((terminal == 'returned' and value['preparation_status'] not in {'refreshed', 'not_applicable'})
            or (terminal != 'returned' and value['preparation_status'] is not None)):
        raise ValueError('Preparation status must match the actual return')
    command = value['command']
    if (type(command) is not dict or set(command) != {'terminal', 'error_class', 'elapsed_seconds',
            'return_code', 'return_code_observation', 'stdout', 'stderr'}
            or command['terminal'] not in {'not_started', 'returned', 'raised', 'cancelled'}
            or command['error_class'] not in _ERROR_NAMES | {None}
            or (command['elapsed_seconds'] is not None and not seconds(command['elapsed_seconds']))):
        raise ValueError('Exact command observation required')
    if command['terminal'] in {'raised', 'cancelled'}:
        if command['error_class'] is None:
            raise ValueError('Observed command exception required')
    elif command['error_class'] is not None:
        raise ValueError('Command exception cannot be invented')
    if command['return_code_observation'] == 'integer':
        if command['terminal'] != 'returned' or type(command['return_code']) is not int:
            raise ValueError('Only an actually returned integer exit code is allowed')
    elif command['return_code_observation'] != 'unavailable' or command['return_code'] is not None:
        raise ValueError('Unknown command exit code stays null')
    for name in ('stdout', 'stderr'):
        field = command[name]
        if type(field) is not dict or set(field) != {'observation', 'utf8_bytes', 'sha256'}:
            raise ValueError('Output metadata only, no arbitrary text')
        if field['observation'] == 'text_utf8':
            if (command['terminal'] != 'returned' or type(field['utf8_bytes']) is not int
                    or field['utf8_bytes'] < 0 or not sha(field['sha256'])):
                raise ValueError('Returned text hashes and UTF-8 byte counts required')
        elif (field['observation'] not in {'missing', 'null', 'unsupported_type', 'not_utf8_encodable'}
                or field['utf8_bytes'] is not None or field['sha256'] is not None):
            raise ValueError('Unavailable output hashes and lengths remain null')
        if command['terminal'] != 'returned' and field['observation'] != 'missing':
            raise ValueError('No command output was returned')
    if command['terminal'] == 'not_started' and command['elapsed_seconds'] is not None:
        raise ValueError('No command timing can be invented')
    if (command['terminal'] == 'not_started' and terminal != 'guard_refused'
            and value['failure_stage'] not in {'root_context_create', 'root_context_enter', 'command_binding'}):
        raise ValueError('Missing command must agree with the observed failure stage')
    if value['failure_stage'] == 'command_binding' and 'source_binding_failed' not in value['diagnostic_issues']:
        raise ValueError('Command binding refusal must remain latched')
    if value['failure_stage'] == 'command_execution' and command['terminal'] not in {'raised', 'cancelled'}:
        raise ValueError('Execution exception must agree with actual command observation')
    if terminal == 'returned' and (command['terminal'] != 'returned' or
            (command['return_code_observation'] == 'integer' and command['return_code'] != 0)):
        raise ValueError('Original preparation cannot return after a missing or nonzero command')
    if terminal == 'guard_refused' and (value['source_verified_before'] or value['source_verified_after']
            or command['terminal'] != 'not_started' or value['elapsed_seconds'] is not None
            or 'source_binding_failed' not in value['diagnostic_issues']):
        raise ValueError('Guard refusal occurs before preparation starts')
    if (value['elapsed_seconds'] is not None and command['elapsed_seconds'] is not None
            and command['elapsed_seconds'] > value['elapsed_seconds']):
        raise ValueError('Command duration must fit inside the callback body')
    complete = bool(value['source_verified_before'] and value['source_verified_after']
        and not value['diagnostic_issues'] and value['elapsed_seconds'] is not None
        and (command['terminal'] == 'not_started' or command['elapsed_seconds'] is not None)
        and (command['terminal'] != 'returned' or
            (command['return_code_observation'] == 'integer'
             and all(command[n]['observation'] in {'text_utf8', 'null'} for n in ('stdout', 'stderr')))))
    if value['observation_complete'] is not complete or value['infrastructure_category'] != _category(value):
        raise ValueError('Diagnostic completeness or infrastructure category changed')
    return deepcopy(value)


def validate(value):
    """Validate metadata only; never authenticate a producer or admit execution."""
    try:
        return _validate(value)
    except (KeyError, TypeError, OverflowError):
        raise ValueError('Malformed preparation metadata') from None
