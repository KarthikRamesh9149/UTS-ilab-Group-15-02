import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from qualify_oracle import check_host, frozen_dataset


class OracleQualificationTests(unittest.TestCase):
    def host(self, disk=30_000_000_000, pressure='1', thermal='No thermal warning level has been recorded'):
        def output(command, **kwargs):
            return thermal if command[0] == 'pmset' else pressure
        with patch('qualify_oracle.shutil.disk_usage', return_value=SimpleNamespace(free=disk)), \
             patch('qualify_oracle.subprocess.check_output', side_effect=output):
            return check_host()

    def test_healthy_host_allowed(self):
        self.assertEqual(self.host()['memory_pressure_level'], 1)

    def test_disk_critical_memory_and_throttling_stop(self):
        for arguments in [{'disk': 19_999_999_999}, {'pressure': '4'},
                          {'thermal': 'CPU_Speed_Limit = 80'}, {'thermal': 'Thermal_Level = 1'}]:
            with self.subTest(arguments=arguments), self.assertRaises(RuntimeError):
                self.host(**arguments)

    def test_unknown_memory_signal_fails_closed(self):
        with self.assertRaises(ValueError):
            self.host(pressure='unknown')

    def test_dataset_mutation_or_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stage2').mkdir()
            (root / 'dataset').mkdir()
            path = root / 'dataset/file'
            path.write_bytes(b'frozen')
            (root / 'stage2/dataset_provenance.json').write_text(json.dumps({
                'dataset_path': 'dataset', 'canonical': {'file_hashes': [
                    {'path': 'file', 'sha256': hashlib.sha256(b'frozen').hexdigest()}]}}))
            self.assertEqual(frozen_dataset(root), root / 'dataset')
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                frozen_dataset(root)
            path.write_bytes(b'frozen')
            (root / 'dataset/extra').touch()
            with self.assertRaises(ValueError):
                frozen_dataset(root)
