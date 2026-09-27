"""Producer sequencing and real private-file checks, with mocked native work."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qualify_no_cutoff_custom as qualifier
import no_cutoff_custom_policy as policy
import no_cutoff_custom_runtime as runtime
from credit_only_experiment import digest
from scored_gateway import durable_json, private_directory
from test_no_cutoff_custom_policy import document_fixture, qualification_fixture


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.doc = document_fixture()
        self.enterContext(patch.object(policy, 'ORIGINAL_FREEZE_SHA256', policy.fingerprint(self.doc)))
        self.proof = qualification_fixture(self.doc)
        self.save_outputs()

    def save_outputs(self):
        values = {self.proof['regression_path'] + '/regression.json': self.proof['offline'],
                  self.proof['regression_path'] + '/regression.txt': {'synthetic_test_log': True}}
        for case in self.proof['synthetic']:
            values[case['runtime_path'] + '/evidence.json'] = case
            values[case['runtime_path'] + '/.runtime/stage2/scored-trials/synthetic-nc-' + case['mode'] + '/result.json'] = dict(
                status='interrupted' if case['mode'] == 'cancel_setup' else 'verified',
                harness=policy.CONDITION, custom_study=policy.EXPERIMENT, model_revoked=True,
                containers_removed=True, networks_removed=True, volumes_removed=True,
                verifier_result=None if case['mode'] == 'cancel_setup' else {'rewards': {'reward': 1}})
        for name, value in values.items():
            path = self.root / name; private_directory(path.parent); durable_json(path, value)
            self.proof['evidence_files'][name] = digest(path)

    def test_bound_outputs_are_read_not_just_boolean_claims(self):
        policy.validate_qualification(self.doc, self.proof)
        runtime.verify_native_files(self.root, self.proof)
        name = next(iter(self.proof['evidence_files']))
        (self.root / name).write_text('{}')
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)

    def test_changed_result_rehashed_still_needs_revocation_and_verifier(self):
        name = self.proof['synthetic'][0]['runtime_path'] + '/.runtime/stage2/scored-trials/synthetic-nc-tools/result.json'
        path = self.root / name
        value = json.loads(path.read_text()); value['model_revoked'] = False
        path.write_text(json.dumps(value)); self.proof['evidence_files'][name] = digest(path)
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)

    def test_missing_output_and_path_escape_rejected(self):
        bad = deepcopy(self.proof); bad['evidence_files'].pop(next(iter(bad['evidence_files'])))
        with self.assertRaises(ValueError): policy.validate_qualification(self.doc, bad)
        bad = deepcopy(self.proof); bad['synthetic'][0]['runtime_path'] = '../../original'
        with self.assertRaises(ValueError): policy.validate_qualification(self.doc, bad)

    def test_symlinked_output_cannot_substitute_evidence(self):
        name = next(iter(self.proof['evidence_files'])); path = self.root / name
        other = path.with_name('copy.json'); path.rename(other); path.symlink_to(other)
        with self.assertRaises(ValueError): runtime.verify_native_files(self.root, self.proof)

    def test_private_save_retains_and_never_overwrites_different_input(self):
        path = self.root / 'saved.json'
        qualifier.save_once(path, {'value': 1.0}); qualifier.save_once(path, {'value': 1.0})
        with self.assertRaises(ValueError): qualifier.save_once(path, {'value': 1})
        self.assertEqual(path.read_text().count('1.0'), 1)


class ProducerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.rt = private_directory(self.root / '.runtime/stage2')
        self.enterContext(patch.object(runtime, 'DEPLOYMENT', self.root))

    def test_completed_qualification_and_started_attempts_refuse_before_authentication(self):
        for name in (policy.QUALIFICATION, 'scored-trials/started/started.json'):
            path = self.rt / name; private_directory(path.parent); durable_json(path, {})
            with patch.object(qualifier.original, 'authenticate') as auth:
                with self.assertRaises(ValueError): qualifier.qualify(self.root)
                auth.assert_not_called()
            path.unlink()

    def test_authentication_precedes_ancestor_locks_and_container_check(self):
        calls = []
        def auth(*args): calls.append('authenticate'); return {'synthetic': True}
        def lock(*args): calls.append('lock')
        def check(*args): calls.append('recheck')
        with patch.object(qualifier, 'read_candidate', return_value={}), \
                patch.object(qualifier.original, 'authenticate', side_effect=auth), \
                patch.object(qualifier, 'lock_all', side_effect=lock), \
                patch.object(qualifier.original, 'recheck', side_effect=check), \
                patch.object(qualifier, 'docker', return_value='owned'):
            with self.assertRaisesRegex(ValueError, 'owned'): qualifier.qualify(self.root)
        self.assertEqual(calls, ['authenticate', 'lock', 'recheck'])

    def test_native_regression_failure_retained_without_qualification(self):
        class Fail(unittest.TestCase):
            def runTest(self): self.fail('Synthetic producer test failure')
        folder = private_directory(self.rt / 'fixture')
        with patch.object(qualifier.unittest.defaultTestLoader, 'loadTestsFromNames', return_value=unittest.TestSuite([Fail()])):
            with self.assertRaises(ValueError): qualifier.regression(folder)
        self.assertEqual(json.loads((folder / 'regression.json').read_text())['failures'], 1)
        self.assertTrue((folder / 'regression.txt').is_file())
        self.assertFalse((self.rt / policy.QUALIFICATION).exists())

    def test_gateway_dockerfile_copies_every_qualified_image_source(self):
        code = (Path(__file__).parent / 'fixtures/Dockerfile.custom-no-cutoff').read_text()
        copied = next(line for line in code.splitlines() if line.startswith('COPY ')).split()[1:-1]
        self.assertEqual(set(copied), set(qualifier.IMAGE_FILES))
        source = Path(qualifier.__file__).read_text()
        self.assertIn("'--pull=false', '--network=none'", source)
        self.assertIn('original.authenticate(root, document)', source)
        self.assertNotIn('ObservedOpenRouter(', source)


if __name__ == '__main__': unittest.main()
