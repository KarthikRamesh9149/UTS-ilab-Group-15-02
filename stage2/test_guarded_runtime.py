import unittest
from guarded_runtime import with_task_guard


class GuardedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.image = 'sha256:' + 'a' * 64
        self.source = {'services': {'main': {'network_mode': 'none', 'cpus': 4,
            'mem_limit': '8192m', 'volumes': ['socket:/socket:ro'],
            'depends_on': {'model-gateway': {'condition': 'service_healthy'}}},
            'model-gateway': {'network_mode': 'none'}}}

    def test_preserves_limits_socket_gateway_and_input(self):
        result = with_task_guard(self.source, self.image)
        main = result['services']['main']
        self.assertEqual(main['cpus'], 4)
        self.assertEqual(main['mem_limit'], '8192m')
        self.assertEqual(main['volumes'], ['socket:/socket:ro'])
        self.assertEqual(result['services']['model-gateway'], self.source['services']['model-gateway'])
        self.assertEqual(self.source['services']['main']['network_mode'], 'none')
        self.assertEqual(len(main['depends_on']), 2)
        self.assertIn('NET_ADMIN', main['cap_drop'])

    def test_rejects_mutable_image(self):
        with self.assertRaises(ValueError):
            with_task_guard(self.source, 'guard:latest')

    def test_rejects_task_network_override(self):
        self.source['services']['main']['network_mode'] = 'host'
        with self.assertRaises(ValueError):
            with_task_guard(self.source, self.image)

    def test_rejects_privileged_task(self):
        for key, value in [('privileged', True), ('cap_add', ['NET_ADMIN']), ('ports', ['80:80'])]:
            with self.subTest(key=key):
                self.source['services']['main'][key] = value
                with self.assertRaises(ValueError):
                    with_task_guard(self.source, self.image)
                del self.source['services']['main'][key]
