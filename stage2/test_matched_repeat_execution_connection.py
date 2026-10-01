"""Local exclusive Mac state and real framing; all native observations mocked."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

import matched_repeat_execution_connection as connection
import matched_repeat_runtime as native_runtime
from test_matched_repeat_completion import synthetic_qualification_inputs

NONCE = 'a1' * 16
COMMIT = 'c2' * 20
PEER = dict(pid=123, start_ticks=456)


class OperatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.root.chmod(0o700)
        (self.root / '.runtime/netcup').mkdir(parents=True, mode=0o700)
        self.root.joinpath('.runtime').chmod(0o700)
        (self.root / 'stage2').mkdir(mode=0o700)
        source = Path(connection.__file__).parent / 'progress_dashboard.py'
        raw = source.read_bytes(); self.root.joinpath('stage2/progress_dashboard.py').write_bytes(raw)
        self.files = {'stage2/progress_dashboard.py': hashlib.sha256(raw).hexdigest()}
        self.files.update(synthetic_qualification_inputs(self, self.root))
        self.enterContext(patch.object(connection, 'REPO', self.root))
        self.enterContext(patch.object(connection, '__file__', str(self.root / 'stage2/matched_repeat_execution_connection.py')))
        self.enterContext(patch.object(connection.secrets, 'token_hex', return_value=NONCE))
        self.enterContext(patch.object(connection.handoff.original.receiver, '_parents', return_value=('local-parent',)))
        def read(name, expected=None):
            path = self.root / name; before = connection.boot.identity(path.lstat())
            if path.is_symlink(): raise ValueError('No symlink')
            raw = path.read_bytes()
            if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Changed bytes')
            if connection.boot.identity(path.lstat()) != before: raise ValueError('Replaced file')
            return raw
        self.enterContext(patch.object(connection.handoff.original.launch, '_raw', side_effect=read))
        self.prepare = self.enterContext(patch.object(connection, 'prepare', return_value=({}, self.files)))
        self.current = self.enterContext(patch.object(connection, '_current'))
        self.program = self.enterContext(patch.object(connection.service, 'native_program', return_value='pass\n'))
        self.process = Mock(stdin=io.BytesIO(), stdout=io.BytesIO(),
            wait=Mock(return_value=0), poll=Mock(return_value=None))
        self.popen = self.enterContext(patch.object(connection.subprocess, 'Popen', return_value=self.process))
        self.sent = dict(recovery_document_sha256='a'*64, recovery_archive_sha256='b'*64,
            original=dict(operator_document_sha256='c'*64, archive_sha256='d'*64))
        self.send = self.enterContext(patch.object(connection.handoff, 'send', return_value=self.sent))

    def replies(self, operation):
        base = connection.completion.base('terminus-2', NONCE, self.files, COMMIT, operation)
        ready = dict(base, kind='baseline_receiver_ready_not_authenticated', native_process=PEER)
        accepted = dict(base, kind='baseline_handoff_committed_operation_accepted_not_completed',
            native_process=PEER, prerequisites_sha256='e'*64,
            recovery_document_sha256=self.sent['recovery_document_sha256'],
            recovery_archive_sha256=self.sent['recovery_archive_sha256'], **self.sent['original'])
        return ready, accepted

    def invoke(self, operation='qualify-repeat'):
        ready, accepted = self.replies(operation)
        with patch.object(connection, 'read_reply', side_effect=[ready, accepted]):
            result = connection._operate(COMMIT, 'terminus-2', operation)
        return result, self.root / connection.state_name('terminus-2', operation)

    def test_actual_sender_is_required_and_acceptance_is_not_qualification(self):
        result, path = self.invoke()
        self.send.assert_called_once_with(self.process.stdin)
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['repeat_execution_qualified'])
        self.assertEqual({p.name for p in path.iterdir()}, {'intent.json','receiver.json','result.json'})
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in path.iterdir()))
        self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        self.process.kill.assert_not_called()

    def test_run_is_a_separate_one_shot_operation(self):
        result, path = self.invoke('run-repeat')
        self.assertEqual(result['operation'], 'run-repeat')
        self.assertIn('-run-', path.name); self.assertNotIn('-qualify-', path.name)

    def test_existing_success_or_failure_is_never_replayed(self):
        self.invoke()
        with self.assertRaisesRegex(ValueError, 'terminal'): self.invoke()
        self.popen.assert_called_once(); self.send.assert_called_once()

    def test_incomplete_handoff_preserves_failure_and_kills_only_owned_client(self):
        self.send.side_effect = BrokenPipeError('synthetic transfer refusal')
        with self.assertRaises(BrokenPipeError): self.invoke()
        path = self.root / connection.state_name('terminus-2','qualify-repeat')
        self.assertEqual({p.name for p in path.iterdir()}, {'intent.json','receiver.json','failure.json'})
        self.process.kill.assert_called_once()
        with self.assertRaises(ValueError): self.invoke()
        self.popen.assert_called_once()

    def test_wrong_readiness_never_calls_actual_sender(self):
        ready, _ = self.replies('qualify-repeat'); ready['paid_launch_ready'] = True
        with patch.object(connection, 'read_reply', return_value=ready), self.assertRaises(ValueError):
            connection.qualify_native(COMMIT)
        self.send.assert_not_called()

    def test_both_actual_archive_identities_must_match_acknowledgement(self):
        ready, accepted = self.replies('qualify-repeat')
        for key in ('recovery_document_sha256','recovery_archive_sha256','operator_document_sha256','archive_sha256'):
            bad = dict(accepted, **{key:'f'*64})
            with self.subTest(key=key), self.assertRaises(ValueError):
                connection.reply(bad,'terminus-2',NONCE,self.files,COMMIT,'qualify-repeat',sent=self.sent,peer=PEER)
        connection.reply(accepted,'terminus-2',NONCE,self.files,COMMIT,'qualify-repeat',sent=self.sent,peer=PEER)

    def test_source_drift_after_send_cannot_publish_operator_success(self):
        self.current.side_effect = [None, None, None, ValueError('late source change')]
        with self.assertRaises(ValueError): self.invoke()
        path = self.root / connection.state_name('terminus-2','qualify-repeat')
        self.assertTrue((path/'failure.json').exists()); self.assertFalse((path/'result.json').exists())

    def test_ambiguous_ssh_exit_is_not_success(self):
        self.process.wait.return_value = 1
        with self.assertRaises(ValueError): self.invoke()
        self.assertFalse((self.root/connection.state_name('terminus-2','qualify-repeat')/'result.json').exists())

    def test_exact_pinned_ssh_options_are_preserved(self):
        args = connection.command('terminus-2',NONCE,self.files,COMMIT,'qualify-repeat')
        fixed=connection.ssh_command(self.root)
        self.assertEqual(args[:-1],fixed[:-3]+['-o','ServerAliveInterval=30',
            '-o','ServerAliveCountMax=150']+fixed[-3:-2])
        remote = shlex.split(args[-1]); ast.parse(remote[-1])
        self.assertEqual(remote[-5:-1], [str(connection.boot.root_for('terminus-2')/'.venv/bin/python'),'-I','-B','-c'])
        with patch.object(connection,'ssh_command',return_value=['ssh','changed']), self.assertRaises(ValueError):
            connection.command('terminus-2',NONCE,self.files,COMMIT,'qualify-repeat')

    def test_both_baselines_keep_the_same_transport_window_and_commands(self):
        self.assertEqual(30*150,connection.read_reply.__globals__['TIMEOUT'])
        fixed=connection.ssh_command(self.root)
        for harness in ('terminus-2','openhands'):
            for operation in ('qualify-repeat','run-repeat'):
                for role in ('relay','status'):
                    actual=connection.command(harness,NONCE,self.files,COMMIT,operation,role=role)
                    self.assertEqual(actual[:-1],fixed[:-3]+['-o','ServerAliveInterval=30',
                        '-o','ServerAliveCountMax=150']+fixed[-3:-2])
                    self.assertIn(str(connection.boot.root_for(harness)/'.venv/bin/python'),actual[-1])
        self.assertEqual(connection.ssh_command(self.root),fixed)

    def test_openhands_cannot_use_a_terminus_only_handoff(self):
        self.prepare.side_effect = ValueError('Actual completed-Terminus reader refused')
        with self.assertRaisesRegex(ValueError, 'completed-Terminus'):
            connection.run_native(COMMIT,'openhands')
        self.prepare.assert_called_once_with(COMMIT, 'openhands'); self.popen.assert_not_called()
        self.send.assert_not_called()

    def test_no_generic_stop_restart_inspection_or_caller_command_exists(self):
        for operation in ('stop','restart','inspect-prerequisites','shell'):
            with self.assertRaises(ValueError): connection.state_name('terminus-2',operation)
        with self.assertRaises(ValueError):
            connection.command('terminus-2',NONCE,self.files,COMMIT,'qualify-repeat',role='shell')

    def test_same_byte_source_replacement_changes_local_identity(self):
        bindings = dict(local=self.files)
        before = connection._identities(bindings)
        path = self.root/'stage2/progress_dashboard.py'; raw = path.read_bytes()
        old = path.with_suffix('.old'); path.rename(old); path.write_bytes(raw)
        self.assertNotEqual(connection._identities(bindings), before)

    def test_status_does_not_capture_archive_open_handoff_or_write_operation(self):
        bindings = dict(local=self.files)
        value = dict(bindings=bindings, identities=connection._identities(bindings))
        observed = dict(kind='read_only_baseline_operation_status_not_admission', operation='run-repeat',
            status='running', counts={'harness':'terminus-2'}, paid_launch_ready=False, automatic_resume=False)
        with patch.object(connection, '_source_inputs', return_value=(value, self.files)), \
                patch.object(connection.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps(observed).encode())), \
                patch.object(connection.handoff.original.launch, '_recheck'), \
                patch.object(connection.handoff.operator, '_loaded'):
            self.assertEqual(connection.status_native(COMMIT, 'run-repeat'), observed)
        self.prepare.assert_not_called(); self.send.assert_not_called(); self.popen.assert_not_called()
        self.assertEqual(list((self.root/'.runtime/netcup').iterdir()), [])


class MacSourceReaderTests(unittest.TestCase):
    """Real Mac-source reader; Git/anchor and fixed-checkout facts are fixtures."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.root.chmod(0o700)
        stage = self.root/'stage2'; stage.mkdir(mode=0o700)
        self.operator = connection.handoff.operator
        modules = (connection, self.operator)
        self.sources = {}
        for module in modules:
            path = stage/Path(module.__file__).name
            path.write_bytes(Path(module.__file__).read_bytes()); path.chmod(0o600)
            self.sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.enterContext(patch.object(module, '__file__', str(path)))
        self.bindings = dict(commit=COMMIT,
            local={'stage2/'+n:h for n,h in self.sources.items()})
        for module in modules:
            self.enterContext(patch.object(module, 'REPO', self.root))
        self.enterContext(patch.object(self.operator.original.launch, 'REPO', self.root))
        self.mac = self.enterContext(patch.object(self.operator.original.launch, '_operator'))
        self.enterContext(patch.object(self.operator.original, '_prepare',
            return_value=(self.bindings, {'proof':{'sources':dict(self.sources)}})))
        self.enterContext(patch.object(connection.policy, 'REQUIRED_SOURCE_FILES', frozenset(self.sources)))
        self.native = self.enterContext(patch.object(native_runtime, 'loaded_sources',
            side_effect=AssertionError('Mac orchestration cannot use the native interpreter gate')))

    def test_actual_source_preparation_uses_real_mac_origins_not_native_prefix(self):
        self.assertNotEqual(Path(sys.prefix).resolve(), self.root/'.venv')
        value, files = connection._source_inputs(COMMIT, 'terminus-2')
        self.assertEqual(value['sources'], self.sources)
        self.assertEqual(set(files), set(self.bindings['local']) |
            {connection.boot.BASELINE_INPUT, connection.boot.FINAL_INPUT})
        self.assertEqual(len(value['identities']), 2)
        self.mac.assert_called_once(); self.native.assert_not_called()

    def test_current_operator_rechecks_real_loaded_mac_source(self):
        value, _ = connection._source_inputs(COMMIT, 'terminus-2')
        value['recovery'] = dict(bindings=self.bindings, sources={}, retained={})
        with patch.object(self.operator.original.launch, '_recheck'), \
                patch.object(self.operator, '_sources', return_value={}), \
                patch.object(self.operator, '_retained', return_value={}):
            connection._current(value)
            path = self.root/'stage2/matched_repeat_execution_connection.py'
            path.write_bytes(path.read_bytes()+b'\n# changed\n')
            with self.assertRaises(ValueError): self.operator._current(value['recovery'])
        self.native.assert_not_called()

    def test_late_unbound_project_import_is_refused(self):
        path = self.root/'stage2/unbound_mac_reader_fixture.py'; path.write_text('pass\n'); path.chmod(0o600)
        module = ModuleType(path.stem); module.__file__ = str(path)
        with patch.dict(sys.modules, {path.stem:module}), self.assertRaises(ValueError):
            self.operator._loaded(self.bindings)

    def test_other_checkout_origin_is_refused(self):
        with patch.object(connection, '__file__', str(self.root/'elsewhere/matched_repeat_execution_connection.py')):
            with self.assertRaises(ValueError): self.operator._loaded(self.bindings)

    def test_bound_module_without_origin_is_refused(self):
        with patch.dict(sys.modules, {connection.__name__:ModuleType(connection.__name__)}):
            with self.assertRaises(ValueError): self.operator._loaded(self.bindings)

    def test_wrong_operator_location_and_mac_context_refuse(self):
        with patch.object(self.operator, '__file__', str(self.root/'elsewhere/matched_repeat_recovery_operator.py')):
            with self.assertRaises(ValueError): self.operator._loaded(self.bindings)
        self.mac.side_effect = ValueError('Not the fixed Mac checkout')
        with self.assertRaises(ValueError): self.operator._loaded(self.bindings)
