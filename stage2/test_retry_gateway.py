import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from urllib.error import HTTPError, URLError

from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError
from credit_only_policy import POLICY, POLICY_FILE
from model_protocol import ModelSettings
from openrouter_transport import TransportError, error_diagnostic
from retry_gateway import RetrySession
from retry_runtime import activate, Cooldown, deadline_for, deadline_factory
from retry_transport import ObservedOpenRouter
from scored_gateway import durable_json, private_directory
from test_credit_only_gateway import Client, PAYLOAD, TOKEN

SETTINGS = ModelSettings(384000, 1., 'high')
REQUEST = dict(PAYLOAD, max_tokens=384000)


class Clock:
    boot_id = 'test-boot'
    now = 100.
    def monotonic(self): return self.now
    def wall(self): return 1800000000. + self.now


class Event:
    def __init__(self, clock): self.clock, self.cancelled = clock, False
    def is_set(self): return self.cancelled
    def set(self): self.cancelled = True
    def wait(self, seconds): self.clock.now += seconds


class Flaky(Client):
    def __init__(self, clock, failures):
        super().__init__()
        self.clock, self.failures = clock, list(failures)
    def complete(self, payload, **kwargs):
        if self.failures:
            self.calls.append(deepcopy(payload))
            status, headers = self.failures.pop(0)
            diagnostic = error_diagnostic(status=status)
            self.last_failure = dict(http_status=status, retry_after_values=headers,
                diagnostic=diagnostic, observed_at_utc=datetime.fromtimestamp(self.clock.wall(), timezone.utc),
                now_monotonic=self.clock.monotonic())
            kwargs['on_response_headers'](diagnostic)
            raise TransportError('private error', diagnostic=diagnostic)
        self.last_failure = None
        return super().complete(payload, **kwargs)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        durable_json(self.runtime / POLICY_FILE, POLICY)
        from retry_policy import POLICY_FILE as RECOVERY_FILE, POLICY as RECOVERY_POLICY
        durable_json(self.runtime / RECOVERY_FILE, RECOVERY_POLICY)
        self.clock = Clock()
    def tearDown(self): self.temp.cleanup()
    def session(self, failures=(), name='retry-test', timeout=100):
        activate(self.runtime, name, timeout, SETTINGS, self.clock)
        session = RetrySession(self.root, name, 'final', TOKEN,
            Flaky(self.clock, failures), settings=SETTINGS, clock=self.clock)
        session.cancelled = Event(self.clock)
        return session
    def test_429_recovers_identical_payload_records_physical_calls(self):
        with self.session([(429, ['7']), (429, [])]) as session:
            response = session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 3)
            self.assertEqual(session.client.calls, [session.client.calls[0]] * 3)
            self.assertEqual(self.clock.now, 114.5)
            self.assertEqual(session.client.completion_wait_seconds, 85.5)
            self.assertEqual(response['provider'], 'DeepInfra')
            accounting = summarise(self.runtime, session.trial_id)
            self.assertEqual(accounting['unknown_cost_requests'], 2)
            self.assertEqual(accounting['requests'], 3)
            logical = json.loads((session.evidence / 'logical-000001.json').read_text())
            self.assertTrue(logical['accepted_for_agent'])
            self.assertEqual(logical['last_physical_sequence'], 3)
            self.assertFalse(list(self.runtime.glob('*.sqlite')))
    def test_provider_wait_survives_trial_boundary_without_replay(self):
        with self.session([(429, ['200'])], timeout=20) as session:
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
        with self.session(name='next', timeout=400) as session:
            session.complete(TOKEN, REQUEST)
            self.assertEqual(self.clock.now, 300.)
            self.assertEqual(len(session.client.calls), 1)
    def test_auth_credit_failures_do_not_retry(self):
        for status in (401, 402, 403):
            with self.session([(status, ['1'])], name='status-' + str(status)) as session:
                with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
                self.assertEqual(len(session.client.calls), 1)
                self.assertTrue((session.evidence / 'provider-stop.json').exists())
    def test_transient_network_and_server_errors_recover(self):
        for status in (None, 408, 429, 500, 502, 503, 504):
            with self.session([(status, [])], name='transport-' + str(status)) as session:
                session.complete(TOKEN, REQUEST)
                self.assertEqual(len(session.client.calls), 2)
    def test_bad_request_and_wrong_identity_never_retry(self):
        with self.session([(400, [])]) as session:
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
        with self.session(name='identity') as session:
            session.client.response['model'] = 'wrong'
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
    def test_conflicting_header_stops_instead_of_hammering(self):
        with self.session([(429, ['1', '2'])]) as session:
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
            self.assertEqual(json.loads((session.evidence / 'provider-stop.json').read_text())['reason'], 'retry_header_invalid')
    def test_cancelled_or_expired_never_dispatches(self):
        with self.session() as session:
            session.cancelled.set()
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertFalse(session.client.calls)
        with self.session(name='expired', timeout=1) as session:
            self.clock.now += 2
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertFalse(session.client.calls)
    def test_no_project_iteration_or_spending_limit(self):
        with self.session([(429, ['0'])] * 30) as session:
            session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 31)
    def test_revocation_during_wait(self):
        with self.session([(429, ['10'])]) as session:
            session.cancelled.wait = lambda seconds: session.cancelled.set()
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
    def test_private_lifecycle_and_boot_identity(self):
        with self.session() as session:
            path = self.runtime / 'retry-lifecycle/retry-test.json'
            path.chmod(0o644)
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            path.chmod(0o600)
            self.clock.boot_id = 'changed'
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            self.assertFalse(session.client.calls)
    def test_reboot_preserves_wall_clock_cooldown(self):
        cool = Cooldown(self.runtime, self.clock)
        cool.update(170., 3)
        self.clock.boot_id = 'new'
        self.clock.now += 10
        restored = Cooldown(self.runtime, self.clock)
        self.assertEqual(restored.until, 170.)
        self.assertEqual(restored.count, 3)
    def test_factory_activates_after_setup_only(self):
        class Agent:
            async def run(self, *args): return 'done'
        def factory(**kwargs): return Agent()
        factory.harness = 'openhands'
        factory.model_protocol_sha256 = SETTINGS.fingerprint()
        wrapped = deadline_factory(factory, self.root, SETTINGS, clock=self.clock)
        agent = wrapped(paths=SimpleNamespace(trial_dir=Path('real-trial')), agent_timeout_seconds=900)
        self.assertFalse((self.runtime / 'retry-lifecycle').exists())
        self.assertEqual(asyncio.run(agent.run()), 'done')
        self.assertEqual(deadline_for(self.runtime, 'real-trial', SETTINGS, self.clock), 1000.)


class TransportTests(unittest.TestCase):
    def test_observer_retains_header_not_raw_body(self):
        headers = Message()
        headers.add_header('Retry-After', '11')
        class Opener:
            def open(self, request, **kwargs):
                raise HTTPError(request.full_url, 429, 'private', headers,
                    io.BytesIO(b'{"error":{"code":429,"message":"DO-NOT-LOG"}}'))
        client = ObservedOpenRouter('synthetic', clock=Clock(), generation_enabled=True, opener=Opener())
        with self.assertRaises(TransportError): client.complete(REQUEST)
        self.assertEqual(client.last_failure['retry_after_values'], ['11'])
        self.assertNotIn('DO-NOT-LOG', str(client.last_failure))
    def test_transport_loss_is_explicit_unknown(self):
        class Opener:
            def open(self, request, **kwargs): raise URLError('DO-NOT-LOG')
        client = ObservedOpenRouter('synthetic', clock=Clock(), generation_enabled=True, opener=Opener())
        with self.assertRaises(TransportError): client.complete(REQUEST)
        self.assertIsNone(client.last_failure['http_status'])
        self.assertNotIn('DO-NOT-LOG', str(client.last_failure))


if __name__ == '__main__': unittest.main()
