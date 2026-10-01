"""Real Darwin files/ACL subprocesses plus narrow negative fixtures.

Linux only checks the explicit platform refusal; it cannot stand in for the
actual Mac tests. No native host, provider, archive, credential or study write.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import mac_operator_files as mac


class MacFileTests(unittest.TestCase):
    def setUp(self):
        if sys.platform == 'darwin':
            temp = tempfile.TemporaryDirectory(prefix='.uts-mac-io-', dir=Path.home())
        else:
            temp = tempfile.TemporaryDirectory(prefix='uts-mac-io-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.root.chmod(0o700)

    def available(self):
        if sys.platform == 'darwin': return True
        with self.assertRaises(ValueError): mac.directories(self.root,private=True)
        return False

    def test_real_private_durable_write_read_and_actual_acl(self):
        if not self.available(): return
        # No os.listxattr or ACL subprocess mocking in this positive case.
        before = mac.directories(self.root,private=True)
        identity = mac.save(self.root/'value.json',{'zero':0,'float':1.0,'unknown':None})
        raw, actual = mac.raw(self.root,'value.json')
        self.assertEqual(identity,actual)
        self.assertEqual(mac.directories(self.root,private=True),before)
        self.assertIsNone(mac.loads(raw)['unknown'])
        self.assertIs(type(mac.loads(raw)['float']),float)
        self.assertEqual(stat.S_IMODE((self.root/'value.json').stat().st_mode),0o600)
        self.assertEqual(mac.acl(self.root/'value.json'),())

    def test_exclusive_write_does_not_replace(self):
        if not self.available(): return
        mac.write_bytes(self.root/'value',b'original')
        before=mac.raw(self.root,'value')
        with self.assertRaises(FileExistsError): mac.write_bytes(self.root/'value',b'replaced')
        self.assertEqual(mac.raw(self.root,'value'),before)

    def test_directory_child_change_requires_fresh_coherent_acl_observation(self):
        if not self.available(): return
        actual_run=mac.subprocess.run; calls=[]
        def observe(*args,**kwargs):
            result=actual_run(*args,**kwargs); calls.append(args[0])
            if len(calls)==1:
                (self.root/'ordinary-child').write_bytes(b'owned synthetic child')
            return result
        # A child addition changes directory times/size, not its identity or
        # protection. Accept only after another unchanged actual ACL read.
        with patch.object(mac,'subprocess',NS(run=observe)):
            self.assertEqual(mac.acl(self.root),())
        self.assertEqual(len(calls),2)

    def test_continuous_directory_changes_never_produce_acl_acceptance(self):
        if not self.available(): return
        actual_run=mac.subprocess.run; calls=[]
        def observe(*args,**kwargs):
            result=actual_run(*args,**kwargs); calls.append(args[0])
            (self.root/('child-'+str(len(calls)))).write_bytes(b'owned')
            return result
        with patch.object(mac,'subprocess',NS(run=observe)),self.assertRaises(ValueError):
            mac.acl(self.root)
        self.assertEqual(len(calls),3)

    def test_changed_directory_permissions_refuse_without_reobservation(self):
        if not self.available(): return
        actual_run=mac.subprocess.run; calls=[]
        def observe(*args,**kwargs):
            result=actual_run(*args,**kwargs); calls.append(args[0])
            self.root.chmod(0o750)
            return result
        with patch.object(mac,'subprocess',NS(run=observe)),self.assertRaises(ValueError):
            mac.acl(self.root)
        self.assertEqual(len(calls),1)

    def test_replaced_directory_refuses_without_reobservation(self):
        if not self.available(): return
        folder=self.root/'directory'; folder.mkdir(mode=0o700)
        actual_run=mac.subprocess.run; calls=[]
        def observe(*args,**kwargs):
            result=actual_run(*args,**kwargs); calls.append(args[0])
            folder.rename(self.root/'retained'); folder.mkdir(mode=0o700)
            return result
        with patch.object(mac,'subprocess',NS(run=observe)),self.assertRaises(ValueError):
            mac.acl(folder)
        self.assertEqual(len(calls),1)

    def test_regular_file_change_refuses_without_reobservation(self):
        if not self.available(): return
        path=self.root/'file'; mac.write_bytes(path,b'first')
        actual_run=mac.subprocess.run; calls=[]
        def observe(*args,**kwargs):
            result=actual_run(*args,**kwargs); calls.append(args[0])
            path.write_bytes(b'changed')
            return result
        with patch.object(mac,'subprocess',NS(run=observe)),self.assertRaises(ValueError):
            mac.acl(path)
        self.assertEqual(len(calls),1)

    def test_acl_grant_refuses_even_when_directory_children_changed(self):
        if not self.available(): return
        calls=[]
        def observe(*args,**kwargs):
            calls.append(args[0]); (self.root/'child').write_bytes(b'owned')
            return NS(returncode=0,stdout=b'drwx------+ 1 u g 1 Jan 1 p\n 0: group:everyone allow write\n',stderr=b'')
        with patch.object(mac,'subprocess',NS(run=observe)),self.assertRaises(ValueError):
            mac.acl(self.root)
        self.assertEqual(len(calls),1)

    def test_nonfinite_serialization_precedes_creation(self):
        if not self.available(): return
        with self.assertRaises(ValueError): mac.save(self.root/'bad.json',{'x':float('nan')})
        self.assertFalse((self.root/'bad.json').exists())

    def test_metadata_hash_and_window(self):
        if not self.available(): return
        mac.write_bytes(self.root/'value',b'abc')
        self.assertEqual(mac.raw(self.root,'value',hashlib.sha256(b'abc').hexdigest())[0],b'abc')
        with self.assertRaises(ValueError): mac.raw(self.root,'value','0'*64)
        with patch.object(mac,'WINDOW',2),self.assertRaises(ValueError): mac.raw(self.root,'value')

    def test_opaque_payload_reader_has_no_metadata_size_limit(self):
        if not self.available(): return
        mac.write_bytes(self.root/'payload',b'not a metadata limit')
        with patch.object(mac,'WINDOW',1),mac.opened(self.root/'payload') as (stream,_):
            self.assertEqual(stream.read(),b'not a metadata limit')

    def test_private_mode_is_not_inferred(self):
        if not self.available(): return
        path=self.root/'value'; mac.write_bytes(path,b'x'); path.chmod(0o644)
        with self.assertRaises(ValueError): mac.raw(self.root,'value')
        self.assertEqual(mac.raw(self.root,'value',private=False)[0],b'x')
        path.chmod(0o666)
        with self.assertRaises(ValueError): mac.raw(self.root,'value',private=False)

    def test_private_directory_mode(self):
        if not self.available(): return
        self.root.chmod(0o755)
        with self.assertRaises(ValueError): mac.directories(self.root,private=True)

    def test_symlink_and_hardlink_refused(self):
        if not self.available(): return
        mac.write_bytes(self.root/'value',b'x')
        (self.root/'link').symlink_to(self.root/'value')
        with self.assertRaises((ValueError,OSError)): mac.raw(self.root,'link')
        os.link(self.root/'value',self.root/'hardlink')
        with self.assertRaises(ValueError): mac.raw(self.root,'value')

    def test_fifo_open_is_nonblocking_and_refused(self):
        if not self.available(): return
        os.mkfifo(self.root/'fifo',0o600)
        with self.assertRaises(ValueError): mac.raw(self.root,'fifo')

    def test_same_byte_replacement_during_open_refused(self):
        if not self.available(): return
        mac.write_bytes(self.root/'value',b'x')
        with self.assertRaises(ValueError),mac.opened(self.root/'value') as (stream,_):
            self.assertEqual(stream.read(),b'x')
            (self.root/'value').rename(self.root/'retained')
            mac.write_bytes(self.root/'value',b'x')

    def test_parent_replacement_refused(self):
        if not self.available(): return
        folder=self.root/'private'; folder.mkdir(mode=0o700); mac.write_bytes(folder/'value',b'x')
        with self.assertRaises(ValueError),mac.opened(folder/'value') as (stream,_):
            self.assertEqual(stream.read(),b'x')
            folder.rename(self.root/'retained'); folder.mkdir(mode=0o700)
            mac.write_bytes(folder/'value',b'x')

    def test_acl_grants_extra_entries_errors_and_missing_output_refused(self):
        if not self.available(): return
        replies=[
            NS(returncode=0,stdout=b'drwx------+ 1 u g 1 Jan 1 p\n 0: group:everyone allow write\n',stderr=b''),
            NS(returncode=0,stdout=b'drwx------ 1 u g 1 Jan 1 p\n 0: group:everyone deny delete\n',stderr=b''),
            NS(returncode=1,stdout=b'',stderr=b''),NS(returncode=0,stdout=b'',stderr=b''),
            NS(returncode=0,stdout=b'drwx------ 1 u g 1 Jan 1 p\n',stderr=b'error')]
        for reply in replies:
            with self.subTest(reply=reply.returncode),patch.object(mac.subprocess,'run',return_value=reply),self.assertRaises(ValueError):
                mac.acl(self.root)

    def test_only_actual_fixed_home_can_have_exact_deny_delete_acl(self):
        if not self.available(): return
        reply=NS(returncode=0,stdout=b'drwxr-x---+ 1 u g 1 Jan 1 p\n 0: group:everyone deny delete\n',stderr=b'')
        with patch.object(mac.subprocess,'run',return_value=reply):
            with self.assertRaises(ValueError): mac.acl(self.root)
            self.assertEqual(mac.acl(mac.OPERATOR_HOME),(b'0: group:everyone deny delete',))
            reply.stdout += b' 1: group:everyone allow read\n'
            with self.assertRaises(ValueError): mac.acl(mac.OPERATOR_HOME)

    def test_platform_and_relative_paths_refused(self):
        with patch.object(mac.sys,'platform','linux'),self.assertRaises(ValueError):
            mac.directories(self.root)
        for name in ('/absolute','a/../b','a//b','./x','x\n',''):
            with self.subTest(name=name),self.assertRaises(ValueError): mac.relative(name)

    def test_strict_json_duplicate_nonfinite_nonobject(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'[]',b'\xff'):
            with self.subTest(raw=raw),self.assertRaises((ValueError,UnicodeError)): mac.loads(raw)


if __name__ == '__main__':
    unittest.main()
