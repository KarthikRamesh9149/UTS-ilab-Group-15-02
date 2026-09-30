"""Real Mac baseline archive/report paths; native measurements are synthetic."""
import inspect
import sys
import unittest
from unittest.mock import patch

import mac_operator_files as mac
import matched_repeat_mac_archive as archive
import matched_repeat_recovery_operator as operator
import matched_repeat_reporting as reporting
import test_matched_repeat_reporting as fixture


class MacBaselineTests(fixture.ReportingTests):
    def test_mac_actual_89_archive_uses_same_strict_stream_reader(self):
        if sys.platform!='darwin':
            with patch.object(mac,'_darwin',side_effect=ValueError('Darwin required')):
                with self.assertRaises(ValueError):mac.directories(self.root,private=True)
            return
        data,_,path,inventory,_,receipt=self.sample()
        with patch.object(mac,'_acl',wraps=mac._acl) as acl:
            result=archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)
        self.assertEqual(result['verified_result_files'],89)
        self.assertGreater(acl.call_count,1)
        self.assertFalse(result['paid_launch_ready'])

    def test_mac_backup_and_export_real_io(self):
        if sys.platform!='darwin':
            # The parent fixture intentionally emulates this OS boundary for
            # Linux wire tests. Here restore the actual platform gate.
            with patch.object(mac,'_darwin',side_effect=ValueError('Darwin required')):
                with self.assertRaises(ValueError):reporting._parents()
            return
        with patch.object(mac,'_acl',wraps=mac._acl) as acl:
            self.test_fixed_mac_backup_then_fresh_audit_export_same_archive_no_replay()
        self.assertGreater(acl.call_count,1)

    def test_mac_baseline_dependency_calls_corrected_recovery_archive_reader(self):
        source=inspect.getsource(operator._retained)
        self.assertIn("mac_recovery._read_backup",source)
        self.assertNotIn("recovery.boot.raw",source)
        self.assertNotIn("recovery.boot.directories",source)
        self.assertIn("mac_archive.verify",inspect.getsource(reporting._read_backup))


def load_tests(loader,tests,pattern):
    # Do not duplicate every inherited synthetic fixture test in this module.
    return unittest.TestSuite(MacBaselineTests(name) for name in loader.getTestCaseNames(MacBaselineTests)
        if name.startswith('test_mac_'))
