"""Synthetic provenance contracts, never substitute live qualification evidence."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from deferred_billing import _encoded, _write
from receipt_runtime_transition import (ADDED, CHANGED, CHECKS, TRANSITION,
    descriptor_matches, digest, gateway_for_trial, qualified_transition)
from scoring_admission import source_hashes, validate
from model_protocol import ModelSettings
import test_scoring_admission as fixtures


class ReceiptRuntimeTransitionTests(unittest.TestCase):
    def setUp(self):
        fixture = self.fixture = fixtures.AdmissionTests()
        fixture.setUp(); self.addCleanup(fixture.tearDown)
        self.root = fixture.root
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True, mode=0o700)
        self.admission = copy.deepcopy(fixture.document)
        for name in ADDED:
            self.admission['source_hashes'].pop(name)
        # Original live proofs continue to bind the original sources/images.
        for binding in self.admission['proofs'].values():
            path = self.root / binding['path']
            proof = json.loads(path.read_text())
            proof['source_hashes'] = self.admission['source_hashes']
            path.write_text(json.dumps(proof))
            binding['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.registration = {'admission': self.admission, 'source_hashes': dict(self.admission['source_hashes']),
                             'cells': ['original synthetic cell'], 'qualification_review': {'original': True}}
        (self.root / 'stage2/budget_policy.json').write_text('frozen budget')
        self.registration['source_hashes']['budget_policy.json'] = hashlib.sha256(b'frozen budget').hexdigest()
        _write(self.runtime / 'baseline-matrix.json', self.registration)
        for name in CHANGED:
            (self.root / 'stage2' / name).write_text('candidate accounting source')
        self.sources = source_hashes(self.root)
        self.settings = ModelSettings(**self.admission['settings'])
        folder = self.runtime / 'accounting-qualification-v1'; folder.mkdir(mode=0o700)
        self.activation = self.runtime / 'receipt-accounting-activations-v1' / ('scored--' + 'e' * 64 + '.json')
        self.activation.parent.mkdir(mode=0o700); _write(self.activation, {'synthetic': True})
        result = self.runtime / 'scored-trials/original/result.json'
        result.parent.mkdir(parents=True, mode=0o700); result.parent.parent.chmod(0o700)
        _write(result, {'synthetic': True})
        self.value = {'schema_version': 1, 'kind': 'qualified_additive_receipt_accounting_transition',
            'scope': 'accounting_only_no_replay_no_model_or_limit_change', 'reviewer': 'unit-test fixture only',
            'original_admission_sha256': digest(self.admission),
            'baseline_registration_sha256': hashlib.sha256((self.runtime / 'baseline-matrix.json').read_bytes()).hexdigest(),
            'source_hashes': self.sources, 'gateway_image': 'sha256:' + 'c' * 64,
            'guard_image': self.admission['guard_image'], 'host_environment': self.admission['host_environment'],
            'model_protocol_sha256': self.settings.fingerprint(), 'proofs': {},
            'activation_files': {str(self.activation.relative_to(self.runtime)): hashlib.sha256(self.activation.read_bytes()).hexdigest()},
            'preserved_results': {str(result.relative_to(self.runtime)): hashlib.sha256(result.read_bytes()).hexdigest()}}
        self.proofs = {}
        for role, checks in CHECKS.items():
            proof = {key: self.value[key] for key in ('source_hashes', 'gateway_image', 'guard_image',
                     'host_environment', 'model_protocol_sha256')}
            proof.update(status='passed', live_api_calls=0, checks=dict.fromkeys(checks, True))
            if role == 'offline': proof.update(tests_run=1, failures=0, errors=0, skipped=0)
            if role == 'replay':
                proof.update(activation_files=self.value['activation_files'], preserved_results=self.value['preserved_results'])
            if role == 'gateway': proof['parent_image'] = self.admission['gateway_image']
            if role == 'synthetic': proof['kind'] = 'synthetic_full_runner_not_benchmark_score'
            self.proofs[role] = proof
            self.save_proof(role)
        self.save()

    def save_proof(self, role):
        path = self.runtime / 'accounting-qualification-v1' / (role + '.json')
        path.write_bytes(_encoded(self.proofs[role])); path.chmod(0o600)
        self.value['proofs'][role] = {'path': str(path.relative_to(self.runtime)),
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def save(self):
        path = self.runtime / TRANSITION
        path.write_bytes(_encoded(self.value)); path.chmod(0o600)

    def test_qualified_transition_preserves_original_admission_and_live_proofs(self):
        original = copy.deepcopy(self.admission)
        raw = (self.runtime / 'baseline-matrix.json').read_bytes()
        self.assertEqual(validate(self.root, self.admission), self.settings)
        self.assertEqual(self.admission, original)
        self.assertEqual((self.runtime / 'baseline-matrix.json').read_bytes(), raw)

    def test_changed_candidate_without_transition_remains_unqualified(self):
        (self.runtime / TRANSITION).unlink()
        with self.assertRaisesRegex(ValueError, 'Runtime code changed'):
            validate(self.root, self.admission)

    def test_stale_runtime_proof_is_not_relabelled_as_fresh(self):
        self.proofs['synthetic']['source_hashes'] = self.admission['source_hashes']
        self.save_proof('synthetic'); self.save()
        with self.assertRaises(ValueError): validate(self.root, self.admission)

    def test_each_required_proof_and_check_is_mandatory(self):
        original = copy.deepcopy(self.value)
        for role in CHECKS:
            with self.subTest(role=role):
                self.value = copy.deepcopy(original); del self.value['proofs'][role]; self.save()
                with self.assertRaises(ValueError): validate(self.root, self.admission)
        self.value = original
        for role, checks in CHECKS.items():
            for check in checks:
                with self.subTest(role=role, check=check):
                    self.proofs[role]['checks'][check] = False; self.save_proof(role); self.save()
                    with self.assertRaises(ValueError): validate(self.root, self.admission)
                    self.proofs[role]['checks'][check] = True; self.save_proof(role)

    def test_source_changes_outside_accounting_rejected_even_if_manifest_updated(self):
        for name in ('native_agents.py', 'model_protocol.py', 'study_budget.py', 'trial_estimator.py'):
            with self.subTest(name=name):
                (self.root / 'stage2' / name).write_text('forbidden change')
                self.value['source_hashes'] = source_hashes(self.root); self.save()
                with self.assertRaisesRegex(ValueError, 'other source changes'):
                    validate(self.root, self.admission)
                (self.root / 'stage2' / name).write_text('synthetic test source\n')

    def test_frozen_nonruntime_budget_input_cannot_change(self):
        (self.root / 'stage2/budget_policy.json').write_text('larger allowance')
        with self.assertRaisesRegex(ValueError, 'non-runtime'): validate(self.root, self.admission)

    def test_modified_candidate_is_rejected(self):
        (self.root / 'stage2/receipt_accounting.py').write_text('unqualified change')
        with self.assertRaises(ValueError): validate(self.root, self.admission)

    def test_original_result_registration_or_receipt_activation_cannot_change(self):
        for path in (self.runtime / 'baseline-matrix.json', self.activation,
                     self.runtime / 'scored-trials/original/result.json'):
            original = path.read_bytes(); path.write_bytes(original + b' ')
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                validate(self.root, self.admission)
            path.write_bytes(original)

    def test_original_failed_live_proof_still_rejected(self):
        entry = self.admission['proofs']['terminus_live']
        path = self.root / entry['path']; path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evidence changed'): validate(self.root, self.admission)

    def test_original_admission_cannot_be_substituted(self):
        changed = copy.deepcopy(self.admission); changed['setup_timeout_seconds'] = 9999
        with self.assertRaises(ValueError): validate(self.root, changed)

    def test_host_protocol_guard_and_gateway_bindings_required(self):
        original = copy.deepcopy(self.value)
        for key, changed in (('host_environment', {}), ('model_protocol_sha256', '0' * 64),
                ('guard_image', 'sha256:' + 'd' * 64), ('gateway_image', self.admission['gateway_image'])):
            self.value = copy.deepcopy(original); self.value[key] = changed; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): validate(self.root, self.admission)

    def test_qualified_gateway_selection_is_explicit_and_records_transition(self):
        image, binding = gateway_for_trial(self.root, self.admission['gateway_image'],
                                          self.admission['guard_image'], self.settings)
        self.assertEqual(image, self.value['gateway_image'])
        self.assertEqual(binding, hashlib.sha256((self.runtime / TRANSITION).read_bytes()).hexdigest())
        with self.assertRaises(ValueError):
            gateway_for_trial(self.root, image, self.admission['guard_image'], self.settings)

    def test_no_transition_keeps_original_gateway(self):
        (self.runtime / TRANSITION).unlink()
        self.assertEqual(gateway_for_trial(self.root, 'original', 'guard', self.settings), ('original', None))

    def test_descriptor_allows_only_current_qualified_source_binding_difference(self):
        expected = copy.deepcopy(self.registration); expected['source_hashes'].update(self.sources)
        self.assertTrue(descriptor_matches(self.root, self.admission, self.registration, expected))
        altered = dict(expected, source_hashes={'unqualified': 'source'})
        self.assertFalse(descriptor_matches(self.root, self.admission, self.registration, altered))
        for field, changed in (('cells', ['another task']), ('qualification_review', {}), ('admission', {})):
            altered = dict(expected, **{field: changed})
            self.assertFalse(descriptor_matches(self.root, self.admission, self.registration, altered))

    def test_tampered_or_symlinked_proof_and_public_transition_rejected(self):
        path = self.runtime / self.value['proofs']['offline']['path']
        original = path.read_bytes(); path.write_bytes(original + b' ')
        with self.assertRaises(ValueError): validate(self.root, self.admission)
        path.write_bytes(original)
        path.rename(path.with_suffix('.saved')); path.symlink_to(path.with_suffix('.saved'))
        with self.assertRaises((ValueError, OSError)): validate(self.root, self.admission)

    def test_public_transition_rejected(self):
        (self.runtime / TRANSITION).chmod(0o644)
        with self.assertRaises(ValueError): validate(self.root, self.admission)

    def test_paid_or_skipped_or_incomplete_qualification_is_not_accepted(self):
        original = copy.deepcopy(self.proofs)
        for key, value in (('live_api_calls', 1), ('tests_run', 0), ('skipped', 1), ('errors', 1)):
            self.proofs = copy.deepcopy(original); self.proofs['offline'][key] = value
            self.save_proof('offline'); self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): validate(self.root, self.admission)


if __name__ == '__main__':
    unittest.main()
