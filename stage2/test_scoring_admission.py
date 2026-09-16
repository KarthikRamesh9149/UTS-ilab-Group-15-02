import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from gateway_policy import MODEL, ENDPOINT
from model_protocol import ModelSettings
from scoring_admission import RUNTIME_FILES, RUNTIME_CHECKS, LIVE_CHECKS, source_hashes, validate


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        folder = self.root / 'stage2'
        folder.mkdir()
        for name in RUNTIME_FILES: (folder / name).write_text('synthetic test source\n')
        settings = ModelSettings(64, 1., 'high')
        self.document = {'model': MODEL, 'endpoint': ENDPOINT,
            'settings': {'max_output_tokens': 64, 'temperature': 1., 'reasoning_effort': 'high'},
            'source_hashes': source_hashes(self.root), 'gateway_image': 'sha256:' + 'a' * 64,
            'guard_image': 'sha256:' + 'b' * 64, 'proofs': {}}
        for role, kind in {'runtime': 'synthetic_full_runner_not_benchmark_score',
                'terminus_live': 'actual_terminus_agent_live_setup_not_scored',
                'openhands_live': 'actual_openhands_agent_live_setup_not_scored',
                'custom_live': 'actual_custom_agent_live_setup_not_scored'}.items():
            evidence = {'kind': kind, 'status': 'passed', 'checks': dict.fromkeys(RUNTIME_CHECKS if role == 'runtime' else LIVE_CHECKS, True),
                'model_protocol_sha256': settings.fingerprint(), 'source_hashes': self.document['source_hashes'],
                'gateway_image': self.document['gateway_image'], 'guard_image': self.document['guard_image'],
                'live_api_calls': 0 if role == 'runtime' else 2}
            path = folder / (role + '.json')
            path.write_text(json.dumps(evidence))
            self.document['proofs'][role] = {'path': 'stage2/' + path.name,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def tearDown(self): self.temp.cleanup()

    def test_complete_matching_fixture_contract(self):
        self.assertEqual(validate(self.root, self.document), ModelSettings(64, 1., 'high'))

    def test_missing_role_is_not_qualified(self):
        del self.document['proofs']['custom_live']
        with self.assertRaises(ValueError): validate(self.root, self.document)

    def test_changed_evidence_is_rejected(self):
        (self.root / 'stage2/runtime.json').write_text('{}')
        with self.assertRaises(ValueError): validate(self.root, self.document)

    def test_changed_runtime_source_is_rejected(self):
        (self.root / 'stage2/scored_trial.py').write_text('changed synthetic source')
        with self.assertRaises(ValueError): validate(self.root, self.document)

    def test_changed_model_settings_are_rejected(self):
        self.document['settings']['temperature'] = 0.
        with self.assertRaises(ValueError): validate(self.root, self.document)

    def test_wrong_image_is_rejected(self):
        self.document['gateway_image'] = 'sha256:' + 'c' * 64
        with self.assertRaises(ValueError): validate(self.root, self.document)
