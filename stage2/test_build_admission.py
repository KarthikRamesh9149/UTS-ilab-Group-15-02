import unittest

from build_admission import build
from model_protocol import ModelSettings
import test_scoring_admission


class BuildAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_scoring_admission.AdmissionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.proofs = {role: value['path'] for role, value in self.fixture.document['proofs'].items()}

    def test_builds_only_matching_passed_proofs(self):
        result = build(self.fixture.root, proofs=self.proofs, settings=ModelSettings(64, 1., 'high'))
        self.assertEqual(result['proofs'], self.fixture.document['proofs'])
        self.assertEqual(result['setup_timeout_seconds'], 900)

    def test_changed_protocol_is_rejected(self):
        with self.assertRaises(ValueError):
            build(self.fixture.root, proofs=self.proofs, settings=ModelSettings(8192, 1., 'high'))

    def test_missing_proof_is_rejected(self):
        del self.proofs['custom_live']
        with self.assertRaises(ValueError):
            build(self.fixture.root, proofs=self.proofs, settings=ModelSettings(64, 1., 'high'))

    def test_path_escape_is_rejected(self):
        self.proofs['runtime'] = '../outside.json'
        with self.assertRaises(ValueError):
            build(self.fixture.root, proofs=self.proofs, settings=ModelSettings(64, 1., 'high'))
