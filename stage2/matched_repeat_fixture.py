"""Fake-only baseline rehearsal gateway, never production admission.

This component scripts native baseline wire responses; it does not construct
a baseline, run a task, create qualification, or open a prerequisite session.
The future locked qualifier must supply a separate fixture runtime and an
actually network-isolated gateway. No production proof is fabricated here.
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
from gateway_policy import MODEL, ENDPOINT
from credit_only_gateway import prepare_credit_request
from matched_repeat_gateway import MatchedRepeatSession
from matched_repeat_policy import (SETTINGS, HARNESSES, PROBE_MODES, fingerprint,
    POLICY_FILE, MANIFEST_FILE, BASELINE_FILE, FINAL_FILE, PREDECESSOR_FILE,
    RUNTIME_FILE, QUALIFICATION_FILE, REGISTRATION_FILE, IMAGE_INTENT_FILE, IMAGE_RESULT_FILE)
from openrouter_transport import TransportError, error_diagnostic

FIXTURE_FILE = 'matched-repeat-isolated-fixture.json'
FIXTURE_KIND = 'isolated-synthetic-matched-repeat-not-paid-admission'
SYNTHETIC_KEY = 'synthetic-not-a-real-key'
EXPECTED_LOGICAL = {'terminus-2': 3, 'openhands': 2}
OBSERVATION = 'UTS_MATCHED_REPEAT_OBSERVED'
# The observation is not a contiguous substring of the command. Merely echoing
# terminal keystrokes must not satisfy the scripted tool-output check.
COMMAND = ("printf '%s' UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result && "
    "printf '%s%s\\n' UTS_MATCHED_REPEAT_ OBSERVED")
TOOL_CALL_ID = 'call_matched_repeat_marker'
PRODUCTION_FILES = frozenset({POLICY_FILE, MANIFEST_FILE, BASELINE_FILE, FINAL_FILE,
    PREDECESSOR_FILE, RUNTIME_FILE, QUALIFICATION_FILE, REGISTRATION_FILE,
    IMAGE_INTENT_FILE, IMAGE_RESULT_FILE, 'matched-repeat-image-build-failure.json',
    'matched-repeat-dispatch.json', 'matched-repeat-dispatch-result.json',
    'matched-repeat-dispatch-failure.json'})
# This is a parser window for the tiny fixture record, not a task/model limit.
MAX_FIXTURE_BYTES = 16384


def fixture_document(harness, mode):
    """Non-admitting fixture identity, not a witness or native proof."""
    if harness not in HARNESSES or mode not in PROBE_MODES:
        raise ValueError('Only fixed baseline rehearsal identities are supported')
    return dict(kind=FIXTURE_KIND, harness=harness, mode=mode, stage='final',
        trial_id='synthetic-matched-repeat-' + harness + '-' + mode,
        model_protocol_sha256=SETTINGS.fingerprint(), live_api_calls=0,
        paid_launch_ready=False, repeat_execution_qualified=False)


def _pairs(values):
    answer = {}
    for name, value in values:
        if name in answer:
            raise ValueError('Duplicate fixture field')
        answer[name] = value
    return answer


def _constant(value):
    raise ValueError('Nonfinite fixture value')


def _private_bytes(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or any(p.is_symlink() for p in path.parents):
        raise ValueError('Regular absolute private fixture path required')
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > MAX_FIXTURE_BYTES):
                raise ValueError('Owned private regular fixture file required')
            raw = handle.read(MAX_FIXTURE_BYTES + 1)
        if len(raw) > MAX_FIXTURE_BYTES:
            raise ValueError('Fixture metadata exceeds its parser window')
        return raw
    except OSError:
        raise ValueError('Required private fixture file is unavailable') from None


def read_fixture(runtime, trial, stage):
    runtime = Path(runtime)
    try:
        info = runtime.lstat()
    except OSError:
        raise ValueError('Existing private fixture runtime required') from None
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077
            or not runtime.is_absolute() or runtime.resolve() != runtime):
        raise ValueError('Owned private fixture runtime required')
    if any((runtime / name).exists() or (runtime / name).is_symlink() for name in PRODUCTION_FILES):
        raise ValueError('A rehearsal must not use production repeat evidence')
    raw = _private_bytes(runtime / FIXTURE_FILE)
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    candidates = [fixture_document(harness, mode) for harness in HARNESSES for mode in PROBE_MODES]
    expected = next((v for v in candidates if v['trial_id'] == trial), None)
    if stage != 'final' or expected is None or fingerprint(value) != fingerprint(expected):
        raise ValueError('Only an exact isolated synthetic identity is admitted')
    return value, hashlib.sha256(raw).hexdigest()


def require_network_isolation():
    # An actual Docker network=none namespace is required by the host fixture.
    # This interface observation is a guard, not network-peer authentication or
    # an OS sandbox. The provider also has no external transport implementation.
    if sys.platform != 'linux' or {p.name for p in Path('/sys/class/net').iterdir()} != {'lo'}:
        raise ValueError('Synthetic gateway requires native Linux and network=none')


class SyntheticProvider:
    """Finite synthetic dialogue; its length is not a baseline request cap."""
    def __init__(self, key, *, harness, mode, clock, generation_enabled, completion_wait_seconds):
        fixture_document(harness, mode)
        if key != SYNTHETIC_KEY or generation_enabled is not True:
            raise ValueError('Only the synthetic credential and scripted responses are supported')
        require_network_isolation()
        self.completion_wait_seconds = validate_completion_wait(completion_wait_seconds)
        self.harness, self.mode, self.clock = harness, mode, clock
        self.calls, self.accepted = 0, 0
        self.failed, self.last_failure, self.retry_request_sha256 = False, None, None

    def _request(self, request):
        if not isinstance(request, dict):
            raise ValueError('Prepared baseline request required')
        provider = dict(only=[ENDPOINT], order=[ENDPOINT], allow_fallbacks=False,
            require_parameters=True, quantizations=['fp8'])
        without_provider = {k:v for k,v in request.items() if k != 'provider'}
        canonical = prepare_credit_request(without_provider, SETTINGS)
        if (fingerprint(request) != fingerprint(canonical)
                or request.get('provider') != provider
                or request.get('max_tokens') != SETTINGS.max_output_tokens):
            raise ValueError('Frozen baseline model or provider contract changed')
        if self.harness == 'terminus-2':
            if request.get('tools') or request.get('tool_choice') is not None:
                raise ValueError('Native Terminus JSON/terminal protocol required')
        else:
            names = {tool.get('function', {}).get('name') for tool in request.get('tools', [])
                if isinstance(tool, dict) and isinstance(tool.get('function', {}), dict)}
            if not {'execute_bash', 'finish'} <= names:
                raise ValueError('Original OpenHands shell and finish tools required')
        return fingerprint(request)

    def _observed(self, request):
        last = request['messages'][-1]
        expected_role = 'user' if self.harness == 'terminus-2' else 'tool'
        if (last.get('role') != expected_role or OBSERVATION not in (last.get('content') or '')
                or self.harness == 'openhands' and last.get('tool_call_id') != TOOL_CALL_ID):
            raise ValueError('Actual synthetic marker tool feedback required')
        if self.accepted == 2 and 'include "task_complete": true' not in last['content']:
            raise ValueError('Original Terminus completion confirmation required')

    def complete(self, request, *, on_response_headers):
        # Clear a previous retry descriptor before any assertion can fail. An
        # invalid later request must never look like another transient 429.
        self.last_failure = None
        try:
            require_network_isolation()
            if self.failed or self.mode == 'cancel_setup' or not callable(on_response_headers):
                raise ValueError('No model request is permitted for this fixture state')
            binding = self._request(request)
            if self.accepted >= EXPECTED_LOGICAL[self.harness]:
                raise ValueError('Synthetic dialogue already completed; do not replay')
            if self.calls == 1 and binding != self.retry_request_sha256:
                raise ValueError('Shared recovery must preserve the rejected request')
            if self.accepted:
                self._observed(request)
        except BaseException:
            self.failed = True
            raise
        self.calls += 1
        if self.calls == 1:
            self.retry_request_sha256 = binding
            diagnostic = error_diagnostic(status=429)
            self.last_failure = dict(http_status=429, retry_after_values=['1'], diagnostic=diagnostic,
                observed_at_utc=datetime.fromtimestamp(self.clock.wall(), timezone.utc),
                now_monotonic=self.clock.monotonic())
            on_response_headers(diagnostic)
            raise TransportError('synthetic-rate-limit', diagnostic=diagnostic)
        marker = self.accepted == 0
        if self.harness == 'terminus-2':
            content = dict(analysis='Synthetic baseline rehearsal.', plan='Write marker, then confirm completion.',
                commands=[dict(keystrokes=COMMAND + '\n', duration=1.)] if marker else [],
                task_complete=not marker)
            message, finish = dict(role='assistant', content=json.dumps(content)), 'stop'
        else:
            arguments = {'command': COMMAND} if marker else {'message': 'Synthetic rehearsal complete.'}
            message = dict(role='assistant', content=None, tool_calls=[dict(type='function',
                id=TOOL_CALL_ID if marker else 'call_matched_repeat_finish',
                function=dict(name='execute_bash' if marker else 'finish', arguments=json.dumps(arguments)))])
            finish = 'tool_calls'
        on_response_headers(error_diagnostic(status=200))
        self.accepted += 1
        return dict(id='gen-synthetic-matched-repeat-' + self.harness + '-' + str(self.calls),
            model=MODEL, provider='DeepInfra', object='chat.completion', created=1,
            choices=[dict(index=0, finish_reason=finish, message=deepcopy(message))],
            usage=dict(prompt_tokens=10, completion_tokens=4, total_tokens=14))


class FixtureSession(MatchedRepeatSession):
    """Fake-only route: never accepts a real provider or production registry."""
    def require_session_policy(self):
        try:
            require_network_isolation()
            if type(self.client) is not SyntheticProvider or self.settings != SETTINGS:
                raise ValueError('Exact synthetic provider and frozen model required')
            value, binding = read_fixture(self.runtime, self.trial_id, self.stage)
            if (self.client.harness != value['harness'] or self.client.mode != value['mode']
                    or self.client.clock is not self.clock
                    or getattr(self, 'fixture_file_sha256', binding) != binding):
                raise ValueError('Fixture identity or private bytes changed within an attempt')
            self.fixture_file_sha256 = binding
        except BaseException:
            self.stopped = True
            raise

    def require_recovery_policy(self):
        self.require_session_policy()


def gateway_fixture(trial, wait):
    """Fixed gateway-only entry; no root, factory, command or paid-mode option."""
    require_network_isolation()
    wait = validate_completion_wait(wait)
    value, binding = read_fixture(Path('/study/.runtime/stage2'), trial, 'final')
    expected = ('OPENROUTER_API_KEY=' + SYNTHETIC_KEY + '\n').encode()
    if (_private_bytes(Path('/run/openrouter.env')) != expected
            or any(os.environ.get(name) for name in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 'DEEPINFRA_API_TOKEN'))):
        raise ValueError('Only the dedicated synthetic credential file is permitted')
    def client_factory(key, *, clock, generation_enabled, completion_wait_seconds):
        current, observed = read_fixture(Path('/study/.runtime/stage2'), trial, 'final')
        if observed != binding or current != value:
            raise ValueError('Fixture changed before provider construction')
        return SyntheticProvider(key, harness=value['harness'], mode=value['mode'], clock=clock,
            generation_enabled=generation_enabled, completion_wait_seconds=completion_wait_seconds)
    from retry_gateway import serve
    serve('/study', trial, 'final', '/run/trial-token', '/run/openrouter.env',
        '/socket/private/model.sock', completion_wait_seconds=wait,
        client_factory=client_factory, session_factory=FixtureSession)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', action='store_true', required=True)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    try:
        gateway_fixture(args.trial, args.completion_wait_seconds)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit('Synthetic repeat gateway stopped: ' + type(exc).__name__) from None
