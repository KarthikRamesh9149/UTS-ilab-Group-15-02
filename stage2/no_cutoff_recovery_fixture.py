"""Isolated fake-model gateway for six recovery lifecycle cases, never paid.

Only a fixed synthetic credential and network=none are accepted. The finite
dialogue exercises original C0-NC tools; it adds no limit to the paid gateway.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from completion_wait import validate_completion_wait
from credit_only_gateway import prepare_credit_request
from gateway_policy import MODEL, ENDPOINT
from no_cutoff_recovery_gateway import NoCutoffRecoverySession
import no_cutoff_recovery_policy as policy
from openrouter_transport import TransportError, error_diagnostic

FIXTURE_FILE = 'no-cutoff-recovery-fixture.json'
FIXTURE_KIND = 'isolated_synthetic_C0_NC_recovery_not_paid_registration'
SYNTHETIC_KEY = 'synthetic-not-a-real-key'
EXPECTED_LOGICAL = 2
MARKER = 'UTS_RECOVERY_OBSERVED'
COMMAND = "printf '%s' UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result; printf '%s%s\\n' UTS_RECOVERY_ OBSERVED"
TOKEN = 'call_recovery_marker'
NO_MODEL = frozenset({'prepare_nonzero', 'prepare_exception', 'cancel_setup'})


def document(mode):
    if mode not in policy.PROBE_MODES: raise ValueError('Fixed recovery rehearsal mode required')
    return dict(kind=FIXTURE_KIND, mode=mode, condition=policy.CONDITION, stage='final',
        trial_id='synthetic-nc-recovery-' + mode, model_protocol_sha256=policy.MODEL_SHA256,
        live_api_calls=0, paid_launch_ready=False, recovery_execution_qualified=False)


def private_bytes(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in path.parents):
        raise ValueError('Canonical synthetic input required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        s = os.fstat(stream.fileno())
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_nlink != 1
                or stat.S_IMODE(s.st_mode) != 0o600 or s.st_size > 16384):
            raise ValueError('Private small synthetic input required')
        raw = stream.read(16385)
        if (policy._identity(os.fstat(stream.fileno())) != policy._identity(s)
                or policy._identity(path.lstat()) != policy._identity(s) or len(raw) > 16384):
            raise ValueError('Synthetic input changed during read')
    return raw


def read_fixture(runtime, trial, stage):
    runtime = Path(runtime)
    policy._directory(runtime.lstat())
    forbidden = set(policy.INPUT_FILES) | {policy.RUNTIME_FILE, policy.IMAGE_INTENT_FILE,
        policy.IMAGE_RESULT_FILE, policy.QUALIFIER_INTENT_FILE, policy.QUALIFIER_RESULT_FILE,
        policy.QUALIFIER_FAILURE_FILE}
    if any((runtime / n).exists() or (runtime / n).is_symlink() for n in forbidden):
        raise ValueError('Synthetic runtime cannot contain paid recovery inputs')
    raw = private_bytes(runtime / FIXTURE_FILE)
    value = json.loads(raw, object_pairs_hook=policy._pairs, parse_constant=policy._constant)
    if type(value) is not dict: raise ValueError('Exact synthetic record required')
    expected = document(value.get('mode'))
    if stage != 'final' or trial != expected['trial_id']: raise ValueError('Synthetic identity changed')
    policy._same(value, expected)
    return value, hashlib.sha256(raw).hexdigest()


def network_isolation():
    if sys.platform != 'linux' or {p.name for p in Path('/sys/class/net').iterdir()} != {'lo'}:
        raise ValueError('Native network-less synthetic gateway required')


class SyntheticProvider:
    def __init__(self, key, *, mode, clock, generation_enabled, completion_wait_seconds):
        document(mode); network_isolation()
        if key != SYNTHETIC_KEY or generation_enabled is not True:
            raise ValueError('Dedicated synthetic provider only')
        self.mode = mode; self.clock = clock
        self.completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
        self.calls = self.accepted = 0; self.failed = False; self.last_failure = None
        self.first = None

    def complete(self, request, *, on_response_headers):
        self.last_failure = None
        try:
            network_isolation()
            if self.failed or self.mode in NO_MODEL or self.accepted >= EXPECTED_LOGICAL:
                raise ValueError('No further synthetic model execution permitted')
            prepared = prepare_credit_request({k: v for k, v in request.items() if k != 'provider'}, policy.SETTINGS)
            policy._same(request, prepared)
            names = {t.get('function', {}).get('name') for t in request.get('tools', [])}
            if not {'execute', 'complete_task'} <= names:
                raise ValueError('Original C0-NC tool protocol required')
            if any('[Task time remaining]' in (m.get('content') or '') for m in request['messages']):
                raise ValueError('C3 dynamic advice must not appear in C0-NC')
            binding = policy.fingerprint(request)
            if self.calls == 1 and binding != self.first:
                raise ValueError('Shared retry must preserve the original rejected request')
            if self.accepted:
                last = request['messages'][-1]
                if last.get('role') != 'tool' or last.get('tool_call_id') != TOKEN or MARKER not in (last.get('content') or ''):
                    raise ValueError('Actual native tool feedback required')
        except BaseException:
            self.failed = True
            raise
        self.calls += 1
        if self.calls == 1:
            self.first = binding; diagnostic = error_diagnostic(status=429)
            self.last_failure = dict(http_status=429, retry_after_values=['1'], diagnostic=diagnostic,
                observed_at_utc=datetime.fromtimestamp(self.clock.wall(), timezone.utc),
                now_monotonic=self.clock.monotonic())
            on_response_headers(diagnostic)
            raise TransportError('synthetic-rate-limit', diagnostic=diagnostic)
        first = self.accepted == 0
        arguments = {'command': COMMAND} if first else dict(summary='Synthetic recovery fixture complete.',
            checks=[dict(criterion='Fixture marker', observation='Actual marker tool feedback observed', satisfied=True)])
        message = dict(role='assistant', content=None, tool_calls=[dict(type='function',
            id=TOKEN if first else 'call_recovery_complete', function=dict(
                name='execute' if first else 'complete_task', arguments=json.dumps(arguments)))])
        self.accepted += 1; on_response_headers(error_diagnostic(status=200))
        return dict(id='gen-synthetic-recovery-' + str(self.calls), model=MODEL, provider='DeepInfra',
            object='chat.completion', created=1, choices=[dict(index=0, finish_reason='tool_calls', message=deepcopy(message))],
            usage=dict(prompt_tokens=10, completion_tokens=4, total_tokens=14))


class FixtureSession(NoCutoffRecoverySession):
    def require_session_policy(self):
        try:
            network_isolation()
            if type(self.client) is not SyntheticProvider or self.settings != policy.SETTINGS:
                raise ValueError('No real provider in recovery rehearsal')
            path = self.runtime / FIXTURE_FILE
            identity = policy._identity(path.lstat())
            value, binding = read_fixture(self.runtime, self.trial_id, self.stage)
            if (self.client.mode != value['mode'] or self.client.clock is not self.clock
                    or getattr(self, 'fixture_file_sha256', binding) != binding
                    or policy._identity(path.lstat()) != identity
                    or getattr(self, 'fixture_file_identity', identity) != identity):
                raise ValueError('Synthetic input changed within an attempt')
            self.fixture_file_sha256 = binding
            self.fixture_file_identity = identity
        except BaseException:
            self.stopped = True
            raise

    def require_recovery_policy(self):
        self.require_session_policy()


def gateway(trial, wait):
    network_isolation(); wait = validate_completion_wait(wait)
    path = Path('/study/.runtime/stage2') / FIXTURE_FILE
    identity = policy._identity(path.lstat())
    value, binding = read_fixture(path.parent, trial, 'final')
    if policy._identity(path.lstat()) != identity: raise ValueError('Synthetic input identity changed')
    if (private_bytes('/run/openrouter.env') != ('OPENROUTER_API_KEY=' + SYNTHETIC_KEY + '\n').encode()
            or any(os.environ.get(n) for n in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPINFRA_API_TOKEN'))):
        raise ValueError('Only the dedicated synthetic credential is allowed')
    def factory(key, **kwargs):
        current, observed = read_fixture(Path('/study/.runtime/stage2'), trial, 'final')
        if current != value or observed != binding or policy._identity(path.lstat()) != identity:
            raise ValueError('Synthetic provider input changed')
        return SyntheticProvider(key, mode=value['mode'], **kwargs)
    from retry_gateway import serve
    serve('/study', trial, 'final', '/run/trial-token', '/run/openrouter.env',
        '/socket/private/model.sock', completion_wait_seconds=wait,
        client_factory=factory, session_factory=FixtureSession)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', action='store_true', required=True)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    try: gateway(args.trial, args.completion_wait_seconds)
    except KeyboardInterrupt: pass
    except Exception: raise SystemExit('Synthetic recovery gateway refused') from None
