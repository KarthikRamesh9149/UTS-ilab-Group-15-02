"""One-shot retained state with mocked native audit; no native operation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_inventory_audit as audit
import no_cutoff_final_audit_transport as legacy
import no_cutoff_final_reporting as launch
import no_cutoff_final_transport as transport
import test_no_cutoff_final_transport as fixtures


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory()); self.root = Path(self.temp).resolve()
        self.enterContext(patch.object(launch, 'REPO', self.root))
        self.enterContext(patch.object(audit, '__file__', str(self.root / 'stage2/no_cutoff_final_inventory_audit.py')))
        (self.root / '.runtime').mkdir(mode=0o755); (self.root / '.runtime/netcup').mkdir(mode=0o700)
        # Other in-process tests may retain a restrictive umask. Set fixture
        # permissions explicitly so readable-parent and drift checks are real.
        (self.root / '.runtime').chmod(0o755)
        (self.root / '.runtime/netcup').chmod(0o700)
        self.bindings = dict(commit='a' * 40, native={}, reporting={}, local={}, anchors={})
        self.enterContext(patch.object(launch, '_prepare', return_value=self.bindings))
        self.enterContext(patch.object(launch, '_recheck'))
        self.preflight = self.enterContext(patch.object(launch, 'inspect_deployment'))
        self.data = {'aggregates': {'full89': {'passed': 50, 'failed': 36, 'no_verifier_result': 3}}}
        self.raw = json.dumps(self.data).encode()
        self.called = self.enterContext(patch.object(launch, '_audit', return_value=(self.data, self.raw, fixtures.metadata(self.raw))))

    def run_audit(self): return audit.collect('a' * 40)

    def test_exclusive_validated_snapshot_is_not_backup_or_paid_admission(self):
        result = self.run_audit(); folder = self.root / audit.DESTINATION
        self.assertEqual({p.name for p in folder.iterdir()}, {'intent.json', 'diagnostics.json', 'snapshot.json', 'result.json'})
        self.assertEqual((folder / 'snapshot.json').read_bytes(), self.raw)
        self.assertFalse(result['off_server_backup_verified']); self.assertFalse(result['paid_launch_ready'])
        self.called.assert_called_once(); self.preflight.assert_called_once()
        self.assertEqual((self.root / '.runtime').stat().st_mode & 0o777, 0o755)
        for p in folder.iterdir(): self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_second_attempt_refuses_before_another_native_call(self):
        self.run_audit(); self.called.reset_mock(); self.preflight.reset_mock()
        with self.assertRaises(ValueError): self.run_audit()
        self.called.assert_not_called(); self.preflight.assert_not_called()

    def test_failure_retained_without_snapshot_or_retry_and_old_state_unchanged(self):
        old = self.root / legacy.DESTINATION; old.mkdir(mode=0o700)
        (old / 'failure.json').write_bytes(b'old failure'); (old / 'failure.json').chmod(0o600)
        meta = fixtures.metadata(b''); meta.update(status='child_exit', error_type='ValueError', returncode=1)
        self.called.side_effect = transport.AuditTransportError(meta)
        with self.assertRaises(transport.AuditTransportError): self.run_audit()
        folder = self.root / audit.DESTINATION
        self.assertEqual({p.name for p in folder.iterdir()}, {'intent.json', 'failure.json'})
        failure = json.loads((folder / 'failure.json').read_bytes())
        self.assertFalse(failure['completed_final_audit_verified']); self.assertFalse(failure['automatic_resume'])
        self.assertEqual((old / 'failure.json').read_bytes(), b'old failure')
        self.called.reset_mock()
        with self.assertRaises(ValueError): self.run_audit()
        self.called.assert_not_called()

    def test_public_or_writable_private_boundary_refuses_before_ssh(self):
        (self.root / '.runtime/netcup').chmod(0o755)
        with self.assertRaises(ValueError): self.run_audit()
        self.preflight.assert_not_called(); self.called.assert_not_called()

    def test_parent_identity_drift_refuses_verified_output(self):
        def changed(bindings):
            (self.root / '.runtime').chmod(0o700)
            return self.data, self.raw, fixtures.metadata(self.raw)
        self.called.side_effect = changed
        with self.assertRaises(transport.AuditTransportError): self.run_audit()
        self.assertFalse((self.root / audit.DESTINATION / 'snapshot.json').exists())

    def test_preflight_refusal_leaves_no_operation_state(self):
        self.preflight.side_effect = ValueError('preflight')
        with self.assertRaises(ValueError): self.run_audit()
        self.assertFalse((self.root / audit.DESTINATION).exists()); self.called.assert_not_called()

    def test_no_caller_root_snapshot_or_timeout_override(self):
        for values in ({'root': self.root}, {'snapshot': self.data}, {'timeout': 9999}):
            with self.assertRaises(TypeError): audit.collect('a' * 40, **values)
