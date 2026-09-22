from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from credit_only_experiment import cells, coverage, cleanup_complete
from credit_only_policy import POLICY, POLICY_FILE
from credit_only_gateway import PassiveSession, CreditOnlyHandler
from gateway_http import make_server
from model_protocol import ModelSettings
from native_agents import agent_factory
from run_credit_only import pending_stops, counts
import run_credit_only as runner
from scored_gateway import durable_json, private_directory
from test_credit_only_gateway import Client, SETTINGS, TOKEN


class ScopeTests(unittest.TestCase):
    def test_178_unique_cells_one_per_task_harness(self):
        task_ids = ['task-' + str(i) for i in range(89)]
        matrix = cells(task_ids)
        self.assertEqual(len(matrix), 178)
        self.assertEqual(len({c['trial_id'] for c in matrix}), 178)
        self.assertEqual({(c['task_id'], c['harness']) for c in matrix},
                         {(task, harness) for task in task_ids for harness in ('terminus-2', 'openhands')})
        self.assertTrue(all(c['trial_id'].startswith('creditonly1-') for c in matrix))
        for bad in (task_ids[:-1], task_ids + ['extra'], task_ids[:-1] + [task_ids[0]]):
            with self.assertRaises(ValueError): cells(bad)

    def test_results_need_cleanup_not_cost_receipts(self):
        result = dict(containers_removed=True, networks_removed=True, volumes_removed=True,
                      status='verified', billing={'charged_usd': None, 'unknown_cost_requests': 5})
        self.assertTrue(cleanup_complete(result))
        self.assertFalse(cleanup_complete(dict(result, containers_removed=False)))
        self.assertFalse(cleanup_complete(dict(result, status='cleanup_failed')))
        incomplete = dict(result, harness='terminus-2', verifier_result={'rewards': None})
        self.assertEqual(counts({'incomplete': incomplete})['terminus-2']['no_verifier_result'], 1)


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name).resolve()
        self.original = self.directory / 'original'
        self.previous = self.directory / 'previous'
        self.root = self.directory / 'new'
        for base in (self.original, self.previous, self.root):
            private_directory(base / '.runtime/stage2')
            (base / 'stage2').mkdir()
        self.runtime = self.root / '.runtime/stage2'
        durable_json(self.runtime / POLICY_FILE, POLICY)
        self.matrix = [dict(trial_id='creditonly1-final-' + str(i), task_id='task-' + str(i), harness=h)
            for i, h in enumerate(('terminus-2', 'openhands'))]
        durable_json(self.original / '.runtime/stage2/baseline-matrix.json',
            {'admission': {'settings': {'max_output_tokens': 8192, 'temperature': 1., 'reasoning_effort': 'high'},
                           'setup_timeout_seconds': 900}})
        durable_json(self.previous / '.runtime/stage2/baseline-repeat-matrix.json', {'cells': []})
        durable_json(self.root / 'stage2/input_manifest.json', {'all_task_ids': ['task-' + str(i) for i in range(89)]})
        self.proof = dict(host_environment={}, model_protocol_sha256=SETTINGS.fingerprint(),
                          gateway_image='sha256:' + 'a'*64, guard_image='sha256:' + 'b'*64)
        self.calls = []
        self.error_after_dispatch = False
        self.stop = False
        self.stack = ExitStack()
        for key, value in (('__file__', str(self.root / 'stage2/run_credit_only.py')),
                ('DEPLOYMENT', self.root), ('ORIGINAL', self.original), ('PREDECESSOR', self.previous)):
            self.stack.enter_context(patch.object(runner, key, value))
        self.stack.enter_context(patch.object(runner, 'validate_qualification', return_value=self.proof))
        self.stack.enter_context(patch.object(runner, 'sources', return_value={}))
        self.stack.enter_context(patch.object(runner, 'cells', return_value=self.matrix))
        self.stack.enter_context(patch.object(runner, 'docker', return_value=''))
        self.stack.enter_context(patch('host_environment.snapshot', return_value={}))
        self.stack.enter_context(patch('builtins.print'))
        async def trial(**kwargs):
            self.calls.append(kwargs)
            trial_id = kwargs['trial_id']
            folder = private_directory(self.runtime / 'scored-trials' / trial_id)
            result = {k: kwargs[k] for k in ('trial_id', 'task_id')}
            result.update(harness=kwargs['agent_factory'].harness, status='verified', model_revoked=True,
                containers_removed=True, networks_removed=True, volumes_removed=True,
                verifier_result={'rewards': {'reward': 0}}, billing={'charged_usd': None, 'unknown_cost_requests': 4})
            durable_json(folder / 'started.json', result)
            durable_json(folder / 'result.json', result)
            if self.stop:
                evidence = private_directory(self.runtime / 'scored-attempts' / trial_id)
                durable_json(evidence / 'provider-stop.json', {'reason': 'provider_credit_exhausted', 'trial_id': trial_id})
            if self.error_after_dispatch:
                raise RuntimeError('Retained infrastructure error')
            return result
        self.stack.enter_context(patch.object(runner, 'run_trial', side_effect=trial))

    async def asyncTearDown(self):
        self.stack.close()
        self.temp.cleanup()

    async def test_no_accounting_gate_and_no_task_replay(self):
        with patch('openrouter_transport.OpenRouter', side_effect=AssertionError('No balance calls before dispatch')):
            await runner.run()
            await runner.run()
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(call['accounting_mode'] == 'provider-credit-only' for call in self.calls))
        registered = json.loads((self.runtime / runner.REGISTRATION).read_text())
        self.assertEqual(registered['policy'], POLICY)
        self.assertEqual(registered['predecessor_status'], 'terminal_partial')
        completed, partial = coverage(self.runtime, self.matrix)
        self.assertFalse(partial)
        self.assertEqual(counts(completed)['terminus-2']['failed'], 1)

    async def test_actual_exhaustion_stops_unstarted_tasks_and_restart(self):
        self.stop = True
        await runner.run()
        await runner.run()
        self.assertEqual(len(self.calls), 1)
        completed, _ = coverage(self.runtime, self.matrix)
        self.assertEqual(len(pending_stops(self.runtime, completed)), 1)
        self.assertFalse((self.runtime / 'scored-trials' / self.matrix[1]['trial_id']).exists())

    async def test_manual_top_up_resumes_only_unstarted_task(self):
        self.stop = True
        await runner.run()
        self.stop = False
        with patch('openrouter_transport.load_key', return_value='synthetic'), \
             patch('openrouter_transport.OpenRouter') as provider:
            provider.return_value.balance.return_value = '1'
            await runner.run(confirm_manual_top_up=self.matrix[0]['trial_id'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual({c['trial_id'] for c in self.calls}, {c['trial_id'] for c in self.matrix})
        completed, _ = coverage(self.runtime, self.matrix)
        self.assertFalse(pending_stops(self.runtime, completed))

    async def test_incomplete_attempt_is_not_replayed(self):
        private_directory(self.runtime / 'scored-trials' / self.matrix[0]['trial_id'])
        with self.assertRaises(ValueError): await runner.run()
        self.assertFalse(self.calls)

    async def test_live_predecessor_lock_prevents_overlap(self):
        import fcntl
        with (self.previous / '.runtime/stage2/matrix.lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): await runner.run()
        self.assertFalse(self.calls)

    async def test_cleaned_up_infrastructure_failure_retained_once(self):
        self.error_after_dispatch = True
        await runner.run()
        await runner.run()
        self.assertEqual(len(self.calls), 2)


class NativeClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_terminus_client_accepts_no_billing_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = private_directory(root / '.runtime/stage2')
            durable_json(runtime / POLICY_FILE, POLICY)
            client = Client()
            client.response['usage'].pop('cost')
            client.response.update(object='chat.completion', created=1)
            client.response['choices'][0].update(index=0, finish_reason='stop')
            with PassiveSession(root, 'native-client', 'final', TOKEN, client, settings=SETTINGS) as session:
                server = make_server(lambda: session, handler=CreditOnlyHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
                    agent = agent_factory('terminus-2', SETTINGS)(paths=SimpleNamespace(agent_dir=root),
                        host_api_base=base, container_api_base=base, trial_token=TOKEN,
                        agent_timeout_seconds=60, completion_wait_seconds=60)
                    response = await agent._llm.call('Synthetic client fixture', **agent._llm_call_kwargs)
                    self.assertEqual(response.content, 'fixture')
                    self.assertEqual(len(client.calls), 1)
                    self.assertNotIn('max_price', client.calls[0]['provider'])
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__': unittest.main()
