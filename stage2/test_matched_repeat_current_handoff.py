"""Current lock fixtures around the unchanged archived handoff regression tests.

Every archived test body still runs. Only the session-integration test needs
the current lock/ancestry and retired-host fixture; no archived byte is edited.
All native manager, library and host observations remain explicitly mocked.
"""
from pathlib import Path
from unittest.mock import Mock, patch

import test_matched_repeat_amended_handoff as archived
import matched_repeat_locks as locks
import matched_repeat_execution_bootstrap as bootstrap
import matched_repeat_revision as retired


class CurrentAmendedHandoffTests(archived.AmendedHandoffTests):
    def test_actual_amended_witness_is_consumed_by_same_task_locked_session(self):
        paths = tuple(self.repo / '.runtime/stage2' / name
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'))
        for path in paths:
            self.assertFalse(path.exists())
            path.write_bytes(b''); path.chmod(0o600)
        actual_acquire = locks.acquire

        def acquire(stack, root, harness):
            self.assertEqual(Path(root), self.repo)
            lease = actual_acquire(stack, root, harness)
            # The archived test body supplies this mocked sentinel lock to
            # assert audit-before-lock ordering. Keep that assertion as well
            # as the new actual protected leases. Never call a native audit.
            sentinel = archived.session.original_audit.lock_all
            self.assertIsInstance(sentinel, Mock)
            sentinel(stack, root, harness)
            return lease

        def preserve(boot):
            # This local fixture mocks native host observations, not the
            # owning session or its actual protected lock leases.
            self.assertIs(boot, bootstrap)
            self.assertTrue(self.locked)

        with patch.object(locks, '_parents', side_effect=lambda path:
                tuple(p for p in reversed(path.parents) if p == self.repo or p.is_relative_to(self.repo))), \
                patch.object(locks.os, 'listxattr', return_value=[], create=True), \
                patch.object(locks, 'paths', return_value=paths), \
                patch.object(locks, 'acquire', side_effect=acquire) as used, \
                patch.object(retired, 'native', side_effect=preserve) as preserved:
            super().test_actual_amended_witness_is_consumed_by_same_task_locked_session()
            used.assert_called_once()
            # Early/late reads on entry, explicit recheck and normal exit.
            self.assertEqual(preserved.call_count, 6)
