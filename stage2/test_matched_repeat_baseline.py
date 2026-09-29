"""Current byte/control inspection tests, not historical or native study proof."""
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
from unittest.mock import patch

import matched_repeat_baseline as baseline
import matched_repeat_baseline_probe as probe
import matched_repeat_policy as policy
from test_matched_repeat_runtime import TreeTests


class ProbeFileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def write(self, name, raw=b'Fixture bytes'):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(0o600)
        return hashlib.sha256(raw).hexdigest()

    def test_actual_file_hashes_permissions_and_source_drift(self):
        bound = {name: self.write(name) for name in ('stage2/a.py', '.runtime/stage2/a.json')}
        probe.check_files(self.root, bound)
        self.write('stage2/a.py', b'Drift')
        with self.assertRaisesRegex(ValueError, 'changed'): probe.check_files(self.root, bound)

    def test_private_input_requires_owned_private_permissions(self):
        name = '.runtime/stage2/a.json'; bound = {name: self.write(name)}
        (self.root / name).chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'private'): probe.check_files(self.root, bound)

    def test_paths_symlinks_missing_files_and_invalid_hashes_fail_closed(self):
        self.write('source.py')
        (self.root / 'alias.py').symlink_to(self.root / 'source.py')
        for name in ('../source.py', '/source.py', 'a//b', 'a/./b', 'alias.py'):
            with self.subTest(name=name), self.assertRaises(ValueError): probe.regular(self.root, name)
        with self.assertRaises(FileNotFoundError): probe.regular(self.root, 'missing')
        for value in ({}, {'source.py': True}, {'source.py': 'not-a-hash'}):
            with self.subTest(value=value), self.assertRaises(ValueError): probe.check_files(self.root, value)

    def test_real_tree_includes_unrecorded_code_prompts_metadata_and_binary_bytes(self):
        names = ('harbor/agent.py', 'harbor/prompt.j2', 'harbor/extra-unrecorded.py',
            'x.so', 'harbor.dist-info/RECORD', 'harbor.dist-info/METADATA')
        expected = {name: self.write(name, ('bytes:' + name).encode()) for name in names}
        self.write('harbor/__pycache__/agent.cpython-312.pyc')
        self.write('x.pyc'); self.write('x.pyo')
        self.assertEqual(probe.installed_tree(self.root), expected)
        self.write('harbor/prompt.j2', b'Altered prompt')
        self.assertNotEqual(probe.installed_tree(self.root), expected)

    def test_tree_rejects_file_directory_cache_symlinks_and_empty_inventory(self):
        with self.assertRaisesRegex(ValueError, 'empty'): probe.installed_tree(self.root)
        self.write('real.py')
        for name in ('alias.py', 'alias-dir', '__pycache__'):
            path = self.root / name; path.symlink_to(self.root / 'real.py')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Symlinked'):
                probe.installed_tree(self.root)
            path.unlink()

    def test_version_inventory_reads_all_distributions_not_only_core_names(self):
        names = ('harbor', 'litellm', 'openai', 'httpx', 'httpcore', 'tenacity', 'extra-app')
        lock = '\n'.join(name + '==1.0 \\' for name in names)
        distributions = [NS(metadata={'Name': name}, version='1.0') for name in names]
        distributions.append(NS(metadata={'Name': 'pip'}, version='25.0'))
        with patch.object(probe.importlib.metadata, 'distributions', return_value=distributions) as call:
            got = probe.versions(self.root, lock)
        self.assertEqual(got, dict(dict.fromkeys(names, '1.0'), pip='25.0'))
        call.assert_called_once_with(path=[str(self.root)])

    def test_missing_duplicate_unpinned_or_mismatching_versions_are_refused(self):
        names = ('harbor', 'litellm', 'openai', 'httpx', 'httpcore', 'tenacity')
        lock = '\n'.join(name + '==1.0' for name in names)
        good = [NS(metadata={'Name': name}, version='1.0') for name in names]
        for bad in (good[:-1], good + [good[0]], good + [NS(metadata={'Name': 'unlocked'}, version='1')],
                [NS(metadata={'Name': 'harbor'}, version='2')] + good[1:]):
            with patch.object(probe.importlib.metadata, 'distributions', return_value=bad):
                with self.assertRaises(ValueError): probe.versions(self.root, lock)
        with self.assertRaises(ValueError): probe.versions(self.root, 'harbor==1.0')

    def test_no_effects_guard_refuses_network_process_and_mutation_events(self):
        for event in ('socket.connect', 'socket.__new__', 'socket.getaddrinfo', 'subprocess.Popen',
                'os.system', 'os.fork', 'os.exec', 'os.posix_spawn', 'os.mkdir', 'os.rename', 'os.remove'):
            with self.subTest(event=event), self.assertRaises(RuntimeError): probe.no_effects(event, ())
        for mode, flags in (('w', 0), ('a', 0), ('r+', 0), (None, os.O_WRONLY), (None, os.O_CREAT)):
            with self.subTest(mode=mode, flags=flags), self.assertRaises(RuntimeError):
                probe.no_effects('open', ('unused', mode, flags))
        probe.no_effects('open', ('file', 'r', os.O_RDONLY))
        probe.no_effects('os.listdir', (str(self.root),))

    def test_non_native_or_nonisolated_probe_is_not_real_native_identity(self):
        self.write('stage2/a.py')
        with self.assertRaises(ValueError): probe.inspect(self.root, {'stage2/a.py': '1' * 64})


class NativeProbeTests(unittest.TestCase):
    """Exercise the actual probe flow with only the native context mocked."""
    def setUp(self):
        ProbeFileTests.setUp(self)
        self.site = self.root / '.venv/lib/python3.12/site-packages'
        self.site.mkdir(parents=True)
        self.write('.venv/lib/python3.12/site-packages/harbor/agent.py')
        self.bound = {'stage2/a.py': self.write('stage2/a.py'),
            'stage2/custom-requirements.lock': self.write('stage2/custom-requirements.lock', b'fixture lock')}
        self.enterContext(patch.object(probe.platform, 'system', return_value='Linux'))
        self.enterContext(patch.object(probe.platform, 'machine', return_value='x86_64'))
        self.enterContext(patch.object(sys, 'prefix', str(self.root / '.venv')))
        flags = {name: getattr(sys.flags, name) for name in dir(sys.flags)
            if not name.startswith('_') and type(getattr(sys.flags, name)) is int}
        self.enterContext(patch.object(sys, 'flags', NS(**dict(flags, isolated=True))))
        self.enterContext(patch.object(sys, 'dont_write_bytecode', True))
        self.enterContext(patch.object(sys, 'path', list(sys.path)))
        self.enterContext(patch.object(sys, 'pycache_prefix', None))
        self.enterContext(patch.object(probe.sysconfig, 'get_path', return_value=str(self.site)))
        self.versions = self.enterContext(patch.object(probe, 'versions', return_value={'harbor': '0.22.0'}))
        self.controls = self.enterContext(patch.object(probe, 'controls', return_value={'fixture': True}))
        self.guard = self.enterContext(patch.object(sys, 'addaudithook'))
        self.modules = self.enterContext(patch.dict(sys.modules, {}, clear=True))

    def read(self): return probe.inspect(self.root, self.bound)

    write = ProbeFileTests.write

    def test_full_probe_rechecks_real_bytes_and_never_claims_historical_attestation(self):
        before = sorted(self.root.rglob('*'))
        got = self.read()
        self.assertEqual(got['inputs'], self.bound)
        self.assertIn('harbor/agent.py', got['library_files'])
        self.assertFalse(got['historical_installed_bytes_attested'])
        self.assertFalse(got['baseline_execution_qualified']); self.assertFalse(got['paid_launch_ready'])
        self.assertEqual(got['live_api_calls'], 0)
        self.assertEqual(sorted(self.root.rglob('*')), before)
        self.assertEqual(sys.pycache_prefix, str(self.root / '.runtime/unused-baseline-inspection-bytecode'))
        self.guard.assert_called_once_with(probe.no_effects)

    def test_source_mutation_during_constructors_is_rejected(self):
        self.controls.side_effect = lambda root: self.write('stage2/a.py', b'drift')
        with self.assertRaisesRegex(ValueError, 'changed'): self.read()

    def test_installed_file_mutation_during_constructors_is_rejected(self):
        self.controls.side_effect = lambda root: self.write('.venv/lib/python3.12/site-packages/harbor/agent.py', b'drift')
        with self.assertRaisesRegex(ValueError, 'changed'): self.read()

    def test_existing_bytecode_location_is_rejected_before_constructor(self):
        self.write('.runtime/unused-baseline-inspection-bytecode/injected.pyc')
        with self.assertRaisesRegex(ValueError, 'must not exist'): self.read()
        self.controls.assert_not_called()

    def test_loaded_library_outside_inventory_or_other_checkout_is_rejected(self):
        for filename in ('/other/site-packages/harbor/agent.py', str(self.site / 'unlisted.py'), '/other/stage2/a.py'):
            sys.modules['fixture'] = NS(__file__=filename)
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, 'Loaded'):
                self.read()

    def test_bound_source_drift_is_refused_before_controls(self):
        self.write('stage2/a.py', b'drift')
        with self.assertRaises(ValueError): self.read()
        self.controls.assert_not_called(); self.guard.assert_not_called()

    def test_symlinked_library_ancestor_is_rejected_before_controls(self):
        library = self.root / '.venv/lib'; moved = self.root / 'outside-lib'
        library.rename(moved); library.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'library directory'): self.read()
        self.controls.assert_not_called()


def observation(root, inputs):
    return dict(kind='current_installed_baseline_constructor_observation', root=str(root),
        inputs=inputs, historical_installed_bytes_attested=False, baseline_execution_qualified=False,
        live_api_calls=0, paid_launch_ready=False, python='3.12.13',
        site_relative='.venv/lib/python3.12/site-packages', versions={'harbor': '0.22.0'},
        library_files={'harbor/agent.py': 'a' * 64}, controls=dict(model_protocol_sha256=policy.MODEL_SHA256,
            terminus=dict(max_turns=1000000), openhands=dict(version='0.62.0', python_version='3.12',
                resolved_env={'MAX_ITERATIONS': '1000000'})))


class HostTests(TreeTests):
    def setUp(self):
        super().setUp()
        self.root = self.root.resolve()
        self.original_root = self.root / 'original'; self.original_root.mkdir()
        self.enterContext(patch.object(baseline, 'ORIGINAL_ROOT', self.original_root))
        self.enterContext(patch.object(baseline, '__file__', str(self.root / 'stage2/matched_repeat_baseline.py')))
        self.enterContext(patch.object(baseline.platform, 'system', return_value='Linux'))
        self.enterContext(patch.dict(baseline.runtime.DEPLOYMENTS, {'terminus-2': self.root}))
        self.enterContext(patch.object(baseline.runtime, 'loaded_sources'))
        self.enterContext(patch.object(baseline, 'check_files'))
        self.inactive = self.enterContext(patch.object(baseline, 'inactive_ancestors'))
        self.reader = self.enterContext(patch.object(baseline, '_read', side_effect=lambda r, b, p: observation(r, b)))

    def read(self): return baseline.inspect(self.root, self.f.original, self.f.final, 'terminus-2')

    def test_calls_both_actual_readers_and_binds_their_source_input_maps(self):
        got = self.read()
        self.assertEqual(got['kind'], baseline.KIND); self.assertFalse(got['paid_launch_ready'])
        self.assertFalse(got['limitations']['historical_installed_byte_manifest_available'])
        self.assertFalse(got['limitations']['original_backup_contains_virtualenv'])
        self.assertEqual([c.args[0] for c in self.reader.call_args_list], [self.original_root, self.root])
        self.assertIn('.runtime/stage2/corrected-qualification.json', got['original']['inputs'])
        self.assertIn('.runtime/stage2/' + policy.BASELINE_FILE, got['repeat']['inputs'])
        self.assertEqual(got['source_transition']['orchestration_changes'], {})
        self.assertEqual(self.inactive.call_count, 2)

    def test_installed_bytes_versions_python_and_controls_must_match(self):
        for key, value in (('library_files', {'harbor/agent.py': 'b' * 64}), ('versions', {'harbor': '999'}),
                ('python', '3.13.0'), ('site_relative', 'elsewhere'), ('controls', {})):
            def differing(root, inputs, producer):
                result = observation(root, inputs)
                if root == self.root: result[key] = value
                return result
            self.reader.side_effect = differing
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'differ'): self.read()

    def test_matching_altered_turn_guards_or_baseline_settings_are_not_admissible(self):
        for key in ('terminus', 'openhands'):
            def altered(root, inputs, producer):
                got = observation(root, inputs)
                if key == 'terminus': got['controls'][key]['max_turns'] = 100
                else: got['controls'][key]['version'] = '0.63.0'
                return got
            self.reader.side_effect = altered
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'settings'): self.read()

    def test_active_ancestor_fails_before_original_interpreter(self):
        self.inactive.side_effect = ValueError('Active final')
        with self.assertRaises(ValueError): self.read()
        self.reader.assert_not_called()

    def test_wrong_host_or_changed_agent_code_fails_before_original_interpreter(self):
        with patch.object(baseline.platform, 'system', return_value='Darwin'):
            with self.assertRaises(ValueError): self.read()
        self.write('stage2/native_agents.py', b'Change native tools')
        with self.assertRaises(ValueError): self.read()
        self.reader.assert_not_called()

    def test_recheck_actually_reads_again_and_rejects_copied_fabricated_or_stale_document(self):
        got = self.read(); self.reader.reset_mock()
        self.assertEqual(baseline.recheck(self.root, self.f.original, self.f.final, 'terminus-2', got), got)
        self.assertEqual(self.reader.call_count, 2)
        got['paid_launch_ready'] = True
        with self.assertRaisesRegex(ValueError, 'bound observation'):
            baseline.recheck(self.root, self.f.original, self.f.final, 'terminus-2', got)


class ProcessTests(unittest.TestCase):
    def test_underscore_library_names_are_valid_but_traversal_is_not(self):
        root = Path('/fixture'); bindings = {'stage2/a.py': 'a' * 64}
        record = observation(root, bindings)
        record['library_files'] = {'_cffi_backend.cpython-312.so': 'a' * 64}
        with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=json.dumps(record))):
            self.assertEqual(baseline._read(root, bindings, '')['library_files'], record['library_files'])
        for path in ('../escape', 'a//b', '/outside', 'a\\b', 'a\nb'):
            record['library_files'] = {path: 'a' * 64}
            with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=json.dumps(record))):
                with self.assertRaises(ValueError): baseline._read(root, bindings, '')

    def test_child_uses_own_isolated_interpreter_and_no_production_environment(self):
        root = Path('/fixture'); bindings = {'stage2/a.py': 'a' * 64}
        result = NS(stdout=json.dumps(observation(root, bindings)))
        with patch.object(baseline.subprocess, 'run', return_value=result) as process:
            baseline._read(root, bindings, '# Bound probe bytes')
        args, opts = process.call_args
        self.assertEqual(args[0], ['/fixture/.venv/bin/python', '-I', '-B', '-'])
        self.assertEqual(opts['cwd'], root); self.assertTrue(opts['check'])
        self.assertEqual(opts['env'], {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
            'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'DO_NOT_TRACK': '1'})
        self.assertIn('inspect(', opts['input'])
        self.assertNotIn('collect', opts['input'])

    def test_child_claiming_native_qualification_or_wrong_inputs_is_refused(self):
        root = Path('/fixture'); bindings = {'stage2/a.py': 'a' * 64}
        for field, value in (('root', '/other'), ('inputs', {}), ('paid_launch_ready', True),
                ('baseline_execution_qualified', True), ('live_api_calls', 1), ('library_files', {})):
            record = observation(root, bindings); record[field] = value
            with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=json.dumps(record))):
                with self.subTest(field=field), self.assertRaises(ValueError): baseline._read(root, bindings, '')

    def test_real_local_constructors_under_effect_guard_without_setup_or_provider_access(self):
        # This deliberately tests local constructors, not native inspection.
        stage = Path(__file__).resolve().parent; repo = stage.parent
        program = ('import sys\nsys.path.insert(0, ' + repr(str(stage)) + ')\n'
            'from matched_repeat_baseline_probe import controls, no_effects\n'
            'sys.addaudithook(no_effects)\nimport json\n'
            'print(json.dumps(controls(' + repr(str(repo)) + '), sort_keys=True))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-'], input=program, check=True,
            capture_output=True, text=True, env={'PATH': '/usr/bin:/bin', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}, timeout=60)
        got = json.loads(result.stdout)
        self.assertEqual(got['terminus']['max_turns'], 1000000)
        self.assertTrue(got['terminus']['summarize']); self.assertEqual(got['terminus']['summarization_free_tokens'], 8000)
        self.assertEqual(got['terminus']['fixture_completion_timeout'], 7200.)
        self.assertEqual(got['terminus']['call_kwargs']['max_tokens'], 384000)
        self.assertEqual(got['openhands']['resolved_env']['MAX_ITERATIONS'], '1000000')
        self.assertEqual(got['openhands']['fixture_completion_timeout'], '7200')
        self.assertEqual(got['openhands']['version'], '0.62.0')
        self.assertNotIn('api_key', result.stdout.lower())


class AncestorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.enterContext(patch.object(baseline, 'ORIGINAL_ROOT', self.root / 'original'))
        self.enterContext(patch.object(baseline, 'FINAL_ROOT', self.root / 'final'))
        self.state = 'LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'
        self.final = self.enterContext(patch.object(baseline.final_guard, 'service'))

    def test_only_readonly_service_queries_and_no_collector(self):
        with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=self.state)) as run:
            baseline.inactive_ancestors()
        self.assertEqual(run.call_count, 1); self.final.assert_called_once_with()
        self.assertTrue(all(call.args[0][:2] == ['systemctl', 'show'] for call in run.call_args_list))

    def test_active_failed_unloaded_or_persistent_stopped_ancestors_refused(self):
        for state in (self.state.replace('inactive', 'active'), self.state.replace('MainPID=0', 'MainPID=1'),
                self.state.replace('ExecMainStatus=0', 'ExecMainStatus=1'), self.state.replace('loaded', 'not-found')):
            with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=state)):
                with self.subTest(state=state), self.assertRaises(ValueError): baseline.inactive_ancestors()
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            path = self.root / 'final/.runtime/stage2' / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}')
            with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=self.state)):
                with self.assertRaises(ValueError): baseline.inactive_ancestors()
            path.unlink()

    def test_final_requires_actual_success_guard_even_if_original_is_inactive(self):
        self.final.side_effect = ValueError('No retained invocation evidence')
        with patch.object(baseline.subprocess, 'run', return_value=NS(stdout=self.state)), self.assertRaises(ValueError):
            baseline.inactive_ancestors()


if __name__ == '__main__': unittest.main()
