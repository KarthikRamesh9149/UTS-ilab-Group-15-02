"""Offline agent-loop tests. A scripted fake model and a local-bash fake environment; no network."""
import asyncio
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from harbor.environments.base import ExecResult
from harbor.models.agent.context import AgentContext

from saranya_harness.agent import (PWD_MARKER, SaranyaMinimalAgent, command_timeout, parse_action, split_marker,
                                   trim_history, truncate, wrap_command)
from saranya_harness.budget import LEDGER_ENV, OVERALL_CAP_ENV
from saranya_harness.openrouter import Completion, ModelError


def completion(content, cost='0.001', prompt=1000, output=50):
    return Completion(content=content, prompt_tokens=prompt, completion_tokens=output, cached_tokens=200,
                      reported_cost_usd=None if cost is None else Decimal(cost), generation_id='gen-x',
                      provider='DeepInfra', model='deepseek/deepseek-v4-flash-0731', retries=0)


class FakeModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []
        self.closed = False

    async def complete(self, messages):
        self.seen.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    async def aclose(self):
        self.closed = True


class LocalBashEnvironment:
    """Runs commands with local bash in a scratch directory, like Harbor's `bash -c`."""

    def __init__(self, workdir):
        self.workdir = workdir
        self.commands = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.commands.append((command, timeout_sec))
        process = await asyncio.create_subprocess_exec(
            'bash', '-c', command, cwd=cwd or self.workdir,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        stdout, _ = await process.communicate()
        return ExecResult(stdout=stdout.decode(), stderr=None, return_code=process.returncode)


class HelperTest(unittest.TestCase):
    def test_parse_action(self):
        self.assertEqual(parse_action('Plan.\n```bash\nls -la\n```'), ('command', 'ls -la'))
        self.assertEqual(parse_action('DONE'), ('done', None))
        self.assertEqual(parse_action(' done. '), ('done', None))
        self.assertEqual(parse_action('I think we are DONE now'), ('none', None))
        self.assertEqual(parse_action('```bash\n\n```'), ('none', None))
        # A command block wins over a trailing DONE: the agent must say DONE alone.
        self.assertEqual(parse_action('```bash\nmake\n```\nDONE')[0], 'command')

    def test_split_marker(self):
        self.assertEqual(split_marker(f'hello\n{PWD_MARKER}/app/src\n'), ('hello', '/app/src'))
        self.assertEqual(split_marker('no marker'), ('no marker', None))

    def test_truncate_keeps_head_and_tail(self):
        text = 'a' * 5000 + 'b' * 10000
        result = truncate(text)
        self.assertTrue(result.startswith('a' * 4000) and result.endswith('b' * 6000))
        self.assertIn('5000 characters omitted', result)

    def test_command_timeout_default_request_and_bounds(self):
        self.assertEqual(command_timeout('make'), 60)
        self.assertEqual(command_timeout('# timeout=600\nmake -j4'), 600)
        self.assertEqual(command_timeout('  # Timeout: 3600\nmake'), 3600)
        self.assertEqual(command_timeout('# timeout=1\ntrue'), 1)
        for bad in ('0', '3601', '90.5', '-5', 'ten'):
            self.assertIsNone(command_timeout(f'# timeout={bad}\nmake'), bad)
        # Only the first line counts, as the prompt says.
        self.assertEqual(command_timeout('make\n# timeout=600'), 60)
        self.assertEqual(command_timeout('# build the project\nmake'), 60)

    def test_trim_history_keeps_system_and_task(self):
        messages = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 't'}]
        messages += [{'role': r, 'content': 'x' * 100} for r in ('assistant', 'user') * 5]
        dropped = trim_history(messages, max_chars=450)
        self.assertEqual(messages[:2], [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 't'}])
        self.assertEqual(dropped, 3)
        self.assertEqual(messages[2]['role'], 'assistant')


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.workdir = root / 'work'
        self.workdir.mkdir()
        self.ledger = root / 'ledger.jsonl'
        self.logs = root / 'trial-1' / 'agent'
        self.env_vars = {OVERALL_CAP_ENV: '2', LEDGER_ENV: str(self.ledger)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_agent(self, replies, env_vars=None, **kwargs):
        model = FakeModel(replies)
        agent = SaranyaMinimalAgent(self.logs, client_factory=lambda: model, **kwargs)
        environment = LocalBashEnvironment(str(self.workdir))
        context = AgentContext()
        with mock.patch.dict('os.environ', self.env_vars if env_vars is None else env_vars, clear=True):
            asyncio.run(agent.run('Create hello.txt', environment, context))
        return model, environment, context

    def test_cwd_and_exit_code_carry_over_and_done_stops(self):
        model, environment, context = self.run_agent([
            completion('```bash\nmkdir -p sub && cd sub && export X=1\n```'),
            completion('```bash\npwd; echo "X=$X"; false\n```'),
            completion('DONE'),
        ])
        observation = model.seen[2][-1]['content']
        self.assertIn('Exit code: 1', observation)
        self.assertIn(str(self.workdir / 'sub'), observation)
        self.assertTrue(observation.endswith('X='))  # environment variables do not persist
        self.assertNotIn(PWD_MARKER, observation)
        self.assertTrue(all(timeout == 60 for _, timeout in environment.commands))  # C0's default
        self.assertEqual(context.metadata['stop_reason'], 'done')
        self.assertEqual(context.metadata['model_calls'], 3)
        self.assertEqual((context.n_input_tokens, context.n_cache_tokens, context.n_output_tokens), (3000, 600, 150))
        self.assertAlmostEqual(context.cost_usd, 0.003)
        self.assertIsNone(context.metadata['model_call_ceiling'])
        self.assertTrue(model.closed)

    def test_requested_timeout_is_used_and_invalid_request_is_refused(self):
        model, environment, context = self.run_agent([
            completion('```bash\n# timeout=900\necho long\n```'),
            completion('```bash\n# timeout=7200\necho too-long\n```'),
            completion('DONE'),
        ])
        self.assertEqual([timeout for _, timeout in environment.commands], [900])
        refusal = model.seen[2][-1]['content']
        self.assertIn('not run', refusal)
        self.assertIn('between 1 and 3600 seconds', refusal)
        self.assertEqual(context.metadata['command_timeout_seconds'], {'default': 60, 'max': 3600})

    def test_no_spending_approval_makes_no_model_call(self):
        model, _, context = self.run_agent([completion('DONE')], env_vars={LEDGER_ENV: str(self.ledger)})
        self.assertEqual(model.seen, [])
        self.assertEqual(context.metadata['stop_reason'], 'no_spending_approval')

    def test_per_trial_budget_stop_is_recorded(self):
        model, _, context = self.run_agent(
            [completion('```bash\necho hi\n```', cost='0.05')] * 5, per_trial_cap_usd='0.10')
        self.assertEqual(len(model.seen), 1)
        self.assertEqual(context.metadata['stop_reason'], 'budget_per_trial')
        self.assertEqual(context.metadata['budget_stop']['scope'], 'per_trial')
        ledger = [json.loads(line) for line in self.ledger.read_text().splitlines()]
        self.assertEqual([r['kind'] for r in ledger], ['request', 'stop'])
        trajectory = (self.logs / 'saranya-trajectory.jsonl').read_text()
        self.assertIn('budget_stop', trajectory)

    def test_unknown_cost_uses_list_price_estimate(self):
        _, _, context = self.run_agent([completion('DONE', cost=None, prompt=1_000_000, output=0)])
        self.assertEqual(context.metadata['cost_sources'], {'estimated_list_price': 1})
        self.assertAlmostEqual(context.cost_usd, 0.06)

    def test_no_command_gets_corrective_feedback(self):
        model, _, _ = self.run_agent([completion('Let me think.'), completion('DONE')])
        self.assertIn('No command found', model.seen[1][-1]['content'])

    def test_rosetta_signature_is_recorded(self):
        _, _, context = self.run_agent([
            completion('```bash\necho "rosetta error: Unimplemented syscall number 282"\n```'),
            completion('DONE')])
        [signal] = context.metadata['infrastructure_signals']
        self.assertEqual(signal['call'], 1)

    def test_model_error_stops_and_keeps_usage(self):
        _, _, context = self.run_agent([completion('```bash\ntrue\n```'),
                                        ModelError('bad', status=400, error_type='invalid_request')])
        self.assertEqual(context.metadata['stop_reason'], 'model_error')
        self.assertEqual(context.metadata['model_calls'], 1)

    def test_context_error_trims_history_once_then_continues(self):
        long = '```bash\nprintf "%0.s-" $(seq 1 3000)\n```'
        _, _, context = self.run_agent([completion(long), completion(long), completion(long),
                                        ModelError('too long', status=400, error_type='context_length_exceeded'),
                                        completion('DONE')])
        self.assertEqual(context.metadata['stop_reason'], 'done')
        self.assertGreater(context.metadata['history_pairs_dropped'], 0)

    def test_cancellation_keeps_reservation_as_possible_charge(self):
        model =FakeModel([completion('```bash\ntrue\n```'), asyncio.CancelledError()])
        agent = SaranyaMinimalAgent(self.logs, client_factory=lambda: model)
        context = AgentContext()
        with mock.patch.dict('os.environ', self.env_vars, clear=True):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(agent.run('task', LocalBashEnvironment(str(self.workdir)), context))
        self.assertEqual(context.metadata['cost_sources'].get('interrupted_reserved'), 1)
        self.assertGreater(context.cost_usd, 0.069)
        self.assertTrue(model.closed)

    def test_other_models_are_refused(self):
        with self.assertRaises(ValueError):
            SaranyaMinimalAgent(self.logs, model_name='openai/gpt-4o-mini')
        SaranyaMinimalAgent(self.logs, model_name='openrouter/deepseek/deepseek-v4-flash-0731')

    def test_wrap_command_quotes_cwd(self):
        self.assertIn("cd '/tmp/a b'", wrap_command('ls', '/tmp/a b'))


if __name__ == '__main__':
    unittest.main()
