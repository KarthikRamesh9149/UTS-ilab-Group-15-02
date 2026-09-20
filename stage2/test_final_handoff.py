"""Synthetic final matrices only; no provider, SSH, report or real ZIP export."""
import hashlib
import json
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import zipfile

import final_handoff
from model_protocol import ModelSettings
import test_export_final as fixtures


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ExportTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.fixture.registration['freeze']['files'] = {name: 'f' * 64 for name in final_handoff.FROZEN_FILES}
        self.fixture.registration['freeze']['selection']['selected'] = 'C2'
        self.fixture.registration['review']['private_notes'] = 'PRIVATE_REVIEW_DO_NOT_COPY'
        (self.fixture.runtime / 'final-matrix.json').write_text(json.dumps(self.fixture.registration))
        self.settings = ModelSettings(8192, 1., 'high')
        self.fixture.validate.return_value = self.settings
        for identifier, row in self.fixture.rows.items():
            row['model_protocol_sha256'] = self.settings.fingerprint()
            row['billing']['model_protocol_sha256'] = self.settings.fingerprint()
            (self.fixture.runtime / 'scored-trials' / identifier / 'result.json').write_text(json.dumps(row))
        path = self.fixture.runtime / 'model-protocol.json'
        path.write_text(json.dumps(self.settings.document()))
        path.chmod(0o600)
        self.destination = self.root / 'output/final-evidence/complete-run'

    def package(self):
        return final_handoff.package(self.root, self.destination)

    def test_complete_local_package_is_code_free_and_hashed(self):
        (self.root / '.env').write_text('PRIVATE_CREDENTIAL_DO_NOT_COPY')
        (self.root / 'source.py').write_text('PRIVATE_SOURCE_DO_NOT_COPY')
        archive = self.package()
        with zipfile.ZipFile(archive) as zipped:
            self.assertIsNone(zipped.testzip())
            self.assertEqual(set(zipped.namelist()), set(final_handoff.EXPORT_NAMES) | {'README.md', 'METHOD.json', 'CHECKSUMS.json'})
            checksums = json.loads(zipped.read('CHECKSUMS.json'))
            for name, value in checksums.items():
                self.assertEqual(hashlib.sha256(zipped.read(name)).hexdigest(), value)
            for name in zipped.namelist():
                self.assertNotIn(b'DO_NOT_COPY', zipped.read(name))
                self.assertNotIn(b'DO_NOT_EXPORT_THIS_RAW_TEXT', zipped.read(name))
            self.assertIn(b'not total project spending', zipped.read('README.md'))
            method = json.loads(zipped.read('METHOD.json'))
            provenance = json.loads(zipped.read('provenance.json'))
            self.assertEqual(method['frozen_source_sha256'], self.fixture.registration['freeze']['files'])
            self.assertEqual(method['final_registration_sha256'], provenance['final_registration_sha256'])
            self.assertEqual(method['model_protocol'], self.settings.document())
        marker = json.loads((self.destination / 'archive_complete.json').read_text())
        self.assertEqual(marker['rows'], 267)
        self.assertEqual(marker['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertIs(marker['published'], False)
        self.assertFalse(stat.S_IMODE(archive.stat().st_mode) & 0o077)
        self.assertEqual(self.fixture.completed_cell.call_count, 267)

    def test_incomplete_matrix_makes_no_delivery_output(self):
        identifier = next(iter(self.fixture.rows))
        (self.fixture.runtime / 'scored-trials' / identifier / 'result.json').unlink()
        with self.assertRaises(ValueError): self.package()
        self.assertFalse(self.destination.parent.exists())

    def test_billing_failure_makes_no_delivery_output(self):
        self.fixture.completed_cell.side_effect = ValueError('unresolved billing')
        with self.assertRaises(ValueError): self.package()
        self.assertFalse(self.destination.exists())

    def test_existing_output_is_not_overwritten_or_reaudited(self):
        archive = self.package()
        before = archive.read_bytes()
        self.fixture.completed_cell.reset_mock()
        with self.assertRaises(FileExistsError): self.package()
        self.assertEqual(archive.read_bytes(), before)
        self.fixture.completed_cell.assert_not_called()

    def test_output_outside_local_ignored_folder_is_rejected(self):
        for destination in (self.root / 'stage2/results', self.root / 'output/final-evidence/../escape'):
            with self.subTest(path=destination), self.assertRaises(ValueError):
                final_handoff.package(self.root, destination)
        self.fixture.completed_cell.assert_not_called()

    def test_symlinked_output_is_rejected(self):
        outside = self.root / 'elsewhere'
        outside.mkdir()
        (self.root / 'output').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): self.package()
        self.assertEqual(list(outside.iterdir()), [])

    def test_bad_export_rejected_before_output(self):
        original = final_handoff.export
        for kind in ('corrupt', 'extra', 'symlink', 'wrong_rows', 'wrong_scope', 'wrong_model'):
            def tamper(root, destination):
                folder = original(root, destination)
                if kind == 'corrupt':
                    (folder / 'final_trials.csv').write_text('corrupt')
                elif kind == 'extra':
                    (folder / 'source.py').write_text('DO_NOT_COPY')
                elif kind == 'symlink':
                    (folder / 'comparison.json').unlink()
                    (folder / 'comparison.json').symlink_to(root / 'stage2/input_manifest.json')
                else:
                    marker = json.loads((folder / 'export_complete.json').read_text())
                    if kind == 'wrong_rows':
                        marker['rows'] = 266
                    else:
                        provenance = json.loads((folder / 'provenance.json').read_text())
                        provenance['scope' if kind == 'wrong_scope' else 'model_protocol_sha256'] = 'wrong'
                        raw = json.dumps(provenance).encode()
                        (folder / 'provenance.json').write_bytes(raw)
                        marker['files']['provenance.json'] = hashlib.sha256(raw).hexdigest()
                    (folder / 'export_complete.json').write_text(json.dumps(marker))
                return folder
            with self.subTest(kind=kind), patch('final_handoff.export', side_effect=tamper):
                with self.assertRaises(ValueError): self.package()
                self.assertFalse(self.destination.exists())

    def test_failed_zip_has_no_completion_marker(self):
        with patch('final_handoff.zipfile.ZipFile.writestr', side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError): self.package()
        self.assertFalse((self.destination / 'archive_complete.json').exists())

    def test_changed_registration_after_export_cannot_supply_method_metadata(self):
        original = final_handoff.export
        def replace_registration(root, destination):
            folder = original(root, destination)
            (self.fixture.runtime / 'final-matrix.json').write_text('{}')
            return folder
        with patch('final_handoff.export', side_effect=replace_registration):
            with self.assertRaises(ValueError): self.package()
        self.assertFalse(self.destination.exists())

    def test_only_source_hash_allowlist_can_enter_method_metadata(self):
        original = self.fixture.registration['freeze']['files']
        mutations = [dict(original, private_key='DO_NOT_COPY'),
                     {name: 'DO_NOT_COPY' for name in original}, {}]
        for files in mutations:
            self.fixture.registration['freeze']['files'] = files
            (self.fixture.runtime / 'final-matrix.json').write_text(json.dumps(self.fixture.registration))
            with self.subTest(files=files), self.assertRaises(ValueError): self.package()
            self.assertFalse(self.destination.exists())

    def test_repeated_audit_of_unchanged_evidence_is_deterministic(self):
        first = self.package().read_bytes()
        second = final_handoff.package(self.root, self.destination.with_name('second-export')).read_bytes()
        self.assertEqual(first, second)
