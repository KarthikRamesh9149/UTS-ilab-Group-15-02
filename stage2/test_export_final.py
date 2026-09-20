import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import test_final_analysis
from export_final import collect, export
from final_schedule import schedule
from matrix_resume import DEFERRED_TERMINAL


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = test_final_analysis.AnalysisTests()
        fixture.setUp()
        self.rows = {row['trial_id']: row for row in fixture.rows}
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True, mode=0o700)
        (self.root / 'stage2').mkdir()
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({
            'all_task_ids': fixture.tasks, 'development_ids': fixture.tasks[:20]}))
        freeze = {'admission': {}, 'selection': {'selected_parent': 'C1'}}
        self.registration = {'kind': 'final_evaluation_started', 'freeze': freeze, 'review': {},
            'development_evidence': {}, 'cells': schedule(fixture.tasks, custom_condition='C2', custom_parent='C1')}
        (self.runtime / 'final-matrix.json').write_text(json.dumps(self.registration))
        for identifier, row in self.rows.items():
            directory = self.runtime / 'scored-trials' / identifier
            directory.mkdir(parents=True)
            row['untrusted_agent_text'] = 'DO_NOT_EXPORT_THIS_RAW_TEXT'
            (directory / 'result.json').write_text(json.dumps(row))
        settings = Mock()
        settings.fingerprint.return_value = 'protocol'
        for name, options in {
            'verify': dict(return_value='C2'), 'validate': dict(return_value=settings),
            'assess': dict(return_value={'paid_expansion_allowed': True}),
            'prerequisites': dict(return_value={}),
            'completed_cell': dict(side_effect=lambda root, cell, settings: self.rows[cell['trial_id']])}.items():
            p = patch('export_final.' + name, **options)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)

    def test_complete_export_allowlists_fields_and_checksums(self):
        destination = export(self.root, self.root / 'export')
        with (destination / 'final_trials.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 267)
        self.assertEqual(self.completed_cell.call_count, 267)
        for role in ('custom', 'terminus-2', 'openhands'):
            self.assertEqual(sum(row['role'] == role for row in rows), 89)
        for path in destination.iterdir():
            self.assertNotIn('DO_NOT_EXPORT_THIS_RAW_TEXT', path.read_text())
        marker = json.loads((destination / 'export_complete.json').read_text())
        for name, digest in marker['files'].items():
            self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), digest)
        provenance = json.loads((destination / 'provenance.json').read_text())
        self.assertTrue(provenance['accuracy_complete'])
        self.assertTrue(provenance['billing_complete'])
        self.assertTrue(provenance['receipt_reaudited'])
        self.assertTrue(provenance['all_receipts_verified'])
        self.assertEqual(provenance['deferred_billing_registrations'], {})
        self.assertEqual(provenance['accounting_coverage'], 1.)

    def defer(self):
        row = next(iter(self.rows.values()))
        entry = test_final_analysis.deferred_view(row, reward=1)
        path = self.runtime / 'scored-trials' / row['trial_id'] / 'result.json'
        path.write_text(json.dumps(row))
        return row, entry

    def test_deferred_export_preserves_nulls_and_labels_accounting_provenance(self):
        deferred, entry = self.defer()
        with patch('final_analysis.validated_deferred_cell', return_value=entry) as validate:
            bundle = collect(self.root)
        validate.assert_called_once_with(self.runtime.resolve(), deferred, 'protocol')
        row = next(row for row in bundle['rows'] if row['trial_id'] == deferred['trial_id'])
        self.assertEqual(row['reward'], 1)
        self.assertEqual(row['status'], 'billing_unresolved')
        self.assertFalse(row['billing_verified'])
        self.assertEqual(row['resume_disposition'], DEFERRED_TERMINAL)
        self.assertEqual(row['accounting_coverage'], 'deferred')
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.assertIsNone(row[field])
            self.assertIsNone(bundle['summary']['accounting'][field])
        self.assertEqual(row['known_billed_subtotal_usd'], '0.003')
        self.assertEqual(row['retained_reservation_nanodollars'], 20_000_000)
        self.assertEqual(row['hard_reserved_nanodollars'], 23_000_000)
        self.assertEqual(row['deferred_billing_sha256'], entry['sidecar_sha256'])
        self.assertEqual(row['billing_deferral_policy_sha256'], entry['policy_sha256'])
        path = self.runtime / 'scored-trials' / deferred['trial_id'] / 'result.json'
        self.assertEqual(row['result_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        provenance = bundle['provenance']
        self.assertTrue(provenance['accuracy_complete'])
        self.assertFalse(provenance['billing_complete'])
        self.assertTrue(provenance['receipt_reaudited'])
        self.assertFalse(provenance['all_receipts_verified'])
        self.assertEqual(provenance['billing_deferred_trials'], 1)
        self.assertEqual(provenance['accounting_coverage'], 266 / 267)
        self.assertEqual(provenance['deferred_billing_registrations'][deferred['trial_id']], {
            'registration_sha256': entry['sidecar_sha256'],
            'original_result_sha256': entry['original_result_sha256'],
            'policy_sha256': entry['policy_sha256']})
        with patch('final_analysis.validated_deferred_cell', return_value=entry):
            destination = export(self.root, self.root / 'export')
        with (destination / 'final_trials.csv').open() as handle:
            rows = list(csv.DictReader(handle))
        csv_row = next(row for row in rows if row['trial_id'] == deferred['trial_id'])
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.assertEqual(csv_row[field], '')
        self.assertEqual(csv_row['billing_verified'], 'False')
        self.assertNotIn('None', (destination / 'final_trials.csv').read_text())
        summary = json.loads((destination / 'comparison.json').read_text())
        self.assertIsNone(summary['accounting']['charged_usd'])
        self.assertTrue(summary['accuracy_complete'])
        self.assertFalse(summary['billing_complete'])
        for comparison in summary['full_89']['paired'].values():
            self.assertFalse(comparison['efficiency_win_accepted'])

    def test_unregistered_deferral_prevents_any_export(self):
        self.defer()
        destination = self.root / 'export'
        with self.assertRaises((ValueError, OSError)):
            export(self.root, destination)
        self.assertFalse(destination.exists())

    def test_rejected_deferral_evidence_prevents_any_export(self):
        self.defer()
        destination = self.root / 'export'
        with patch('final_analysis.validated_deferred_cell', side_effect=ValueError('evidence changed')):
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                export(self.root, destination)
        self.assertFalse(destination.exists())

    def test_missing_result_creates_no_export(self):
        identifier = next(iter(self.rows))
        (self.runtime / 'scored-trials' / identifier / 'result.json').unlink()
        destination = self.root / 'export'
        with self.assertRaises(ValueError): export(self.root, destination)
        self.assertFalse(destination.exists())

    def test_existing_export_not_overwritten(self):
        destination = export(self.root, self.root / 'export')
        before = (destination / 'export_complete.json').read_bytes()
        with self.assertRaises(FileExistsError): export(self.root, destination)
        self.assertEqual(before, (destination / 'export_complete.json').read_bytes())

    def test_changed_registration_rejected(self):
        self.registration['cells'].pop()
        (self.runtime / 'final-matrix.json').write_text(json.dumps(self.registration))
        with self.assertRaises(ValueError): collect(self.root)
        self.completed_cell.assert_not_called()

    def test_billing_failure_prevents_export(self):
        self.completed_cell.side_effect = ValueError('unresolved billing')
        with self.assertRaises(ValueError): export(self.root, self.root / 'export')
        self.assertFalse((self.root / 'export').exists())

    def test_result_changed_during_audit_rejected(self):
        def mutate(root, cell, settings):
            path = self.runtime / 'scored-trials' / cell['trial_id'] / 'result.json'
            path.write_text('{}')
            return self.rows[cell['trial_id']]
        self.completed_cell.side_effect = mutate
        with self.assertRaises(ValueError): collect(self.root)

    def install_baseline_registration(self):
        from run_baselines import BINDING_FILES, _descriptor
        for name in BINDING_FILES:
            path = self.root / 'stage2' / name
            if not path.exists(): path.write_text('{}')
        for name, options in {
            'validate': dict(return_value=self.validate.return_value),
            'source_hashes': dict(return_value={'fixture_runtime': 'frozen'}),
            'assess': dict(return_value={'paid_expansion_allowed': True}),
        }.items():
            patched = patch('run_baselines.' + name, **options)
            patched.start()
            self.addCleanup(patched.stop)
        self.registration['freeze']['selection']['selected'] = 'C2'
        descriptor = _descriptor(self.root, self.registration['freeze']['admission'], {}, self.validate.return_value)
        path = self.runtime / 'baseline-matrix.json'
        path.write_text(json.dumps(descriptor))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.registration['baseline_registration_sha256'] = digest
        (self.runtime / 'final-matrix.json').write_text(json.dumps(self.registration))
        return path, digest

    def test_baseline_first_final_export_revalidates_and_records_original_registration(self):
        path, digest = self.install_baseline_registration()
        original = path.read_bytes()
        from run_baselines import validate_registration
        with patch('export_final.validate_registration', wraps=validate_registration) as validate_baseline:
            destination = export(self.root, self.root / 'baseline-first-export')
        self.assertEqual(validate_baseline.call_count, 2)
        self.assertTrue(all(call.args == (self.root.resolve(), self.registration['freeze']['admission'])
                            for call in validate_baseline.call_args_list))
        provenance = json.loads((destination / 'provenance.json').read_text())
        self.assertEqual(provenance['baseline_registration_sha256'], digest)
        self.assertEqual(path.read_bytes(), original)
        with (destination / 'final_trials.csv').open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 267)

    def test_orphan_or_missing_baseline_hash_prevents_export(self):
        self.registration['baseline_registration_sha256'] = 'a' * 64
        (self.runtime / 'final-matrix.json').write_text(json.dumps(self.registration))
        with self.assertRaises(ValueError): collect(self.root)
        self.completed_cell.assert_not_called()
        self.install_baseline_registration()
        del self.registration['baseline_registration_sha256']
        (self.runtime / 'final-matrix.json').write_text(json.dumps(self.registration))
        with self.assertRaises(ValueError): collect(self.root)
        self.completed_cell.assert_not_called()

    def test_missing_tampered_or_unsafe_baseline_registration_prevents_export(self):
        path, _ = self.install_baseline_registration()
        original = path.read_bytes()
        path.write_bytes(original + b'\n')
        with self.assertRaises(ValueError): collect(self.root)
        path.unlink()
        with self.assertRaises(ValueError): collect(self.root)
        path.symlink_to(self.runtime / 'missing-baseline')
        with self.assertRaises(ValueError): collect(self.root)
        self.completed_cell.assert_not_called()

    def test_baseline_binding_change_prevents_export_even_with_matching_file_hash(self):
        self.install_baseline_registration()
        (self.root / 'stage2/run_baselines.py').write_text('changed frozen binding')
        with self.assertRaisesRegex(ValueError, 'Baseline configuration or evidence changed'):
            export(self.root, self.root / 'invalid-export')
        self.assertFalse((self.root / 'invalid-export').exists())
        self.completed_cell.assert_not_called()

    def test_baseline_change_during_result_audit_prevents_export(self):
        baseline_path, _ = self.install_baseline_registration()
        original = baseline_path.read_bytes()
        def mutate(root, cell, settings):
            baseline_path.write_bytes(original + b'\n')
            return self.rows[cell['trial_id']]
        self.completed_cell.side_effect = mutate
        with self.assertRaises(ValueError): export(self.root, self.root / 'changed-export')
        self.assertFalse((self.root / 'changed-export').exists())
