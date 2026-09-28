"""Final producer sequence with fake native readers and real temporary files."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qualify_no_cutoff_final as qualifier
import no_cutoff_final_policy as policy
import no_cutoff_final_runtime as identity
from scored_gateway import durable_json, private_directory
from test_no_cutoff_final_policy import Fixture


class ProducerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.f = Fixture(self, self.root)
        self.rt = self.f.runtime
        (self.rt / policy.QUALIFICATION_FILE).unlink()
        (self.rt / policy.REGISTRATION_FILE).unlink()
        (self.root / 'stage2/input_manifest.json').write_bytes((Path(__file__).parent / 'input_manifest.json').read_bytes())
        self.enterContext(patch.object(identity, 'DEPLOYMENT', self.root))

    def test_completed_proof_registry_started_attempt_and_stop_refuse_before_audit(self):
        for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE,
                'operator-stop-request.json', 'scored-trials/started/started.json'):
            path = self.rt / name; private_directory(path.parent); durable_json(path, {})
            with patch.object(qualifier.evidence, 'authenticate') as auth:
                with self.assertRaises(ValueError): qualifier.qualify(self.root)
                auth.assert_not_called()
            path.unlink()

    def test_wrong_root_refused_without_native_reads(self):
        with patch.object(identity, 'DEPLOYMENT', self.root / 'other'), \
                patch.object(qualifier.evidence, 'authenticate') as auth:
            with self.assertRaises(ValueError): qualifier.qualify(self.root)
            auth.assert_not_called()

    def test_authentication_precedes_locks_and_owned_resource_check(self):
        calls = []
        with patch.object(qualifier.evidence, 'authenticate', side_effect=lambda *a: calls.append('authenticate') or {}), \
                patch.object(qualifier, 'lock_all', side_effect=lambda *a: calls.append('lock')), \
                patch.object(qualifier.evidence, 'recheck', side_effect=lambda *a: calls.append('recheck')), \
                patch.object(qualifier, 'docker', return_value='owned'), patch.object(qualifier, 'probe') as probe:
            with self.assertRaisesRegex(ValueError, 'owned'): qualifier.qualify(self.root)
        self.assertEqual(calls, ['authenticate', 'lock', 'recheck']); probe.assert_not_called()

    def test_native_regression_failure_retained_without_passed_proof(self):
        class Failure(unittest.TestCase):
            def runTest(self): self.fail('Synthetic producer test failure')
        folder = private_directory(self.rt / 'regression-fixture')
        with patch.object(qualifier.unittest.defaultTestLoader, 'loadTestsFromNames', return_value=unittest.TestSuite([Failure()])):
            with self.assertRaises(ValueError): qualifier.regression(folder)
        self.assertEqual(json.loads((folder / 'regression.json').read_text())['failures'], 1)
        self.assertTrue((folder / 'regression.txt').is_file())
        self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())

    def test_private_inputs_are_nonreplacing_and_preserve_json_number_types(self):
        path = self.rt / 'private-test.json'
        qualifier.save_once(path, {'value': 1.0}); original = path.read_bytes()
        qualifier.save_once(path, {'value': 1.0})
        with self.assertRaises(ValueError): qualifier.save_once(path, {'value': 1})
        self.assertEqual(path.read_bytes(), original); self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def run_producer(self, *, failed=False, drift=False):
        current = {key: deepcopy(self.f.proof[key]) for key in (
            'sources', 'sources_sha256', 'dependencies', 'python_runtime', 'host_environment')}
        calls = []
        def regression(folder):
            report = deepcopy(self.f.proof['offline'])
            durable_json(folder / 'regression.json', report)
            (folder / 'regression.txt').write_text('Synthetic local test, not native qualification\n')
            return report
        async def probe(root, image, guard, document, mode):
            calls.append(mode)
            case = deepcopy(next(c for c in self.f.proof['synthetic'] if c['mode'] == mode))
            if failed:
                case['status'] = 'failed'; case['checks']['model_revoked'] = False
            folder = private_directory(root / case['runtime_path'])
            durable_json(folder / 'evidence.json', case)
            path = folder / '.runtime/stage2/scored-trials' / ('synthetic-nc-final-' + mode)
            private_directory(path)
            durable_json(path / 'result.json', dict(trial_id='synthetic-nc-final-' + mode, stage='final',
                harness=policy.CONDITION, custom_study=policy.EXPERIMENT, gateway_image_id=image,
                status='interrupted' if mode == 'cancel_setup' else 'verified', model_revoked=not failed,
                containers_removed=True, networks_removed=True, volumes_removed=True,
                verifier_result=None if mode == 'cancel_setup' else {'rewards': {'reward': 1}}))
            return case
        with patch.object(qualifier.evidence, 'authenticate', return_value={'synthetic': True}) as auth, \
                patch.object(qualifier.evidence, 'recheck') as recheck, patch.object(qualifier, 'lock_all'), \
                patch.object(qualifier, 'docker', return_value=''), \
                patch.object(identity, 'inspect', side_effect=[current, {}] if drift else None, return_value=current), \
                patch.object(identity, '_images', side_effect=lambda refs: {ref: {'id': ref} for ref in refs}), \
                patch.object(qualifier, 'build_gateway', return_value=(self.f.proof['gateway_image'], self.f.proof['guard_image'])), \
                patch.object(qualifier, 'regression', side_effect=regression), patch.object(qualifier, 'probe', side_effect=probe), \
                patch('builtins.print'):
            if failed or drift:
                with self.assertRaises(ValueError): qualifier.qualify(self.root)
                self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
            else:
                result = qualifier.qualify(self.root)
                self.assertEqual(result['native_cases'], 3); self.assertEqual(result['live_api_calls'], 0)
                saved = json.loads((self.rt / policy.QUALIFICATION_FILE).read_text())
                self.assertEqual(len(saved['evidence_files']), 8)
                identity.verify_native_files(self.root, saved)
                policy.validate_qualification(self.f.document, self.f.manifest, saved)
                self.assertEqual(saved['candidate_sha256'], policy.fingerprint(self.f.document))
                self.assertEqual(saved['validation_results_sha256'], policy.fingerprint(self.f.document['result_bindings']))
                self.assertEqual(saved['orchestration_changes'], self.f.proof['orchestration_changes'])
                self.assertGreaterEqual(recheck.call_count, 3)
            auth.assert_called_once_with(self.root, self.f.document)
        self.assertEqual(calls, ['tools'] if failed else list(policy.PROBE_MODES))
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
        self.assertFalse((self.rt / 'scored-trials').exists())

    def test_producer_binds_real_output_files_after_mocked_native_cases(self):
        self.run_producer()

    def test_failed_fixture_is_retained_without_running_next_or_granting_qualification(self):
        self.run_producer(failed=True)
        cases = list(self.rt.glob('native-no-cutoff-final-C0-NC-*/evidence.json'))
        self.assertEqual(len(cases), 1); self.assertEqual(json.loads(cases[0].read_text())['status'], 'failed')

    def test_changed_host_or_source_during_rehearsal_does_not_grant_qualification(self):
        self.run_producer(drift=True)


class ImageTests(unittest.TestCase):
    def test_dockerfile_copies_all_bound_image_files_and_has_final_entrypoint(self):
        code = (Path(__file__).parent / 'fixtures/Dockerfile.no-cutoff-final').read_text()
        names = next(line for line in code.splitlines() if line.startswith('COPY ')).split()[1:-1]
        self.assertEqual(set(names), set(qualifier.IMAGE_FILES))
        self.assertIn('"/study/stage2/no_cutoff_final_gateway.py"', code)
        self.assertTrue(set(qualifier.IMAGE_FILES) <= policy.REQUIRED_SOURCE_FILES | policy.development.REQUIRED_SOURCE_FILES
            | {'credit_only_gateway.py', 'retry_gateway.py', 'portable_custom_policy.py', 'portable_final_selection.py',
               'portable_custom_probe.py', 'custom_control.py', 'deadline_custom_contract.py', 'deadline_custom_policy.py',
               'deadline_final_selection.py'})

    def build(self, *, change=None):
        root = Path('/synthetic-final-host')
        parent = dict(gateway_image='sha256:' + 'a' * 64, guard_image='sha256:' + 'b' * 64)
        image = 'sha256:' + 'c' * 64
        old = dict(RootFS={'Layers': ['layer-a']}, Config={'Env': [], 'Entrypoint': ['old']})
        new = dict(RootFS={'Layers': ['layer-a', 'layer-b']}, Config={'Env': [],
            'Entrypoint': ['python', '/study/stage2/no_cutoff_final_gateway.py']})
        sources = dict.fromkeys(qualifier.IMAGE_FILES, 'd' * 64)
        installed = dict(sources)
        if change == 'layers': new['RootFS']['Layers'][0] = 'other'
        elif change == 'config': new['Config']['Env'] = ['changed']
        elif change == 'source': installed['no_cutoff_final_gateway.py'] = 'e' * 64
        commands = []
        def command(*args):
            commands.append(args)
            if args[:2] == ('docker', 'build'): return image
            if args[:2] == ('docker', 'inspect'): return json.dumps([old, new])
            if 'print(json.dumps' in args[-1]: return json.dumps(installed)
            return ''
        with patch.object(qualifier, 'private_read', return_value=parent), patch.object(qualifier, 'command', side_effect=command):
            if change:
                with self.assertRaises(ValueError): qualifier.build_gateway(root, sources)
            else:
                self.assertEqual(qualifier.build_gateway(root, sources), (image, parent['guard_image']))
        return commands

    def test_pinned_layer_preserving_build_has_no_network_or_image_pull(self):
        commands = self.build()
        build = next(c for c in commands if c[:2] == ('docker', 'build'))
        self.assertIn('--pull=false', build); self.assertIn('--network=none', build)
        for call in (c for c in commands if c[:2] == ('docker', 'run')):
            self.assertIn('--network=none', call); self.assertIn('--read-only', call)
        self.assertIn('import no_cutoff_final_gateway, no_cutoff_final_probe', commands[-1])

    def test_drifted_layers_configuration_or_installed_bytes_rejected(self):
        for change in ('layers', 'config', 'source'):
            with self.subTest(change=change): self.build(change=change)


if __name__ == '__main__': unittest.main()
