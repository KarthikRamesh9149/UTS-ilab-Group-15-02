import copy
import hashlib
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
        self.tasks, self.c2_parent = fixture.tasks, 'C0'
        settings = ModelSettings(8192, 1., 'high')
        fixture.protocol = settings.fingerprint()
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': fixture.tasks}))
        self.trials, bills = {}, {}
        self.registration_dir = self.root / '.runtime/stage2/development-blocks'
        self.registration_dir.mkdir(parents=True)
        for condition in ('C0', 'C1', 'C2'):
            self.trials[condition] = []
            for i, row in enumerate(fixture.block(condition, parent='C0' if condition == 'C2' else None)):
                identifier = f'dev-{condition}-{i:02d}-{row["task_id"]}'
                self.trials[condition].append(identifier)
                row['trial_id'] = identifier
                folder = self.root / '.runtime/stage2/scored-trials' / identifier
                folder.mkdir(parents=True)
                (folder / 'result.json').write_text(json.dumps(row))
                bills[identifier] = row['billing']
            self.write_registration(condition)
        self.valid = patch('finalist_freeze.validate', return_value=settings)
        self.audit = patch('finalist_freeze.audit_trial', side_effect=lambda _, identifier, stage: bills[identifier])
        self.assessment = patch('finalist_freeze.assess', return_value={'paid_expansion_allowed': True})
        self.valid.start(); self.audit.start()
        self.review_assess = self.assessment.start()
        self.addCleanup(self.valid.stop); self.addCleanup(self.audit.stop)
        self.addCleanup(self.assessment.stop)

    def freeze(self):
        return build(self.root, admission={}, trials=self.trials, c2_parent=self.c2_parent, custom_max_model_calls=100)

    def write_registration(self, condition):
        cells = [dict(trial_id=identifier, task_id=self.tasks[index], stage='development',
                      harness=condition, **({'parent': self.c2_parent} if condition == 'C2' else {}))
                 for index, identifier in enumerate(self.trials[condition])]
        document = {'block': condition, 'cells': cells, 'admission': {},
                    'qualification_review': {'fixture': 'same reviewed block'},
                    'limits': {'max_model_calls': 100, 'max_repair_cycles': 2},
                    'runner_sha256': hashlib.sha256((self.root / 'stage2/run_development.py').read_bytes()).hexdigest()}
        path = self.registration_dir / (condition + '.json')
        path.write_text(json.dumps(document))
        return path, document

    def trial_path(self, condition, index):
        return self.root / '.runtime/stage2/scored-trials' / self.trials[condition][index] / 'result.json'

    def test_complete_evidence_freezes_and_refuses_overwrite(self):
        document = self.freeze()
        self.assertEqual(verify(self.root, document), 'C0')
        self.assertEqual(len(document['development_evidence']), 60)
        self.assertEqual(set(document['development_block_evidence']), {'C0', 'C1', 'C2'})
        path = self.root / 'freeze.json'
        save(self.root, path, document)
        with self.assertRaises(FileExistsError): save(self.root, path, document)

    def test_changed_source_rejected(self):
        document = self.freeze()
        (self.root / 'stage2/custom_control.py').write_text('changed prompt')
        with self.assertRaises(ValueError): verify(self.root, document)

    def test_changed_selection_evidence_rejected(self):
        document = self.freeze()
        self.trial_path('C0', 0).write_text('{}')
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

    def test_diagnostic_repeat_and_unregistered_trial_cannot_substitute(self):
        original = self.trials['C0'][0]
        for identifier in ('dev-diagnostic-00-task-0', 'dev-C0-repeat-00-task-0', 'dev-C0-0'):
            with self.subTest(identifier=identifier):
                row = json.loads(self.trial_path('C0', 0).read_text())
                self.trials['C0'][0] = identifier
                row['trial_id'] = identifier
                substitute = self.trial_path('C0', 0)
                substitute.parent.mkdir()
                substitute.write_text(json.dumps(row))
                with self.assertRaisesRegex(ValueError, 'exact canonical development cells'):
                    self.freeze()
                self.trials['C0'][0] = original

    def test_missing_and_symlinked_block_registration_rejected(self):
        path = self.registration_dir / 'C2.json'
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing or unsafe'):
            self.freeze()
        path.symlink_to(self.registration_dir / 'C1.json')
        with self.assertRaisesRegex(ValueError, 'Missing or unsafe'):
            self.freeze()

    def test_registration_source_admission_limits_and_parent_are_bound(self):
        path, original = self.write_registration('C2')
        mutations = [dict(original, runner_sha256='0' * 64),
            dict(original, admission={'fixture': 'older qualified sources'}),
            dict(original, limits={'max_model_calls': 200, 'max_repair_cycles': 2}),
            dict(original, block='C1'), dict(original, extra='unexpected metadata')]
        parent_drift = copy.deepcopy(original)
        parent_drift['cells'][0]['parent'] = 'C1'
        mutations.append(parent_drift)
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                path.write_text(json.dumps(mutated))
                with self.assertRaisesRegex(ValueError, 'registration source, admission, limits or parent'):
                    self.freeze()
        path.write_text(json.dumps(original))
        self.assertEqual(self.freeze()['selection']['selected_parent'], 'C0')

    def test_distinct_valid_block_reviews_are_individually_reassessed(self):
        reviews = []
        for condition in ('C0', 'C1', 'C2'):
            path, document = self.write_registration(condition)
            document['qualification_review'] = {'fixture': 'current first20 evidence',
                'reviewer': condition + '-reviewer', 'notes': condition + '-specific review notes'}
            reviews.append(document['qualification_review'])
            path.write_text(json.dumps(document))
        document = self.freeze()
        self.assertEqual([call.args[2] for call in self.review_assess.call_args_list], reviews)
        self.assertEqual(verify(self.root, document), 'C0')

    def test_failed_or_stale_block_review_cannot_freeze(self):
        self.review_assess.return_value = {'paid_expansion_allowed': False}
        with self.assertRaisesRegex(ValueError, 'review has not cleared expansion'):
            self.freeze()
        self.review_assess.side_effect = ValueError('Review is stale or does not cover exactly the first 20 results')
        with self.assertRaisesRegex(ValueError, 'Review is stale'):
            self.freeze()

    def test_registration_hash_mutation_invalidates_existing_freeze(self):
        document = self.freeze()
        path = self.registration_dir / 'C0.json'
        path.write_text(json.dumps(json.loads(path.read_text()), indent=2))
        with self.assertRaisesRegex(ValueError, 'do not match reaudited evidence'):
            verify(self.root, document)

    def test_valid_c1_parent_is_supported_without_changing_selection_rule(self):
        self.c2_parent = 'C1'
        path = self.trial_path('C1', 10)
        row = json.loads(path.read_text())
        row['verifier_result']['rewards']['reward'] = 1
        path.write_text(json.dumps(row))
        for index in range(20):
            path = self.trial_path('C2', index)
            row = json.loads(path.read_text())
            row['agent_context']['metadata']['custom_parent'] = 'C1'
            path.write_text(json.dumps(row))
        self.write_registration('C2')
        document = self.freeze()
        self.assertEqual(document['selection']['selected_parent'], 'C1')
        self.assertEqual(verify(self.root, document), 'C1')

    def test_matching_task_set_does_not_allow_swapped_canonical_cell_identities(self):
        first, second = self.trial_path('C0', 0), self.trial_path('C0', 1)
        first_row, second_row = json.loads(first.read_text()), json.loads(second.read_text())
        first_row['task_id'], second_row['task_id'] = second_row['task_id'], first_row['task_id']
        first.write_text(json.dumps(first_row))
        second.write_text(json.dumps(second_row))
        with self.assertRaisesRegex(ValueError, 'registered condition identity'):
            self.freeze()
