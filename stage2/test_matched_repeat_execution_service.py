"""Real durable local service files; native systemd/peer/lifecycle facts mocked."""
import asyncio
import ast
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_execution_service as service
import qualify_matched_repeat as qualifier
import run_matched_repeat as runner
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save
from test_matched_repeat_completion import synthetic_qualification_inputs


class ServiceExecutionTests(LocalFiles, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        # Mock only system ancestry outside the owned local fixture in BOTH
        # bootstrap namespaces; retain real in-fixture protection checks.
        self.enterContext(patch.object(service.boot, 'directories', side_effect=service.evidence.bootstrap.directories))
        self.enterContext(patch.dict(service.boot.ROOTS, {'terminus-2': self.root}))
        self.enterContext(patch.dict(service.runtime.DEPLOYMENTS, {'terminus-2': self.root}))
        self.operation = 'qualify-repeat'; self.nonce = '1' * 32; self.commit = '2' * 40
        save(self.root, 'stage2/synthetic.py', b'# local fixture only\n')
        self.files, self.identities = service.evidence.capture(self.root, ['stage2/synthetic.py'])
        self.files.update(synthetic_qualification_inputs(self, self.root))
        self.identities = service.evidence.capture(self.root, self.files)[1]
        self.path = self.root / service.completion.operation_state(self.operation)
        self.expected = service.completion.base('terminus-2', self.nonce, self.files, self.commit, self.operation)
        self.process = dict(pid=12345, start_ticks=56789); self.relay = dict(pid=12344, start_ticks=56780)
        self.events = []; self.live = False; self.exit_error = None; self.ack_error = False
        self.recovered = dict(kind='live_completed_recovery_for_baseline_not_admission', harness='terminus-2',
            operator_commit=self.commit, recovery_document_sha256='3' * 64, archive_sha256='4' * 64,
            paid_launch_ready=False)
        self.record = dict(inputs=self.files, harness='terminus-2', completed_recovery=self.recovered,
            predecessor=dict(operator_document_sha256='5' * 64, streamed_backup={'sha256': '6' * 64}))
        self.intent_raw = self.intent()
        self.enterContext(patch.object(service, 'check', side_effect=self.check))
        self.enterContext(patch.object(service.completion, 'process_identity', return_value=self.process))
        self.enterContext(patch.object(service.session, 'open_execution_session', side_effect=self.open))
        self.enterContext(patch.object(service.session, 'recheck', side_effect=self.recheck))
        self.enterContext(patch.object(service.session, 'require_execution', side_effect=self.require))
        self.completion = self.enterContext(patch.object(service.completion, 'read', side_effect=self.completed))
        self.verify = self.enterContext(patch.object(service.session, 'verify_qualification', side_effect=self.qualified))
        self.qualifier = self.enterContext(patch.object(qualifier, 'qualify', side_effect=self.produce))
        self.runner = self.enterContext(patch.object(runner, 'run', side_effect=self.produce))
        self.connection = NS(sendall=self.sendall, shutdown=lambda mode: self.events.append('half-close'))

    def intent(self):
        raw = json.dumps(dict(self.expected, relay_process=self.relay, created_utc='2026-09-30T00:00:00Z')).encode()
        relative = self.path.relative_to(self.root).as_posix()
        save(self.root, relative + '/intent.json', raw)
        save(self.root, relative + '/service-started.json', json.dumps(dict(self.expected,
            native_process=self.process, invocation_id='7' * 32)).encode())
        save(self.root, relative + '/service.log', b'private local fixture log\n')
        return raw

    def check(self, harness, files, identities):
        self.assertEqual(harness, 'terminus-2'); service.evidence.check(self.root, files, identities)
        return self.root

    @contextmanager
    def open(self, root, harness, incoming):
        self.assertEqual((root, harness), (self.root, 'terminus-2'))
        self.owner = asyncio.current_task(); self.live = True; self.events.append('live-composite-session')
        try:
            yield self
            self.events.append('normal-exit-recheck')
            if self.exit_error is not None: raise self.exit_error
        finally:
            self.live = False; self.events.append('both-witnesses-invalid')

    def require(self, active):
        self.assertIs(active, self); self.assertTrue(self.live); self.assertIs(asyncio.current_task(), self.owner)
        return deepcopy(self.recovered)

    def recheck(self, active):
        self.require(active); self.events.append('actual-reread'); return deepcopy(self.record)

    def completed(self, active, operation):
        self.require(active); self.assertEqual(operation, 'qualify-repeat'); self.events.append('actual-qualifier-exit')

    def qualified(self, active):
        self.require(active); self.events.append('actual-qualification-files')

    def sendall(self, raw):
        self.assertTrue(self.live); self.assertTrue((self.path / 'accepted.json').is_file())
        self.assertFalse((self.path / 'result.json').exists()); self.events.append('durable-acceptance-ack')
        self.accepted = service.boot.loads(raw)
        if self.ack_error: raise BrokenPipeError('Synthetic lost acknowledgement')

    async def produce(self, active):
        self.require(active); self.events.append('actual-operation')
        name = service.policy.QUALIFIER_RESULT_FILE if self.operation == 'qualify-repeat' else runner.RESULT
        save(self.root, service.completion.RT + name, b'{"synthetic_local_producer_only":true}')
        return {'not_an_admission_or_completion_receipt': True}

    async def execute(self):
        return await service.execute('terminus-2', self.nonce, self.files, self.commit, self.identities,
            object(), self.connection, self.path, self.intent_raw, self.operation)

    async def test_same_main_task_actual_producer_and_post_exit_success(self):
        value = await self.execute()
        self.qualifier.assert_awaited_once_with(self); self.runner.assert_not_called()
        self.assertLess(self.events.index('durable-acceptance-ack'), self.events.index('actual-operation'))
        self.assertLess(self.events.index('actual-operation'), self.events.index('normal-exit-recheck'))
        self.assertFalse(self.live); self.assertTrue((self.path / 'result.json').is_file())
        self.assertEqual(value, service.boot.loads((self.path / 'result.json').read_bytes()))
        self.assertEqual(self.accepted['recovery_archive_sha256'], self.recovered['archive_sha256'])
        self.assertFalse(value['paid_launch_ready'])

    async def test_lost_acknowledgement_does_not_cancel_committed_native_operation(self):
        self.ack_error = True
        await self.execute()
        self.qualifier.assert_awaited_once(); self.assertTrue((self.path / 'result.json').is_file())

    async def test_late_context_failure_cannot_leave_success_after_producer(self):
        self.exit_error = ValueError('Final witness recheck refused')
        with self.assertRaises(ValueError): await self.execute()
        self.assertTrue((self.root / service.completion.RT / service.policy.QUALIFIER_RESULT_FILE).is_file())
        self.assertFalse((self.path / 'result.json').exists()); self.assertFalse(self.live)

    async def test_cancelled_operation_keeps_acceptance_without_success(self):
        self.qualifier.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError): await self.execute()
        self.assertTrue((self.path / 'accepted.json').is_file())
        self.assertFalse((self.path / 'result.json').exists()); self.assertFalse(self.live)

    async def test_wrong_actual_handoff_revision_refuses_before_ack_or_operation(self):
        self.recovered['operator_commit'] = 'f' * 40
        with self.assertRaises(ValueError): await self.execute()
        self.qualifier.assert_not_called(); self.assertFalse((self.path / 'accepted.json').exists())

    async def test_operation_return_flags_without_durable_producer_refuse(self):
        self.qualifier.side_effect = None; self.qualifier.return_value = {'passed': True}
        with self.assertRaises((OSError, ValueError)): await self.execute()
        self.assertFalse((self.path / 'result.json').exists())

    async def test_existing_or_partial_operation_cannot_be_replayed(self):
        await self.execute()
        with self.assertRaises((OSError, ValueError)): await self.execute()
        self.qualifier.assert_awaited_once()

    async def test_source_change_after_actual_producer_refuses(self):
        actual = self.produce
        async def changed(active):
            await actual(active); (self.root / 'stage2/synthetic.py').write_bytes(b'changed')
        self.qualifier.side_effect = changed
        with self.assertRaises(ValueError): await self.execute()
        self.assertFalse((self.path / 'result.json').exists())

    async def test_paid_branch_checks_real_qualifier_exit_and_qualification_first(self):
        self.operation = 'run-repeat'; self.path = self.root / service.completion.operation_state(self.operation)
        self.expected = service.completion.base('terminus-2', self.nonce, self.files, self.commit, self.operation)
        self.intent_raw = self.intent()
        await self.execute()
        self.assertLess(self.events.index('actual-qualifier-exit'), self.events.index('durable-acceptance-ack'))
        self.assertLess(self.events.index('actual-qualification-files'), self.events.index('actual-operation'))
        self.runner.assert_awaited_once_with(self); self.qualifier.assert_not_called()

    async def test_failed_qualifier_service_prevents_paid_branch_even_with_saved_proof(self):
        self.operation = 'run-repeat'; self.path = self.root / service.completion.operation_state(self.operation)
        self.expected = service.completion.base('terminus-2', self.nonce, self.files, self.commit, self.operation)
        self.intent_raw = self.intent(); self.completion.side_effect = ValueError('Actual qualifier service failed')
        with self.assertRaises(ValueError): await self.execute()
        self.runner.assert_not_called(); self.assertFalse((self.path / 'accepted.json').exists())

    def invoke_failed_service(self, error):
        # Remove only the synthetic pre-existing fixture start record: serve
        # must create its own exclusive record, never reuse a real attempt.
        (self.path / 'service-started.json').unlink()
        with patch.object(service.completion, 'started', return_value='7' * 32), \
                patch.object(service, '_service_process', side_effect=error):
            with self.assertRaises(type(error)) as raised:
                service.serve('terminus-2', self.nonce, self.files, self.commit,
                    self.identities, self.relay, self.operation)
        self.assertIs(raised.exception, error)
        self.qualifier.assert_not_called(); self.runner.assert_not_called()
        self.assertFalse((self.path / 'accepted.json').exists())
        self.assertFalse((self.path / 'result.json').exists())
        self.assertTrue((self.path / 'failure.json').is_file())
        diagnostic = self.path / 'failure-diagnostic.json'
        self.assertEqual(diagnostic.stat().st_mode & 0o777, 0o600)
        return service.boot.loads(diagnostic.read_bytes())

    async def test_real_failure_file_keeps_child_code_and_preserves_failed_attempt(self):
        before = {name: service.evidence.read(self.root,
            (self.path / name).relative_to(self.root).as_posix())
            for name in ('intent.json', 'service.log')}
        error = service.subprocess.CalledProcessError(7, ['PRIVATE_COMMAND'], stderr=b'PRIVATE_STDERR')
        record = self.invoke_failed_service(error)
        self.assertEqual(record['stage'], 'service_identity')
        self.assertEqual(record['error_class'], 'CalledProcessError')
        self.assertEqual(record['exceptions'][0]['returncode'], 7)
        self.assertNotIn('PRIVATE_', json.dumps(record))
        for name, saved in before.items():
            self.assertEqual(service.evidence.read(self.root,
                (self.path / name).relative_to(self.root).as_posix()), saved)
        with self.assertRaises(ValueError):
            service.serve('terminus-2', self.nonce, self.files, self.commit,
                self.identities, self.relay, self.operation)

    async def test_diagnostic_failure_does_not_replace_original_exception(self):
        with patch.object(service, 'failure_diagnostic', side_effect=TypeError('PRIVATE_DIAGNOSTIC')):
            record = self.invoke_failed_service(FileNotFoundError('PRIVATE_ORIGINAL'))
        self.assertTrue(record['diagnostic_unavailable'])
        self.assertFalse(record['automatic_resume']); self.assertFalse(record['paid_launch_ready'])
        self.assertNotIn('PRIVATE_', json.dumps(record))


class ServiceContractTests(unittest.TestCase):
    def test_real_program_generator_accepts_actual_source_and_private_input_shape(self):
        stage = Path(service.__file__).absolute().parent
        files = {'stage2/' + name: hashlib.sha256((stage / name).read_bytes()).hexdigest()
            for name in service.policy.REQUIRED_SOURCE_FILES}
        files.update({service.boot.BASELINE_INPUT: service.boot.BASELINE_SHA,
            service.boot.FINAL_INPUT: service.boot.FINAL_SHA})
        for operation in ('qualify-repeat', 'run-repeat'):
            for role in ('relay', 'service', 'status'):
                with self.subTest(operation=operation, role=role):
                    program = service.native_program('terminus-2', 'a' * 32, files, 'b' * 40,
                        role=role, operation=operation,
                        relay_process={'pid': 123, 'start_ticks': 456} if role == 'service' else None)
                    ast.parse(program)
                    self.assertIn(service.boot.BASELINE_INPUT, program)
                    self.assertIn(service.boot.FINAL_INPUT, program)

    def test_fixed_detached_command_has_no_parent_wait_restart_or_runtime_ceiling(self):
        root = service.boot.root_for('terminus-2'); path = root / service.completion.operation_state('qualify-repeat')
        with patch.object(service, 'folder', return_value=path), patch.object(service, 'native_program', return_value='BOUND'):
            argv = service.service_command('terminus-2', 'a' * 32, {}, 'b' * 40, {'pid': 1, 'start_ticks': 2}, 'qualify-repeat')
        self.assertIn('--property=Type=exec', argv); self.assertIn('--property=RemainAfterExit=yes', argv)
        self.assertIn('--property=Restart=no', argv); self.assertIn('--property=StandardInput=null', argv)
        self.assertEqual(argv[-5:], [str(root / '.venv/bin/python'), '-I', '-B', '-c', 'BOUND'])
        self.assertFalse(any(x in argv for x in ('--pipe', '--scope', '--wait')))
        self.assertFalse(any('RuntimeMax' in x for x in argv))

    def test_acknowledgements_are_bounded_strict_and_never_qualification_flags(self):
        value = {'kind': 'baseline_handoff_committed_operation_accepted_not_completed', 'paid_launch_ready': False}
        self.assertEqual(service._read_reply(io.BytesIO(service._line(value))), value)
        for raw in (b'{}', b'{}\nextra', b'{"x":1,"x":2}\n', b'x' * (service.REPLY_LIMIT + 1)):
            with self.subTest(raw=raw[:20]), self.assertRaises((ValueError, UnicodeError)):
                service._read_reply(io.BytesIO(raw))
        with self.assertRaises(ValueError): service._line({'oversized': 'x' * service.REPLY_LIMIT})

    def test_peer_checks_actual_root_credentials_and_fixed_process_identity(self):
        socket = NS(getsockopt=lambda *args: service.struct.pack('3i', 123, 0, 0))
        with patch.object(service.socket, 'SO_PEERCRED', 17, create=True), \
                patch.object(service.completion, 'process_identity', return_value={'pid': 123, 'start_ticks': 456}) as read:
            self.assertEqual(service._peer('terminus-2', socket), {'pid': 123, 'start_ticks': 456})
            read.assert_called_once_with(service.boot.root_for('terminus-2'), 123)
            for pid, uid, gid in ((0, 0, 0), (123, 1, 0), (123, 0, 1)):
                socket.getsockopt = lambda *args: service.struct.pack('3i', pid, uid, gid)
                with self.assertRaises(ValueError): service._peer('terminus-2', socket)

    def test_service_identity_requires_stable_manager_invocation_and_real_process(self):
        state = dict(ActiveState='active', SubState='running', MainPID='123', InvocationID='a' * 32)
        with patch.object(service.completion, 'manager', return_value=state) as manager, \
                patch.object(service.completion, 'process_identity', return_value={'pid': 123, 'start_ticks': 456}):
            self.assertEqual(service._service_process('terminus-2', 'fixed.service')['pid'], 123)
            self.assertEqual(manager.call_count, 2)
            manager.side_effect = [state, dict(state, InvocationID='b' * 32)]
            with self.assertRaises(ValueError): service._service_process('terminus-2', 'fixed.service')


class FailureDiagnosticTests(unittest.TestCase):
    """Metadata contracts only; no host, provider or failed-attempt replay."""
    root = Path('/synthetic-baseline-diagnostic')
    files = {'stage2/site.py': 'a' * 64}

    def record(self, error, stage='live_execution_session'):
        return service.failure_diagnostic(self.root, self.files, stage, error)

    def test_exact_known_exception_types_are_not_collapsed(self):
        transport_error = service.handoff.original.launch.transport.AuditTransportError
        errors = [ValueError(), TypeError(), KeyError(), IndexError(), AssertionError(),
            FileNotFoundError(), PermissionError(), BrokenPipeError(), OSError(), RuntimeError(),
            TimeoutError(), service.subprocess.CalledProcessError(7, ['PRIVATE_COMMAND']),
            service.subprocess.TimeoutExpired(['PRIVATE_COMMAND'], 300),
            json.JSONDecodeError('PRIVATE_MESSAGE', 'PRIVATE_DOCUMENT', 0),
            transport_error({}), asyncio.CancelledError(), SystemExit(), KeyboardInterrupt()]
        for error in errors:
            with self.subTest(kind=type(error).__name__):
                record = self.record(error)
                self.assertEqual(record['error_class'], type(error).__name__)
                self.assertEqual(record['exceptions'][0]['error_class'], type(error).__name__)
                self.assertFalse(record['automatic_resume']); self.assertFalse(record['paid_launch_ready'])
                self.assertNotIn('PRIVATE_', json.dumps(record))

    def test_unknown_or_spoofed_types_do_not_expose_names_or_messages(self):
        spoof = type('ValueError', (ValueError,), {'__module__': 'builtins',
            '__str__': lambda self: self.fail_if_formatted()})
        for error in (spoof('PRIVATE_VALUE'), type('PRIVATE_EXCEPTION_NAME', (Exception,), {})()):
            record = self.record(error)
            self.assertEqual(record['error_class'], 'OtherException')
            self.assertNotIn('PRIVATE_', json.dumps(record))

    def test_only_bound_source_sites_are_hashed_without_paths_or_locals(self):
        filename = str(self.root / 'stage2/site.py')
        scope = {'__name__': 'synthetic', 'PRIVATE_LOCAL': 'PRIVATE_SECRET'}
        try:
            exec(compile("raise TypeError('PRIVATE_MESSAGE')\n", filename, 'exec'), scope)
        except TypeError as error:
            record = self.record(error)
        sites = record['exceptions'][0]['bound_sites_sha256']
        expected = hashlib.sha256((('a' * 64) + ':1').encode()).hexdigest()
        self.assertEqual(sites, [expected])
        raw = json.dumps(record)
        for forbidden in ('PRIVATE_', filename, 'site.py', str(self.root)):
            self.assertNotIn(forbidden, raw)

    def test_child_exit_code_is_kept_without_command_or_output(self):
        error = service.subprocess.CalledProcessError(-9, ['PRIVATE_ARG'],
            output=b'PRIVATE_STDOUT', stderr=b'PRIVATE_STDERR')
        item = self.record(error)['exceptions'][0]
        self.assertEqual(item['returncode'], -9)
        self.assertNotIn('PRIVATE_', json.dumps(item))
        error.returncode = True
        self.assertIsNone(self.record(error)['exceptions'][0]['returncode'])
        error.returncode = 'PRIVATE_CODE'
        self.assertIsNone(self.record(error)['exceptions'][0]['returncode'])

    def test_transport_fields_are_explicitly_filtered_not_copied(self):
        error_type = service.handoff.original.launch.transport.AuditTransportError
        error = error_type(dict(status='child_exit', error_type='ValueError', returncode=1,
            stdout_bytes=25, diagnostics={'PRIVATE': 'SECRET'}, command='PRIVATE_COMMAND'))
        item = self.record(error)['exceptions'][0]
        self.assertEqual(item['transport'], dict(status='child_exit', error_class='ValueError',
            returncode=1, stdout_bytes=25))
        self.assertNotIn('PRIVATE', json.dumps(item))
        error.metadata = dict(status='PRIVATE_STATUS', error_type='PRIVATE_ERROR',
            returncode='PRIVATE_CODE', stdout_bytes=-1)
        self.assertEqual(self.record(error)['exceptions'][0]['transport'],
            dict(status='unavailable', error_class='OtherException', returncode=None, stdout_bytes=None))

    def test_exception_chain_is_bounded_cycle_safe_and_respects_suppression(self):
        errors = [TypeError() for _ in range(20)]
        for first, second in zip(errors, errors[1:]): first.__cause__ = second
        errors[-1].__cause__ = errors[0]
        self.assertEqual(len(self.record(errors[0])['exceptions']), 8)
        first = ValueError(); second = TypeError(); first.__context__ = second
        self.assertEqual(len(self.record(first)['exceptions']), 2)
        first.__suppress_context__ = True
        self.assertEqual(len(self.record(first)['exceptions']), 1)
        first.__cause__ = second; second.__cause__ = first
        self.assertEqual(len(self.record(first)['exceptions']), 2)

    def test_untrusted_stage_and_invalid_bindings_cannot_leak(self):
        for stage in ('PRIVATE_STAGE', [], {'PRIVATE': 'STAGE'}, None):
            self.assertEqual(self.record(ValueError(), stage)['stage'], 'unavailable')
        record = service.failure_diagnostic(self.root, {'stage2/site.py': 'PRIVATE_HASH'},
            'live_execution_session', ValueError('PRIVATE_MESSAGE'))
        self.assertNotIn('PRIVATE', json.dumps(record))

    def test_deep_tracebacks_share_one_bounded_site_budget(self):
        scope = {}
        source = 'def deep(n):\n if n: return deep(n-1)\n raise ValueError("PRIVATE")\ndeep(200)\n'
        try:
            exec(compile(source, str(self.root / 'stage2/site.py'), 'exec'), scope)
        except ValueError as error:
            following = TypeError(); following.__cause__ = error
            record = self.record(following)
        self.assertEqual(sum(len(item['bound_sites_sha256']) for item in record['exceptions']), 16)
        self.assertLess(len(json.dumps(record)), 4096)


if __name__ == '__main__': unittest.main()
