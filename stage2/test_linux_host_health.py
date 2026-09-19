from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from linux_host_health import check_linux_host


class LinuxHealthTests(unittest.TestCase):
    def check(self, disk=50_000_000_000, available=12*1024**2, psi='0.00', cpus=8, memory=None):
        def read(path):
            if str(path) == '/proc/meminfo':
                return memory if memory is not None else f'MemTotal: 16777216 kB\nMemAvailable: {available} kB\n'
            if str(path) == '/proc/pressure/memory':
                return f'some avg10=0.01 avg60=0.01 avg300=0.01 total=1\nfull avg10={psi} avg60=0.00 avg300=0.00 total=0\n'
            raise AssertionError(path)
        with patch.object(Path, 'read_text', read), patch.object(Path, 'is_dir', return_value=True), \
             patch('linux_host_health.shutil.disk_usage', return_value=SimpleNamespace(free=disk)), \
             patch('linux_host_health.os.sched_getaffinity', return_value=set(range(cpus)), create=True):
            return check_linux_host()

    def test_healthy_linux(self):
        value = self.check()
        self.assertEqual(value['available_cpus'], 8)
        self.assertEqual(value['thermal'], 'not_exposed_by_virtual_machine')

    def test_resource_pressure_stops_before_trial(self):
        for values in ({'disk': 19_999_999_999}, {'available': 9*1024**2}, {'psi': '10.00'},
                       {'psi': 'nan'}, {'psi': '-1'}, {'cpus': 4}, {'memory': 'MemTotal: 1 kB\n'}):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                self.check(**values)

    def test_linux_dispatch(self):
        from qualify_oracle import check_host
        with patch('qualify_oracle.platform.system', return_value='Linux'), \
             patch('linux_host_health.check_linux_host', return_value={'fixture': True}) as check:
            self.assertEqual(check_host(), {'fixture': True})
            check.assert_called_once()
