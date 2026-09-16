from pathlib import Path
import tempfile
import unittest
from production_compose import compose_runtime


class ProductionComposeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name)
        private = path / 'private'
        private.write_text('synthetic')
        private.chmod(0o600)
        self.options = dict(gateway_image='sha256:' + 'a'*64, guard_image='sha256:' + 'b'*64,
            state_dir=path, tokenizer_dir=path, credential_file=private, token_file=private,
            trial_id='test-trial', stage='development', uid=501, gid=20)

    def tearDown(self):
        self.temp.cleanup()

    def test_task_has_no_host_or_model_mounts(self):
        services = compose_runtime(**self.options)['services']
        self.assertNotIn('volumes', services['main'])
        self.assertEqual(services['main']['network_mode'], 'service:task-network-guard')
        self.assertEqual(services['model-relay']['network_mode'], 'service:task-network-guard')
        self.assertEqual(services['model-gateway']['networks'], ['uts-gateway-egress'])
        self.assertEqual(services['model-relay']['volumes'], [
            {'type': 'volume', 'source': 'model-socket', 'target': '/socket', 'read_only': True}])

    def test_only_gateway_sees_credentials_and_ledger(self):
        services = compose_runtime(**self.options)['services']
        for name, service in services.items():
            mounts = [m['target'] for m in service.get('volumes', [])]
            if name == 'model-gateway':
                self.assertIn('/run/openrouter.env', mounts)
                self.assertIn('/study/.runtime/stage2', mounts)
            else:
                self.assertNotIn('/run/openrouter.env', mounts)
                self.assertNotIn('/study/.runtime/stage2', mounts)

    def test_no_published_ports_or_privileged_services(self):
        for service in compose_runtime(**self.options)['services'].values():
            self.assertFalse(service.get('privileged'))
            self.assertFalse(service.get('ports'))

    def test_input_validation(self):
        for key, value in [('uid', True), ('gid', -1), ('trial_id', '../bad'),
                           ('gateway_image', 'image:latest'), ('stage', 'unlimited')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                compose_runtime(**dict(self.options, **{key: value}))

    def test_refuses_missing_mount_sources(self):
        self.options['state_dir'] = Path(self.temp.name) / 'missing'
        with self.assertRaises(ValueError):
            compose_runtime(**self.options)

    def test_refuses_public_credentials(self):
        self.options['credential_file'].chmod(0o644)
        with self.assertRaises(ValueError):
            compose_runtime(**self.options)
