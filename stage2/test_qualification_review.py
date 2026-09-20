import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_qualification_gate
from model_protocol import ModelSettings
from qualification_review import assess, expansion_allowed


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

    def test_amended_review_must_bind_exact_sidecar(self):
        hold = {'sidecar_sha256': 'c' * 64}
        with patch('qualification_review.validate_historical_hold', return_value=hold), \
             patch('qualification_review.evaluate', return_value={'fixture': 'review binding only'}) as gate:
            with self.assertRaisesRegex(ValueError, 'exact historical accounting hold'):
                assess(self.root, {}, self.review)
            gate.assert_not_called()
            self.review['historical_hold_sha256'] = 'b' * 64
            with self.assertRaises(ValueError):
                assess(self.root, {}, self.review)
            self.review['historical_hold_sha256'] = hold['sidecar_sha256']
            assess(self.root, {}, self.review)
            self.assertEqual(gate.call_args.kwargs['runtime'], self.root / '.runtime/stage2')
            self.assertTrue(gate.call_args.kwargs['systemic_review_clear'])

    def amended_report(self):
        return {'paid_expansion_allowed': False, 'accounting_bounded_expansion_allowed': True,
            'status': 'accounting_bounded_expansion_allowed', 'original_billing_completeness_satisfied': False,
            'actual_charge_and_token_totals_complete': False, 'historical_hold_sha256': 'c' * 64,
            'model_protocol_sha256': self.settings.fingerprint(), 'held_terminal_trials': 1,
            'expected_trials': 20, 'observed_trials': 20, 'verified_successes': 10,
            'budget_exhausted_trials': 2, 'accounting_bounded_reasons': []}

    def test_expansion_consumer_requires_validated_documented_amendment(self):
        hold = {'sidecar_sha256': 'c' * 64, 'model_protocol_sha256': self.settings.fingerprint()}
        report = self.amended_report()
        with patch('qualification_review.validate_historical_hold', return_value=hold):
            self.assertTrue(expansion_allowed(self.root, report))
            for key, value in [('status', 'passed'), ('historical_hold_sha256', 'b' * 64),
                               ('verified_successes', 9), ('budget_exhausted_trials', 3),
                               ('observed_trials', 19), ('original_billing_completeness_satisfied', True),
                               ('actual_charge_and_token_totals_complete', True),
                               ('accounting_bounded_reasons', ['billing_unverified'])]:
                with self.subTest(key=key):
                    self.assertFalse(expansion_allowed(self.root, dict(report, **{key: value})))
        with patch('qualification_review.validate_historical_hold', return_value=None):
            self.assertFalse(expansion_allowed(self.root, report))
        with patch('qualification_review.validate_historical_hold', side_effect=ValueError('New pending dispatch')):
            with self.assertRaisesRegex(ValueError, 'pending'):
                expansion_allowed(self.root, report)

    def completion_document(self):
        return {'schema_version': 2, 'sidecar_sha256': 'd' * 64,
                'model_protocol_sha256': self.settings.fingerprint(),
                'holds': [{'trial_id': 'dev-terminus-2-00-video-processing'},
                          {'trial_id': 'dev-terminus-2-05-reshard-c4-data'}]}

    def completion_report(self):
        document = self.completion_document()
        return dict(self.amended_report(), status='completion_amendment_expansion_allowed',
            accounting_bounded_expansion_allowed=False, completion_amendment_expansion_allowed=True,
            historical_hold_sha256=document['sidecar_sha256'], completion_amendment_sha256=document['sidecar_sha256'],
            held_terminal_trials=2, held_trial_ids=sorted(entry['trial_id'] for entry in document['holds']),
            verified_successes=1, budget_exhausted_trials=3, completion_amendment_reasons=[])

    def test_completion_consumer_accepts_low_scores_only_with_exact_validated_v2(self):
        document, report = self.completion_document(), self.completion_report()
        with patch('qualification_review.validate_historical_hold', return_value=document):
            self.assertTrue(expansion_allowed(self.root, report))
            for key, value in [('status', 'original_qualification_passed'),
                ('completion_amendment_sha256', 'e' * 64), ('historical_hold_sha256', 'e' * 64),
                ('held_terminal_trials', 1), ('held_trial_ids', ['not-the-retained-trial']),
                ('observed_trials', 19), ('expected_trials', 19), ('verified_successes', True),
                ('verified_successes', 19), ('budget_exhausted_trials', -1),
                ('budget_exhausted_trials', 21), ('accounting_bounded_expansion_allowed', True),
                ('model_protocol_sha256', 'e' * 64), ('original_billing_completeness_satisfied', True),
                ('actual_charge_and_token_totals_complete', True),
                ('completion_amendment_reasons', ['cleanup_unverified'])]:
                with self.subTest(key=key, value=value):
                    self.assertFalse(expansion_allowed(self.root, dict(report, **{key: value})))
        for validated in (None, dict(document, schema_version=1)):
            with patch('qualification_review.validate_historical_hold', return_value=validated):
                self.assertFalse(expansion_allowed(self.root, report))
        with patch('qualification_review.validate_historical_hold', return_value=document):
            self.assertFalse(expansion_allowed(self.root,
                dict(self.amended_report(), historical_hold_sha256=document['sidecar_sha256'])))

    def test_completion_review_must_bind_prospective_amendment_not_only_old_hash(self):
        document = self.completion_document()
        self.review['historical_hold_sha256'] = document['sidecar_sha256']
        with patch('qualification_review.validate_historical_hold', return_value=document), \
             patch('qualification_review.evaluate', return_value={'fixture': 'binding only'}) as gate:
            with self.assertRaisesRegex(ValueError, 'prospective completion amendment'):
                assess(self.root, {}, self.review)
            gate.assert_not_called()
            self.review['completion_amendment_sha256'] = 'e' * 64
            with self.assertRaises(ValueError):
                assess(self.root, {}, self.review)
            self.review['completion_amendment_sha256'] = document['sidecar_sha256']
            assess(self.root, {}, self.review)
            self.assertTrue(gate.call_args.kwargs['systemic_review_clear'])
