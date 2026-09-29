"""Local pipes/sockets/archives, mocked native/systemd boundaries; no VPS calls."""
import ast
import asyncio
import base64
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import socket
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import matched_repeat_connection as connection
import matched_repeat_service as service
import matched_repeat_policy as policy
import matched_repeat_amended_handoff as handoff
import matched_repeat_stream as wire
from scored_gateway import durable_json
import test_matched_repeat_amended_handoff as handoff_tests

NONCE = 'a1' * 16
HARNESS = 'terminus-2'


class LocalTree(unittest.TestCase):
    def setUp(self):
        # Reuse only setup/cleanup, not the other module's test methods. Its
        # native audits are mocked but actual archive/source readers run.
        self.fixture = handoff_tests.HandoffFixture('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo = self.fixture.repo
        # Current source bytes for the actual stdlib full-inventory guard.
        stage = Path(__file__).resolve().parent
        for name in policy.REQUIRED_SOURCE_FILES:
            raw = (stage / name).read_bytes(); relative = 'stage2/' + name
            self.fixture.save(relative, raw)
            self.fixture.current[name] = hashlib.sha256(raw).hexdigest()
            self.fixture.old_anchors['local'][relative] = hashlib.sha256(raw).hexdigest()
            self.fixture.git_bytes[relative] = raw
        self.files = connection.bindings(self.repo, HARNESS)
        sockets = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(sockets.cleanup)
        self.run = Path(sockets.name).resolve()
        self.enterContext(patch.object(service, 'RUN_BASE', self.run))

    def ready(self, pid=123):
        return dict(kind='matched_repeat_receiver_ready_not_authenticated', operation=service.OPERATION,
            nonce=NONCE, unit=service.identity(HARNESS, NONCE), root=str(self.repo), harness=HARNESS,
            native_pid=pid, bindings_sha256=policy.fingerprint(self.files), paid_launch_ready=False)

    def result(self, pid=123):
        return dict(self.ready(pid), kind='matched_repeat_prerequisites_checked_not_dispatch',
            operator_document_sha256='1' * 64, archive_sha256='2' * 64, prerequisites_sha256='3' * 64)

    def program(self, files=None, role='relay', relay_pid=None):
        encoded = connection.native_program(HARNESS, NONCE, self.files if files is None else files,
            role=role, relay_pid=relay_pid)
        tree = ast.parse(encoded)
        call = tree.body[1].value.args[0].args[0]
        return base64.b64decode(ast.literal_eval(call.args[0])).decode()

    def guard(self, program=None, state=None, imported=None, final_error=None):
        program = self.program() if program is None else program
        final_check=Mock(side_effect=final_error)
        # Only native observations/constant paths are mocked. The generated
        # route must call this before AND after its actual project import.
        program=program.replace('\ncheck()\nos.chdir',
            "\nfinal_guard['ROOT']=Path("+repr(str(connection.baseline.FINAL_ROOT))+")\n"+
            "final_guard['service']=synthetic_final_check\ncheck()\nos.chdir")
        # Execute the actual generated pre/post-import guard with host facts
        # mocked. Real path/symlink/hash reads remain in place on local files.
        previous = Path.stat
        def stat_root(path, *args, **kwargs):
            value = previous(path, *args, **kwargs)
            if str(path).startswith(str(self.repo)):
                values = list(value); values[4] = 0
                return os.stat_result(values)
            return value
        for base in (connection.baseline.ORIGINAL_ROOT, connection.baseline.FINAL_ROOT):
            # Original/final ancestor paths in the generated program are
            # replaced through the builder's existing constant bindings.
            self.assertTrue(base.is_dir())
        state = state or 'LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'
        with patch('platform.system', return_value='Linux'), patch('os.getuid', return_value=0), \
                patch.object(sys, 'prefix', str(self.repo / '.venv')), \
                patch.object(sys, 'flags', NS(isolated=1)), patch.object(sys, 'dont_write_bytecode', True), \
                patch.object(sys, 'pycache_prefix', None), patch.object(Path, 'stat', stat_root), \
                patch('subprocess.check_output', return_value=state), \
                patch.object(service, 'relay', imported or Mock()) as relay, \
                patch('os.chdir'), patch.object(sys, 'path', list(sys.path)):
            exec(compile(program, '<local-native-guard-test>', 'exec'), {'synthetic_final_check':final_check})
        self.assertEqual(final_check.call_count,2)
        return relay


class CommandTests(LocalTree):
    def setUp(self):
        super().setUp()
        self.original = self.repo / 'original'; self.original.mkdir()
        self.enterContext(patch.object(connection.baseline, 'ORIGINAL_ROOT', self.original))

    def test_archived_reporting_revision_is_separate_from_current_repeat_revision(self):
        with patch.object(handoff.export, '_read_backup', wraps=handoff.export._read_backup) as read:
            connection.bindings(self.repo, HARNESS)
        local = read.call_args.args[0]['local']
        self.assertIn('stage2/no_cutoff_final_export.py', local)
        self.assertNotIn('stage2/matched_repeat_service.py', local)
        self.assertIn('stage2/matched_repeat_service.py', self.files)

    def test_exact_pinned_ssh_replaces_only_the_original_interpreter(self):
        old = connection.ssh_command(self.repo)
        cmd = connection.command(self.repo, HARNESS, NONCE, self.files)
        self.assertEqual(cmd[:-1], old[:-2])
        for flag in ('StrictHostKeyChecking=yes', 'IdentitiesOnly=yes', 'BatchMode=yes',
                'ClearAllForwardings=yes', 'RequestTTY=no'):
            self.assertIn(flag, cmd)
        remote = shlex.split(cmd[-1])
        self.assertEqual(remote[:3], ['/usr/bin/env', '-i', 'PATH=/usr/bin:/bin'])
        self.assertEqual(remote[-5:-1], [str(self.repo / '.venv/bin/python'), '-I', '-B', '-c'])
        self.assertNotIn('python3', remote); self.assertNotIn('sshpass', cmd)
        self.assertNotIn('OPENROUTER_API_KEY', remote)

    def test_missing_actual_final_success_refuses_before_native_entry(self):
        relay=Mock()
        with self.assertRaisesRegex(ValueError,'Missing manager completion'):
            self.guard(imported=relay,final_error=ValueError('Missing manager completion'))
        relay.assert_not_called()

    def test_changed_ssh_shape_cannot_silently_add_a_second_interpreter(self):
        with patch.object(connection, 'ssh_command', return_value=['ssh', 'other', 'python3', '-']):
            with self.assertRaisesRegex(ValueError, 'SSH command shape'):
                connection.command(self.repo, HARNESS, NONCE, self.files)

    def test_only_exact_term_inspection_role_nonce_and_root_are_accepted(self):
        for bad in ('../../bad', 'z' * 32, 'a' * 31, '', None):
            with self.subTest(nonce=bad), self.assertRaises(ValueError): service.identity(HARNESS, bad)
        with self.assertRaisesRegex(ValueError, 'OpenHands'): service.identity('openhands', NONCE)
        for role, pid in (('paid', None), ('qualify', None), ('service', True), ('service', 0)):
            with self.subTest(role=role, pid=pid), self.assertRaises(ValueError):
                connection.native_program(HARNESS, NONCE, self.files, role=role, relay_pid=pid)

    def test_pinned_private_anchors_and_new_sources_cannot_be_omitted(self):
        for name in ('stage2/matched_repeat_service.py', '.runtime/stage2/' + policy.FINAL_FILE):
            changed = dict(self.files); changed.pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError): self.program(changed)
        changed = dict(self.files); changed['.runtime/stage2/' + policy.FINAL_FILE] = '0' * 64
        with self.assertRaises(ValueError): self.program(changed)
        changed = dict(self.files); changed['.runtime/stage2/unapproved.json'] = '0' * 64
        with self.assertRaises(ValueError): self.program(changed)

    def test_generated_guard_checks_actual_all_sources_before_and_after_import(self):
        relay = self.guard()
        relay.assert_called_once_with(self.repo, HARNESS, NONCE, self.files)
        code = self.program()
        self.assertLess(code.index('check()\nos.chdir'), code.index('from matched_repeat_service'))
        self.assertIn('unused-matched-connection-bytecode', code)

    def test_guard_refuses_missing_inherited_source_before_import(self):
        changed = dict(self.files)
        name = next(n for n in changed if n.startswith('stage2/') and n[7:] not in policy.REQUIRED_SOURCE_FILES)
        changed.pop(name)
        relay = Mock()
        with self.assertRaisesRegex(ValueError, 'Incomplete native source inventory'):
            self.guard(self.program(changed), imported=relay)
        relay.assert_not_called()

    def test_active_failed_or_stopped_ancestor_refused_without_project_call(self):
        for state in ('LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=55\nExecMainStatus=0\n',
                'LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=1\n'):
            relay = Mock()
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'inactive ancestors'):
                self.guard(state=state, imported=relay)
            relay.assert_not_called()
        marker = self.repo / '.runtime/stage2/provider-stop.json'; marker.symlink_to(self.repo / 'absent')
        with self.assertRaisesRegex(ValueError, 'Persistent repeat stop'): self.guard()

    def test_source_drift_private_permissions_and_symlinks_refused_before_import(self):
        path = self.repo / 'stage2/matched_repeat_service.py'; raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'source/input drift'): self.guard()
        path.write_bytes(raw)
        anchor = self.repo / '.runtime/stage2' / policy.FINAL_FILE; anchor.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'Private owned'): self.guard()
        anchor.chmod(0o600); path.rename(self.repo / 'moved.py'); path.symlink_to(self.repo / 'moved.py')
        with self.assertRaisesRegex(ValueError, 'Symlinked'): self.guard()

    def test_existing_or_symlinked_bytecode_prefix_refused(self):
        path = self.repo / '.runtime/unused-matched-connection-bytecode'
        path.symlink_to(self.repo / 'absent')
        with self.assertRaisesRegex(ValueError, 'cache prefix'): self.guard()

    def test_post_import_source_change_is_refused_before_native_entrypoint(self):
        original_import = __import__; relay = Mock()
        def importing(name, *args, **kwargs):
            value = original_import(name, *args, **kwargs)
            if name == 'matched_repeat_service':
                path = self.repo / 'stage2/matched_repeat_service.py'
                path.write_bytes(path.read_bytes() + b' ')
            return value
        with patch('builtins.__import__', side_effect=importing):
            with self.assertRaisesRegex(ValueError, 'source/input drift'): self.guard(imported=relay)
        relay.assert_not_called()

    def test_detached_fixed_service_has_no_client_stdin_restart_or_runtime_ceiling(self):
        folder = service._control(self.repo, NONCE, create=True)
        cmd = service.service_command(self.repo, HARNESS, NONCE, self.files, 123)
        self.assertIn('--property=Type=exec', cmd); self.assertIn('--property=Restart=no', cmd)
        self.assertIn('--property=StandardInput=null', cmd)
        self.assertIn('--property=StandardOutput=append:' + str(folder / 'service.log'), cmd)
        self.assertEqual(cmd[cmd.index('/usr/bin/env') + 1], '-i')
        for forbidden in ('--pipe', '--scope', '--wait', 'RuntimeMaxSec', 'OPENROUTER_API_KEY'):
            self.assertFalse(any(forbidden in part for part in cmd))
        self.assertIn('serve(root,', self.program(role='service', relay_pid=123))

    def test_incomplete_off_server_backup_refused_before_any_ssh_start(self):
        (self.repo / handoff.receiver.DESTINATION / 'evidence.tar.gz').unlink()
        with patch.object(connection.subprocess, 'Popen') as start:
            with self.assertRaises(ValueError): connection.inspect_native(self.repo)
        start.assert_not_called()

    def test_current_backup_destination_has_no_legacy_fallback(self):
        current = self.repo / handoff.receiver.DESTINATION
        legacy = self.repo / connection.operator.COMPLETED
        self.assertNotEqual(current, legacy)
        self.assertFalse(legacy.exists())
        connection.bindings(self.repo, HARNESS)
        legacy.mkdir(mode=0o700)
        for name in ('snapshot.json', 'backup.json', 'evidence.tar.gz'):
            path = legacy / name
            path.write_bytes((current / name).read_bytes()); path.chmod(0o600)
        (current / 'evidence.tar.gz').unlink()
        with patch.object(connection.subprocess, 'Popen') as start:
            with self.assertRaises(ValueError): connection.inspect_native(self.repo)
        start.assert_not_called()


class MetadataTests(LocalTree):
    def pipe(self, raw):
        reader, writer = os.pipe()
        stream = os.fdopen(reader, 'rb', buffering=0); self.addCleanup(stream.close)
        with os.fdopen(writer, 'wb', buffering=0) as output: output.write(raw)
        return stream

    def test_metadata_pipe_preserves_numeric_types(self):
        value = connection.read_reply(self.pipe(b'{"x":1.0,"paid_launch_ready":false}\n'))
        self.assertIs(type(value['x']), float); self.assertFalse(value['paid_launch_ready'])

    def test_incomplete_duplicate_extra_nonobject_and_oversized_metadata_fail_closed(self):
        for raw in (b'', b'{"x":1}', b'{"x":1,"x":2}\n', b'[]\n', b'{}\nextra', b'{' + b' ' * 50):
            with self.subTest(raw=raw), patch.object(connection, 'REPLY_LIMIT', 40):
                with self.assertRaises(ValueError): connection.read_reply(self.pipe(raw))

    def test_ack_timeout_is_a_transport_error_not_a_study_stop(self):
        reader, writer = os.pipe(); self.addCleanup(os.close, writer)
        with os.fdopen(reader, 'rb', buffering=0) as stream, patch.object(connection, 'TIMEOUT', 0.001):
            with self.assertRaisesRegex(ValueError, 'inspect before retrying'): connection.read_reply(stream)

    def test_native_reply_requires_one_exact_json_line_and_eof(self):
        self.assertEqual(service._read_reply(io.BytesIO(b'{"x":1}\n')), {'x': 1})
        for raw in (b'{}', b'{}\ntrailing', b'{"x":1,"x":2}\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): service._read_reply(io.BytesIO(raw))

    def test_operation_binding_qualifies_neither_readiness_nor_final_receipt(self):
        ready = self.ready(); sent = dict(operator_document_sha256='1' * 64, archive_sha256='2' * 64)
        connection._reply(ready, HARNESS, NONCE, self.files)
        connection._reply(self.result(), HARNESS, NONCE, self.files, sent=sent, pid=123)
        for key, value in (('paid_launch_ready', True), ('native_pid', True), ('nonce', 'b' * 32),
                ('bindings_sha256', '0' * 64), ('unexpected', True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                connection._reply(dict(ready, **{key: value}), HARNESS, NONCE, self.files)
        for key in ('native_pid', 'operator_document_sha256', 'archive_sha256', 'prerequisites_sha256'):
            value = 456 if key == 'native_pid' else 'wrong'
            with self.subTest(key=key), self.assertRaises(ValueError):
                connection._reply(dict(self.result(), **{key: value}), HARNESS, NONCE, self.files, sent=sent, pid=123)
        with self.assertRaises(ValueError): connection._reply(ready, HARNESS, NONCE, self.files, sent=sent, pid=123)

    def test_root_peer_pid_is_checked_without_claiming_network_authentication(self):
        with patch.object(socket, 'SO_PEERCRED', 17, create=True):
            peer = Mock(); peer.getsockopt.return_value = struct.pack('3i', 789, 0, 0)
            self.assertEqual(service._peer(peer), 789)
            for values in ((0, 0, 0), (789, 501, 0), (789, 0, 501)):
                peer.getsockopt.return_value = struct.pack('3i', *values)
                with self.assertRaises(ValueError): service._peer(peer)

    def test_exact_systemd_main_pid_and_proc_cwd_are_required(self):
        with patch('subprocess.check_output', return_value='LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=789\n'), \
                patch('os.readlink', return_value=str(self.repo)):
            self.assertEqual(service._service_pid('fixture.service', self.repo), 789)
        with patch('subprocess.check_output', return_value='LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=789\n'), \
                patch('os.readlink', return_value='/wrong'):
            with self.assertRaisesRegex(ValueError, 'directory'): service._service_pid('fixture.service', self.repo)

    def test_exclusive_private_intent_is_never_reused_and_symlinks_are_refused(self):
        folder = service._control(self.repo, NONCE, create=True)
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(FileExistsError): service._control(self.repo, NONCE, create=True)
        folder.chmod(0o755)
        with self.assertRaises(ValueError): service._control(self.repo, NONCE)
        folder.chmod(0o700); folder.rmdir(); folder.symlink_to(self.repo)
        with self.assertRaises(ValueError): service._control(self.repo, NONCE)

    def test_disconnected_acknowledgement_does_not_stop_authenticated_native_work(self):
        endpoint = Mock(); endpoint.sendall.side_effect = BrokenPipeError('Operator disconnected')
        service._reply(endpoint, self.result())
        endpoint.sendall.assert_called_once()

    def test_service_context_requires_current_private_inputs_own_root_and_sources(self):
        with patch.object(service.session, '_context', return_value=self.repo), \
                patch.object(service, '__file__', str(self.repo / 'stage2/matched_repeat_service.py')), \
                patch.object(service, 'os', NS(getuid=lambda: 0)), \
                patch.object(service.session, '_inputs', return_value=(None, None, self.files)):
            service._context(self.repo, HARNESS, self.files)
            with self.assertRaisesRegex(ValueError, 'actual operator bindings'):
                service._context(self.repo, HARNESS, dict(self.files, changed='0' * 64))
            path = self.repo / 'stage2/matched_repeat_connection.py'; path.write_bytes(b'drift')
            with self.assertRaises(ValueError): service._context(self.repo, HARNESS, self.files)


class OperatorTests(LocalTree):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(connection.secrets, 'token_hex', return_value=NONCE))

    def process(self, *, failure=None, result=None, rc=0):
        process = Mock(stdin=io.BytesIO(), stdout=io.BytesIO(), wait=Mock(return_value=rc), poll=Mock(return_value=None))
        self.start = self.enterContext(patch.object(connection.subprocess, 'Popen', return_value=process))
        self.read = self.enterContext(patch.object(connection, 'read_reply', side_effect=[self.ready(), result or self.result()]))
        self.send = self.enterContext(patch.object(connection.handoff, 'send',
            return_value=dict(operator_document_sha256='1' * 64, archive_sha256='2' * 64), side_effect=failure))
        return process

    def test_exact_sender_and_same_pid_receipt_are_required_and_private_evidence_saved(self):
        process = self.process()
        result = connection.inspect_native(self.repo)
        self.send.assert_called_once_with(self.repo, process.stdin, HARNESS)
        self.assertFalse(result['paid_launch_ready']); process.kill.assert_not_called()
        folder = self.repo / '.runtime/netcup/matched-repeat-connections' / NONCE
        self.assertEqual({p.name for p in folder.iterdir()}, {'intent.json', 'receiver.json', 'result.json'})
        for path in folder.iterdir(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.start.call_count, 1)

    def test_failed_fresh_capture_preserves_identity_and_only_kills_owned_ssh_client(self):
        process = self.process(failure=ValueError('Real capture refused'))
        with self.assertRaisesRegex(ValueError, 'Real capture refused') as caught: connection.inspect_native(self.repo)
        process.kill.assert_called_once(); self.assertIn(NONCE, caught.exception.__notes__[0])
        folder = self.repo / '.runtime/netcup/matched-repeat-connections' / NONCE
        self.assertTrue((folder / 'failure.json').exists()); self.assertFalse((folder / 'result.json').exists())
        self.assertEqual(self.start.call_count, 1)

    def test_wrong_service_pid_cannot_reuse_another_process_session(self):
        self.process(result=self.result(pid=999))
        with self.assertRaisesRegex(ValueError, 'exact live operator transfer'): connection.inspect_native(self.repo)

    def test_untrusted_readiness_refused_before_any_archive_transfer(self):
        self.process(); self.read.side_effect = [dict(self.ready(), paid_launch_ready=True)]
        with self.assertRaises(ValueError): connection.inspect_native(self.repo)
        self.send.assert_not_called()

    def test_ambiguous_ssh_exit_never_returns_success_or_retries(self):
        self.process(rc=1)
        with self.assertRaisesRegex(ValueError, 'ambiguously'): connection.inspect_native(self.repo)
        self.assertEqual(self.start.call_count, 1)

    def test_ssh_creation_failure_still_retains_the_exact_operation_identity(self):
        with patch.object(connection.subprocess, 'Popen', side_effect=OSError('Cannot start client')) as start:
            with self.assertRaises(OSError) as caught: connection.inspect_native(self.repo)
        start.assert_called_once(); self.assertIn(NONCE, caught.exception.__notes__[0])
        self.assertTrue((self.repo / '.runtime/netcup/matched-repeat-connections' / NONCE / 'failure.json').exists())


class ServiceFlowTests(LocalTree):
    def setUp(self):
        super().setUp()
        self.events = []; self.active_task = None
        self.enterContext(patch.object(service, '_context', side_effect=lambda root, *args: root))
        self.enterContext(patch.object(service, '_peer', return_value=os.getpid()))
        self.enterContext(patch.object(service, '_service_pid', return_value=os.getpid()))
        self.enterContext(patch.object(service.session, 'open_session', side_effect=self.opened))
        self.enterContext(patch.object(service.session, 'recheck', side_effect=self.recheck))

    @contextmanager
    def opened(self, root, harness, stream):
        self.active_task = asyncio.current_task(); self.events.append('authenticate')
        # Actual archive stream and native handoff reader, but native audit
        # subprocesses remain mocked by the fixture. Never a native proof.
        witness = handoff.authenticate(root, self.fixture.f.original, self.fixture.f.proof, harness, stream)
        try: yield witness
        finally:
            self.assertIs(asyncio.current_task(), self.active_task)
            self.events.append('closed'); self.active_task = None

    def recheck(self, witness):
        self.assertIs(asyncio.current_task(), self.active_task)
        self.events.append('under-same-task')
        return dict(predecessor=handoff.recheck(self.repo, self.fixture.f.original,
            self.fixture.f.proof, HARNESS, witness), paid_launch_ready=False)

    def flow(self, packet=None, disconnect=False, wrong_peer=False):
        incoming, outgoing = os.pipe(); stdout_r, stdout_w = os.pipe()
        relay_input = os.fdopen(incoming, 'rb'); output = os.fdopen(outgoing, 'wb', buffering=0)
        responses = os.fdopen(stdout_r, 'rb', buffering=0); relay_output = os.fdopen(stdout_w, 'wb', buffering=0)
        self.addCleanup(output.close); self.addCleanup(responses.close)
        threads = []; errors = []
        def run_native():
            try: service.serve(self.repo, HARNESS, NONCE, self.files, os.getpid())
            except BaseException as error: errors.append(error)
        def launch(*args, **kwargs):
            thread = threading.Thread(target=run_native, daemon=True); threads.append(thread); thread.start()
            return NS(returncode=0)
        def relay_print(value, **kwargs):
            try: relay_output.write(value.encode() + b'\n')
            except BrokenPipeError:
                if not disconnect: raise
        def relay_run():
            try: service.relay(self.repo, HARNESS, NONCE, self.files)
            except BaseException as error: errors.append(error)
            finally: relay_input.close(); relay_output.close()
        with patch.object(service.sys, 'stdin', NS(buffer=relay_input)), \
                patch.object(service, 'print', side_effect=relay_print, create=True), \
                patch.object(service.subprocess, 'run', side_effect=launch), \
                patch.object(service, 'TRANSPORT_SECONDS', 5):
            if wrong_peer:
                self.enterContext(patch.object(service, '_service_pid', return_value=os.getpid() + 1))
            relay_thread = threading.Thread(target=relay_run, daemon=True); relay_thread.start()
            try:
                if wrong_peer:
                    with self.assertRaises(ValueError): connection.read_reply(responses)
                else:
                    ready = connection._reply(connection.read_reply(responses), HARNESS, NONCE, self.files)
                    if packet is None: sent = handoff.send(self.repo, output)
                    else: wire._write(output, packet)
                    output.close()
                    if disconnect:
                        responses.close()
                    elif packet is None:
                        result = connection._reply(connection.read_reply(responses), HARNESS, NONCE,
                            self.files, sent=sent, pid=ready['native_pid'])
                        self.assertFalse(result['paid_launch_ready'])
                    else:
                        with self.assertRaises(ValueError): connection.read_reply(responses)
            finally:
                output.close(); relay_thread.join(10)
                for thread in threads: thread.join(10)
                self.assertFalse(relay_thread.is_alive())
                self.assertTrue(all(not t.is_alive() for t in threads))
        return errors

    def test_actual_sender_archive_socket_relay_and_service_session_complete_locally(self):
        before = self.fixture.f.archive.read_bytes()
        self.assertEqual(self.flow(), [])
        self.assertEqual(self.events, ['authenticate', 'under-same-task', 'closed'])
        self.fixture.operator_audit.assert_called_once(); self.fixture.audit.assert_called_once()
        self.assertEqual(self.fixture.f.archive.read_bytes(), before)
        folder = service._control(self.repo, NONCE)
        self.assertEqual({p.name for p in folder.iterdir()}, {'intent.json', 'service.log', 'prerequisites.json', 'result.json'})
        self.assertFalse(service._socket_path(NONCE).exists())
        result = json.loads((folder / 'result.json').read_bytes())
        self.assertEqual(result['prerequisites_sha256'], hashlib.sha256((folder / 'prerequisites.json').read_bytes()).hexdigest())

    def test_client_disconnect_after_committed_transfer_retains_private_native_result(self):
        self.assertEqual(self.flow(disconnect=True), [])
        self.assertEqual(self.events[-1], 'closed')
        self.assertTrue((service._control(self.repo, NONCE) / 'result.json').exists())

    def test_incomplete_transfer_never_opens_a_usable_session_and_retains_failure(self):
        errors = self.flow(packet=wire.MAGIC)
        self.assertTrue(errors); self.fixture.audit.assert_not_called()
        self.assertNotIn('under-same-task', self.events)
        folder = service._control(self.repo, NONCE)
        self.assertTrue((folder / 'failure.json').exists()); self.assertFalse((folder / 'result.json').exists())

    def test_whole_archive_without_operator_commit_is_not_an_authenticated_session(self):
        packet = self.fixture.packet(commit=False)
        errors = self.flow(packet=packet)
        self.assertTrue(errors); self.fixture.audit.assert_not_called()
        self.assertNotIn('under-same-task', self.events)
        self.assertFalse((service._control(self.repo, NONCE) / 'result.json').exists())

    def test_failed_under_lock_recheck_never_writes_success(self):
        with patch.object(service.session, 'recheck', side_effect=ValueError('Under-lock source drift')):
            packet = self.fixture.packet()
            errors = self.flow(packet=packet)
        self.assertTrue(errors); self.assertEqual(self.events[-1], 'closed')
        folder = service._control(self.repo, NONCE)
        self.assertTrue((folder / 'failure.json').exists())
        self.assertFalse((folder / 'prerequisites.json').exists()); self.assertFalse((folder / 'result.json').exists())

    def test_native_connection_lock_is_held_but_no_ancestor_lock_is_preacquired(self):
        from contextlib import ExitStack
        from run_credit_only import hold
        original = self.recheck
        def checked(witness):
            with ExitStack() as contender:
                with self.assertRaises(BlockingIOError):
                    hold(contender, self.repo / '.runtime/stage2', 'matched-repeat-connection.lock')
            # The mock session owns no ancestor locks: this proves the transport
            # itself does not pre-lock the matrix before the authenticators.
            with ExitStack() as contender: hold(contender, self.repo / '.runtime/stage2', 'matrix.lock')
            return original(witness)
        with patch.object(service.session, 'recheck', side_effect=checked):
            self.assertEqual(self.flow(), [])
        with ExitStack() as contender:
            hold(contender, self.repo / '.runtime/stage2', 'matched-repeat-connection.lock')

    def test_wrong_local_socket_peer_cannot_receive_archive_or_open_session(self):
        errors = self.flow(wrong_peer=True)
        self.assertTrue(errors); self.fixture.operator_audit.assert_not_called(); self.fixture.audit.assert_not_called()
        self.assertNotIn('under-same-task', self.events)

    def test_persistent_native_intent_mismatch_is_refused_before_connection(self):
        folder = service._control(self.repo, NONCE, create=True)
        durable_json(folder / 'intent.json', dict(paid_launch_ready=True))
        with patch.object(service.socket, 'socket') as socket_call:
            with self.assertRaisesRegex(ValueError, 'intent differs'):
                service.serve(self.repo, HARNESS, NONCE, self.files, os.getpid())
        socket_call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
