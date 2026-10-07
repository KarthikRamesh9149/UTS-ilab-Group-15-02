"""Exclusive trial lifecycle records and provider cooldown state.

The host gateway owns these private files and serializes their updates."""
import json
import math
import os
from pathlib import Path
import secrets
import stat
import time
import re

from .private_io import durable_json, private_directory

TRANSIENT_HTTP = frozenset((408, 429, 500, 502, 503, 504))


class Clock:
    def __init__(self):
        self.boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def monotonic(self): return time.monotonic()
    def wall(self): return time.time()


def private_read(path):
    path = Path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW)) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Owned private runtime record required')
        value = json.load(handle)
    if not isinstance(value, dict): raise ValueError('Object runtime record required')
    return value


def finite(value):
    try:
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError
        return float(value)
    except (ValueError, OverflowError):
        raise ValueError('Invalid runtime timestamp') from None


def activate(runtime, trial_id, timeout, settings, clock):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
        raise ValueError('Invalid trial identity')
    timeout = finite(timeout)
    if not timeout: raise ValueError('Positive official deadline required')
    folder = private_directory(Path(runtime) / 'retry-lifecycle')
    durable_json(folder / (trial_id + '.json'), dict(trial_id=trial_id,
        model_protocol_sha256=settings.fingerprint(), boot_id=clock.boot_id,
        deadline_monotonic=clock.monotonic() + timeout,
        deadline_utc=clock.wall() + timeout))


def deadline_for(runtime, trial_id, settings, clock):
    value = private_read(Path(runtime) / 'retry-lifecycle' / (trial_id + '.json'))
    if (value.get('trial_id') != trial_id or value.get('model_protocol_sha256') != settings.fingerprint()
            or value.get('boot_id') != clock.boot_id):
        raise ValueError('Authoritative trial lifecycle mismatch')
    return finite(value['deadline_monotonic'])


class Cooldown:
    """One provider/model cooldown shared by successive trial gateway processes."""
    def __init__(self, runtime, clock):
        self.path = Path(runtime) / 'provider-cooldown.json'
        self.clock = clock
        self.count = 0
        self.until = 0.
        if self.path.exists() or self.path.is_symlink():
            state = private_read(self.path)
            if set(state) != {'schema_version', 'boot_id', 'until_monotonic', 'until_utc', 'rejections'} or state['schema_version'] != 1:
                raise ValueError('Invalid cooldown schema')
            if type(state['rejections']) is not int or state['rejections'] < 0:
                raise ValueError('Invalid cooldown rejection count')
            self.count = state['rejections']
            expiry = finite(state['until_monotonic'])
            wall_expiry = finite(state['until_utc'])
            self.until = expiry if state['boot_id'] == clock.boot_id else clock.monotonic() + max(0., wall_expiry - clock.wall())

    def update(self, until, count):
        until = finite(until)
        self.until, self.count = until, count
        value = dict(schema_version=1, boot_id=self.clock.boot_id, until_monotonic=until,
            until_utc=self.clock.wall() + max(0., until - self.clock.monotonic()), rejections=count)
        temp = self.path.with_name('.cooldown-' + secrets.token_hex(12) + '.json')
        try:
            durable_json(temp, value)
            os.replace(temp, self.path)
            descriptor = os.open(self.path.parent, os.O_RDONLY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
        finally:
            temp.unlink(missing_ok=True)

    def reject(self, decision):
        if decision.not_before_monotonic is None:
            raise ValueError('Provider cooldown cannot be determined safely')
        self.update(max(self.until, decision.not_before_monotonic), self.count + 1)

    def success(self):
        self.update(self.clock.monotonic(), 0)

    def wait(self, deadline, cancelled):
        while self.clock.monotonic() < self.until:
            remaining = deadline - self.clock.monotonic()
            if cancelled.is_set() or remaining <= 0: return False
            cancelled.wait(min(1., self.until - self.clock.monotonic(), remaining))
        return not cancelled.is_set() and self.clock.monotonic() < deadline


def deadline_factory(factory, root, settings, *, clock=None):
    """Activate the official clock when the native agent begins, after setup."""
    def create(**kwargs):
        agent = factory(**kwargs)
        native_run = agent.run
        async def run(*args, **options):
            runtime = Path(root) / '.runtime/stage2'
            trial_id = kwargs['paths'].trial_dir.name
            activate(runtime, trial_id, kwargs['agent_timeout_seconds'], settings, clock or Clock())
            return await native_run(*args, **options)
        agent.run = run
        return agent
    create.harness = factory.harness
    create.model_protocol_sha256 = factory.model_protocol_sha256
    return create
