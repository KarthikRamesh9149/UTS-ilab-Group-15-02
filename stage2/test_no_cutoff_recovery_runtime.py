"""Real local files/constructor; native host, service and child calls mocked.

Synthetic qualification/witness fixtures are test-only and grant no admission.
No native root, archive, Docker operation or paid provider is used.
"""
from copy import deepcopy
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_libraries as libraries
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_runtime as runtime
from test_no_cutoff_recovery_policy import Fixture


def sha(raw): return hashlib.sha256(raw).hexdigest()


def save(root, name, raw=b'fixture'):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    for directory in [path.parent, *path.parent.parents]:
        if directory == root or directory.is_relative_to(root): directory.chmod(0o700)
    path.write_bytes(raw); path.chmod(0o600)
    return path


class Patching(unittest.TestCase):
    def mock(self, obj, name, *args, **kwargs):
        item = patch.object(obj, name, *args, **kwargs)
        value = item.start(); self.addCleanup(item.stop)
        return value

    def temporary(self):
        item = tempfile.TemporaryDirectory(); self.addCleanup(item.cleanup)
        return Path(item.name).resolve()


class LibraryFilesTests(Patching):
    def setUp(self):
        self.root = self.temporary()
        # Linux native ancestry and ACL observations are mocked on macOS;
        # all directories/files inside the fixture remain real and checked.
        self.mock(libraries, '_directory_chain', side_effect=lambda root, path:
            [root, *reversed([p for p in path.parents if p != root and p.is_relative_to(root)])])
        self.mock(libraries.os, 'listxattr', return_value=[], create=True)
        self.path = save(self.root, 'stage2/source.py')

    def test_real_hash_and_identity_reread(self):
        self.assertEqual(libraries.read(self.root, 'stage2/source.py', sha(b'fixture')), sha(b'fixture'))

    def test_wrong_hash_refuses(self):
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py', '0' * 64)

    def test_source_same_byte_replacement_during_read_refuses(self):
        original = libraries.hashlib.file_digest
        def replace(stream, kind):
            result = original(stream, kind)
            self.path.unlink(); save(self.root, 'stage2/source.py')
            return result
        self.mock(libraries.hashlib, 'file_digest', side_effect=replace)
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_new_source_group_write_refuses(self):
        self.path.chmod(0o664)
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_original_exception_does_not_relax_private_files(self):
        self.mock(libraries, 'ORIGINAL', self.root)
        self.path.chmod(0o664)
        self.assertEqual(libraries.read(self.root, 'stage2/source.py'), sha(b'fixture'))
        private = save(self.root, '.runtime/stage2/input.json'); private.chmod(0o640)
        with self.assertRaises(ValueError): libraries.read(self.root, '.runtime/stage2/input.json')

    def test_group_writable_ancestor_refuses_new_tree(self):
        self.path.parent.chmod(0o775)
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_original_public_exception_does_not_extend_to_libraries(self):
        self.mock(libraries, 'ORIGINAL', self.root)
        path = save(self.root, '.venv/lib/module.py'); path.chmod(0o664)
        with self.assertRaises(ValueError): libraries.read(self.root, '.venv/lib/module.py')

    def test_acl_refuses(self):
        libraries.os.listxattr.return_value = ['system.posix_acl_access']
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_link_and_hardlink_refuse(self):
        save(self.root, 'stage2/target.py')
        self.path.unlink(); self.path.symlink_to('target.py')
        with self.assertRaises((OSError, ValueError)): libraries.read(self.root, 'stage2/source.py')
        self.path.unlink(); os.link(self.path.parent / 'target.py', self.path)
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_fifo_refuses_without_wait(self):
        self.path.unlink(); os.mkfifo(self.path, 0o600)
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_normalised_names_and_hash_map_required(self):
        for name in ('', '/tmp/a', '../a', 'a/../b', 'a//b', 'a\\b', 'a\x00b', 'a\nb'):
            with self.subTest(name=name), self.assertRaises(ValueError): libraries.relative(name)
        for value in ({}, {'stage2/source.py': True}, {'stage2/source.py': 'X' * 64}):
            with self.subTest(value=value), self.assertRaises(ValueError): libraries.check_files(self.root, value)

    def test_inventory_includes_unrecorded_binary_and_record_not_bytecode(self):
        site = self.root / '.venv/lib/python3.12/site-packages'
        save(self.root, str(site.relative_to(self.root)) + '/_binary.so')
        save(self.root, str(site.relative_to(self.root)) + '/pkg-1.dist-info/RECORD')
        save(self.root, str(site.relative_to(self.root)) + '/unrecorded+data')
        save(self.root, str(site.relative_to(self.root)) + '/__pycache__/old.pyc')
        self.assertEqual(set(libraries.installed_tree(self.root, site)),
            {'_binary.so', 'pkg-1.dist-info/RECORD', 'unrecorded+data'})

    def test_symlinked_library_even_in_cache_refuses(self):
        site = self.root / '.venv/lib/python3.12/site-packages'
        save(self.root, str(site.relative_to(self.root)) + '/module.py')
        (site / '__pycache__').symlink_to(site, target_is_directory=True)
        with self.assertRaises(ValueError): libraries.installed_tree(self.root, site)

    def test_empty_or_unprotected_library_directory_refuses(self):
        site = self.root / '.venv/lib/python3.12/site-packages'
        site.mkdir(parents=True)
        with self.assertRaises(ValueError): libraries.installed_tree(self.root, site)
        save(self.root, str(site.relative_to(self.root)) + '/pkg/module.py')
        (site / 'pkg').chmod(0o777)
        with self.assertRaises(ValueError): libraries.installed_tree(self.root, site)

    def test_wrong_file_group_refuses(self):
        original = libraries.os.getgid()
        self.mock(libraries.os, 'getgid', return_value=original + 1)
        with self.assertRaises(ValueError): libraries.read(self.root, 'stage2/source.py')

    def test_dataset_reader_adds_actual_current_file_protection(self):
        value = (self.root / 'stage2', {'source.py': sha(b'fixture')})
        self.mock(runtime, '_original_dataset', return_value=value)
        self.assertEqual(runtime._dataset(self.root, {'fixture': '1' * 64}), value)
        self.path.chmod(0o666)
        with self.assertRaises(ValueError): runtime._dataset(self.root, {'fixture': '1' * 64})


class LibraryProducerTests(Patching):
    def test_effect_guard_denies_and_latches_credentials_writes_process_connections(self):
        self.mock(libraries, '_ENVIRONMENT', {'SAFE': 'same'})
        for event, args in [('open', ('/x/.env', 'r', 0)), ('open', ('/x/id_ed25519', 'r', 0)),
                ('open', ('/x/a', 'w', os.O_WRONLY)), ('os.putenv', (b'SAFE', b'changed')),
                ('os.unsetenv', (b'SAFE',)), ('subprocess.Popen', ()), ('socket.connect', ()),
                ('os.mkdir', ()), ('os.fork', ())]:
            with self.subTest(event=event), patch.object(libraries, '_VIOLATION', False):
                with self.assertRaises(RuntimeError): libraries.no_effects(event, args)
                self.assertTrue(libraries._VIOLATION)
        libraries.no_effects('os.putenv', (b'SAFE', b'same'))
        libraries.no_effects('open', ('/x/module.py', 'r', 0))

    def test_socket_creation_is_blocked_and_only_denial_count_retained(self):
        self.mock(libraries, '_VIOLATION', False)
        self.mock(libraries, '_SOCKET_CONSTRUCTOR_REFUSALS', 0)
        with self.assertRaises(RuntimeError): libraries.no_effects('socket.__new__', ())
        self.assertFalse(libraries._VIOLATION)
        self.assertEqual(libraries._SOCKET_CONSTRUCTOR_REFUSALS, 1)

    def test_current_environment_has_no_provider_or_dotenv_loading(self):
        value = libraries.environment(libraries.RECOVERY)
        self.assertEqual(value['PYTHON_DOTENV_DISABLED'], '1')
        self.assertEqual(value['LITELLM_MODE'], 'PRODUCTION')
        self.assertFalse(any('KEY' in k or 'TOKEN' in k and k != 'TIKTOKEN_CACHE_DIR' for k in value))
        self.assertNotEqual(value['TIKTOKEN_CACHE_DIR'], libraries.environment(libraries.ORIGINAL)['TIKTOKEN_CACHE_DIR'])

    def test_fixed_native_entry_refuses_local_or_arbitrary_roots(self):
        for root in (Path(__file__).resolve().parents[1], Path('/arbitrary'), libraries.RECOVERY):
            with self.subTest(root=root), self.assertRaises(ValueError): libraries.inspect(root, {'x': '1' * 64})

    def test_loaded_project_and_library_origins_must_match_actual_inventory(self):
        root = self.temporary(); site = root / '.venv/lib/python3.12/site-packages'
        path = save(root, 'stage2/example.py')
        self.mock(libraries, 'read', return_value=sha(b'fixture'))
        modules = {'example': SimpleNamespace(__file__=str(path))}
        self.mock(libraries.sys, 'modules', modules)
        libraries.loaded(root, site, {'stage2/example.py': sha(b'fixture')}, {'pkg.py': '1' * 64})
        for filename in (str(root / 'other/example.py'), None):
            modules['example'].__file__ = filename
            with self.assertRaises(ValueError): libraries.loaded(root, site, {}, {})
        modules.clear(); modules['pkg'] = SimpleNamespace(__file__='/other/site-packages/pkg.py')
        with self.assertRaises(ValueError): libraries.loaded(root, site, {}, {})

    def test_distribution_versions_require_exact_pins_and_all_required_packages(self):
        names = ['harbor', 'deepagents', 'langgraph', 'langchain', 'langchain-core', 'langchain-openai', 'openai', 'httpx']
        lock = '\n'.join(n + '==1.0' for n in names)
        records = [SimpleNamespace(metadata={'Name': n}, version='1.0') for n in names]
        mock = self.mock(libraries.importlib.metadata, 'distributions', return_value=records)
        self.assertEqual(libraries.versions('/unused', lock), dict.fromkeys(names, '1.0'))
        for extra in (records[0], SimpleNamespace(metadata={'Name': 'extra'}, version='1.0'),
                SimpleNamespace(metadata={'Name': 'pip'}, version='')):
            mock.return_value = records + [extra]
            with self.assertRaises(ValueError): libraries.versions('/unused', lock)
        mock.return_value = records[:-1]
        with self.assertRaises(ValueError): libraries.versions('/unused', lock)
        mock.return_value = records
        with self.assertRaises(ValueError): libraries.versions('/unused', lock.replace('openai==1.0', 'openai==2.0'))

    def test_real_constructor_in_credential_free_effect_guarded_child(self):
        root = Path(__file__).resolve().parents[1]
        program = '''import sys, os, json
from pathlib import Path
root=Path.cwd(); sys.path.insert(0,str(root/'stage2'))
import no_cutoff_recovery_libraries as p
p._ENVIRONMENT=dict(os.environ)
sys.addaudithook(p.no_effects)
value=p.controls(root)
if p._VIOLATION: raise ValueError('Forbidden construction side effect')
print(json.dumps(value,sort_keys=True,allow_nan=False))
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-'], input=program, cwd=root,
            env=libraries.environment(root), text=True, capture_output=True, timeout=90, check=True)
        value = json.loads(result.stdout)
        self.assertEqual(value['factory_harness'], 'C0-NC')
        self.assertEqual(value['parent'], 'C0')
        self.assertIsNone(value['metadata']['max_model_calls'])
        self.assertEqual(value['metadata']['execution_contract'], policy.execution_contract())
        self.assertEqual(value['client']['fixture_timeout'], 7200.)
        self.assertEqual(value['client']['max_tokens'], 384000)
        self.assertEqual(value['client']['extra_body'], {'reasoning': {'effort': 'high'}})
        self.assertNotIn('api_key', value['client'])


class LibraryTransportTests(Patching):
    def setUp(self):
        self.root = libraries.RECOVERY
        self.files = {'stage2/example.py': '1' * 64}
        self.record = dict(kind=libraries.KIND, root=str(self.root), inputs=self.files,
            historical_installed_bytes_attested=False, recovery_execution_qualified=False,
            live_api_calls=0, paid_launch_ready=False, python='3.12.13',
            site_relative='.venv/lib/python3.12/site-packages', versions={'harbor': '0.22.0'},
            library_files={'_binary.so': '2' * 64, 'data+suffix': '3' * 64},
            controls={'float': 1.0, 'missing': None}, denied_socket_constructions=2)
        self.run = self.mock(runtime.subprocess, 'run', side_effect=lambda *a, **k:
            SimpleNamespace(stdout=json.dumps(self.record), stderr=''))

    def test_exact_own_isolated_interpreter_stdin_and_credential_free_environment(self):
        self.assertEqual(runtime._library_read(self.root, self.files, 'PRODUCER'), self.record)
        args, kwargs = self.run.call_args
        self.assertEqual(args[0], [str(self.root / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertTrue(kwargs['input'].startswith('PRODUCER\n'))
        self.assertEqual(kwargs['env'], libraries.environment(self.root))
        self.assertEqual(kwargs['timeout'], 300)
        self.assertEqual(kwargs['cwd'], self.root)

    def test_child_failures_suppress_raw_diagnostics_and_never_retry(self):
        self.run.side_effect = subprocess.CalledProcessError(1, 'unused', stderr='SECRET')
        with self.assertRaisesRegex(ValueError, 'raw diagnostics suppressed') as error:
            runtime._library_read(self.root, self.files, 'PRODUCER')
        self.assertNotIn('SECRET', str(error.exception)); self.run.assert_called_once()

    def test_missing_additional_or_nonfinite_duplicate_metadata_refuses(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '[]', json.dumps({**self.record, 'extra': 1})):
            self.run.side_effect = None; self.run.return_value = SimpleNamespace(stdout=raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runtime._library_read(self.root, self.files, 'PRODUCER')

    def test_wrong_root_input_types_or_paid_claim_refuses(self):
        for key, value in [('root', str(libraries.ORIGINAL)), ('inputs', {}), ('paid_launch_ready', True),
                ('live_api_calls', False), ('denied_socket_constructions', True), ('library_files', {}),
                ('site_relative', '/elsewhere'), ('historical_installed_bytes_attested', True)]:
            with self.subTest(key=key), patch.dict(self.record, {key: value}), self.assertRaises(ValueError):
                runtime._library_read(self.root, self.files, 'PRODUCER')


class RuntimeTests(Patching):
    def setUp(self):
        self.root = self.temporary(); self.f = Fixture(self, self.root)
        self.bound = dict(self.f.proof['sources'])
        self.final = deepcopy(self.f.final)
        self.final.update(runtime_identity_sha256='2' * 64, gateway_image='sha256:' + '7' * 64)
        self.mock(policy, 'ORIGINAL_QUALIFICATION', policy.fingerprint(self.final))
        self.f.predecessor['qualification_sha256'] = policy.ORIGINAL_QUALIFICATION
        self.files = {'config.toml': '3' * 64}
        self.inventory = {task: dict(docker_image='image-' + task, agent_timeout_seconds=7200.,
            verifier_timeout_seconds=180., cpus=1, memory_mb=2048) for task in self.f.manifest['all_task_ids']}
        self.old = dict(task_inventory={name: dict(row, image_id='sha256:' + '4' * 64)
            for name, row in self.inventory.items()}, dataset_files_sha256=policy.fingerprint(self.files))
        self.predecessor = dict(predecessor=self.f.predecessor, current_sources_sha256=policy.fingerprint(self.bound))
        self.witness = handoff._Witness()
        handoff._WITNESSES[self.witness] = dict(root=self.root, pid=os.getpid(), thread=threading.get_ident(),
            task=handoff._task(), record=self.predecessor)
        self.addCleanup(handoff.invalidate, self.witness)
        self.inputs = self.mock(runtime, '_inputs', side_effect=self.input_value)
        self.mock(runtime, 'dependencies', return_value=self.final['dependencies'])
        self.python = self.mock(runtime, '_python', return_value=self.final['python_runtime'])
        self.host = self.mock(runtime.host_environment, 'snapshot', return_value=self.final['host_environment'])
        self.dataset = self.mock(runtime, '_dataset', return_value=(self.root / 'dataset', self.files))
        self.limits = self.mock(runtime, '_task_limits', return_value=self.inventory)
        self.images = self.mock(runtime, '_images', side_effect=lambda names: {name: dict(id=
            name if name.startswith('sha256:') else 'sha256:' + '4' * 64) for name in names})
        self.parity = self.mock(runtime, '_library_parity', return_value={'observation': 'synthetic-test-only'})
        self.reread = self.mock(runtime, '_library_recheck')
        self.raw = self.mock(handoff, '_raw', return_value=b'fixture')
        self.loaded = self.mock(handoff.operator, 'loaded')

    def input_value(self, witness):
        handoff._live(witness)
        return self.root, self.final, self.bound, self.f.manifest, self.old, self.predecessor

    def test_exact_original_three_cells_official_limits_and_nonadmitting_result(self):
        value = runtime.inspect(self.witness)
        self.assertEqual([c['original_ordinal'] for c in value['cells']], [63, 64, 65])
        self.assertEqual(len(value['task_inventory']), 3)
        self.assertEqual(value['orchestration_changes'].keys(), {'scored_trial.py'})
        self.assertFalse(value['paid_launch_ready'])
        self.assertFalse(value['limitations']['historical_installed_bytes_attested'])
        self.assertFalse(value['limitations']['native_qualification'])
        self.assertEqual(self.inputs.call_count, 2)
        self.assertEqual(self.limits.call_count, 3)
        self.reread.assert_called_once()
        self.assertEqual({c.args[1] for c in self.raw.call_args_list}, {'stage2/' + n for n in self.bound})

    def test_non_native_host_refuses_and_latches_witness(self):
        self.host.return_value = dict(execution_mode='emulated')
        with self.assertRaises(ValueError): runtime.inspect(self.witness)
        self.host.return_value = self.final['host_environment']
        with self.assertRaises(ValueError): runtime.inspect(self.witness)

    def test_dependencies_python_or_dataset_drift_refuses(self):
        for mock, value in ((runtime.dependencies, {}), (self.python, {}),
                (self.dataset, (self.root / 'dataset', {'config.toml': 'f' * 64}))):
            with self.subTest(mock=mock), patch.object(mock, 'return_value', value), self.assertRaises(ValueError):
                runtime.inspect(self.witness)
            self.assertNotIn(self.witness, handoff._WITNESSES)
            handoff._WITNESSES[self.witness] = dict(root=self.root, pid=os.getpid(), thread=threading.get_ident(),
                task=handoff._task(), record=self.predecessor)

    def test_held_out_configuration_change_refuses_without_reading_solution(self):
        changed = deepcopy(self.inventory)
        changed[self.f.manifest['all_task_ids'][0]]['cpus'] = 2
        self.limits.return_value = changed
        with self.assertRaises(ValueError): runtime.inspect(self.witness)
        self.parity.assert_not_called()

    def test_image_tag_drift_or_missing_inspection_refuses(self):
        self.images.side_effect = lambda names: {name: dict(id='sha256:' + 'f' * 64) for name in names}
        with self.assertRaises(ValueError): runtime.inspect(self.witness)
        self.parity.assert_not_called()

    def test_final_library_drift_refuses_and_restoration_does_not_revive(self):
        self.reread.side_effect = ValueError('changed')
        with self.assertRaises(ValueError): runtime.inspect(self.witness)
        self.reread.side_effect = None
        with self.assertRaises(ValueError): runtime.inspect(self.witness)

    def test_late_source_file_read_occurs_after_host_images_and_handoff(self):
        order = []
        self.reread.side_effect = lambda value: order.append('libraries')
        self.raw.side_effect = lambda *a: order.append('source') or b'fixture'
        old = self.inputs.side_effect
        self.inputs.side_effect = lambda w: order.append('handoff') or old(w)
        self.host.side_effect = lambda: order.append('host') or self.final['host_environment']
        runtime.inspect(self.witness)
        self.assertLess(max(i for i, x in enumerate(order) if x == 'handoff'), order.index('libraries'))
        self.assertLess(max(i for i, x in enumerate(order) if x == 'host'), order.index('libraries'))
        self.assertGreater(order.index('source'), order.index('libraries'))

    def test_recheck_rereads_and_saved_drift_invalidates(self):
        original = runtime.inspect(self.witness)
        self.assertEqual(runtime.recheck(self.witness, original), original)
        original['paid_launch_ready'] = True
        with self.assertRaises(ValueError): runtime.recheck(self.witness, original)
        self.assertNotIn(self.witness, handoff._WITNESSES)

    def test_constructed_saved_and_wrong_thread_handles_refuse(self):
        for value in (handoff._Witness(), self.predecessor, None):
            with self.subTest(kind=type(value).__name__), self.assertRaises((ValueError, TypeError)):
                runtime.inspect(value)
        handoff._WITNESSES[self.witness]['thread'] += 1
        with self.assertRaises(ValueError): runtime.inspect(self.witness)
        self.assertNotIn(self.witness, handoff._WITNESSES)

    def test_cancellation_invalidates_witness(self):
        self.parity.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError): runtime.inspect(self.witness)
        self.assertNotIn(self.witness, handoff._WITNESSES)


class InputTests(Patching):
    def setUp(self):
        self.root = self.temporary(); self.original = self.temporary()
        f = Fixture(self, self.root); self.final = f.final; self.bound = f.proof['sources']
        old = {key: deepcopy(self.final[key]) for key in
            ('sources', 'sources_sha256', 'dependencies', 'python_runtime', 'host_environment')}
        old['candidate_sha256'] = policy.ORIGINAL_CANDIDATE
        self.old_raw = json.dumps(old).encode()
        self.final['runtime_identity_sha256'] = policy.fingerprint(old)
        self.final_raw = json.dumps(self.final).encode()
        self.mock(policy, 'ORIGINAL_QUALIFICATION', policy.fingerprint(self.final))
        self.mock(policy, 'ORIGINAL_QUALIFICATION_FILE_SHA256', sha(self.final_raw))
        self.copy = save(self.root, handoff.phase.RT + policy.ORIGINAL_FILE, self.final_raw)
        self.manifest = save(self.root, 'stage2/input_manifest.json', f.manifest_raw)
        self.old = save(self.original, handoff.phase.RT + 'no-cutoff-final-runtime.json', self.old_raw)
        self.mock(handoff.report, 'ROOT', self.original)
        self.mock(handoff.report, 'INPUTS', {'no-cutoff-final-runtime.json': sha(self.old_raw)})
        self.mock(handoff.phase.guard.os, 'listxattr', return_value=[], create=True)
        self.witness = handoff._Witness()
        handoff._WITNESSES[self.witness] = dict(root=self.root, pid=os.getpid(), thread=threading.get_ident(),
            task=handoff._task())
        self.addCleanup(handoff.invalidate, self.witness)
        self.mock(handoff, 'recheck', return_value={'current_sources_sha256': policy.fingerprint(self.bound)})
        self.mock(handoff, '_context', return_value=self.root)
        self.mock(runtime, '__file__', str(self.root / 'stage2/no_cutoff_recovery_runtime.py'))
        self.mock(handoff.operator, 'sources', return_value=self.bound)
        self.loaded = self.mock(handoff.operator, 'loaded')

    def test_actual_original_private_and_manifest_bytes_are_read(self):
        value = runtime._inputs(self.witness)
        self.assertEqual(value[0], self.root)
        self.assertEqual(value[1], self.final)
        self.assertEqual(value[4], json.loads(self.old_raw))
        self.loaded.assert_called_once_with(self.root, self.bound)

    def test_whitespace_drift_in_any_anchor_refuses(self):
        for path in (self.copy, self.manifest, self.old):
            raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.subTest(path=path.name), self.assertRaises(ValueError): runtime._inputs(self.witness)
            path.write_bytes(raw)

    def test_private_mode_and_link_refuse(self):
        self.copy.chmod(0o640)
        with self.assertRaises(ValueError): runtime._inputs(self.witness)
        self.copy.chmod(0o600); self.copy.unlink(); self.copy.symlink_to(self.old)
        with self.assertRaises(ValueError): runtime._inputs(self.witness)

    def test_live_source_mismatch_refuses(self):
        handoff.recheck.return_value = {'current_sources_sha256': '0' * 64}
        with self.assertRaises(ValueError): runtime._inputs(self.witness)

    def test_wrong_deployment_module_or_stale_description_refuses(self):
        with self.assertRaises(ValueError): runtime._inputs(handoff._Witness())
        with patch.object(runtime, '__file__', '/other/stage2/no_cutoff_recovery_runtime.py'):
            with self.assertRaises(ValueError): runtime._inputs(self.witness)


class ParityTests(Patching):
    def setUp(self):
        self.root = libraries.RECOVERY
        self.final = dict(sources={'original.py': '1' * 64}, dependencies=dict(python='3.12.13', packages={'harbor': '0.22.0'}))
        self.bound = dict.fromkeys((*runtime.CURRENT_ORIGINAL_HELPERS, 'no_cutoff_recovery_libraries.py'), '2' * 64)
        self.raw = self.mock(handoff, '_raw', return_value=b'PRODUCER')
        controls = dict(factory_harness='C0-NC', parent='C0', base_parent=None, version=policy.CANDIDATE_VERSION,
            model_protocol_sha256=policy.MODEL_SHA256, python_runtime_sha256=policy.PYTHON_SHA256,
            metadata=dict(execution_contract=policy.execution_contract(), max_model_calls=None))
        self.value = dict(python='3.12.13', site_relative='.venv/lib/python3.12/site-packages',
            versions={'harbor': '0.22.0'}, library_files={'pkg.py': '3' * 64}, controls=controls)
        self.child = self.mock(runtime, '_library_read', side_effect=self.read)

    def read(self, root, inputs, producer): return dict(deepcopy(self.value), root=str(root), inputs=inputs)

    def test_both_real_child_call_sites_and_separate_current_helper_binding(self):
        result = runtime._library_parity(self.root, self.final, self.bound)
        self.assertEqual(self.child.call_count, 2)
        self.assertEqual(self.child.call_args_list[0].args[0], handoff.report.ROOT)
        self.assertEqual(self.child.call_args_list[1].args[0], self.root)
        self.assertEqual(set(result['original']['inputs']), {'stage2/original.py',
            *('stage2/' + n for n in runtime.CURRENT_ORIGINAL_HELPERS),
            '.runtime/stage2/no-cutoff-final-qualification.json'})
        self.assertEqual(self.final['sources'], {'original.py': '1' * 64})

    def test_matching_version_with_different_actual_library_bytes_refuses(self):
        def changed(root, files, producer):
            value = self.read(root, files, producer)
            if root == self.root: value['library_files']['pkg.py'] = '4' * 64
            return value
        self.child.side_effect = changed
        with self.assertRaises(ValueError): runtime._library_parity(self.root, self.final, self.bound)

    def test_same_wrong_constructor_or_call_cap_cannot_pass_parity(self):
        for key, value in (('parent', 'C3'), ('factory_harness', 'terminus-2'), ('version', 'changed')):
            with self.subTest(key=key), patch.dict(self.value['controls'], {key: value}), self.assertRaises(ValueError):
                runtime._library_parity(self.root, self.final, self.bound)
        self.value['controls']['metadata']['max_model_calls'] = 100
        with self.assertRaises(ValueError): runtime._library_parity(self.root, self.final, self.bound)

    def test_source_drift_after_children_refuses(self):
        def read(root, files, producer):
            result = self.read(root, files, producer)
            if root == self.root: self.raw.side_effect = ValueError('changed')
            return result
        self.child.side_effect = read
        with self.assertRaises(ValueError): runtime._library_parity(self.root, self.final, self.bound)

    def test_final_reread_inspects_both_actual_library_trees_and_inputs(self):
        record = dict(self.value, root=str(self.root), inputs={'stage2/custom-requirements.lock': '4' * 64})
        other = dict(record, root=str(libraries.ORIGINAL))
        check = self.mock(libraries, 'check_files')
        tree = self.mock(libraries, 'installed_tree', return_value=self.value['library_files'])
        loaded = self.mock(libraries, 'loaded')
        self.mock(libraries, 'versions', return_value=self.value['versions'])
        runtime._library_recheck(dict(original=other, recovery=record))
        self.assertEqual(check.call_count, 4); self.assertEqual(tree.call_count, 2)
        loaded.assert_called_once_with(self.root, self.root / record['site_relative'],
            record['inputs'], record['library_files'])
        tree.return_value = {'pkg.py': '5' * 64}
        with self.assertRaises(ValueError): runtime._library_recheck(dict(original=other, recovery=record))


if __name__ == '__main__': unittest.main()
