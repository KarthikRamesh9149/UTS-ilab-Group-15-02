"""Durable, metadata-only trace spool for the CETUS study.

No network calls or implicit SDK telemetry. A future qualified Harbor runner
must call this hook; this file alone is not a live Harbor integration.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading

KINDS = {'trial', 'setup', 'agent', 'generation', 'tool', 'graph', 'verifier', 'cleanup'}
STATUSES = {'ok', 'error', 'timeout', 'interrupted'}
HARNESS = {'terminus-2', 'openhands', 'C0', 'C1', 'C2', 'C3', 'C4', 'C0-NC'}
LABEL = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,160}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
COUNTS = {'input_tokens', 'output_tokens', 'requests', 'tool_calls', 'repairs', 'charged_nanodollars'}
NUMBERS = {'duration_seconds', 'gpu_allocation_seconds', 'cpu_allocation_seconds'}


def validate(event):
    allowed = {'event_id', 'trace_id', 'trial_id', 'kind', 'sequence', 'harness',
               'task_id', 'status', 'protocol_sha256', 'started_ns', 'ended_ns',
               'reward', 'metrics'}
    if set(event) != allowed:
        raise ValueError('Unexpected trace fields; raw text and credentials are not exportable')
    for key in ('trial_id', 'task_id'):
        if not isinstance(event[key], str) or not LABEL.fullmatch(event[key]):
            raise ValueError('Invalid trace identifier')
    for key in ('protocol_sha256', 'event_id', 'trace_id'):
        if not isinstance(event[key], str) or not HASH.fullmatch(event[key]):
            raise ValueError('Invalid trace fingerprint')
    if event['kind'] not in KINDS or event['harness'] not in HARNESS or event['status'] not in STATUSES:
        raise ValueError('Unregistered observation')
    for key in ('sequence', 'started_ns', 'ended_ns'):
        if type(event[key]) is not int or event[key] < 0:
            raise ValueError('Invalid trace time/sequence')
    if event['ended_ns'] < event['started_ns']:
        raise ValueError('Negative observation duration')
    reward = event['reward']
    if reward is not None and (event['kind'] != 'verifier' or type(reward) not in (int, float) or reward not in (0, 1)):
        raise ValueError('Only the verifier may supply binary reward')
    metrics = event['metrics']
    if not isinstance(metrics, dict) or not set(metrics) <= COUNTS | NUMBERS:
        raise ValueError('Unknown metrics')
    for key, value in metrics.items():
        if key in COUNTS:
            if type(value) is not int or value < 0:
                raise ValueError('Invalid count')
        elif type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid measurement')
    identity = event['protocol_sha256'] + ':' + event['trial_id']
    if event['trace_id'] != hashlib.sha256(identity.encode()).hexdigest():
        raise ValueError('Trace identity mismatch')
    if event['event_id'] != hashlib.sha256((identity + ':' + str(event['sequence'])).encode()).hexdigest():
        raise ValueError('Event identity mismatch')
    return event


def observation(*, trial_id, task_id, harness, protocol_sha256, kind, sequence,
                started_ns, ended_ns, status='ok', metrics=None, reward=None):
    identity = protocol_sha256 + ':' + trial_id
    return validate(dict(trial_id=trial_id, task_id=task_id, harness=harness,
        protocol_sha256=protocol_sha256, kind=kind, sequence=sequence,
        started_ns=started_ns, ended_ns=ended_ns, status=status, metrics=metrics or {}, reward=reward,
        trace_id=hashlib.sha256(identity.encode()).hexdigest(),
        event_id=hashlib.sha256((identity + ':' + str(sequence)).encode()).hexdigest()))


class TraceSpool:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink() or self.directory.stat().st_mode & 0o077:
            raise ValueError('Private non-symlink trace directory required')

    def record(self, event):
        validate(event)
        payload = json.dumps(event, sort_keys=True, allow_nan=False).encode() + b'\n'
        destination = self.directory / (event['event_id'] + '.json')
        # Write a private, fsynced temporary file, then link atomically without
        # overwriting an event. This also handles concurrent duplicate writers.
        import tempfile
        fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=self.directory)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_symlink() or destination.read_bytes() != payload:
                    raise ValueError('Conflicting event identity')
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            os.unlink(temporary)
        return event['event_id']

    def events(self):
        events = []
        for path in sorted(self.directory.glob('*.json')):
            if path.is_symlink():
                raise ValueError('Symlink in spool')
            event = validate(json.loads(path.read_text()))
            if path.stem != event['event_id']:
                raise ValueError('Spool filename mismatch')
            events.append(event)
        return sorted(events, key=lambda e: (e['trace_id'], e['sequence']))


class PhaseRecorder:
    """Passive execute_phases observer; no SDK, network, tools or model access.

    Construct a new recorder and a fresh per-attempt spool for every trial.
    Partial attempts cannot be replayed under the same identity.
    """
    def __init__(self, spool, *, trial_id, task_id, harness, protocol_sha256):
        self.spool = spool
        self.identity = dict(trial_id=trial_id, task_id=task_id, harness=harness,
                             protocol_sha256=protocol_sha256)
        # Validate identifiers before the lifecycle can start executing.
        observation(**self.identity, kind='trial', sequence=0, started_ns=0, ended_ns=0)
        if any(e['trial_id'] == trial_id for e in spool.events()):
            raise ValueError('Trial trace already exists; replay prohibited')
        self.sequence = 1
        self.closed = False
        self._lock = threading.RLock()

    def __call__(self, *, kind, started_ns, ended_ns, seconds, status='ok', reward=None, metrics=None):
        with self._lock:
            return self._record(kind=kind, started_ns=started_ns, ended_ns=ended_ns, seconds=seconds,
                                status=status, reward=reward, metrics=metrics)

    def _record(self, *, kind, started_ns, ended_ns, seconds, status, reward, metrics):
        if self.closed:
            raise ValueError('Trial trace already closed')
        sequence = 0 if kind == 'trial' else self.sequence
        self.sequence += 1
        event = observation(**self.identity, kind=kind, sequence=sequence,
            started_ns=started_ns, ended_ns=ended_ns, status=status, reward=reward,
            metrics={**(metrics or {}), 'duration_seconds': seconds})
        self.spool.record(event)
        self.closed = kind == 'trial'
