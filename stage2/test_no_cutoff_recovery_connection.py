"""Real local files/pipes/sockets/locks; native manager/host/audits are mocked.

No actual retained archive, SSH, Docker, native qualification or provider call.
Synthetic original89 fixtures exercise the real capture/handoff/session path.
"""
import ast
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import socket
import struct
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import no_cutoff_recovery_bootstrap as boot
import no_cutoff_recovery_connection as connection
import no_cutoff_recovery_service as service
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_session as session
import no_cutoff_recovery_runtime as runtime
import no_cutoff_recovery_policy as policy
import test_no_cutoff_recovery_handoff as fixtures

NONCE = 'a1' * 16
PEER = dict(pid=123, start_ticks=456)
STAGE = Path(__file__).resolve().parent
ACTUAL_CONTEXT = boot.context


class LocalTree(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RecoveryOriginalHandoffTests('runTest'); self.f.setUp()
        self.addCleanup(self.f.doCleanups); self.root = self.f.root; self.commit = self.f.commit
        for module in (connection, service):
            self.enterContext(patch.object(module, '__file__', str(self.root / 'stage2' / (module.__name__ + '.py'))))
        for module in (boot, service, handoff): self.enterContext(patch.object(module, 'ROOT', self.root))
        self.enterContext(patch.object(boot, 'QUALIFICATION_SHA', policy.ORIGINAL_QUALIFICATION_FILE_SHA256))
        self.enterContext(patch.object(boot, 'context'))
        self.enterContext(patch.object(boot, 'VIOLATION', False))
        self.value, self.files = connection.prepare(self.commit)
        self.identities = boot.check(self.files)
        self.enterContext(patch.object(connection.secrets, 'token_hex', return_value=NONCE))
        self.enterContext(patch.object(service, 'process_identity', return_value=deepcopy(PEER)))
        self.enterContext(patch.object(service, '_service_process', return_value=deepcopy(PEER)))
        self.enterContext(patch.object(service, '_peer', return_value=deepcopy(PEER)))
        # Only Linux completion facts are replaced, not pre-import file checks.
        self.ancestors = self.enterContext(patch.object(boot, 'ancestors'))
        self.enterContext(patch('no_cutoff_recovery_install._retained_operator_states', return_value=('local-synthetic-retained-state',)))

    def ready(self):
        return dict(service.base(NONCE, self.files, self.commit),
            kind='recovery_receiver_ready_not_authenticated', native_process=deepcopy(PEER))

    def result(self):
        return dict(self.ready(), kind='recovery_prerequisites_checked_not_dispatch',
            operator_document_sha256='1' * 64, archive_sha256='2' * 64, prerequisites_sha256='3' * 64)

    def native_folder(self):
        path = self.root / service.STATE; path.mkdir(mode=0o700)
        service.save(path / 'intent.json', dict(service.base(NONCE, self.files, self.commit),
            relay_process=deepcopy(PEER), created_utc='2026-09-29T20:00:00+00:00'))
        self.f.e.save(service.STATE + '/service.log', b'')
        return path


class GuardTests(LocalTree):
    def test_service_failure_diagnostic_never_serializes_messages_or_subclass_names(self):
        path = self.native_folder()
        class PrivateExceptionName(ValueError):
            def __str__(self): raise AssertionError('Do not stringify private exceptions')
        service._failure_diagnostic(path, 'live_session', PrivateExceptionName('private output'))
        raw = (path / 'failure-diagnostic.json').read_bytes()
        self.assertEqual(boot.loads(raw), dict(stage='live_session', error_class='OtherException',
            automatic_resume=False, paid_launch_ready=False))
        self.assertNotIn(b'private', raw); self.assertNotIn(b'PrivateExceptionName', raw)

    def test_service_failure_diagnostic_retains_fixed_class_and_refuses_unknown_stage(self):
        path = self.native_folder()
        with self.assertRaises(ValueError): service._failure_diagnostic(path, 'arbitrary output', ValueError())
        self.assertFalse((path / 'failure-diagnostic.json').exists())
        service._failure_diagnostic(path, 'socket_connect', TimeoutError('unpublished'))
        self.assertEqual(boot.loads((path / 'failure-diagnostic.json').read_bytes())['error_class'], 'TimeoutError')
        with self.assertRaises(FileExistsError): service._failure_diagnostic(path, 'socket_connect', TimeoutError())

    def test_actual_full_inventory_and_identities_are_read(self):
        self.assertEqual(set(boot.check(self.files)), set(self.files))
        self.assertIn('stage2/no_cutoff_recovery_service.py', self.files)
        self.assertNotIn('stage2/no_cutoff_recovery_service.py', self.value['bindings']['local'])

    def test_omitted_inherited_or_current_source_is_refused(self):
        for name in ('stage2/no_cutoff_recovery_service.py', next('stage2/' + n for n in self.f.final['sources'])):
            files = dict(self.files); files.pop(name)
            with self.subTest(name=name), self.assertRaises((ValueError, KeyError)): boot.check(files)

    def test_exact_private_original_anchor_is_required(self):
        files = dict(self.files); files[boot.QUALIFICATION] = '0' * 64
        with self.assertRaises(ValueError): boot.check(files)

    def test_same_byte_source_replacement_is_detected(self):
        path = self.root / 'stage2/no_cutoff_recovery_service.py'; raw = path.read_bytes()
        path.unlink(); path.write_bytes(raw); path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'identity replaced'): boot.check(self.files, self.identities)

    def test_unsafe_private_mode_symlink_hardlink_and_fifo_refuse(self):
        name = boot.QUALIFICATION; path = self.root / name; raw = path.read_bytes()
        for kind in ('mode', 'symlink', 'hardlink', 'fifo'):
            with self.subTest(kind=kind):
                path.unlink(); self.f.e.save(name, raw)
                if kind == 'mode': path.chmod(0o644)
                elif kind == 'symlink': path.unlink(); path.symlink_to(self.root / 'missing')
                elif kind == 'hardlink':
                    other = path.with_name('other.json'); other.write_bytes(raw); os.link(other, path.with_name('hard.json'))
                    path.unlink(); os.link(other, path)
                else: path.unlink(); os.mkfifo(path, 0o600)
                with self.assertRaises((ValueError, OSError)): boot.raw(self.root, name)

    def test_acl_and_writable_parent_refuse(self):
        with patch.object(boot.os, 'listxattr', return_value=['system.posix_acl_access'], create=True):
            with self.assertRaises(ValueError): boot.check(self.files)
        path = self.root / 'stage2'; path.chmod(0o777)
        with self.assertRaises(ValueError): boot.check(self.files)

    def test_safe_new_evidence_does_not_change_directory_identity(self):
        before = boot.directories(self.root, private=True)
        self.native_folder()
        self.assertEqual(before, boot.directories(self.root, private=True))
        boot.check(self.files, self.identities)

    def test_pinned_command_keeps_all_original_ssh_options(self):
        old = connection.ssh_command(self.root)
        cmd = connection.command(NONCE, self.files, self.commit)
        self.assertEqual(cmd[:-1], old[:-2])
        remote = shlex.split(cmd[-1]); self.assertEqual(remote[:2], ['/usr/bin/env', '-i'])
        self.assertIn('PYTHON_DOTENV_DISABLED=1', remote)
        self.assertIn('TIKTOKEN_CACHE_DIR=' + boot.environment()['TIKTOKEN_CACHE_DIR'], remote)
        self.assertEqual(remote[-5:-1], [str(self.root / '.venv/bin/python'), '-I', '-B', '-c'])
        self.assertNotIn('OPENROUTER_API_KEY', cmd[-1]); ast.parse(remote[-1])

    def test_mac_bootstrap_read_does_not_assume_linux_ancestral_groups(self):
        with patch.object(boot, 'ROOT', Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260929')):
            program = connection.native_program(NONCE, self.files, self.commit, role='relay')
        self.assertIn("types.ModuleType('no_cutoff_recovery_bootstrap')", program)
        ast.parse(program)

    def native_context(self):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('platform.system', return_value='Linux'))
        stack.enter_context(patch('os.getuid', return_value=0)); stack.enter_context(patch('os.getgid', return_value=0))
        stack.enter_context(patch.object(sys, 'prefix', str(self.root / '.venv')))
        stack.enter_context(patch.object(sys, 'executable', str(self.root / '.venv/bin/python')))
        stack.enter_context(patch.object(sys, 'flags', NS(isolated=1)))
        stack.enter_context(patch.object(sys, 'dont_write_bytecode', True))
        stack.enter_context(patch.object(sys, 'pycache_prefix', str(self.root / '.absent-bytecode-cache')))
        stack.enter_context(patch.dict(os.environ, boot.environment(), clear=True))
        stack.enter_context(patch.object(boot, 'directories'))
        return stack

    def test_exact_native_environment_interpreter_and_isolation_required(self):
        with self.native_context():
            ACTUAL_CONTEXT()
            with patch.dict(os.environ, EXTRA_UNEXPECTED='1'), self.assertRaises(ValueError): ACTUAL_CONTEXT()
            with patch.object(sys, 'executable', '/other/python'), self.assertRaises(ValueError): ACTUAL_CONTEXT()
            with patch.object(sys, 'flags', NS(isolated=0)), self.assertRaises(ValueError): ACTUAL_CONTEXT()

    def test_absent_bytecode_prefix_cannot_be_replaced_by_existing_path_or_symlink(self):
        with self.native_context():
            path = self.root / '.absent-bytecode-cache'; path.symlink_to(self.root / 'absent')
            with self.assertRaises(ValueError): ACTUAL_CONTEXT()
            path.unlink(); path.mkdir()
            with self.assertRaises(ValueError): ACTUAL_CONTEXT()

    def test_any_ssh_option_or_destination_change_refuses(self):
        old = connection.ssh_command(self.root)
        for args in (old + ['-tt'], ['ssh', 'other', 'python3', '-'], [p.replace('yes', 'no') for p in old]):
            with self.subTest(args=args), patch.object(connection, 'ssh_command', return_value=args):
                with self.assertRaises(ValueError): connection.command(NONCE, self.files, self.commit)

    def test_only_fixed_inspection_roles_full_commit_and_process_are_accepted(self):
        for nonce in ('', 'a' * 31, '../bad', None):
            with self.assertRaises(ValueError): service.identity(nonce)
        for role, peer in (('paid', None), ('qualify', None), ('service', {'pid': True, 'start_ticks': 1}),
                ('service', None), ('relay', PEER)):
            with self.subTest(role=role, peer=peer), self.assertRaises(ValueError):
                connection.native_program(NONCE, self.files, self.commit, role=role, relay_process=peer)
        with self.assertRaises(ValueError): connection.native_program(NONCE, self.files, 'abc', role='relay')

    def test_detached_service_has_no_restart_stdin_or_runtime_cap(self):
        self.native_folder(); cmd = service.service_command(NONCE, self.files, self.commit, PEER)
        for part in ('--property=Type=exec', '--property=Restart=no', '--property=StandardInput=null'):
            self.assertIn(part, cmd)
        for part in ('--pipe', '--scope', '--wait', 'RuntimeMaxSec', 'OPENROUTER_API_KEY'):
            self.assertFalse(any(part in item for item in cmd))
        self.assertIn('PYTHON_DOTENV_DISABLED=1', cmd)

    def test_preimport_guard_precedes_import_and_rechecks_before_entry(self):
        events = []; real_check = boot.check
        def check(*args): events.append('check'); return real_check(*args)
        def ancestors(*args): events.append('ancestors')
        with patch.object(boot, 'check', side_effect=check), patch.object(boot, 'ancestors', side_effect=ancestors), \
                patch.object(sys, 'addaudithook') as hook, patch.object(sys, 'path', list(sys.path)), \
                patch.object(sys, 'pycache_prefix', None), patch('os.chdir'), \
                patch.object(service, 'relay', side_effect=lambda *a: events.append('relay')):
            boot.main(NONCE, self.files, self.commit, 'relay')
        self.assertEqual(events, ['check', 'ancestors', 'check', 'ancestors', 'check', 'relay'])
        hook.assert_called_once_with(boot.no_effects)

    def test_changed_sources_before_import_never_reach_entry(self):
        path = self.root / 'stage2/no_cutoff_recovery_service.py'; path.write_bytes(b'changed')
        with patch.object(service, 'relay') as relay, patch.object(sys, 'pycache_prefix', None):
            with self.assertRaises(ValueError): boot.main(NONCE, self.files, self.commit, 'relay')
        relay.assert_not_called()

    def test_post_import_byte_change_never_reaches_entry(self):
        def changed(*args):
            if self.ancestors.call_count == 2:
                path = self.root / 'stage2/no_cutoff_recovery_service.py'; path.write_bytes(path.read_bytes() + b' ')
        self.ancestors.side_effect = changed
        with patch.object(sys, 'addaudithook'), patch.object(sys, 'path', list(sys.path)), \
                patch.object(sys, 'pycache_prefix', None), patch('os.chdir'), patch.object(service, 'relay') as relay:
            with self.assertRaises(ValueError): boot.main(NONCE, self.files, self.commit, 'relay')
        relay.assert_not_called()

    def test_import_effect_and_credentials_refuse_with_latched_failure(self):
        with patch.object(boot, 'IMPORTING', True):
            with self.assertRaises(RuntimeError): boot.no_effects('socket.__new__', ())
            self.assertFalse(boot.VIOLATION)
            with self.assertRaises(RuntimeError): boot.no_effects('subprocess.Popen', ())
            self.assertTrue(boot.VIOLATION)
        with patch.object(boot, 'VIOLATION', False), self.assertRaises(RuntimeError):
            boot.no_effects('open', ('/ignored/.env', 'r', 0))
        with patch.object(boot, 'VIOLATION', False), self.assertRaises(RuntimeError):
            boot.no_effects('os.putenv', (b'OPENROUTER_API_KEY', b'synthetic'))


class MetadataTests(unittest.TestCase):
    def pipe(self, raw):
        reader, writer = os.pipe(); stream = os.fdopen(reader, 'rb', buffering=0); self.addCleanup(stream.close)
        with os.fdopen(writer, 'wb', buffering=0) as output: output.write(raw)
        return stream

    def test_pipe_preserves_python_numeric_types(self):
        self.assertIs(type(connection.read_reply(self.pipe(b'{"x":1.0}\n'))['x']), float)

    def test_malformed_duplicate_extra_and_oversized_ack_refuse(self):
        for raw in (b'', b'{}', b'{"x":1,"x":2}\n', b'[]\n', b'{}\nextra', b'{' + b' ' * 100):
            with self.subTest(raw=raw), patch.object(connection, 'REPLY_LIMIT', 50), self.assertRaises(ValueError):
                connection.read_reply(self.pipe(raw))

    def test_ack_timeout_does_not_signal_any_native_process(self):
        reader, writer = os.pipe(); self.addCleanup(os.close, writer)
        with os.fdopen(reader, 'rb', buffering=0) as stream, patch.object(connection, 'TIMEOUT', 0.001):
            with self.assertRaisesRegex(ValueError, 'without retry'): connection.read_reply(stream)

    def test_socket_ack_requires_eof_and_exact_metadata(self):
        self.assertEqual(service._read_reply(io.BytesIO(b'{"x":1}\n')), {'x': 1})
        for raw in (b'{}', b'{}\nextra', b'{"x":1,"x":2}\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): service._read_reply(io.BytesIO(raw))

    def test_ack_loss_preserves_native_success(self):
        peer = Mock(); peer.sendall.side_effect = BrokenPipeError()
        service._reply(peer, {'paid_launch_ready': False})
        peer.sendall.assert_called_once()

    def test_actual_peer_credentials_are_required(self):
        with patch.object(socket, 'SO_PEERCRED', 17, create=True), \
                patch.object(service, 'process_identity', return_value=PEER) as process:
            sock = Mock(); sock.getsockopt.return_value = struct.pack('3i', 123, 0, 0)
            self.assertEqual(service._peer(sock), PEER); process.assert_called_with(123)
            for value in ((0, 0, 0), (123, 501, 0), (123, 0, 20)):
                sock.getsockopt.return_value = struct.pack('3i', *value)
                with self.assertRaises(ValueError): service._peer(sock)

    def test_service_manager_is_reread_around_process_identity(self):
        state = 'LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=123\nInvocationID=' + 'b' * 32 + '\n'
        with patch('subprocess.check_output', return_value=state) as read, \
                patch.object(service, 'process_identity', return_value=PEER):
            self.assertEqual(service._service_process('fixture.service'), PEER); self.assertEqual(read.call_count, 2)
            read.side_effect = [state, state.replace('MainPID=123', 'MainPID=124')]
            with self.assertRaises(ValueError): service._service_process('fixture.service')

    def test_proc_owner_executable_cwd_and_start_ticks_are_checked_twice(self):
        status = 'Uid:\t0 0 0 0\nGid:\t0 0 0 0\n'
        statline = '123 (fixture process) ' + ' '.join(['S'] + ['0'] * 18 + ['456'])
        def read(path, *args, **kwargs): return status if path.name == 'status' else statline
        def link(path): return str(service.ROOT) if path.name == 'cwd' else str((service.ROOT / '.venv/bin/python').resolve())
        with patch.object(Path, 'read_text', read), patch('os.readlink', side_effect=link):
            self.assertEqual(service.process_identity(123), PEER)
            with patch('os.readlink', return_value='/wrong'), self.assertRaises(ValueError): service.process_identity(123)
            status = 'Uid:\t0 501 0 0\nGid:\t0 0 0 0\n'
            with self.assertRaises(ValueError): service.process_identity(123)

    def test_process_identity_cannot_be_recycled_between_proc_reads(self):
        values = iter(['123 (fixture) ' + ' '.join(['S'] + ['0'] * 18 + [ticks]) for ticks in ('456', '457')])
        def read(path, *args, **kwargs):
            return 'Uid:\t0 0 0 0\nGid:\t0 0 0 0\n' if path.name == 'status' else next(values)
        def link(path): return str(service.ROOT) if path.name == 'cwd' else str((service.ROOT / '.venv/bin/python').resolve())
        with patch.object(Path, 'read_text', read), patch('os.readlink', side_effect=link), self.assertRaises(ValueError):
            service.process_identity(123)


class OperatorTests(LocalTree):
    def process(self, *, failure=None, result=None, rc=0):
        process = Mock(stdin=io.BytesIO(), stdout=io.BytesIO(), wait=Mock(return_value=rc), poll=Mock(return_value=None))
        self.start = self.enterContext(patch.object(connection.subprocess, 'Popen', return_value=process))
        self.read = self.enterContext(patch.object(connection, 'read_reply', side_effect=[self.ready(), result or self.result()]))
        self.send = self.enterContext(patch.object(handoff, 'send', return_value=dict(
            operator_document_sha256='1' * 64, archive_sha256='2' * 64), side_effect=failure))
        return process

    def test_actual_sender_called_and_exact_result_is_privately_retained(self):
        process = self.process(); result = connection.inspect_native(self.commit)
        self.send.assert_called_once_with(process.stdin); process.kill.assert_not_called()
        self.assertFalse(result['paid_launch_ready'])
        path = self.root / connection.STATE
        self.assertEqual({p.name for p in path.iterdir()}, {'intent.json', 'receiver.json', 'result.json'})
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in path.iterdir()))

    def test_failure_is_terminal_and_does_not_open_another_connection(self):
        process = self.process(failure=ValueError('synthetic refusal'))
        with self.assertRaises(ValueError): connection.inspect_native(self.commit)
        process.kill.assert_called_once()
        self.assertTrue((self.root / connection.STATE / 'failure.json').is_file())
        with self.assertRaisesRegex(ValueError, 'terminal'): connection.inspect_native(self.commit)
        self.start.assert_called_once()

    def test_untrusted_readiness_cannot_trigger_actual_handoff(self):
        self.process(); self.read.side_effect = [dict(self.ready(), paid_launch_ready=True)]
        with self.assertRaises(ValueError): connection.inspect_native(self.commit)
        self.send.assert_not_called()

    def test_wrong_process_start_identity_refuses_result(self):
        self.process(result=dict(self.result(), native_process=dict(PEER, start_ticks=999)))
        with self.assertRaises(ValueError): connection.inspect_native(self.commit)

    def test_wrong_capture_or_archive_and_ambiguous_ssh_exit_refuse(self):
        self.process(result=dict(self.result(), archive_sha256='9' * 64))
        with self.assertRaises(ValueError): connection.inspect_native(self.commit)
        self.assertFalse((self.root / connection.STATE / 'result.json').exists())

    def test_nonzero_ssh_exit_never_returns_success(self):
        self.process(rc=1)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'): connection.inspect_native(self.commit)

    def test_missing_backup_refuses_before_ssh_or_connection_intent(self):
        (self.f.e.folder / 'evidence.tar.gz').unlink()
        with patch.object(connection.subprocess, 'Popen') as start, self.assertRaises(ValueError):
            connection.inspect_native(self.commit)
        start.assert_not_called(); self.assertFalse((self.root / connection.STATE).exists())

    def test_uncommitted_source_refuses_before_any_native_operation(self):
        self.f.git_bytes['stage2/no_cutoff_recovery_service.py'] += b' '
        with patch.object(connection.subprocess, 'Popen') as start, self.assertRaises(ValueError):
            connection.inspect_native(self.commit)
        start.assert_not_called()

    def test_client_creation_failure_retains_private_fixed_status_only(self):
        with patch.object(connection.subprocess, 'Popen', side_effect=OSError('private raw diagnostic')):
            with self.assertRaises(OSError): connection.inspect_native(self.commit)
        raw = (self.root / connection.STATE / 'failure.json').read_text()
        self.assertNotIn('private raw diagnostic', raw)

    def test_same_byte_operator_source_replacement_refuses_after_transfer(self):
        self.process()
        def send(_):
            path = self.root / 'stage2/no_cutoff_recovery_service.py'; raw = path.read_bytes()
            path.unlink(); path.write_bytes(raw); path.chmod(0o600)
            return dict(operator_document_sha256='1' * 64, archive_sha256='2' * 64)
        self.send.side_effect = send
        with self.assertRaisesRegex(ValueError, 'identity replaced'): connection.inspect_native(self.commit)
        self.assertFalse((self.root / connection.STATE / 'result.json').exists())

    def test_same_byte_operator_intent_replacement_refuses_completion(self):
        self.process()
        def send(_):
            path = self.root / connection.STATE / 'intent.json'; raw = path.read_bytes()
            path.unlink(); path.write_bytes(raw); path.chmod(0o600)
            return dict(operator_document_sha256='1' * 64, archive_sha256='2' * 64)
        self.send.side_effect = send
        with self.assertRaisesRegex(ValueError, 'evidence changed'): connection.inspect_native(self.commit)
        self.assertFalse((self.root / connection.STATE / 'result.json').exists())


class ServiceSessionTests(LocalTree):
    def setUp(self):
        super().setUp()
        self.configure_session()

    def configure_session(self, create=True):
        self.enterContext(patch.object(session, '_context', return_value=self.root))
        # Full actual lock mechanics, only the fixed Linux ancestry paths are
        # substituted with local protected lock files. No production bypass.
        locks = []
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            relative = '.runtime/stage2/test-ancestor/' + name
            self.f.e.save(relative, b''); (self.root / relative).parent.chmod(0o700); locks.append(self.root / relative)
        self.enterContext(patch.object(session, '_lock_paths', return_value=tuple(locks)))
        self.enterContext(patch.object(session, '_lock_parents', side_effect=lambda path:
            tuple(p for p in reversed(path.parents) if p == self.root or p.is_relative_to(self.root))))
        self.enterContext(patch.object(runtime.libraries, '_directory_chain', side_effect=lambda root, path:
            [root, *reversed([p for p in path.parents if p != root and p.is_relative_to(root)])]))
        self.enterContext(patch.object(runtime, 'inspect', side_effect=self.host))
        self.enterContext(patch.object(runtime, 'recheck', side_effect=lambda witness, old: self.host(witness)))
        if create:
            self.path = self.native_folder()
            service.save(self.path / 'service-started.json', dict(service.base(NONCE, self.files, self.commit), native_process=PEER))

    def host(self, witness):
        record = handoff.recheck(witness); sources = handoff.operator.sources(self.root, self.f.final)
        return dict(kind=runtime.KIND, experiment=policy.EXPERIMENT, condition=policy.CONDITION,
            original_qualification_sha256=policy.fingerprint(self.f.final),
            original_runtime_sha256=self.f.final['runtime_identity_sha256'], plan_sha256=policy.PLAN_SHA256,
            predecessor_sha256=policy.fingerprint(record['predecessor']), sources=sources,
            sources_sha256=policy.fingerprint(sources), paid_launch_ready=False)

    def invoke(self, packet=None, *, disconnect=False):
        reader, writer = os.pipe(); errors = []; sent = []
        def write():
            try:
                with os.fdopen(writer, 'wb', buffering=0) as stream:
                    if packet is None: sent.append(handoff.send(stream))
                    else: stream.write(packet)
            except BrokenPipeError: pass
            except BaseException as error: errors.append(error)
        thread = threading.Thread(target=write); thread.start()
        peer = Mock()
        if disconnect: peer.sendall.side_effect = BrokenPipeError()
        intent = (self.path / 'intent.json').read_bytes()
        async def consume():
            with os.fdopen(reader, 'rb', buffering=0) as stream:
                try:
                    return await service.inspect_session(NONCE, self.files, self.commit,
                        self.identities, stream, peer, self.path, intent)
                except BaseException:
                    service._failure(self.path, 'failure.json', service.base(NONCE, self.files, self.commit)); raise
        try: result = asyncio.run(consume())
        finally:
            thread.join(10); self.assertFalse(thread.is_alive())
        if errors: raise errors[0]
        return result, peer, sent

    def test_real_sender_handoff_locked_session_and_exit_precede_success(self):
        before = self.f.archive_raw
        result, peer, sent = self.invoke()
        connection.reply(result, NONCE, self.files, self.commit, sent=sent[0], peer=PEER)
        self.assertEqual((self.f.e.folder / 'evidence.tar.gz').read_bytes(), before)
        self.assertEqual(len(session._SESSIONS), 0); self.assertEqual(len(handoff._WITNESSES), 0)
        self.f.e.collect.assert_called_once(); self.f.native_audit.assert_called_once(); peer.sendall.assert_called_once()

    def test_sender_audit_finishes_before_receiver_ancestor_process_checks(self):
        # The real sender does its required original audit before emitting any
        # header. Keep it pending until the real receiver is reading the pipe:
        # a pre-header ancestor process check would reject this required audit.
        receiving = threading.Event(); audited = threading.Event(); events = []
        read_header = handoff.wire.read_header
        def audit(commit):
            self.assertEqual(commit, self.commit)
            if not receiving.wait(5): raise AssertionError('Receiver never waited for the live header')
            events.append('operator-audit-finished'); audited.set()
            return deepcopy(self.f.e.fresh)
        def header(stream):
            events.append('waiting-for-header'); receiving.set()
            value = read_header(stream); events.append('header-received'); return value
        def ancestors(root):
            if not audited.is_set():
                receiving.set()  # Release the local test writer on old-code refusal.
                raise ValueError('Required sender audit is still active')
            self.assertIn('header-received', events)
            events.append('ancestor-check')
        self.f.e.collect.side_effect = audit; self.f.no_stop.side_effect = ancestors
        with patch.object(handoff.wire, 'read_header', side_effect=header):
            result, _, sent = self.invoke()
        self.assertEqual(events[:4], ['waiting-for-header', 'operator-audit-finished',
            'header-received', 'ancestor-check'])
        self.f.e.collect.assert_called_once_with(self.commit)
        self.f.native_audit.assert_called_once()
        self.assertEqual(len(sent), 1); self.assertFalse(result['paid_launch_ready'])

    def test_missing_final_commit_never_saves_success(self):
        with self.assertRaises(ValueError): self.invoke(self.f.packet(committed=False))
        self.assertFalse((self.path / 'result.json').exists()); self.assertTrue((self.path / 'failure.json').exists())

    def test_actual_handoff_revision_must_equal_detached_operation_revision(self):
        self.commit = 'b' * 40
        expected = service.base(NONCE, self.files, self.commit)
        self.f.e.save(service.STATE + '/intent.json', json.dumps(dict(expected, relay_process=PEER,
            created_utc='2026-09-29T20:00:00+00:00')).encode())
        self.f.e.save(service.STATE + '/service-started.json', json.dumps(dict(expected, native_process=PEER)).encode())
        with self.assertRaises(ValueError): self.invoke()
        self.assertFalse((self.path / 'prerequisites.json').exists())
        self.assertFalse((self.path / 'result.json').exists())
        self.assertFalse(session._SESSIONS); self.assertFalse(handoff._WITNESSES)

    def test_trailing_transfer_data_refuses(self):
        with self.assertRaises(ValueError): self.invoke(self.f.packet(tail=b'extra'))
        self.assertFalse((self.path / 'result.json').exists())

    def test_normal_exit_source_refusal_cannot_publish_early_success(self):
        original = service.save
        def save(path, value):
            raw = original(path, value)
            if path.name == 'prerequisites.json':
                source = self.root / 'stage2/no_cutoff_recovery_service.py'; source.write_bytes(source.read_bytes() + b' ')
            return raw
        with patch.object(service, 'save', side_effect=save), self.assertRaises(ValueError): self.invoke()
        self.assertTrue((self.path / 'prerequisites.json').is_file())
        self.assertFalse((self.path / 'result.json').exists()); self.assertFalse(session._SESSIONS)

    def test_disconnect_after_complete_transfer_does_not_erase_success(self):
        result, peer, _ = self.invoke(disconnect=True)
        self.assertEqual(result, boot.loads((self.path / 'result.json').read_bytes()))
        self.assertFalse((self.path / 'failure.json').exists()); peer.sendall.assert_called_once()

    def test_cancellation_exception_invalidates_handles_without_success(self):
        original = service.save
        def save(path, value):
            raw = original(path, value)
            if path.name == 'prerequisites.json': raise asyncio.CancelledError()
            return raw
        with patch.object(service, 'save', side_effect=save), self.assertRaises(asyncio.CancelledError): self.invoke()
        self.assertFalse(session._SESSIONS); self.assertFalse(handoff._WITNESSES)
        self.assertFalse((self.path / 'result.json').exists())

    def test_same_byte_retained_intent_replacement_cannot_publish_success(self):
        original = service.save
        def save(path, value):
            raw = original(path, value)
            if path.name == 'prerequisites.json':
                intent = self.path / 'intent.json'; before = intent.read_bytes(); intent.unlink()
                intent.write_bytes(before); intent.chmod(0o600)
            return raw
        with patch.object(service, 'save', side_effect=save), self.assertRaises(ValueError): self.invoke()
        self.assertFalse((self.path / 'result.json').exists())

    def test_existing_service_start_refuses_before_connect(self):
        with patch.object(service.socket, 'socket') as sock, self.assertRaisesRegex(ValueError, 'restarted'):
            service.serve(NONCE, self.files, self.commit, self.identities, PEER)
        sock.assert_not_called()


class TransportTests(LocalTree):
    host = ServiceSessionTests.host

    def setUp(self):
        super().setUp(); ServiceSessionTests.configure_session(self, create=False)
        # macOS's short Unix-path limit needs a short owned fixture parent.
        # Only its system ancestry is substituted; actual leaf identity, ACL,
        # owner/group/mode and replacement checks still run on real sockets.
        temp = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(temp.cleanup)
        self.run = Path(temp.name).resolve(); os.chown(self.run, -1, os.getgid())
        actual = boot.directories
        def directories(path, private=False):
            if path == self.run or path.is_relative_to(self.run):
                chain = [self.run, *reversed([p for p in path.parents if p != self.run and p.is_relative_to(self.run)])]
                if path != self.run: chain.append(path)
                saved = []
                for directory in chain:
                    s = directory.lstat(); boot.acl(directory)
                    if directory.resolve() != directory or not directory.is_dir() or s.st_uid != os.getuid() or s.st_gid != os.getgid() or s.st_mode & 0o077:
                        raise ValueError('Unsafe local socket directory')
                    saved.append((str(directory), s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid))
                return tuple(saved)
            return actual(path, private=private)
        self.enterContext(patch.object(boot, 'directories', side_effect=directories))
        self.enterContext(patch.object(service, 'RUN_BASE', self.run))

    def flow(self, *, packet=None, disconnect=False, wrong_peer=False):
        read, write = os.pipe(); response_read, response_write = os.pipe()
        incoming = os.fdopen(read, 'rb', buffering=0); outgoing = os.fdopen(write, 'wb', buffering=0)
        responses = os.fdopen(response_read, 'rb', buffering=0); acknowledgement = os.fdopen(response_write, 'wb', buffering=0)
        self.addCleanup(outgoing.close); self.addCleanup(responses.close)
        started = threading.Event(); errors = []; observed = []
        def start(*args, **kwargs): started.set(); return NS(returncode=0)
        def relay():
            try: service.relay(NONCE, self.files, self.commit, self.identities)
            except BaseException as error: errors.append(error)
            finally: incoming.close(); acknowledgement.close()
        def operator():
            try:
                ready = connection.reply(connection.read_reply(responses), NONCE, self.files, self.commit)
                if packet is None: sent = handoff.send(outgoing)
                else: outgoing.write(packet)
                outgoing.close()
                if disconnect: responses.close()
                elif packet is None:
                    result = connection.reply(connection.read_reply(responses), NONCE, self.files, self.commit,
                        sent=sent, peer=ready['native_process'])
                    observed.append(result)
                else: connection.read_reply(responses)
            except BaseException as error: errors.append(error)
            finally: outgoing.close()
        with patch.object(service, 'sys', NS(stdin=NS(buffer=incoming), stdout=NS(buffer=acknowledgement))), \
                patch.object(service.subprocess, 'run', side_effect=start), patch.object(service, 'TIMEOUT', 10):
            if wrong_peer: self.enterContext(patch.object(service, '_peer', return_value=dict(PEER, start_ticks=999)))
            threads = [threading.Thread(target=relay), threading.Thread(target=operator)]
            for thread in threads: thread.start()
            try:
                self.assertTrue(started.wait(10))
                try: service.serve(NONCE, self.files, self.commit, self.identities, PEER)
                except BaseException as error: errors.append(error)
            finally:
                for thread in threads: thread.join(15)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
        return errors, observed

    def test_actual_pipe_socket_relay_service_handoff_and_session_complete_locally(self):
        errors, observed = self.flow(); self.assertEqual(errors, [])
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0], boot.loads((self.root / service.STATE / 'result.json').read_bytes()))
        self.assertFalse(session._SESSIONS); self.assertFalse(handoff._WITNESSES)
        self.f.e.collect.assert_called_once(); self.f.native_audit.assert_called_once()
        self.assertFalse(any(self.run.iterdir()))

    def test_incomplete_transfer_retains_native_failure_without_success_or_replay(self):
        errors, observed = self.flow(packet=self.f.packet(committed=False))
        self.assertTrue(errors); self.assertEqual(observed, [])
        self.assertTrue((self.root / service.STATE / 'failure.json').exists())
        self.assertFalse((self.root / service.STATE / 'result.json').exists())
        read, write = os.pipe(); os.close(write)
        with os.fdopen(read, 'rb') as stream, patch.object(service, 'sys', NS(stdin=NS(buffer=stream))):
            with self.assertRaises(FileExistsError): service.relay(NONCE, self.files, self.commit, self.identities)

    def test_wrong_root_peer_process_refuses_before_archive_authentication(self):
        errors, observed = self.flow(wrong_peer=True)
        self.assertTrue(errors); self.assertEqual(observed, [])
        self.f.native_audit.assert_not_called()
        self.assertFalse((self.root / service.STATE / 'result.json').exists())

    def test_client_acknowledgement_loss_does_not_stop_detached_completed_session(self):
        errors, observed = self.flow(disconnect=True)
        self.assertEqual(observed, [])
        self.assertTrue((self.root / service.STATE / 'result.json').exists())
        self.assertFalse((self.root / service.STATE / 'failure.json').exists())
        self.assertTrue(all(isinstance(error, BrokenPipeError) for error in errors))
        self.assertFalse(session._SESSIONS)


class ImportTests(unittest.TestCase):
    def test_credential_free_real_import_child_has_no_external_effect(self):
        program = '''
import sys
sys.path.insert(0, STAGE)
import no_cutoff_recovery_bootstrap as b
b.ROOT=__import__('pathlib').Path(STAGE).parent
expected=b.environment()
expected['TIKTOKEN_CACHE_DIR']=str(__import__('pathlib').Path(sys.prefix)/'lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers')
b.environment=lambda:dict(expected)
__import__('os').environ.update(expected)
sys.addaudithook(b.no_effects)
b.IMPORTING=True
import no_cutoff_recovery_connection, no_cutoff_recovery_service
b.IMPORTING=False
assert not b.VIOLATION
print('credential-free recovery imports passed')
'''.replace('STAGE', repr(str(STAGE)))
        env = dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', LITELLM_MODE='PRODUCTION',
            LITELLM_LOCAL_MODEL_COST_MAP='True', PYTHON_DOTENV_DISABLED='1', DO_NOT_TRACK='1')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', program], env=env,
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('imports passed', result.stdout)
