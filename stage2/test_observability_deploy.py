import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from netcup.deploy_observability import run, validate
from netcup.prepare_observability import EXPECTED, SOURCE, DIGEST


class ObservabilityDeploymentTests(unittest.TestCase):
    def fixture(self):
        document = {'name': 'uts-observability', 'volumes': {}, 'services': {name: {
            'image': 'registry.example/' + name + ':4', 'restart': 'no', 'ports': []} for name in EXPECTED}}
        document['services']['langfuse-web']['ports'] = ['127.0.0.1:3300:3000']
        document['services']['minio']['ports'] = ['127.0.0.1:3390:9000']
        return document

    def test_unapproved_ports_mounts_and_capabilities_rejected(self):
        original = self.fixture()
        validate(original)
        for key, value in [('ports', ['3300:3000']), ('volumes', ['/home:/host']),
                           ('privileged', True), ('restart', 'always'), ('env_file', '.env'),
                           ('network_mode', 'host'), ('cap_add', ['NET_ADMIN'])]:
            document = copy.deepcopy(original)
            document['services']['langfuse-web'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate(document)

    def test_images_pinned_before_start_and_existing_deployment_not_upgraded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); directory = root / '.runtime/stage2/observability-test'
            directory.mkdir(mode=0o700, parents=True)
            for name, data in [('compose.json', self.fixture()), ('credentials.json', {}),
                               ('source.json', {'url': SOURCE, 'sha256': DIGEST})]:
                path = directory / name; path.write_text(json.dumps(data)); path.chmod(0o600)
            def inspect(command, **kwargs):
                if command[1] == 'ps': return ''
                image = command[-1]
                return json.dumps([{'Id': 'sha256:' + 'a'*64,
                    'RepoDigests': [image.rsplit(':',1)[0] + '@sha256:' + 'b'*64]}])
            execute = Mock()
            result = run(root, directory, execute=execute, output=inspect)
            self.assertEqual(len(result['pinned_services']), 6)
            pinned = json.loads((directory / 'compose.pinned.json').read_text())
            self.assertTrue(all('@sha256:' in s['image'] for s in pinned['services'].values()))
            self.assertIn('--wait', execute.call_args[0][0])
            self.assertEqual((directory / 'compose.pinned.json').stat().st_mode & 0o077, 0)
            with self.assertRaises(ValueError): run(root, directory, execute=execute, output=inspect)
            self.assertEqual(execute.call_count, 3)

    def test_running_benchmark_prevents_any_deployment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); directory = root / '.runtime/stage2/observability-test'
            directory.mkdir(mode=0o700, parents=True)
            for name, data in [('compose.json', self.fixture()), ('credentials.json', {}),
                               ('source.json', {'url': SOURCE, 'sha256': DIGEST})]:
                p = directory/name; p.write_text(json.dumps(data)); p.chmod(0o600)
            execute = Mock()
            with self.assertRaises(ValueError):
                run(root, directory, execute=execute, output=lambda *a,**k:'uts-scored-active-main-1\n')
            execute.assert_not_called()
