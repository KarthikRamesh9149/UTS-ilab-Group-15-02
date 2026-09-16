import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_development_selection
from finalist_freeze import FROZEN_FILES, build, verify, save
from model_protocol import ModelSettings


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        for name in FROZEN_FILES: (self.root / 'stage2' / name).write_text('fixture')
        (self.root / 'stage2/custom_execution_limits.json').write_text(json.dumps(
            {'max_model_calls': 100, 'max_repair_cycles': 2}))
        fixture = test_development_selection.SelectionTests()
        settings = ModelSettings(8192, 1., 'high')
        fixture.protocol = settings.fingerprint()
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': fixture.tasks}))
        self.trials, bills = {}, {}
        for condition in ('C0', 'C1', 'C2'):
            self.trials[condition] = []
            for i, row in enumerate(fixture.block(condition, parent='C0' if condition == 'C2' else None)):
                identifier = f'dev-{condition}-{i}'
                self.trials[condition].append(identifier)
                row['trial_id'] = identifier
                folder = self.root / '.runtime/stage2/scored-trials' / identifier
                folder.mkdir(parents=True)
                (folder / 'result.json').write_text(json.dumps(row))
                bills[identifier] = row['billing']
        self.valid = patch('finalist_freeze.validate', return_value=settings)
        self.audit = patch('finalist_freeze.audit_trial', side_effect=lambda _, identifier, stage: bills[identifier])
        self.valid.start(); self.audit.start()
        self.addCleanup(self.valid.stop); self.addCleanup(self.audit.stop)

    def freeze(self):
        return build(self.root, admission={}, trials=self.trials, c2_parent='C0', custom_max_model_calls=100)

    def test_complete_evidence_freezes_and_refuses_overwrite(self):
        document = self.freeze()
        self.assertEqual(verify(self.root, document), 'C0')
        self.assertEqual(len(document['development_evidence']), 60)
        path = self.root / 'freeze.json'
        save(self.root, path, document)
        with self.assertRaises(FileExistsError): save(self.root, path, document)

    def test_changed_source_rejected(self):
        document = self.freeze()
        (self.root / 'stage2/custom_control.py').write_text('changed prompt')
        with self.assertRaises(ValueError): verify(self.root, document)

    def test_changed_selection_evidence_rejected(self):
        document = self.freeze()
        (self.root / '.runtime/stage2/scored-trials/dev-C0-0/result.json').write_text('{}')
        with self.assertRaises(ValueError): verify(self.root, document)

    def test_incomplete_development_rejected(self):
        self.trials['C2'].pop()
        with self.assertRaises(ValueError): self.freeze()

    def test_changed_winner_rejected(self):
        document = self.freeze()
        document['selection']['selected'] = 'C2'
        with self.assertRaises(ValueError): verify(self.root, document)

    def test_changed_limits_rejected(self):
        document = self.freeze()
        document['custom_max_model_calls'] = 200
        with self.assertRaises(ValueError): verify(self.root, document)
