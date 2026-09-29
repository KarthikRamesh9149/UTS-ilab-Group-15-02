"""Local fake-environment observations, not native recovery qualification."""
import asyncio
from copy import copy, deepcopy
import hashlib
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from harbor.environments.base import ExecResult
import no_cutoff_recovery_setup as observed
import task_preparation as original
from trial_execution import execute_phases


SECRET = 'synthetic-private-text-never-retain'


class Environment:
    def __init__(self, *, code=0, stdout='', stderr='', error=None,
                 context_error=None, context_stage=None, suppress=False, during=None):
        self.result = NS(return_code=code, stdout=stdout, stderr=stderr)
        self.error, self.context_error, self.context_stage = error, context_error, context_stage
        self.suppress, self.during = suppress, during
        self.calls = []
        self.entered = asyncio.Event()
        self.wait = None

    def with_default_user(self, user):
        self.calls.append(('user', user))
        if self.context_stage == 'create':
            raise self.context_error
        environment = self
        class Context:
            def __enter__(self):
                environment.calls.append(('enter', user))
                if environment.context_stage == 'enter':
                    raise environment.context_error
            def __exit__(self, kind, error, traceback):
                environment.calls.append(('exit', user))
                if environment.context_stage == 'exit':
                    raise environment.context_error
                return environment.suppress
        return Context()

    async def exec(self, command, *, timeout_sec):
        self.calls.append(('command', command, timeout_sec))
        self.entered.set()
        if self.wait is not None:
            await self.wait.wait()
        if self.during is not None:
            self.during()
        if self.error is not None:
            raise self.error
        return self.result

    async def empty_dirs(self, paths, chmod):
        self.calls.append(('clear-verifier', paths, chmod))

    async def stop(self, delete):
        self.calls.append(('destroy', delete))


class ObservationTests(unittest.IsolatedAsyncioTestCase):
    async def run_observed(self, environment):
        observation = observed.PreparationObservation()
        result = await observation.prepare(environment)
        return result, observation.metadata()

    async def failed(self, environment, exception=Exception):
        observation = observed.PreparationObservation()
        with self.assertRaises(exception) as caught:
            await observation.prepare(environment)
        return caught.exception, observation.metadata()

    def test_real_original_file_hash_is_pinned(self):
        self.assertEqual(hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(), observed.PREPARATION_SHA256)
        self.assertEqual(observed._bindings()['task_preparation.py'], observed.PREPARATION_SHA256)
        self.assertEqual(hashlib.sha256(original.COMMAND.encode()).hexdigest(), observed.COMMAND_SHA256)

    async def test_success_has_identical_original_result_command_and_context(self):
        plain, wrapped = Environment(), Environment()
        expected = await original.refresh_package_metadata(plain)
        result, data = await self.run_observed(wrapped)
        self.assertEqual(result, expected)
        self.assertEqual(wrapped.calls, plain.calls)
        self.assertEqual([v for v in wrapped.calls if v[0] == 'command'], [('command', original.COMMAND, 180)])
        self.assertEqual(data['terminal'], 'returned')
        self.assertEqual(data['preparation_status'], 'refreshed')
        self.assertEqual(data['infrastructure_category'], 'preparation_returned')
        self.assertTrue(data['observation_complete'])
        self.assertFalse(data['paid_launch_ready'])
        self.assertFalse(data['native_qualification'])
        self.assertFalse(data['historical_cause_established'])

    async def test_not_applicable_preserves_the_original_return(self):
        text = 'UTS_PACKAGE_METADATA_NOT_APPLICABLE\n'
        result, data = await self.run_observed(Environment(stdout=text))
        self.assertEqual(result, await original.refresh_package_metadata(Environment(stdout=text)))
        self.assertEqual(data['preparation_status'], 'not_applicable')

    async def test_observed_nonzero_is_not_a_mirror_dns_or_timeout_diagnosis(self):
        environment = Environment(code=100, stdout=SECRET, stderr='Temporary failure resolving ' + SECRET)
        error, data = await self.failed(environment, RuntimeError)
        self.assertEqual(str(error), 'Package metadata refresh failed before agent execution')
        self.assertEqual(data['terminal'], 'raised')
        self.assertEqual(data['failure_stage'], 'preparation_result')
        self.assertEqual(data['infrastructure_category'], 'preparation_command_nonzero')
        self.assertEqual(data['command']['return_code'], 100)
        self.assertEqual(data['command']['terminal'], 'returned')
        self.assertTrue(data['observation_complete'])
        self.assertNotIn(SECRET, json.dumps(data))
        self.assertNotIn('Temporary failure', json.dumps(data))
        self.assertEqual(sum(v[0] == 'command' for v in environment.calls), 1)

    async def test_exit_124_does_not_invent_a_timeout(self):
        _, data = await self.failed(Environment(code=124), RuntimeError)
        self.assertEqual(data['command']['return_code'], 124)
        self.assertEqual(data['infrastructure_category'], 'preparation_command_nonzero')

    async def test_negative_return_code_remains_an_actual_integer_not_a_signal_claim(self):
        _, data = await self.failed(Environment(code=-9), RuntimeError)
        self.assertEqual(data['command']['return_code'], -9)
        self.assertEqual(data['infrastructure_category'], 'preparation_command_nonzero')

    async def test_exec_exception_is_same_object_without_fabricated_code_or_output(self):
        exception = RuntimeError(SECRET)
        error, data = await self.failed(Environment(error=exception))
        self.assertIs(error, exception)
        self.assertEqual(data['failure_stage'], 'command_execution')
        self.assertEqual(data['infrastructure_category'], 'command_execution_exception')
        self.assertIsNone(data['command']['return_code'])
        self.assertEqual(data['command']['stdout'], dict(observation='missing', utf8_bytes=None, sha256=None))
        self.assertNotIn(SECRET, json.dumps(data))
        self.assertTrue(data['observation_complete'])

    async def test_timeout_exception_is_observed_not_inferred_from_elapsed_time(self):
        exception = TimeoutError(SECRET)
        error, data = await self.failed(Environment(error=exception), TimeoutError)
        self.assertIs(error, exception)
        self.assertEqual(data['infrastructure_category'], 'command_timeout_exception')
        self.assertIsNone(data['command']['return_code'])
        self.assertLess(data['command']['elapsed_seconds'], 180)

    async def test_arbitrary_exception_class_name_and_str_are_never_inspected(self):
        def forbidden(self):
            raise AssertionError('Exception rendering forbidden')
        exception_type = type(SECRET, (RuntimeError,), {'__str__': forbidden, '__repr__': forbidden})
        exception = exception_type(SECRET)
        error, data = await self.failed(Environment(error=exception), RuntimeError)
        self.assertIs(error, exception)
        self.assertEqual(data['error_class'], 'OtherException')
        self.assertEqual(data['command']['error_class'], 'OtherException')
        self.assertNotIn(SECRET, json.dumps(data))

    async def test_keyboard_interrupt_and_system_exit_are_not_swallowed(self):
        for exception in (KeyboardInterrupt(SECRET), SystemExit(SECRET)):
            with self.subTest(exception_type=type(exception).__name__):
                error, data = await self.failed(Environment(error=exception), type(exception))
                self.assertIs(error, exception)
                self.assertEqual(data['error_class'], type(exception).__name__)

    async def test_context_creation_entry_and_exit_failures_remain_distinct(self):
        for stage in ('create', 'enter', 'exit'):
            exception = RuntimeError(SECRET)
            environment = Environment(context_error=exception, context_stage=stage)
            error, data = await self.failed(environment)
            self.assertIs(error, exception)
            self.assertEqual(data['failure_stage'], 'root_context_' + stage)
            self.assertEqual(data['infrastructure_category'], 'default_user_context_exception')
            self.assertEqual(data['command']['terminal'], 'returned' if stage == 'exit' else 'not_started')
            self.assertTrue(data['observation_complete'])

    async def test_context_exit_exception_keeps_command_failure_metadata_without_misattribution(self):
        exception = ValueError(SECRET)
        error, data = await self.failed(Environment(error=RuntimeError(SECRET),
            context_error=exception, context_stage='exit'))
        self.assertIs(error, exception)
        self.assertEqual(data['failure_stage'], 'root_context_exit')
        self.assertEqual(data['command']['error_class'], 'RuntimeError')
        self.assertEqual(data['infrastructure_category'], 'default_user_context_exception')

    async def test_original_context_suppression_semantics_are_preserved(self):
        environment = Environment(error=RuntimeError(SECRET), suppress=True)
        error, data = await self.failed(environment, UnboundLocalError)
        with self.assertRaises(type(error)):
            await original.refresh_package_metadata(Environment(error=RuntimeError(SECRET), suppress=True))
        self.assertEqual(data['failure_stage'], 'preparation_result')
        self.assertEqual(data['infrastructure_category'], 'unknown')

    async def test_actual_cancellation_propagates_and_does_not_retry(self):
        environment = Environment(); environment.wait = asyncio.Event()
        observation = observed.PreparationObservation()
        running = asyncio.create_task(observation.prepare(environment))
        await environment.entered.wait()
        with self.assertRaises(ValueError):
            observation.metadata()
        running.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await running
        data = observation.metadata()
        self.assertEqual(data['terminal'], 'cancelled')
        self.assertEqual(data['command']['terminal'], 'cancelled')
        self.assertEqual(data['infrastructure_category'], 'preparation_cancelled')
        self.assertTrue(data['observation_complete'])
        self.assertEqual(sum(v[0] == 'command' for v in environment.calls), 1)
        with self.assertRaises(ValueError):
            await observation.prepare(environment)

    async def test_each_callback_has_one_use_after_success_failure_or_cancellation(self):
        for environment in (Environment(), Environment(code=100), Environment(error=asyncio.CancelledError())):
            observation = observed.PreparationObservation()
            try:
                await observation.prepare(environment)
            except (RuntimeError, asyncio.CancelledError):
                pass
            with self.assertRaises(ValueError):
                await observation.prepare(environment)
            self.assertEqual(sum(v[0] == 'command' for v in environment.calls), 1)

    async def test_concurrent_reuse_cannot_call_the_environment_twice(self):
        environment = Environment(); environment.wait = asyncio.Event()
        observation = observed.PreparationObservation()
        running = asyncio.create_task(observation.prepare(environment))
        await environment.entered.wait()
        with self.assertRaises(ValueError):
            await observation.prepare(environment)
        environment.wait.set(); await running
        self.assertEqual(sum(v[0] == 'command' for v in environment.calls), 1)

    async def test_completed_handle_retains_no_environment_output_or_exception(self):
        environment = Environment(error=RuntimeError(SECRET))
        observation = observed.PreparationObservation()
        with self.assertRaises(RuntimeError):
            await observation.prepare(environment)
        self.assertIsNone(observation._task)
        self.assertIsNone(observation._escaping)
        self.assertNotIn(environment, vars(observation).values())
        self.assertNotIn(SECRET, repr(vars(observation)))

    def test_handle_cannot_be_copied_serialised_or_moved_to_a_thread(self):
        observation = observed.PreparationObservation()
        for operation in (copy, deepcopy, pickle.dumps):
            with self.assertRaises(TypeError):
                operation(observation)
        errors = []
        def other_thread():
            for operation in (observed.PreparationObservation, observation.metadata):
                try: operation()
                except ValueError: errors.append(True)
        thread = threading.Thread(target=other_thread); thread.start(); thread.join()
        self.assertEqual(errors, [True, True])
        with patch.object(observed.os, 'getpid', return_value=observation._pid + 1), self.assertRaises(ValueError):
            observation.metadata()

    async def test_metadata_returns_a_defensive_copy(self):
        observation = observed.PreparationObservation()
        await observation.prepare(Environment())
        data = observation.metadata(); data['command']['return_code'] = 123
        self.assertEqual(observation.metadata()['command']['return_code'], 0)

    async def test_real_harbor_exec_result_fields_are_supported(self):
        environment = Environment(); environment.result = ExecResult(return_code=0, stdout='abc', stderr=None)
        _, data = await self.run_observed(environment)
        self.assertTrue(data['observation_complete'])
        self.assertEqual(data['command']['stderr'], dict(observation='null', utf8_bytes=None, sha256=None))

    async def test_unicode_counts_are_utf8_not_characters_or_raw_wire_bytes(self):
        output = 'é🦘\x00' * 20000
        _, data = await self.run_observed(Environment(stdout=output, stderr=SECRET))
        self.assertEqual(data['command']['stdout'], dict(observation='text_utf8',
            utf8_bytes=len(output.encode()), sha256=hashlib.sha256(output.encode()).hexdigest()))
        self.assertNotIn(SECRET, json.dumps(data))
        self.assertNotIn(output, json.dumps(data))

    async def test_empty_and_null_outputs_are_not_confused(self):
        _, data = await self.run_observed(Environment(stdout='', stderr=None))
        self.assertEqual(data['command']['stdout'], dict(observation='text_utf8', utf8_bytes=0,
            sha256=hashlib.sha256(b'').hexdigest()))
        self.assertEqual(data['command']['stderr'], dict(observation='null', utf8_bytes=None, sha256=None))

    async def test_missing_stderr_is_explicit_incomplete_not_empty(self):
        environment = Environment(); del environment.result.stderr
        _, data = await self.run_observed(environment)
        self.assertFalse(data['observation_complete'])
        self.assertEqual(data['command']['stderr']['observation'], 'missing')
        self.assertIsNone(data['command']['stderr']['utf8_bytes'])

    async def test_unsupported_stderr_and_nonencodable_text_stay_unknown(self):
        for output, category in ((b'bytes', 'unsupported_type'), ('\ud800', 'not_utf8_encodable')):
            _, data = await self.run_observed(Environment(stderr=output))
            self.assertEqual(data['command']['stderr']['observation'], category)
            self.assertIsNone(data['command']['stderr']['sha256'])
            self.assertFalse(data['observation_complete'])

    async def test_diagnostic_properties_are_not_executed(self):
        class Result:
            return_code = 0
            stdout = ''
            @property
            def stderr(self):
                raise AssertionError('Do not access arbitrary diagnostic properties')
        environment = Environment(); environment.result = Result()
        _, data = await self.run_observed(environment)
        self.assertEqual(data['command']['stderr']['observation'], 'unsupported_type')
        self.assertFalse(data['observation_complete'])

    async def test_boolean_return_code_is_not_reported_as_integer_zero(self):
        # Original Python comparison accepts False == 0; do not change that
        # outcome, but refuse to claim that a real integer code was observed.
        _, data = await self.run_observed(Environment(code=False))
        self.assertIsNone(data['command']['return_code'])
        self.assertFalse(data['observation_complete'])

    async def test_observability_failure_preserves_success_and_original_failure(self):
        for environment in (Environment(), Environment(code=100)):
            observation = observed.PreparationObservation()
            with patch.object(observed, '_fields', side_effect=ValueError(SECRET)):
                if environment.result.return_code:
                    with self.assertRaises(RuntimeError): await observation.prepare(environment)
                else:
                    self.assertEqual((await observation.prepare(environment))['status'], 'refreshed')
            data = observation.metadata()
            self.assertEqual(data['diagnostic_issues'], ['metadata_capture_failed'])
            self.assertFalse(data['observation_complete'])
            self.assertNotIn(SECRET, json.dumps(data))

    async def test_missing_elapsed_is_not_fabricated_zero_or_a_successful_observation(self):
        observation = observed.PreparationObservation()
        with patch.object(observation, '_elapsed', side_effect=ValueError(SECRET)):
            await observation.prepare(Environment())
        data = observation.metadata()
        self.assertIsNone(data['elapsed_seconds'])
        self.assertIsNone(data['command']['elapsed_seconds'])
        self.assertFalse(data['observation_complete'])

    async def test_preexecution_source_drift_refuses_without_environment_calls(self):
        observation = observed.PreparationObservation(); environment = Environment()
        with patch.object(original, 'COMMAND', 'different'), self.assertRaises(ValueError):
            await observation.prepare(environment)
        self.assertEqual(environment.calls, [])
        data = observation.metadata()
        self.assertEqual(data['terminal'], 'guard_refused')
        self.assertFalse(data['observation_complete'])
        self.assertIsNone(data['elapsed_seconds'])
        with self.assertRaises(ValueError): await observation.prepare(environment)

    async def test_postexecution_source_drift_is_latched_without_replacing_original_outcome(self):
        command = original.COMMAND
        environment = Environment(during=lambda: setattr(original, 'COMMAND', 'different'))
        observation = observed.PreparationObservation()
        try:
            value = await observation.prepare(environment)
            self.assertEqual(value['status'], 'refreshed')
            with self.assertRaises(ValueError): observation.metadata()
        finally:
            original.COMMAND = command
        data = observation.metadata()
        self.assertFalse(data['source_verified_after'])
        self.assertEqual(data['diagnostic_issues'], ['source_binding_failed'])
        self.assertFalse(data['observation_complete'])

    def test_changed_source_bytes_function_code_or_origin_are_refused(self):
        real_source = observed._source
        def changed(path):
            raw = real_source(path)
            return raw + b'\n' if path.name == 'task_preparation.py' else raw
        with patch.object(observed, '_source', changed), self.assertRaises(ValueError):
            observed.PreparationObservation()
        async def fake(environment): return {'status': 'refreshed'}
        with patch.object(original, 'refresh_package_metadata', fake), self.assertRaises(ValueError):
            observed.PreparationObservation()
        with patch.object(original, '__file__', '/other/task_preparation.py'), self.assertRaises(ValueError):
            observed.PreparationObservation()
        with patch.object(observed, '__file__', '/other/no_cutoff_recovery_setup.py'), self.assertRaises(ValueError):
            observed.PreparationObservation()

    def test_component_source_inventory_includes_real_test_and_protocol_bytes(self):
        bindings = observed._bindings()
        self.assertEqual(set(bindings), {'task_preparation.py', *observed.SOURCE_FILES})
        for name in observed.SOURCE_FILES:
            self.assertEqual(bindings[name], hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest())

    def test_source_reader_refuses_links_and_nonregular_files_without_blocking(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); source = root / 'source.py'; source.write_text('fixture')
            self.assertEqual(observed._source(source), b'fixture')
            linked = root / 'linked.py'; linked.symlink_to(source)
            with self.assertRaises(ValueError): observed._source(linked)
            hard = root / 'hard.py'; os.link(source, hard)
            with self.assertRaises(ValueError): observed._source(source)
            fifo = root / 'fifo'; os.mkfifo(fifo)
            with self.assertRaises(ValueError): observed._source(fifo)

    def test_isolated_import_and_fake_execution_have_no_host_stack_write_process_or_network_effect(self):
        program = '''
import asyncio,importlib.abc,json,os,sys
from types import SimpleNamespace
from contextlib import contextmanager
sys.path.insert(0,sys.argv[1])
sys.pycache_prefix=sys.argv[1]+'/.absent-recovery-observer-cache'
class NoHost(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'harbor','litellm','langgraph','langchain','scored_trial',
    'progress_dashboard','no_cutoff_final_report','no_cutoff_final_reporting',
    'openrouter_transport','retry_gateway'}:raise AssertionError('No host or provider import')
sys.meta_path.insert(0,NoHost())
def guard(event,args):
 if event.startswith('subprocess.') or event in {'os.system','os.fork','os.posix_spawn',
   'socket.connect','socket.connect_ex','socket.getaddrinfo','socket.bind','os.remove',
   'os.rename','os.mkdir','os.chmod','os.link','os.symlink'}:raise AssertionError('No external effect')
 if event=='open':
  mode,flags=args[1],args[2]
  if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
   raise AssertionError('No writes')
sys.addaudithook(guard)
import no_cutoff_recovery_setup as observed
class Environment:
 @contextmanager
 def with_default_user(self,user):
  assert user=='root'
  yield
 async def exec(self,command,*,timeout_sec):
  assert timeout_sec==180
  return SimpleNamespace(return_code=0,stdout='',stderr=None)
async def main():
 observation=observed.PreparationObservation()
 await observation.prepare(Environment())
 data=observation.metadata()
 assert data['observation_complete'] and not data['paid_launch_ready']
 print(json.dumps({'local_fake_execution':True,'source_bindings':len(data['sources'])}))
asyncio.run(main())
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(Path(__file__).parent)],
            capture_output=True, text=True, timeout=20, env={'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'local_fake_execution': True, 'source_bindings': 4})

    async def test_observer_source_change_after_capture_cannot_be_hidden_by_self_consistent_metadata(self):
        observation = observed.PreparationObservation()
        await observation.prepare(Environment())
        real_source = observed._source
        def changed(path):
            raw = real_source(path)
            return raw + b'\n' if path.name == 'no_cutoff_recovery_setup.py' else raw
        with patch.object(observed, '_source', changed), self.assertRaises(ValueError):
            observation.metadata()
        self.assertFalse(observation.metadata()['observation_complete'])
        self.assertIn('source_binding_failed', observation.metadata()['diagnostic_issues'])

    async def test_context_cannot_substitute_another_command_between_initial_checks_and_exec(self):
        class ChangedContext(Environment):
            def with_default_user(self, user):
                context = super().with_default_user(user)
                class Entry:
                    def __enter__(self):
                        result = context.__enter__()
                        original.COMMAND = 'do not execute this substituted command'
                        return result
                    def __exit__(self, *args): return context.__exit__(*args)
                return Entry()
        command = original.COMMAND
        environment = ChangedContext(); observation = observed.PreparationObservation()
        try:
            with self.assertRaises(ValueError): await observation.prepare(environment)
        finally:
            original.COMMAND = command
        self.assertFalse(any(v[0] == 'command' for v in environment.calls))
        data = observation.metadata()
        self.assertEqual(data['failure_stage'], 'command_binding')
        self.assertEqual(data['infrastructure_category'], 'source_guard_refused')
        self.assertFalse(data['observation_complete'])

    async def test_prospective_writer_can_require_complete_diagnostics_without_rewriting_an_outcome(self):
        # The component deliberately has no durable writer or production host
        # entry. An eventual failed admission/audit must retain, not replay, the
        # outcome that this unchanged shared lifecycle actually produced.
        environment = Environment()
        with patch.object(observed, '_fields', side_effect=ValueError(SECRET)):
            result, data = await self.lifecycle(environment)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
        self.assertTrue(result['model_revoked'])
        self.assertFalse(data['observation_complete'])
        self.assertNotIn(SECRET, json.dumps(data))

    async def test_metadata_validation_preserves_json_nulls_and_numbers(self):
        _, data = await self.run_observed(Environment(stderr=None))
        raw = json.dumps(data, sort_keys=True, allow_nan=False)
        self.assertEqual(observed.validate(json.loads(raw)), data)
        self.assertIs(type(data['command']['return_code']), int)
        self.assertIs(type(data['elapsed_seconds']), float)
        self.assertIsNone(data['error_class'])

    async def test_metadata_validator_refuses_authority_raw_text_extra_fields_and_bad_types(self):
        _, good = await self.run_observed(Environment())
        mutations = [lambda d: d.update(paid_launch_ready=True),
            lambda d: d.update(native_qualification=True), lambda d: d.update(historical_cause_established=True),
            lambda d: d.update(raw_error=SECRET), lambda d: d.update(schema_version=True),
            lambda d: d.update(command_timeout_seconds=60), lambda d: d.update(elapsed_seconds=float('nan')),
            lambda d: d.update(command_sha256='0' * 64),
            lambda d: d.update(elapsed_seconds=False), lambda d: d.update(error_class=SECRET),
            lambda d: d.update(diagnostic_issues=[SECRET]), lambda d: d.update(diagnostic_issues=[{}]),
            lambda d: d.update(terminal={}), lambda d: d.update(failure_stage=SECRET),
            lambda d: d['sources'].update({'task_preparation.py': '0' * 64}),
            lambda d: d['sources'].update(extra='0' * 64),
            lambda d: d['command'].update(return_code=False),
            lambda d: d['command'].update(return_code_observation='unavailable'),
            lambda d: d['command'].update(terminal='running'),
            lambda d: d['command'].update(return_code=100),
            lambda d: d['command'].update(raw_stdout=SECRET),
            lambda d: d['command']['stdout'].update(utf8_bytes=True),
            lambda d: d['command']['stdout'].update(sha256=SECRET),
            lambda d: d['command']['stdout'].update(text=SECRET),
            lambda d: d['command']['stdout'].update(observation='missing'),
            lambda d: d.update(infrastructure_category='dns'),
            lambda d: d.update(observation_complete=False),
            lambda d: d['command'].update(elapsed_seconds=999999)]
        for index, mutation in enumerate(mutations):
            data = deepcopy(good); mutation(data)
            with self.subTest(index=index), self.assertRaises(ValueError): observed.validate(data)

    async def test_command_exception_cannot_gain_output_exit_code_or_preparation_success(self):
        _, good = await self.failed(Environment(error=RuntimeError(SECRET)))
        for mutation in (lambda d: d['command'].update(return_code=0, return_code_observation='integer'),
                lambda d: d['command']['stdout'].update(observation='null'),
                lambda d: d.update(preparation_status='refreshed'),
                lambda d: d.update(error_class=None)):
            data = deepcopy(good); mutation(data)
            with self.assertRaises(ValueError): observed.validate(data)

    async def lifecycle(self, environment, *, observed_callback=True, cancel=False):
        observation = observed.PreparationObservation()
        calls = environment.calls
        class Agent:
            async def setup(self, environment): calls.append(('agent-setup',))
            async def run(self, instruction, environment, context): calls.append(('agent-run',))
            async def cleanup_after_verification(self): calls.append(('agent-cleanup',))
        class Verifier:
            def __init__(self, *args): calls.append(('verifier-created',))
            async def verify(self):
                calls.append(('verify',))
                return NS(model_dump=lambda **kwargs: {'rewards': {'reward': 0}})
        async def revoke(): calls.append(('revoke',))
        task = NS(instruction='harmless synthetic fixture', config=NS(
            agent=NS(timeout_sec=1800, user='agent'), verifier=NS(timeout_sec=120, user='verifier')))
        result = {}
        operation = execute_phases(agent=Agent(), environment=environment, task=task,
            paths=None, revoke_model=revoke, setup_timeout_seconds=900, verifier_factory=Verifier,
            prepare_environment=observation.prepare if observed_callback else original.refresh_package_metadata,
            retained_result=result)
        if cancel:
            running = asyncio.create_task(operation)
            await environment.entered.wait(); running.cancel()
            with self.assertRaises(asyncio.CancelledError): await running
        else:
            await operation
        return result, observation.metadata() if observed_callback else None

    async def test_shared_real_lifecycle_keeps_setup_agent_verifier_and_cleanup_order(self):
        plain, wrapped = Environment(), Environment()
        before, _ = await self.lifecycle(plain, observed_callback=False)
        after, data = await self.lifecycle(wrapped)
        self.assertEqual(plain.calls, wrapped.calls)
        for name in ('status', 'agent_error_type', 'verifier_error_type', 'verifier_result',
                'model_revoked', 'cleanup_errors', 'environment_preparation'):
            self.assertEqual(before[name], after[name])
        self.assertEqual(after['verifier_result']['rewards']['reward'], 0)
        self.assertEqual(set(after['phase_seconds']), {'setup', 'agent', 'verifier'})
        self.assertTrue(data['observation_complete'])

    async def test_shared_real_lifecycle_retains_setup_failure_missing_verifier_and_cleanup(self):
        for environment in (Environment(code=100), Environment(error=RuntimeError(SECRET))):
            result, data = await self.lifecycle(environment)
            self.assertEqual(result['status'], 'setup_failed')
            self.assertNotIn('environment_preparation', result)
            self.assertEqual(set(result['phase_seconds']), {'setup'})
            self.assertIsNone(result['verifier_result'])
            self.assertTrue(result['model_revoked'])
            self.assertEqual(result['cleanup_errors'], [])
            self.assertNotIn(('agent-setup',), environment.calls)
            self.assertNotIn(('agent-run',), environment.calls)
            self.assertNotIn(('verify',), environment.calls)
            self.assertEqual(environment.calls[-1], ('destroy', True))
            self.assertTrue(data['observation_complete'])

    async def test_shared_real_lifecycle_cancellation_still_revokes_and_cleans(self):
        environment = Environment(); environment.wait = asyncio.Event()
        result, data = await self.lifecycle(environment, cancel=True)
        self.assertTrue(result['model_revoked'])
        self.assertEqual(result['cleanup_errors'], [])
        self.assertEqual(environment.calls[-3:], [('revoke',), ('agent-cleanup',), ('destroy', True)])
        self.assertEqual(data['terminal'], 'cancelled')
        self.assertIsNone(data['command']['return_code'])
        self.assertIsNone(result['verifier_result'])
