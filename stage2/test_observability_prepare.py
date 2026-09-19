import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from netcup.prepare_observability import configuration, prepare


class ObservabilityPreparationTests(unittest.TestCase):
    def fixture(self):
        services = {name: {'image': 'fixture:not-live', 'ports': ['9000:9000'],
                    'restart': 'always', 'environment': {'SALT': '${SALT:-mysalt}'}}
                    for name in ('langfuse-web', 'langfuse-worker', 'postgres', 'redis', 'minio', 'clickhouse')}
        return json.dumps({'services': services, 'volumes': {}}).encode()

    def test_digest_drift_rejected(self):
        with self.assertRaises(ValueError): configuration(b'untrusted')

    def test_private_bindings_no_automatic_restart_and_fresh_secrets(self):
        raw = self.fixture()
        with patch('netcup.prepare_observability.DIGEST', hashlib.sha256(raw).hexdigest()):
            compose, credentials = configuration(raw)
            _, again = configuration(raw)
        ports = [port for service in compose['services'].values() for port in service['ports']]
        self.assertEqual(ports, ['127.0.0.1:3300:3000', '127.0.0.1:3390:9000'])
        self.assertTrue(all(service['restart'] == 'no' for service in compose['services'].values()))
        self.assertNotEqual(credentials['secret_key'], again['secret_key'])
        self.assertNotIn('mysalt', json.dumps(compose))
        self.assertNotIn('OPENROUTER_API_KEY', json.dumps(compose))

    def test_private_exclusive_output(self):
        raw = self.fixture()
        with tempfile.TemporaryDirectory() as directory, \
             patch('netcup.prepare_observability.DIGEST', hashlib.sha256(raw).hexdigest()):
            destination = Path(directory) / 'private'
            prepare(destination, raw)
            self.assertEqual(destination.stat().st_mode & 0o077, 0)
            self.assertTrue(all(path.stat().st_mode & 0o077 == 0 for path in destination.iterdir()))
            with self.assertRaises(FileExistsError): prepare(destination, raw)

    def test_host_mount_rejected(self):
        doc = json.loads(self.fixture())
        doc['services']['langfuse-web']['volumes'] = ['/home:/host']
        raw = json.dumps(doc).encode()
        with patch('netcup.prepare_observability.DIGEST', hashlib.sha256(raw).hexdigest()):
            with self.assertRaises(ValueError): configuration(raw)
