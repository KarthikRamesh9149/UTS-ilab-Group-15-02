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
