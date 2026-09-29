"""Synthetic protected controls and real isolated local imports, not native audit."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import no_cutoff_final_guard as guard
import no_cutoff_final_report as report
import no_cutoff_final_archive as archive
import no_cutoff_final_reporting as launch
import test_no_cutoff_final_archive as fixtures


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root = self.base / 'frozen'; self.root.mkdir(mode=0o700)
        self.enterContext(patch.object(guard, 'ROOT', self.root))
        self.enterContext(patch.object(guard, 'OWNER', os.getuid()))
        self.enterContext(patch.object(guard, 'GROUP', os.getgid()))
        self.enterContext(patch.object(os, 'listxattr', return_value=[], create=True))
        self.enterContext(patch.object(guard, '_ENVIRONMENT_VIOLATION', False))
        self.enterContext(patch.object(guard, '_ENVIRONMENT_GUARD_INSTALLED', False))
        hashes = {}
        for name in guard.REPORTING_LIBRARY_FILES:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            raw = b'synthetic library controls ' + name.encode(); path.write_bytes(raw); path.chmod(0o644)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        self.enterContext(patch.object(guard, 'REPORTING_LIBRARY_FILES', hashes))
        self.cache = self.root / guard.environment_contract()['tokenizer_cache_directory']
        self.cache.mkdir()
        self.env = dict(guard.ENVIRONMENT, TIKTOKEN_CACHE_DIR=str(self.cache))
        self.enterContext(patch.object(guard, 'ENVIRONMENT', self.env))
        self.enterContext(patch.dict(os.environ, self.env, clear=True))
        self.enterContext(patch.dict(sys.modules, {'litellm': None, 'dotenv.main': None,
            'litellm.litellm_core_utils.default_encoding': None}))

    def test_exact_controls_are_read_without_modifying_files(self):
        before = {n: (self.root / n).read_bytes() for n in guard.REPORTING_LIBRARY_FILES}
        guard.reporting_environment()
        self.assertEqual(before, {n: (self.root / n).read_bytes() for n in before})
        self.assertEqual(dict(os.environ), self.env)

    def test_current_controls_never_claim_historical_or_full_inventory(self):
        value = guard.environment_contract()
        self.assertFalse(value['historical_installed_bytes_attested'])
        self.assertFalse(value['full_runtime_library_inventory']); self.assertFalse(value['frozen_libraries_modified'])
        value['library_source_files'].clear(); self.assertEqual(len(guard.REPORTING_LIBRARY_FILES), 3)
        self.assertEqual(self.env['PYTHON_DOTENV_DISABLED'], '1')
        self.assertEqual(self.env['LITELLM_MODE'], 'PRODUCTION')

    def test_extra_credential_or_missing_control_refuses_without_clearing_environment(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'SYNTHETIC-PRIVATE'}):
            with self.assertRaises(ValueError) as caught: guard.reporting_environment()
            self.assertEqual(os.environ['OPENROUTER_API_KEY'], 'SYNTHETIC-PRIVATE')
            self.assertNotIn('SYNTHETIC-PRIVATE', str(caught.exception))
        del os.environ['PYTHON_DOTENV_DISABLED']
        with self.assertRaises(ValueError): guard.reporting_environment()

    def test_changed_library_bytes_are_refused(self):
        (self.root / next(iter(guard.REPORTING_LIBRARY_FILES))).write_bytes(b'changed')
        with self.assertRaises(ValueError): guard.reporting_environment()

    def test_readable_library_is_allowed_but_writable_by_others_is_not(self):
        path = self.root / next(iter(guard.REPORTING_LIBRARY_FILES)); path.chmod(0o664)
        with self.assertRaises(ValueError): guard.reporting_environment()
        path.chmod(0o644); guard.reporting_environment()

    def test_library_hardlink_symlink_and_fifo_are_refused(self):
        path = self.root / next(iter(guard.REPORTING_LIBRARY_FILES)); raw = path.read_bytes()
        os.link(path, self.base / 'hard')
        with self.assertRaises(ValueError): guard.reporting_environment()
        path.unlink(); path.symlink_to(self.base / 'hard')
        with self.assertRaises(ValueError): guard.reporting_environment()
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): guard.reporting_environment()

    def test_missing_or_symlinked_tokenizer_directory_refuses(self):
        self.cache.rmdir()
        with self.assertRaises(ValueError): guard.reporting_environment()
        self.cache.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError): guard.reporting_environment()

    def test_wrong_loaded_library_origin_refuses(self):
        with patch.dict(sys.modules, {'litellm': NS(__file__=str(self.base / 'unbound/__init__.py'))}):
            with self.assertRaises(ValueError): guard.reporting_environment()
        name = next(iter(guard.REPORTING_LIBRARY_FILES))
        with patch.dict(sys.modules, {'litellm': NS(__file__=str(self.root / name))}):
            guard.reporting_environment()

    def test_same_value_tokenizer_assignment_allowed_without_generic_environment_mutation(self):
        guard._environment_event('os.putenv', (b'TIKTOKEN_CACHE_DIR', str(self.cache).encode()))
        guard.reporting_environment()
        with self.assertRaises(ValueError):
            guard._environment_event('os.putenv', (b'TIKTOKEN_CACHE_DIR', b'/unexpected'))
        self.assertTrue(guard._ENVIRONMENT_VIOLATION)

    def test_credential_file_open_is_refused_before_content_read_and_latched(self):
        path = self.root / '.env'; path.write_bytes(b'SYNTHETIC_PRIVATE=value')
        with self.assertRaises(ValueError) as caught:
            guard._environment_event('open', (str(path), 'r', os.O_RDONLY))
        self.assertNotIn('SYNTHETIC_PRIVATE', str(caught.exception))
        self.assertEqual(dict(os.environ), self.env)
        with self.assertRaises(ValueError): guard.reporting_environment()

    def test_environment_deletion_and_new_keys_are_refused(self):
        for event, args in (('os.unsetenv', (b'LANG',)), ('os.putenv', (b'NEW', b'PRIVATE'))):
            with self.assertRaises(ValueError): guard._environment_event(event, args)

    def test_read_only_library_and_existing_backup_paths_remain_allowed(self):
        for path in (next(iter(guard.REPORTING_LIBRARY_FILES)), '.backup-intent.json'):
            guard._environment_event('open', (str(self.root / path), 'r', os.O_RDONLY))
        guard.reporting_environment()

    def test_hook_installation_is_idempotent_but_always_rechecks(self):
        with patch.object(sys, 'addaudithook') as add:
            guard.install_environment_guard(); guard.install_environment_guard()
            add.assert_called_once_with(guard._environment_event)
        (self.root / next(iter(guard.REPORTING_LIBRARY_FILES))).write_bytes(b'changed')
        with self.assertRaises(ValueError): guard.install_environment_guard()


class SnapshotEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ArchiveTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)

    def test_current_library_controls_are_real_support_and_archive_members(self):
        self.assertEqual(self.f.data['reporting_environment'], guard.environment_contract())
        for name, sha in guard.REPORTING_LIBRARY_FILES.items():
            self.assertEqual(self.f.data['supporting_file_sha256'][name], sha)
            self.assertIn(name, self.f.members)
        self.f.verify()

    def test_old_environment_schema_missing_support_and_false_attestation_refuse(self):
        name = next(iter(guard.REPORTING_LIBRARY_FILES))
        for mutate in (lambda v: v.pop('reporting_environment'),
                lambda v: v['reporting_environment'].update(historical_installed_bytes_attested=True),
                lambda v: v['reporting_environment'].update(dotenv_disabled=False),
                lambda v: v['supporting_file_sha256'].pop(name)):
            data = deepcopy(self.f.data); mutate(data)
            with self.assertRaises(ValueError): archive.validate_snapshot(data, self.f.anchors)
        with self.assertRaises(ValueError): self.f.verify(omit={name})

    def test_current_control_change_during_audit_refuses(self):
        path = self.f.root / next(iter(guard.REPORTING_LIBRARY_FILES))
        self.f.f.native.original.authenticate.side_effect = lambda *args: path.write_bytes(b'changed')
        with self.assertRaises(ValueError): report.collect()


class RealLocalImportTests(unittest.TestCase):
    def test_real_local_imports_keep_disabled_dotenv_and_fixed_cache_without_provider_call(self):
        stage = Path(report.__file__).resolve().parent
        cache = Path(sys.prefix) / 'lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers'
        self.assertTrue(cache.is_dir())
        with tempfile.TemporaryDirectory() as folder:
            secret = Path(folder) / '.env'; secret.write_text('SYNTHETIC_IMPORT_SECRET=DO_NOT_READ\n')
            env = dict(report.ENVIRONMENT, TIKTOKEN_CACHE_DIR=str(cache))
            program = r'''
import contextlib,json,os,sys
sys.path.insert(0,STAGE)
import no_cutoff_final_guard as guard
guard.ENVIRONMENT=dict(os.environ)
guard._ENVIRONMENT_VIOLATION=False
blocked=[]
def no_effect(event,args):
 if event in ('socket.connect','socket.sendto','socket.getaddrinfo','subprocess.Popen','os.system','os.mkdir','os.remove','os.rename'):
  blocked.append(event);raise ValueError('Local import effect refused')
 if event=='open' and ((isinstance(args[1],str) and any(v in args[1] for v in 'wax+')) or
   isinstance(args[2],int) and args[2]&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
  blocked.append(event);raise ValueError('Local import write refused')
with open(os.devnull,'w') as quiet,contextlib.redirect_stdout(quiet),contextlib.redirect_stderr(quiet):
 sys.addaudithook(guard._environment_event);sys.addaudithook(no_effect)
 import dotenv
 assert dotenv.load_dotenv(SECRET) is False
 import no_cutoff_final_report as report
 report._native()
 assert dict(os.environ)==guard.ENVIRONMENT and not guard._ENVIRONMENT_VIOLATION and not blocked
print(json.dumps(dict(environment_preserved=True,credential_file_read=False,provider_call=False)))
'''.replace('STAGE', repr(str(stage))).replace('SECRET', repr(str(secret)))
            child = subprocess.run([sys.executable, '-I', '-B', '-c', program], env=env,
                cwd=folder, capture_output=True, timeout=60)
            self.assertEqual(child.returncode, 0, 'Isolated import failed; no raw private diagnostics printed')
            self.assertEqual(json.loads(child.stdout), dict(environment_preserved=True, credential_file_read=False, provider_call=False))

    def test_real_audit_hook_latches_caught_credential_reads_without_reading_contents(self):
        stage = Path(report.__file__).resolve().parent
        program = r'''
import json,os,sys
sys.path.insert(0,STAGE)
import no_cutoff_final_guard as guard
guard.ENVIRONMENT=dict(os.environ)
sys.addaudithook(guard._environment_event)
try: open('.env','rb')
except ValueError: pass
assert guard._ENVIRONMENT_VIOLATION
try: guard.reporting_environment()
except ValueError: print(json.dumps(dict(caught_violation_still_refused=True)))
else: raise AssertionError('Caught read was ignored')
'''.replace('STAGE', repr(str(stage)))
        child = subprocess.run([sys.executable, '-I', '-B', '-c', program],
            env=dict(report.ENVIRONMENT), capture_output=True, timeout=20)
        self.assertEqual(child.returncode, 0)
        self.assertEqual(json.loads(child.stdout), {'caught_violation_still_refused': True})
