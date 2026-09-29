"""Real temporary evidence/archive/export, with synthetic anchors and native/Git mocks."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_amended_predecessor as operator
import matched_repeat_policy as policy
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch
import test_no_cutoff_final_export as fixtures


class CaptureFixture(unittest.TestCase):
    def setUp(self):
        self.e = fixtures.PublicExportTests(); self.e.setUp(); self.addCleanup(self.e.doCleanups)
        self.repo = self.e.root; self.commit = self.e.commit
        self.f = NS(data=self.e.f.data, proof=self.e.f.f.f.proof, original={'synthetic_original': True},
            archive=self.e.folder / 'evidence.tar.gz')
        self.manifest = {'synthetic_manifest': True}
        self.save('stage2/input_manifest.json', producer._json(self.manifest))
        self.enterContext(patch.object(policy, 'INPUT_SHA256', export._hash(producer._json(self.manifest))))
        self.enterContext(patch.object(policy, 'anchors', return_value=self.f.proof['sources']))
        self.enterContext(patch.object(policy, 'schedule', return_value={'synthetic_schedule': True}))
        self.enterContext(patch.object(policy, 'validate_predecessors'))
        for name, value in (('CUSTOM_FINAL_QUALIFICATION_SHA256', phase.QUALIFICATION),
                ('CUSTOM_FINAL_REGISTRATION_SHA256', phase.REGISTRATION), ('CUSTOM_FINAL_SOURCES_SHA256', phase.SOURCE_SET)):
            self.enterContext(patch.object(policy, name, value))
        for name in self.f.data['reporting_source_files']:
            self.save(name, (report.REPORTING / name).read_bytes())
        self.current = {**self.f.proof['sources'],
            **{n[7:]: h for n, h in self.f.data['reporting_source_files'].items()},
            'input_manifest.json': policy.INPUT_SHA256}
        native = {'stage2/' + n: h for n, h in self.f.proof['sources'].items()}
        native.update({phase.RT + n: h for n, h in report.INPUTS.items()})
        native.update(self.f.proof['evidence_files']); native.update(report.HISTORICAL_INPUTS)
        self.e.bindings['native'] = native
        local = {**{'stage2/' + n: h for n, h in self.current.items()}, **export.PREREQUISITES}
        self.old_anchors = dict(proof=self.f.proof, block=self.f.data['registration'], manifest=self.manifest,
            native=dict(native), local=local)
        self.enterContext(patch.object(operator.old, '_anchors', side_effect=lambda _: deepcopy(self.old_anchors)))
        self.enterContext(patch.object(operator.old, '_operator', side_effect=lambda root: Path(root)))
        self.enterContext(patch.object(operator, '__file__', str(self.repo / 'stage2/matched_repeat_amended_predecessor.py')))
        self.e.run_export(); self.e.collect.reset_mock()
        self.git_bytes = {n: (self.repo / n).read_bytes() for n in local}
        self.git_bytes.update({export.DESTINATION + '/' + n: (self.e.target / n).read_bytes() for n in export.OUTPUTS})
        self.e.git.side_effect = self.git
        # Exercise actual current-source rereads after every observation.
        self.e.recheck.side_effect = lambda b: [launch._raw(n, h) for n, h in b['local'].items()]
        self.operator_audit = self.e.collect

    def git(self, operation, ref):
        if operation == 'rev-parse': return (self.commit + '\n').encode()
        return self.git_bytes[ref.split(':', 1)[1]]

    def save(self, name, raw): self.e.save(name, raw)

    def capture(self): return operator.capture(self.commit)


class CaptureTests(CaptureFixture):
    def test_real_capture_audit_archive_export_and_current_bytes_are_all_read(self):
        original = self.f.archive.read_bytes()
        with patch.object(archive, 'verify_archive', wraps=archive.verify_archive) as verify:
            record = self.capture()
        self.operator_audit.assert_called_once_with(self.commit); verify.assert_called_once()
        self.assertEqual(set(record), operator.FIELDS); self.assertFalse(record['paid_launch_ready'])
        self.assertEqual(record['absent_paths'], self.f.data['absent_paths'])
        self.assertEqual(sum(map(len, record['preserved_result_files'].values())), 182)
        self.assertEqual(len(record['predecessors']['blocks'][0]['results_sha256']), 89)
        self.assertEqual(self.f.archive.read_bytes(), original)
        self.assertNotIn('PRIVATE-SENTINEL', json.dumps(record))

    def test_saved_public_verification_result_cannot_replace_real_capture(self):
        with patch.object(export, 'verify_export', side_effect=AssertionError('No leaf metadata shortcut')):
            self.capture()
        self.operator_audit.assert_called_once()

    def test_unsupported_successor_is_refused_before_native_audit(self):
        with self.assertRaisesRegex(ValueError, 'OpenHands'): operator.capture(self.commit, 'openhands')
        self.operator_audit.assert_not_called()

    def test_uncommitted_current_reader_is_refused_before_native_audit(self):
        self.git_bytes['stage2/matched_repeat_amended_predecessor.py'] += b'\n'
        with self.assertRaisesRegex(ValueError, 'committed'): self.capture()
        self.operator_audit.assert_not_called()

    def test_uncommitted_public_results_refuse_handoff(self):
        self.git_bytes[export.DESTINATION + '/trials.json'] += b'\n'
        with self.assertRaisesRegex(ValueError, 'committed'): self.capture()

    def test_changed_original_anchor_map_is_not_a_schema_bypass(self):
        self.old_anchors['native'][phase.RT + 'no-cutoff-final-runtime.json'] = '0' * 64
        with self.assertRaises(ValueError): self.capture()
        self.operator_audit.assert_not_called()

    def test_changed_export_during_actual_native_audit_is_rejected(self):
        def change(_):
            path = self.e.target / 'trials.json'; path.write_bytes(path.read_bytes() + b'\n')
            return deepcopy(self.e.fresh)
        self.operator_audit.side_effect = change
        with self.assertRaises(ValueError): self.capture()

    def test_changed_archive_during_actual_native_audit_is_rejected(self):
        def change(_):
            self.f.archive.write_bytes(b'not the retained archive')
            return deepcopy(self.e.fresh)
        self.operator_audit.side_effect = change
        with self.assertRaises(ValueError): self.capture()

    def test_completed_export_failure_marker_refuses_capture(self):
        self.save(export.STATE + '/failure.json', b'{}')
        with self.assertRaises(ValueError): self.capture()
        self.operator_audit.assert_not_called()

    def test_stale_or_changed_fresh_audit_cannot_be_accepted(self):
        self.e.fresh['collected_utc'] = '2027-01-15T00:00:00+00:00'
        with self.assertRaises(ValueError): self.capture()

    def test_snapshot_raw_numeric_change_is_not_hidden_by_json_equality(self):
        path = self.e.folder / 'snapshot.json'
        path.write_bytes(path.read_bytes().replace(b'7200.0', b'7200'))
        with self.assertRaises(ValueError): self.capture()

    def test_missing_archive_and_partial_private_inventory_fail_without_recreation(self):
        archive_bytes = self.f.archive.read_bytes(); self.f.archive.unlink()
        with self.assertRaises(ValueError): self.capture()
        self.assertFalse(self.f.archive.exists()); self.assertTrue(archive_bytes)
        self.operator_audit.assert_not_called()
