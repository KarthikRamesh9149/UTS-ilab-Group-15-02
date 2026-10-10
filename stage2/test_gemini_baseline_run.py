"""Paid-launcher safety checks with a local fake upstream only."""
import hashlib
import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest
from aiohttp import ClientSession
from gemini_baseline_gateway import BaselineGateway
from gemini_baseline_run import FakeProvider, classify
from gemini_laptop_policy import MODEL, atomic_json, money


class LauncherGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prior = self.root / 'prior.json'
        atomic_json(self.prior, {'cap_usd': '20', 'requests': [
            dict(sequence=0, trial_id='prior-known', reserved_usd='1.10', cost_usd='11.229632850', status='settled'),
            dict(sequence=1, trial_id='prior-unknown', reserved_usd='1.10', cost_usd=None, status='reserved')]})
        self.provider = FakeProvider(self.root)
        self.provider.harness = 'terminus-2'
        origin = await self.provider.start()
        self.addAsyncCleanup(self.provider.runner.cleanup)
        self.gateway = BaselineGateway('fake-key', self.root / 'new', prior_path=self.prior,
            prior_sha256=hashlib.sha256(self.prior.read_bytes()).hexdigest(), cells={'trial': 'terminus-2'})
        self.gateway.origin = origin
        await self.gateway.start()
        self.addAsyncCleanup(self.gateway.close)
        self.gateway.activate('trial', time.monotonic() + 60)

    async def post(self, body=None):
        async with ClientSession() as client:
            async with client.post(self.gateway.url + '/chat/completions',
                headers={'Authorization': 'Bearer ' + self.gateway.token},
                json=body or {'model': MODEL, 'messages': [{'role': 'user', 'content': 'synthetic'}]}) as response:
                await response.read()
                return response.status

    async def test_fake_dispatch_preserves_inherited_costs_and_native_harness(self):
        before = self.prior.read_bytes()
        self.assertEqual(await self.post(), 200)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(self.gateway.ledger.known, money('11.229632850'))
        self.assertEqual(self.gateway.ledger.unresolved, money('1.10'))
        self.assertEqual(self.gateway.ledger.data['requests'][-1]['harness'], 'terminus-2')
        self.assertEqual(self.prior.read_bytes(), before)

    async def test_budget_denial_never_reaches_upstream(self):
        row = self.gateway.ledger.reserve('trial', 100)
        self.gateway.ledger.settle(row, '1.10')
        for _ in range(5):
            row = self.gateway.ledger.reserve('trial', 100)
            self.gateway.ledger.settle(row, '1.10')
        self.assertEqual(await self.post(), 402)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(self.gateway.stop_reason, 'budget_stop')

    async def test_bad_protocol_stops_without_paid_dispatch(self):
        self.assertEqual(await self.post({'model': 'other', 'messages': []}), 400)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(self.gateway.stop_reason, 'invalid_client_protocol')

    async def test_interface_and_loopback_revoke_together(self):
        await self.gateway.revoke()
        await self.gateway.attach_interface('127.0.0.2')
        self.gateway.activate('trial', time.monotonic() + 60)
        await self.gateway.revoke()
        self.assertIsNone(self.gateway.task_site)
        self.assertEqual(await self.post(), 403)
        self.assertEqual(self.provider.calls, 0)

    async def test_reconcile_does_not_modify_original_unknowns(self):
        original = json.loads(self.prior.read_text())['requests']
        await self.gateway.reconcile()
        self.assertEqual(self.gateway.ledger.data['requests'][:2], original)

    async def delayed_credit_check(self, expire):
        started, release = asyncio.Event(), asyncio.Event()
        async def delayed():
            started.set()
            await release.wait()
            return {'available_usd': '100'}
        self.gateway.credit = delayed
        pending = asyncio.create_task(self.post())
        await started.wait()
        if expire:
            self.gateway.active = (self.gateway.active[0], time.monotonic() - 1)
        else:
            self.gateway.active = None
        release.set()
        self.assertEqual(await pending, 403)
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(len(self.gateway.ledger.data['requests']), 2)

    async def test_credit_await_cannot_outlive_revocation(self):
        await self.delayed_credit_check(False)

    async def test_credit_await_cannot_outlive_deadline(self):
        await self.delayed_credit_check(True)


class ClassificationTests(unittest.TestCase):
    def test_official_timeout_is_verifier_failure(self):
        result = {'status': 'verified', 'agent_error_type': 'TimeoutError',
            'verifier_result': {'rewards': {'reward': 0}}}
        self.assertEqual(classify(result, None), 'verifier_failure')

    def test_budget_stop_preserves_official_reward_but_is_separate(self):
        result = {'status': 'verified', 'verifier_result': {'rewards': {'reward': 1}}}
        self.assertEqual(classify(result, 'budget_stop'), 'budget_stop')

    def test_unresolved_transport_or_unscored_is_infrastructure(self):
        result = {'status': 'verified', 'verifier_result': {'rewards': {'reward': 0}}}
        self.assertEqual(classify(result, 'provider_transport_failure'), 'infrastructure_failure')
        self.assertEqual(classify({'status': 'setup_failed'}, None), 'infrastructure_failure')


if __name__ == '__main__':
    unittest.main()
