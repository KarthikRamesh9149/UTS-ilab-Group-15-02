import copy
import csv
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from export_development import collect, export, CONDITIONS, HELD_TERMINAL
import historical_hold as hh
from historical_hold import canonical_hold_document
from model_protocol import ModelSettings


class DevelopmentExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True, mode=0o700)
        (self.runtime / 'matrix.lock').touch(mode=0o600)
        (self.root / 'stage2').mkdir()
        self.tasks = ['video-processing'] + [f'fixture-{index}' for index in range(1, 20)]
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': self.tasks}))
        self.settings = ModelSettings(64, 1., 'high')
        self.admission = {'fixture_only': True, 'secret_not_for_export': 'DO_NOT_EXPORT_PRIVATE_DATA'}
        self.records = {}
        for target, arguments in {
            'export_development.validate': {'return_value': self.settings},
            'export_development.validate_historical_hold': {'return_value': None},
            'matrix_resume.validate_historical_hold': {'return_value': None},
            'matrix_resume.audit_trial': {'side_effect': lambda runtime, identifier, stage: copy.deepcopy(self.records[identifier]['billing'])},
        }.items():
            patched = patch(target, **arguments)
            mock = patched.start()
            self.addCleanup(patched.stop)
            if target == 'export_development.validate_historical_hold': self.report_hold = mock
            if target == 'matrix_resume.validate_historical_hold': self.resume_hold = mock

    def identifier(self, condition, index):
        return f'dev-{condition}-{index:02d}-{self.tasks[index]}'

    def write_result(self, condition, index, reward=0, parent=None):
        identifier = self.identifier(condition, index)
        row = {'trial_id': identifier, 'task_id': self.tasks[index], 'harness': condition,
            'stage': 'development', 'status': 'verified', 'model_protocol_sha256': self.settings.fingerprint(),
            'model_revoked': True, 'containers_removed': True, 'networks_removed': True, 'volumes_removed': True,
            'phase_seconds': {'setup': .5, 'agent': 1.5, 'verifier': .25},
            'verifier_result': {'rewards': {'reward': reward}},
            'billing': {'billing_verified': True, 'model_protocol_sha256': self.settings.fingerprint(),
                'charged_usd': '.002', 'prompt_tokens': 100, 'completion_tokens': 20,
                'requests': 2, 'budget_stop_count': 0},
            'agent_context': {'metadata': {'custom_parent': parent}, 'prompt': 'DO_NOT_EXPORT_PRIVATE_DATA'}}
        self.records[identifier] = row
        self.persist(row)
        return row

    def persist(self, row):
        path = self.runtime / 'scored-trials' / row['trial_id'] / 'result.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row))
        return path

    def write_block(self, condition, passes=10, parent=None):
        return [self.write_result(condition, index, int(index < passes), parent) for index in range(20)]

    def register_c2(self, parent='C0'):
        path = self.runtime / 'development-blocks/C2.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'block': 'C2', 'admission': self.admission,
            'cells': [{'trial_id': self.identifier('C2', i), 'task_id': task, 'stage': 'development',
                       'harness': 'C2', 'parent': parent} for i, task in enumerate(self.tasks)]}))
        return path

    def install_hold(self):
        original = self.write_result('terminus-2', 0, 0)
        original.update(status='billing_unresolved', billing={'billing_verified': False})
        path = self.persist(original)
        hold = canonical_hold_document()
        hold.update(model_protocol_sha256=self.settings.fingerprint(), sidecar_sha256='c' * 64,
            budget_stop_count=2, budget_stop_classification='historical_pending_barrier',
            capacity_budget_stop_count=0, original_result_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.report_hold.return_value = hold
        self.resume_hold.return_value = hold
        return hold, path

    def runtime_bytes(self):
        return {str(path.relative_to(self.runtime)): path.read_bytes()
                for path in self.runtime.rglob('*') if path.is_file()}

    def test_unstarted_snapshot_keeps_all_one_hundred_slots_and_no_imputed_scores(self):
        before = self.runtime_bytes()
        bundle = collect(self.root, self.admission)
        self.assertEqual(len(bundle['rows']), 100)
        self.assertEqual(tuple(bundle['conditions']), CONDITIONS)
        self.assertFalse(bundle['all_primary_cells_terminal'])
        self.assertFalse(bundle['final_accuracy_or_win_claimed'])
        self.assertFalse(bundle['selection_or_expansion_authorized'])
        self.assertEqual(bundle['provenance']['historical_hold_count'], 0)
        self.assertEqual(bundle['provenance']['historical_hold_original_result_sha256'], {})
        for condition in bundle['conditions'].values():
            self.assertEqual(condition['intended_cells'], 20)
            self.assertEqual(condition['unstarted_cells'], 20)
            self.assertEqual(condition['passes'], 0)
            self.assertEqual(condition['terminal_zero_rewards'], 0)
            for field in ('pass_rate_fixed_20', 'full_cost_usd', 'full_prompt_tokens', 'full_requests'):
                self.assertIsNone(condition[field])
            for phase in ('setup', 'agent', 'verifier'):
                self.assertIsNone(condition['full_' + phase + '_seconds'])
                self.assertEqual(condition['cells_with_known_' + phase + '_seconds'], 0)
            self.assertFalse(condition['timing_complete'])
        self.assertTrue(all(row['reward'] is None for row in bundle['rows']))
        self.assertTrue(all(row['agent_seconds'] is None for row in bundle['rows']))
        self.assertEqual(before, self.runtime_bytes())

    def test_partial_gateway_and_ledger_orphans_are_incomplete_not_unstarted(self):
        self.write_result('terminus-2', 0, 1)
        self.write_result('terminus-2', 1, 0)
        (self.runtime / 'scored-trials' / self.identifier('terminus-2', 2)).mkdir()
        (self.runtime / 'scored-attempts' / self.identifier('terminus-2', 3)).mkdir(parents=True)
        with sqlite3.connect(self.runtime / 'scored_budget.sqlite') as db:
            db.execute('CREATE TABLE trial_stages (trial TEXT)')
            db.execute('CREATE TABLE requests (trial TEXT)')
            db.execute('INSERT INTO requests VALUES (?)', (self.identifier('terminus-2', 4),))
        bundle = collect(self.root, self.admission)
        summary = bundle['conditions']['terminus-2']
        self.assertEqual((summary['terminal_cells'], summary['incomplete_cells'], summary['unstarted_cells']), (2, 3, 15))
        self.assertEqual((summary['passes'], summary['terminal_zero_rewards']), (1, 1))
        self.assertEqual(Decimal(summary['known_billed_subtotal_usd']), Decimal('.004'))
        self.assertIsNone(summary['full_cost_usd'])
        self.assertIsNone(summary['pass_rate_fixed_20'])
        self.assertEqual(summary['known_retained_liability_usd'], '0')
        self.assertIsNone(summary['retained_liability_usd'])

    def test_complete_verified_condition_has_exact_fixed_twenty_totals(self):
        rows = self.write_block('openhands', 11)
        rows[0]['phase_seconds']['setup'] = 0
        self.persist(rows[0])
        summary = collect(self.root, self.admission)['conditions']['openhands']
        self.assertEqual(summary['verified_cells'], 20)
        self.assertEqual(summary['pass_rate_fixed_20'], .55)
        self.assertEqual(Decimal(summary['full_cost_usd']), Decimal('.040'))
        self.assertEqual(summary['full_prompt_tokens'], 2000)
        self.assertEqual(summary['full_completion_tokens'], 400)
        self.assertTrue(summary['billing_complete'])
        self.assertTrue(summary['timing_complete'])
        for phase, total in [('setup', 9.5), ('agent', 30.), ('verifier', 5.)]:
            self.assertEqual(summary['full_' + phase + '_seconds'], total)
            self.assertEqual(summary['known_' + phase + '_seconds' + '_subtotal'], total)
            self.assertEqual(summary['cells_with_known_' + phase + '_seconds'], 20)

    def test_historical_zero_and_settled_subtotal_preserve_unknown_full_totals(self):
        self.write_block('terminus-2', 11)
        hold, path = self.install_hold()
        before = path.read_bytes()
        bundle = collect(self.root, self.admission)
        summary = bundle['conditions']['terminus-2']
        row = bundle['rows'][0]
        self.assertEqual((summary['terminal_cells'], summary['verified_cells'], summary['held_cells']), (20, 19, 1))
        self.assertEqual(summary['passes'], 10)
        self.assertEqual(summary['pass_rate_fixed_20'], .5)
        self.assertEqual(Decimal(summary['known_billed_subtotal_usd']), Decimal('.03837446'))
        self.assertEqual(Decimal(summary['retained_liability_usd']), Decimal('.106496'))
        self.assertEqual(summary['historical_pending_barrier_markers'], 2)
        self.assertEqual(summary['known_capacity_budget_stopped_trials'], 0)
        for field in ('full_cost_usd', 'full_prompt_tokens', 'full_completion_tokens', 'full_requests'):
            self.assertIsNone(summary[field])
        self.assertEqual(row['state'], HELD_TERMINAL)
        self.assertEqual(row['status'], 'billing_unresolved')
        self.assertEqual(row['reward'], 0)
        self.assertIs(row['billing_verified'], False)
        self.assertEqual((row['setup_seconds'], row['agent_seconds'], row['verifier_seconds']), (.5, 1.5, .25))
        self.assertTrue(summary['timing_complete'])
        self.assertEqual(summary['full_agent_seconds'], 30.)
        self.assertEqual(bundle['provenance']['historical_hold_sha256'], hold['sidecar_sha256'])
        self.assertEqual(bundle['provenance']['historical_hold_count'], 1)
        self.assertEqual(bundle['provenance']['historical_hold_original_result_sha256'], {
            hold['trial_id']: hold['original_result_sha256']})
        self.assertEqual(path.read_bytes(), before)

    def test_csv_and_json_are_deterministic_allowlisted_and_checksummed(self):
        self.write_result('terminus-2', 1, 1)
        self.install_hold()
        before = self.runtime_bytes()
        first = export(self.root, self.admission, self.root / 'export-one')
        second = export(self.root, self.admission, self.root / 'export-two')
        for path in first.iterdir():
            self.assertEqual(path.read_bytes(), (second / path.name).read_bytes())
            self.assertNotIn('DO_NOT_EXPORT_PRIVATE_DATA', path.read_text())
        with (first / 'development_trials.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]['charged_usd'], '')
        self.assertEqual(rows[0]['reward'], '0')
        self.assertEqual(rows[0]['state'], HELD_TERMINAL)
        self.assertEqual((rows[0]['setup_seconds'], rows[0]['agent_seconds'], rows[0]['verifier_seconds']), ('0.5', '1.5', '0.25'))
        self.assertEqual(rows[2]['agent_seconds'], '')
        marker = json.loads((first / 'export_complete.json').read_text())
        self.assertTrue(marker['snapshot_export_complete_not_experiment_complete'])
        for name, digest in marker['files'].items():
            self.assertEqual(hashlib.sha256((first / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(before, self.runtime_bytes())
        with self.assertRaises(FileExistsError):
            export(self.root, self.admission, first)

    def test_nonhistorical_unresolved_durable_result_rejects_export(self):
        row = self.write_result('terminus-2', 1)
        row['status'] = 'billing_unresolved'
        row['billing']['billing_verified'] = False
        self.persist(row)
        with self.assertRaises(RuntimeError):
            export(self.root, self.admission, self.root / 'bad-export')
        self.assertFalse((self.root / 'bad-export').exists())

    def test_result_mutation_during_audit_rejects_export(self):
        row = self.write_result('terminus-2', 0)
        def changed(*args):
            self.persist(dict(row, status='tampered'))
            return row
        with patch('export_development.completed_cell', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'changed during audit'):
                collect(self.root, self.admission)

    def test_sidecar_mutation_and_forged_held_cost_rejected(self):
        hold, _ = self.install_hold()
        self.report_hold.side_effect = [hold, dict(hold, sidecar_sha256='d' * 64)]
        with self.assertRaisesRegex(ValueError, 'hold changed'):
            collect(self.root, self.admission)
        self.report_hold.side_effect = None
        from matrix_resume import completed_cell
        def impute(root, cell, settings):
            row = completed_cell(root, cell, settings)
            row['billing']['charged_usd'] = '0'
            return row
        with patch('export_development.completed_cell', side_effect=impute):
            with self.assertRaisesRegex(ValueError, 'differs from immutable'):
                collect(self.root, self.admission)

    def test_changed_identity_or_replacement_cell_rejected(self):
        row = self.write_result('terminus-2', 0)
        row['task_id'] = 'wrong'
        self.persist(row)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            collect(self.root, self.admission)
        row['task_id'] = self.tasks[0]
        self.persist(row)
        (self.runtime / 'scored-trials' / (row['trial_id'] + '-replacement')).mkdir()
        with self.assertRaisesRegex(ValueError, 'no substitutions'):
            collect(self.root, self.admission)

    def test_c2_requires_registered_parent_matching_audited_selection(self):
        self.write_result('C2', 0, parent='C0')
        with self.assertRaisesRegex(ValueError, 'lacks registered parent'):
            collect(self.root, self.admission)
        self.register_c2('C0')
        self.write_block('C0', 10)
        self.write_block('C1', 11)
        with self.assertRaisesRegex(ValueError, 'audited registered selection'):
            collect(self.root, self.admission)
        self.write_block('C0', 12)
        bundle = collect(self.root, self.admission)
        self.assertEqual(bundle['conditions']['C2']['terminal_cells'], 1)
        self.assertIsNotNone(bundle['provenance']['c2_registration_sha256'])

    def test_c2_descriptor_parent_tampering_rejected(self):
        path = self.register_c2()
        descriptor = json.loads(path.read_text())
        descriptor['cells'][1]['parent'] = 'C1'
        path.write_text(json.dumps(descriptor))
        with self.assertRaisesRegex(ValueError, 'registration or parent mismatch'):
            collect(self.root, self.admission)

    def test_missing_or_busy_lock_does_not_create_or_read_snapshot(self):
        lock = self.runtime / 'matrix.lock'
        with lock.open('rb') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                collect(self.root, self.admission)
        lock.unlink()
        with self.assertRaisesRegex(ValueError, 'Existing matrix ownership lock'):
            collect(self.root, self.admission)
        self.assertFalse(lock.exists())

    def test_symlinked_evidence_and_runtime_output_rejected(self):
        elsewhere = self.root / 'other'
        elsewhere.mkdir()
        (self.runtime / 'scored-trials').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Unsafe development evidence'):
            collect(self.root, self.admission)
        for directory in ('.runtime', 'stage2', 'sources'):
            with self.subTest(directory=directory), self.assertRaisesRegex(ValueError, 'outside runtime and source'):
                export(self.root, self.admission, self.root / directory / 'export')

    def test_changed_admission_rejects_before_export(self):
        with patch('export_development.validate', side_effect=ValueError('Admission changed')):
            with self.assertRaisesRegex(ValueError, 'Admission changed'):
                export(self.root, self.admission, self.root / 'export')
        self.assertFalse((self.root / 'export').exists())

    def test_partial_condition_reports_only_observed_duration_subtotals(self):
        self.write_result('openhands', 0, 1)
        bundle = collect(self.root, self.admission)
        summary = bundle['conditions']['openhands']
        self.assertEqual(summary['known_agent_seconds_subtotal'], 1.5)
        self.assertEqual(summary['cells_with_known_agent_seconds'], 1)
        for phase in ('setup', 'agent', 'verifier'):
            self.assertIsNone(summary['full_' + phase + '_seconds'])
        self.assertFalse(summary['timing_complete'])
        self.assertIsNone(summary['pass_rate_fixed_20'])
        self.assertFalse(bundle['final_accuracy_or_win_claimed'])

    def test_missing_and_null_durations_remain_unknown_even_for_terminal_cells(self):
        rows = self.write_block('openhands', 11)
        del rows[0]['phase_seconds']['setup']
        rows[1]['phase_seconds']['agent'] = None
        rows[2]['phase_seconds'] = None
        del rows[3]['phase_seconds']
        for row in rows[:4]: self.persist(row)
        bundle = collect(self.root, self.admission)
        summary = bundle['conditions']['openhands']
        self.assertEqual(summary['terminal_cells'], 20)
        self.assertEqual(summary['pass_rate_fixed_20'], .55)
        self.assertEqual(summary['cells_with_known_setup_seconds'], 17)
        self.assertEqual(summary['cells_with_known_agent_seconds'], 17)
        self.assertEqual(summary['cells_with_known_verifier_seconds'], 18)
        self.assertEqual(summary['known_agent_seconds_subtotal'], 25.5)
        self.assertFalse(summary['timing_complete'])
        for phase in ('setup', 'agent', 'verifier'):
            self.assertIsNone(summary['full_' + phase + '_seconds'])
        exported = [row for row in bundle['rows'] if row['harness'] == 'openhands']
        self.assertIsNone(exported[0]['setup_seconds'])
        self.assertIsNone(exported[1]['agent_seconds'])
        self.assertIsNone(exported[2]['verifier_seconds'])

    def test_invalid_phase_durations_fail_before_creating_export(self):
        row = self.write_result('openhands', 0)
        for phase in ('setup', 'agent', 'verifier'):
            original = row['phase_seconds'][phase]
            for invalid in (True, '1.5', -1, float('nan'), float('inf')):
                row['phase_seconds'][phase] = invalid
                self.persist(row)
                with self.subTest(phase=phase, invalid=invalid), self.assertRaisesRegex(ValueError, 'finite and nonnegative'):
                    export(self.root, self.admission, self.root / 'invalid-export')
                self.assertFalse((self.root / 'invalid-export').exists())
            row['phase_seconds'][phase] = original

    def test_malformed_phase_container_is_not_treated_as_missing_measurements(self):
        row = self.write_result('openhands', 0)
        for invalid in ([], '', False, 0):
            row['phase_seconds'] = invalid
            self.persist(row)
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'must be an object'):
                collect(self.root, self.admission)


class TwoHistoricalHoldExportTests(unittest.TestCase):
    """Exercise the real exact-two-hold validator, not a permissive stand-in."""

    identifier = DevelopmentExportTests.identifier
    write_result = DevelopmentExportTests.write_result
    persist = DevelopmentExportTests.persist
    runtime_bytes = DevelopmentExportTests.runtime_bytes

    def setUp(self):
        from test_historical_hold import HoldFixtureV2
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fixture = HoldFixtureV2(self.root)
        self.addCleanup(self.fixture.close)
        self.runtime = self.fixture.runtime
        self.settings = self.fixture.settings
        (self.runtime / 'matrix.lock').touch(mode=0o600)
        (self.root / 'stage2').mkdir()
        self.tasks = ['video-processing'] + [f'fixture-{index}' for index in range(1, 20)]
        self.tasks[5] = 'reshard-c4-data'
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': self.tasks}))
        self.admission = {'fixture_only': True, 'secret_not_for_export': 'DO_NOT_EXPORT_PRIVATE_DATA'}
        self.records = {}
        for target, arguments in {
            'export_development.validate': {'return_value': self.settings},
            'matrix_resume.audit_trial': {'side_effect': lambda runtime, identifier, stage: copy.deepcopy(self.records[identifier]['billing'])},
        }.items():
            patched = patch(target, **arguments)
            patched.start()
            self.addCleanup(patched.stop)

    def complete_terminus(self):
        for index in range(20):
            if index not in (0, 5):
                self.write_result('terminus-2', index, int(index < 12))

    def test_two_held_zeros_sum_liability_without_imputing_full_cost_or_usage(self):
        self.complete_terminus()
        before = self.runtime_bytes()
        held = hh.hold_entries(hh.validate_historical_hold(self.runtime))
        bundle = collect(self.root, self.admission)
        summary = bundle['conditions']['terminus-2']
        self.assertEqual((summary['terminal_cells'], summary['verified_cells'], summary['held_cells']), (20, 18, 2))
        self.assertEqual((summary['passes'], summary['terminal_zero_rewards']), (10, 10))
        self.assertEqual(summary['pass_rate_fixed_20'], .5)
        self.assertEqual(Decimal(summary['known_billed_subtotal_usd']), Decimal('.036') +
                         sum(Decimal(entry['settled_subtotal_nanodollars']) for entry in held) / Decimal(10**9))
        self.assertEqual(Decimal(summary['known_billed_subtotal_usd']), Decimal('.03925122'))
        liability = sum(Decimal(entry['reserved_nanodollars']) for entry in held) / Decimal(10**9)
        self.assertEqual(liability, Decimal('.212992'))
        self.assertEqual(Decimal(summary['known_retained_liability_usd']), liability)
        self.assertEqual(Decimal(summary['retained_liability_usd']), liability)
        self.assertEqual(summary['unknown_terminal_cost_cells'], 2)
        self.assertFalse(summary['billing_complete'])
        self.assertFalse(summary['usage_complete'])
        for field in ('full_cost_usd', 'full_prompt_tokens', 'full_completion_tokens', 'full_requests'):
            self.assertIsNone(summary[field])
        self.assertEqual(summary['known_prompt_tokens_subtotal'], 1800)
        self.assertEqual(summary['known_completion_tokens_subtotal'], 360)
        self.assertEqual(summary['known_requests_subtotal'], 36)
        for field in ('prompt_tokens', 'completion_tokens', 'requests'):
            self.assertEqual(summary['cells_with_known_' + field], 18)
        self.assertEqual(summary['historical_pending_barrier_markers'],
                         sum(entry['budget_stop_count'] for entry in held))
        self.assertEqual(summary['known_capacity_budget_stopped_trials'], 0)
        rows = {row['trial_id']: row for row in bundle['rows']}
        for entry in held:
            row = rows[entry['trial_id']]
            self.assertEqual((row['state'], row['status'], row['reward']), (HELD_TERMINAL, 'billing_unresolved', 0))
            self.assertIs(row['billing_verified'], False)
            self.assertEqual(row['historical_hold_sha256'], entry['sidecar_sha256'])
            for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
                self.assertIsNone(row[field])
            original = json.loads(self.fixture.results[entry['trial_id']].read_text())
            for phase in ('setup', 'agent', 'verifier'):
                self.assertEqual(row[phase + '_seconds'], (original.get('phase_seconds') or {}).get(phase))
        provenance = bundle['provenance']
        self.assertEqual(provenance['historical_hold_count'], 2)
        self.assertEqual(provenance['historical_hold_sha256'], held[0]['sidecar_sha256'])
        self.assertEqual(provenance['historical_hold_original_result_sha256'], {
            entry['trial_id']: entry['original_result_sha256'] for entry in held})
        self.assertFalse(bundle['final_accuracy_or_win_claimed'])
        self.assertFalse(bundle['selection_or_expansion_authorized'])
        self.assertEqual(before, self.runtime_bytes())

    def test_tampering_either_original_result_fails_before_output(self):
        for path in self.fixture.results.values():
            original = path.read_bytes()
            try:
                path.write_bytes(original + b' ')
                with self.subTest(trial=path.parent.name), self.assertRaises(ValueError):
                    export(self.root, self.admission, self.root / 'tampered-export')
                self.assertFalse((self.root / 'tampered-export').exists())
            finally:
                path.write_bytes(original)

    def test_neither_hold_can_be_substituted_by_another_trial_identity(self):
        for identifier in self.fixture.results:
            replacement = self.runtime / 'scored-trials' / (identifier + '-replacement')
            replacement.mkdir()
            try:
                with self.subTest(trial=identifier), self.assertRaisesRegex(ValueError, 'no substitutions'):
                    collect(self.root, self.admission)
            finally:
                replacement.rmdir()

    def test_a_third_unresolved_result_is_not_a_held_zero(self):
        row = self.write_result('terminus-2', 6)
        row['status'] = 'billing_unresolved'
        row['billing']['billing_verified'] = False
        self.persist(row)
        with self.assertRaisesRegex(RuntimeError, 'Unverified attempt'):
            export(self.root, self.admission, self.root / 'unknown-export')
        self.assertFalse((self.root / 'unknown-export').exists())

    def test_a_third_pending_ledger_request_blocks_the_snapshot(self):
        ledger = self.fixture.ledger()
        try:
            ledger.db.execute("INSERT INTO requests VALUES ('third-unknown','third-trial',1,NULL,'pending')")
        finally:
            ledger.close()
        with self.assertRaises(ValueError):
            export(self.root, self.admission, self.root / 'third-hold-export')
        self.assertFalse((self.root / 'third-hold-export').exists())

    def test_forged_zero_charge_is_rejected_for_either_held_view(self):
        from matrix_resume import completed_cell
        for identifier in self.fixture.results:
            def impute(root, cell, settings):
                row = completed_cell(root, cell, settings)
                if row is not None and row['trial_id'] == identifier:
                    row['billing']['charged_usd'] = '0'
                return row
            with self.subTest(trial=identifier), patch('export_development.completed_cell', side_effect=impute):
                with self.assertRaisesRegex(ValueError, 'differs from immutable'):
                    collect(self.root, self.admission)

    def test_two_hold_csv_remains_allowlisted_and_read_only(self):
        before = self.runtime_bytes()
        destination = export(self.root, self.admission, self.root / 'two-hold-export')
        with (destination / 'development_trials.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        held_rows = [row for row in rows if row['state'] == HELD_TERMINAL]
        self.assertEqual({row['trial_id'] for row in held_rows}, set(self.fixture.results))
        self.assertEqual(len(held_rows), 2)
        self.assertTrue(all(row['reward'] == '0' for row in held_rows))
        for row in held_rows:
            for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
                self.assertEqual(row[field], '')
        for path in destination.iterdir():
            self.assertNotIn('DO_NOT_EXPORT_PRIVATE_DATA', path.read_text())
        self.assertEqual(before, self.runtime_bytes())


if __name__ == '__main__':
    unittest.main()
