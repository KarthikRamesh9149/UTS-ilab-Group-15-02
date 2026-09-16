import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_qualification_gate
from model_protocol import ModelSettings
from qualification_review import assess


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        fixture = test_qualification_gate.QualificationGateTests()
        fixture.setUp()
        self.settings = ModelSettings(8192, 1., 'high')
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': fixture.tasks}))
        self.records, hashes = {}, {}
        for i, row in enumerate(fixture.rows):
            identifier = f'dev-terminus-2-{i:02d}-{row["task_id"]}'
            row['trial_id'] = identifier
            row['model_protocol_sha256'] = self.settings.fingerprint()
            row['billing']['model_protocol_sha256'] = self.settings.fingerprint()
            folder = self.root / '.runtime/stage2/scored-trials' / identifier
            folder.mkdir(parents=True)
            raw = json.dumps(row).encode()
            (folder / 'result.json').write_bytes(raw)
            hashes[identifier] = hashlib.sha256(raw).hexdigest()
            self.records[identifier] = row
        self.review = {'kind': 'terminus20_systemic_review', 'reviewer': 'synthetic-test-reviewer',
            'model_protocol_sha256': self.settings.fingerprint(), 'reviewed_result_hashes': hashes,
            'findings': {key: {'clear': True, 'notes': 'Synthetic fixture, not a real review.'}
                         for key in ('parser', 'routing', 'environment')}}
        validator = patch('qualification_review.validate', return_value=self.settings)
        cells = patch('qualification_review.completed_cell', side_effect=lambda _, cell, settings: self.records.get(cell['trial_id']))
        validator.start(); cells.start()
        self.addCleanup(validator.stop); self.addCleanup(cells.stop)

    def test_matching_review_and_threshold_pass(self):
        self.assertTrue(assess(self.root, {}, self.review)['paid_expansion_allowed'])

    def test_environment_failure_blocks_expansion(self):
        self.review['findings']['environment']['clear'] = False
        self.assertFalse(assess(self.root, {}, self.review)['paid_expansion_allowed'])

    def test_stale_review_rejected(self):
        identifier = next(iter(self.records))
        self.review['reviewed_result_hashes'][identifier] = 'b' * 64
        with self.assertRaises(ValueError): assess(self.root, {}, self.review)

    def test_missing_trial_or_category_rejected(self):
        identifier, row = self.records.popitem()
        with self.assertRaises(ValueError): assess(self.root, {}, self.review)
        self.records[identifier] = row
        del self.review['findings']['parser']
        with self.assertRaises(ValueError): assess(self.root, {}, self.review)

    def test_no_implicit_clear_flag(self):
        self.review['findings']['environment']['clear'] = 'true'
        with self.assertRaises(ValueError): assess(self.root, {}, self.review)

    def test_review_does_not_override_low_accuracy(self):
        next(iter(self.records.values()))['verifier_result']['rewards']['reward'] = 0
        self.assertFalse(assess(self.root, {}, self.review)['paid_expansion_allowed'])
