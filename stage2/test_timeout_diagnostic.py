import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from timeout_diagnostic import select, summarise, POLICY, QUALIFICATION
from credit_only_experiment import digest
from retry_policy import SETTINGS


class TimeoutDiagnosticTests(unittest.TestCase):
    def fixture(self):
        return [dict(trial_id=f'corrected1-{h}-{i}', harness=h, task_id=f'task-{i}',
                     reward=0 if i < count else 1, agent_error_type='TimeoutError',
                     http_429_requests=1, result_sha256='a'*64)
                for h, count in (('terminus-2', 11), ('openhands', 19)) for i in range(89)]

    def test_all_30_and_original_identities_are_preserved(self):
        rows = self.fixture()
        before = copy.deepcopy(rows)
        cells = select(rows)
        self.assertEqual(len(cells), 30)
        self.assertEqual(len({r['trial_id'] for r in cells}), 30)
        self.assertTrue(all(r['trial_id'].startswith('timeoutdiag1-') for r in cells))
        self.assertEqual(rows, before)

    def test_incomplete_original_is_not_eligible(self):
        with self.assertRaises(ValueError): select(self.fixture()[:-1])

    def test_duplicate_original_is_rejected(self):
        rows = self.fixture(); rows[0] = rows[1]
        with self.assertRaises(ValueError): select(rows)

    def test_non_timeout_is_not_selected(self):
        rows = self.fixture(); rows[0]['agent_error_type'] = 'APIError'
        with self.assertRaises(ValueError): select(rows)

    def test_pass_with_timeout_is_not_a_failure(self):
        rows = self.fixture(); rows[0]['reward'] = 1
        with self.assertRaises(ValueError): select(rows)

    def test_no_429_is_not_selected(self):
        rows = self.fixture(); rows[0]['http_429_requests'] = 0
        with self.assertRaises(ValueError): select(rows)

    def test_unknown_reward_is_not_zero(self):
        rows = self.fixture(); rows[0]['reward'] = None
        with self.assertRaises(ValueError): select(rows)

    def test_invalid_count_is_not_inferred(self):
        for count in (-1, None, True):
            rows = self.fixture(); rows[0]['http_429_requests'] = count
            with self.assertRaises(ValueError): select(rows)

    def test_summary_keeps_clean_contaminated_and_unknown_separate(self):
        rows = [dict(trial_id=str(i), reward=reward, no_recorded_api_errors=clean,
                     http_429_requests=rate_limits, known_cost_usd='0.01', unknown_cost_requests=unknown)
                for i, (reward, clean, rate_limits, unknown) in enumerate(
                    [(1, True, 0, 0), (0, True, 0, 0), (1, False, 2, 2), (None, False, 0, 1)])]
        summary = summarise(rows)
        self.assertEqual(summary['passed'], 2)
        self.assertEqual(summary['passed_without_recorded_api_errors'], 1)
        self.assertEqual(summary['failed_without_recorded_api_errors'], 1)
        self.assertEqual(summary['repeated_with_http_429'], 1)
        self.assertEqual(summary['other_nonclean_attempts'], 1)
        self.assertEqual(summary['no_verifier_result'], 1)
        self.assertEqual(summary['remaining'], 26)
        self.assertEqual(summary['unknown_cost_requests'], 3)
        self.assertIsNone(summary['additional_original_passes_established'])

    def test_duplicate_repeat_cannot_inflate_summary(self):
        row = dict(trial_id='same', reward=1, no_recorded_api_errors=True,
                   http_429_requests=0, known_cost_usd='0', unknown_cost_requests=0)
        with self.assertRaises(ValueError): summarise([row, row])

    def test_single_attempt_unchanged_limits_and_no_original_replacement(self):
        self.assertEqual(POLICY['attempts_per_selected_cell'], 1)
        self.assertFalse(POLICY['repeated_until_pass'])
        self.assertFalse(POLICY['original_scores_replaced'])
        self.assertFalse(POLICY['automatic_top_up'])
        self.assertEqual(POLICY['official_time_and_resources'], 'unchanged')


class DiagnosticDispatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from run_timeout_diagnostic import dispatch
        self.dispatch = dispatch
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True)
        (self.runtime / 'baseline-matrix.json').write_text(json.dumps({'admission': {'setup_timeout_seconds': 900}}))
        (self.runtime / QUALIFICATION).write_text('{}')
        self.cells = [dict(trial_id=f'timeoutdiag1-{i}', task_id=f'fixture-{i}', harness=h)
                      for i, h in enumerate(('terminus-2', 'openhands'))]
        self.identity = dict(cells=self.cells, gateway_image='gateway', guard_image='guard')
        self.descriptor = dict(self.identity, qualification_sha256=digest(self.runtime / QUALIFICATION))
        for name, kwargs in {
                'ORIGINAL': dict(new=self.root), 'qualified': dict(return_value=self.identity),
                'Clock': {}, 'Cooldown': {}, 'agent_factory': dict(return_value='qualified_factory'),
                'run_trial': dict(side_effect=self.execute),
                'observe': dict(side_effect=self.observation)}.items():
            item = patch('run_timeout_diagnostic.' + name, **kwargs)
            value = item.start(); self.addCleanup(item.stop)
            setattr(self, name, value)
        self.Cooldown.return_value.until = 0
        self.Cooldown.return_value.clock.monotonic.return_value = 1
        quiet = patch('builtins.print'); quiet.start(); self.addCleanup(quiet.stop)

    async def execute(self, **kwargs):
        folder = self.runtime / 'scored-trials' / kwargs['trial_id']
        folder.mkdir(parents=True)
        result = dict(trial_id=kwargs['trial_id'], task_id=kwargs['task_id'],
            harness=next(c['harness'] for c in self.cells if c['trial_id'] == kwargs['trial_id']),
            status='verified', verifier_result={'rewards': {'reward': 0}}, model_revoked=True,
            model_protocol_sha256=SETTINGS.fingerprint(),
            containers_removed=True, networks_removed=True, volumes_removed=True)
        (folder / 'result.json').write_text(json.dumps(result))
        return result

    def observation(self, runtime, cell, result):
        return dict(cell, reward=0, no_recorded_api_errors=True, http_429_requests=0,
                    known_cost_usd='0.01', unknown_cost_requests=0)

    async def test_resume_keeps_failed_attempts_without_replay(self):
        await self.dispatch(self.root, self.descriptor)
        await self.dispatch(self.root, self.descriptor)
        self.assertEqual(self.run_trial.call_count, 2)
        for call in self.run_trial.call_args_list:
            self.assertEqual(call.kwargs['accounting_mode'], 'provider-credit-only')

    async def test_interrupted_attempt_stops_before_spending(self):
        (self.runtime / 'scored-trials' / self.cells[0]['trial_id']).mkdir(parents=True)
        with self.assertRaises(ValueError): await self.dispatch(self.root, self.descriptor)
        self.run_trial.assert_not_called()

    async def test_provider_stop_does_not_launch_next_cell(self):
        async def stopped(**kwargs):
            result = await self.execute(**kwargs)
            folder = self.runtime / 'scored-attempts' / kwargs['trial_id']
            folder.mkdir(parents=True)
            (folder / 'provider-stop.json').write_text(json.dumps({'reason': 'provider_credit_exhausted'}))
            return result
        self.run_trial.side_effect = stopped
        await self.dispatch(self.root, self.descriptor)
        self.assertEqual(self.run_trial.call_count, 1)
        with self.assertRaises(ValueError): await self.dispatch(self.root, self.descriptor)
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_source_drift_prevents_next_attempt(self):
        self.qualified.side_effect = [self.identity, ValueError('source changed')]
        with self.assertRaises(ValueError): await self.dispatch(self.root, self.descriptor)
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_changed_qualification_prevents_spending(self):
        (self.runtime / QUALIFICATION).write_text('{"changed": true}')
        with self.assertRaises(ValueError): await self.dispatch(self.root, self.descriptor)
        self.run_trial.assert_not_called()

    async def test_missing_revocation_stops_dispatch(self):
        async def unrevoked(**kwargs):
            result = await self.execute(**kwargs)
            result['model_revoked'] = False
            return result
        self.run_trial.side_effect = unrevoked
        with self.assertRaises(RuntimeError): await self.dispatch(self.root, self.descriptor)
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_resume_rechecks_original_revocation_and_protocol(self):
        await self.dispatch(self.root, self.descriptor)
        path = self.runtime / 'scored-trials' / self.cells[0]['trial_id'] / 'result.json'
        value = json.loads(path.read_text()); value['model_revoked'] = False
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): await self.dispatch(self.root, self.descriptor)
        self.assertEqual(self.run_trial.call_count, 2)


if __name__ == '__main__':
    unittest.main()
