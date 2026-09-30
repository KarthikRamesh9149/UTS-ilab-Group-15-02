"""Local files/locks/imports and fake Docker, not a native image qualification."""
import ast
import asyncio
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matched_repeat_images as images
import matched_repeat_policy as policy
import matched_repeat_session as session
import test_matched_repeat_session as fixtures
from test_matched_repeat_policy import predecessors

STAGE = Path(__file__).resolve().parent
PARENT = 'sha256:' + '1' * 64
GUARD = 'sha256:' + '2' * 64
GATEWAY = 'sha256:' + '3' * 64


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.q = q = fixtures.SessionTests('runTest'); q.setUp(); self.addCleanup(q.doCleanups)
        self.root = q.root; self.rt = q.f.runtime
        # Real allowlisted source bytes in a temporary synthetic ancestor tree.
        # All native prerequisites remain mocked, never fabricated for real admission.
        for name in (*images.IMAGE_FILES, images.DOCKERFILE):
            q.actual[name] = q.write('stage2/' + name, (STAGE / name).read_bytes())
            if name not in policy.REQUIRED_SOURCE_FILES:
                q.f.final['sources'][name] = q.actual[name]
            if name in q.f.original['sources'] and name not in policy.INHERITED_BASELINE_DELTAS:
                q.f.original['sources'][name] = q.actual[name]
        q.f.original.update(gateway_image=PARENT, guard_image=GUARD)
        q.f.final['sources_sha256'] = policy.fingerprint(q.f.final['sources'])
        for key, value in (('ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(q.f.original)),
                ('CUSTOM_FINAL_QUALIFICATION_SHA256', policy.fingerprint(q.f.final)),
                ('CUSTOM_FINAL_SOURCES_SHA256', q.f.final['sources_sha256'])):
            self.enterContext(patch.object(policy, key, value))
        for name, value, anchor in ((policy.BASELINE_FILE, q.f.original, 'ORIGINAL_FILE_SHA256'),
                (policy.FINAL_FILE, q.f.final, 'FINAL_FILE_SHA256')):
            self.enterContext(patch.object(session.baseline, anchor, q.private(name, value)))
        q.f.predecessor = predecessors(q.f.manifest, 'terminus-2')
        q.pred['predecessors'] = deepcopy(q.f.predecessor)
        for record in (q.pred, q.old, q.library, q.host):
            record['original_qualification_sha256'] = policy.fingerprint(q.f.original)
            record['custom_final_qualification_sha256'] = policy.fingerprint(q.f.final)
            record['sources_sha256' if record is q.host else 'current_sources_sha256'] = policy.fingerprint(q.actual)
        q.host['sources'] = deepcopy(q.actual)
        q.host['source_transition'] = policy.source_transition(q.f.original, q.f.final, q.actual)
        for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE, images.INTENT, images.RESULT):
            (self.rt / name).unlink()  # Temporary synthetic fixture only.
        self.native = dict(Id=PARENT, Os='linux', Architecture='amd64',
            RootFS=dict(Type='layers', Layers=['sha256:' + 'a' * 64]),
            Config=dict(Entrypoint=['python', '/study/stage2/retry_gateway.py'], Env=['LANG=C.UTF-8'],
                OnBuild=None, Volumes=None, WorkingDir='/study/stage2'))
        self.guard = dict(deepcopy(self.native), Id=GUARD)
        self.gateway = dict(deepcopy(self.native), Id=GATEWAY)
        self.gateway['RootFS']['Layers'].append('sha256:' + 'b' * 64)
        self.gateway['Config']['Entrypoint'] = images.ENTRYPOINT[:]
        self.tagged = False; self.commands = []; self.contexts = []; self.report = None
        self.docker = self.enterContext(patch.object(images, '_command', side_effect=self.command))

    def command(self, root, *args, data=None):
        self.assertEqual(root, self.root); self.assertTrue(self.q.locked)
        images._config(root)
        self.commands.append(args)
        if args[:2] == ('image', 'inspect'):
            reference = args[2]
            value = (self.native if reference.startswith('uts-matched-repeat-parent-') else
                {PARENT:self.native, GUARD:self.guard, GATEWAY:self.gateway}[reference])
            return json.dumps([value])
        if args[:2] == ('image', 'ls'):
            return PARENT + '\n' if self.tagged else ''
        if args[:2] == ('image', 'tag'):
            self.assertEqual(args[2], PARENT); self.tagged = True; return ''
        if args[0] == 'build':
            self.assertIsInstance(data, bytes); self.contexts.append(data); return GATEWAY + '\n'
        if args[:2] == ('container', 'ls'):
            return ''
        if args[0] == 'run':
            expected = {name:self.q.actual[name] for name in images.IMAGE_FILES}
            return json.dumps(self.report if self.report is not None else dict(installed=expected,
                loaded={n:expected[n + '.py'] for n in ('matched_repeat_gateway', 'matched_repeat_fixture', 'retry_gateway')},
                import_only=True, live_api_calls=0))
        self.fail('Unexpected Docker operation: ' + repr(args))

    async def build(self):
        with self.q.open() as active:
            return images.build(active)

    def failure(self, expression=''):
        with self.assertRaisesRegex((ValueError, RuntimeError, OSError), expression):
            asyncio.run(self.build())
        if (self.rt / images.INTENT).exists():
            self.assertTrue((self.rt / images.FAILURE).is_file())
        self.assertFalse((self.rt / images.RESULT).exists())

    def test_build_uses_live_session_original_parent_and_exact_private_context(self):
        result = asyncio.run(self.build())
        self.assertEqual(result['gateway_image'], GATEWAY)
        self.assertEqual(result['inputs']['parent_gateway_image'], PARENT)
        self.assertEqual(result['inputs']['guard_image'], GUARD)
        for name in ('paid_launch_ready', 'repeat_execution_qualified', 'historical_installed_bytes_attested'):
            self.assertFalse(result[name])
        self.assertEqual(result['live_api_calls'], 0)
        self.assertEqual(len(self.contexts), 1)
        with tarfile.open(fileobj=io.BytesIO(self.contexts[0])) as archive:
            self.assertEqual(set(archive.getnames()), {*images.COPY_FILES, 'Dockerfile'})
            self.assertTrue(all(m.isfile() and m.mode == 0o644 for m in archive.getmembers()))
            self.assertEqual(archive.extractfile('Dockerfile').read(), images._dockerfile())
            for name in images.COPY_FILES:
                self.assertEqual(archive.extractfile(name).read(), (self.root / 'stage2' / name).read_bytes())
        build = next(c for c in self.commands if c[0] == 'build')
        self.assertIn('--pull=false', build); self.assertIn('--network=none', build); self.assertEqual(build[-1], '-')
        run = next(c for c in self.commands if c[0] == 'run')
        for flag in ('--network=none', '--read-only', '--cap-drop=ALL', '-I', '-B', '--rm'):
            self.assertIn(flag, run)
        self.assertNotIn('-v', run); self.assertNotIn('--env', run)
        self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
        self.q.auth.assert_called_once(); self.q.old_auth.assert_called_once()
        self.q.process.assert_not_called()
        for name in (images.INTENT, images.RESULT):
            self.assertEqual((self.rt / name).stat().st_mode & 0o777, 0o600)

    def test_existing_build_is_verified_with_fresh_session_without_rebuild(self):
        result = asyncio.run(self.build()); count = len(self.contexts)
        async def verify():
            with self.q.open() as active: return images.verify(active)
        self.assertEqual(asyncio.run(verify()), result)
        self.assertEqual(len(self.contexts), count)
        self.assertEqual(self.q.auth.call_count, 2); self.assertEqual(self.q.old_auth.call_count, 2)

    def test_saved_closed_constructed_and_cross_task_sessions_cannot_build(self):
        for value in ({}, session._Session()):
            with self.assertRaises(ValueError): images.build(value)
        async def checks():
            with self.q.invalidated() as active:
                saved = session.describe(active)
                with self.assertRaises(ValueError): images.build(saved)
                async def child(): return images.build(active)
                with self.assertRaisesRegex(ValueError, 'async tasks'): await asyncio.create_task(child())
            with self.assertRaises(ValueError): images.build(active)
        asyncio.run(checks()); self.docker.assert_not_called()

    def test_process_and_thread_change_are_refused(self):
        async def checks():
            for target, attribute, label in ((session.os, 'getpid', 'processes'),
                    (session.threading, 'get_ident', 'threads')):
                with self.q.invalidated() as active:
                    with patch.object(target, attribute, return_value=-1), self.assertRaisesRegex(ValueError, label):
                        images.build(active)
        asyncio.run(checks()); self.docker.assert_not_called()

    def test_sync_and_non_main_thread_service_invocation_are_refused(self):
        with self.q.invalidated() as active:
            with patch.object(session, '_task', return_value=None), self.assertRaisesRegex(ValueError, 'async tasks'):
                images.build(active)
        async def check():
            with self.q.invalidated() as active, patch.object(threading, 'main_thread', return_value=object()):
                with self.assertRaisesRegex(ValueError, 'threads'): images.build(active)
        asyncio.run(check()); self.docker.assert_not_called()

    def test_active_ancestor_or_stop_prevents_any_image_command(self):
        self.q.inactive.side_effect = ValueError('Active custom final')
        self.failure('Active custom final'); self.docker.assert_not_called()
        self.q.inactive.side_effect = None
        self.q.private('operator-stop-request.json', dict(automatic_resume=False))
        self.failure(); self.docker.assert_not_called()

    def test_retained_intent_qualification_registration_dispatch_and_attempts_refuse_rebuild(self):
        for name in (images.INTENT, images.RESULT, images.FAILURE, images.CONFIG,
                policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE, 'matched-repeat-dispatch.json',
                'matched-repeat-dispatch-result.json', 'matched-repeat-dispatch-failure.json',
                'scored-trials', 'scored-attempts'):
            path = self.rt / name; path.write_bytes(b'Preserve retained synthetic fixture')
            async def check():
                with self.q.open() as active:
                    with self.assertRaises(ValueError): images.build(active)
            with self.subTest(name=name): asyncio.run(check())
            self.assertEqual(path.read_bytes(), b'Preserve retained synthetic fixture'); path.unlink()
        self.docker.assert_not_called()

    def test_rebuild_refused_for_both_same_and_fresh_session(self):
        async def check():
            with self.q.open() as active:
                images.build(active)
                with self.assertRaisesRegex(ValueError, 'automatic rebuild'): images.build(active)
        asyncio.run(check())
        with self.assertRaisesRegex(ValueError, 'automatic rebuild'): asyncio.run(self.build())
        self.assertEqual(len(self.contexts), 1)

    def test_parent_config_trigger_or_volume_refused_without_build(self):
        self.native['Config']['OnBuild'] = ['RUN false']
        self.failure('build triggers'); self.assertEqual(self.contexts, [])

    def test_parent_volume_refused_without_build(self):
        self.native['Config']['Volumes'] = {'/persistent': {}}
        self.failure('implicit volumes'); self.assertEqual(self.contexts, [])

    def test_foreign_parent_tag_is_not_overwritten(self):
        original = self.command
        self.docker.side_effect = lambda root, *args, **kw: (GUARD if args[:2] == ('image', 'ls')
            else original(root, *args, **kw))
        self.failure('mismatched repeat parent tag')
        self.assertFalse(any(c[:2] == ('image', 'tag') for c in self.commands))

    def test_existing_matching_parent_tag_is_reused_without_retagging(self):
        self.tagged = True; asyncio.run(self.build())
        self.assertFalse(any(c[:2] == ('image', 'tag') for c in self.commands))

    def test_layer_or_config_drift_is_refused(self):
        self.gateway['RootFS']['Layers'][0] = 'sha256:' + 'c' * 64
        self.failure('original base'); self.assertFalse(any(c[0] == 'run' for c in self.commands))

    def test_non_entrypoint_configuration_changes_are_refused(self):
        self.gateway['Config']['Env'].append('CHANGED=1')
        self.failure('configuration')

    def test_linux_legacy_flag_omission_keeps_actual_raw_metadata_bound(self):
        self.native['Config']['ArgsEscaped'] = True
        result = asyncio.run(self.build())
        self.assertEqual(result['observations']['parent_metadata_sha256'], policy.fingerprint(self.native))
        self.assertEqual(result['observations']['gateway_metadata_sha256'], policy.fingerprint(self.gateway))
        self.assertNotIn('ArgsEscaped', self.gateway['Config'])
        async def verify():
            with self.q.open() as active:
                return images.verify(active)
        self.assertEqual(asyncio.run(verify()), result)

    def test_compatibility_does_not_accept_null_numeric_or_other_config_drift(self):
        self.native['Config']['ArgsEscaped'] = True
        self.assertTrue(images._same_linux_config(self.native, self.gateway))
        for value in (False, None, 0, 1, 'true', [], {}):
            changed = deepcopy(self.gateway); changed['Config']['ArgsEscaped'] = value
            with self.subTest(value=value):
                self.assertFalse(images._same_linux_config(self.native, changed))
        for key, value in (('Cmd', ['unexpected']), ('Env', ['CHANGED=1']),
                ('User', 'other'), ('WorkingDir', '/other'), ('Entrypoint', ['sh']),
                ('OnBuild', ['RUN unexpected']), ('Volumes', {'/data': {}})):
            changed = deepcopy(self.gateway); changed['Config'][key] = value
            with self.subTest(key=key):
                self.assertFalse(images._same_linux_config(self.native, changed))
        for key, value in (('Os', 'windows'), ('Architecture', 'arm64')):
            changed = deepcopy(self.gateway); changed[key] = value
            with self.subTest(key=key):
                self.assertFalse(images._same_linux_config(self.native, changed))

    def test_false_or_numeric_parent_does_not_get_omission_exception(self):
        for value in (False, None, 0, 1, 'true'):
            self.native['Config']['ArgsEscaped'] = value
            with self.subTest(value=value):
                self.assertFalse(images._same_linux_config(self.native, self.gateway))

    def test_raw_legacy_flag_change_after_build_still_refuses_verification(self):
        self.native['Config']['ArgsEscaped'] = True
        asyncio.run(self.build())
        self.gateway['Config']['ArgsEscaped'] = True
        async def verify():
            with self.q.invalidated() as active:
                with self.assertRaises(ValueError): images.verify(active)
        asyncio.run(verify())
        self.assertEqual(len(self.contexts), 1)

    def test_unexpected_image_identity_or_architecture_is_refused(self):
        self.guard['Architecture'] = 'arm64'; self.failure('native Linux')
        self.assertEqual(self.contexts, [])

    def test_installed_source_mismatch_is_refused(self):
        self.report = dict(installed={}, loaded={}, import_only=True, live_api_calls=0)
        self.failure('installed source')
        self.assertEqual(json.loads((self.rt / images.FAILURE).read_bytes())['stage'],
            'verify_built_gateway_image')

    def test_unchanged_base_helpers_are_observed_not_copied(self):
        result = asyncio.run(self.build())
        helpers = {'calibrate_tokenizer.py', 'extended_token_calibration.py', 'setup_probe.py'}
        self.assertTrue(helpers <= result['observations']['installed_sources'].keys())
        self.assertTrue(helpers <= policy.REQUIRED_SOURCE_FILES)
        with tarfile.open(fileobj=io.BytesIO(self.contexts[0])) as archive:
            self.assertFalse(helpers & set(archive.getnames()))

    def test_image_metadata_drift_during_probe_is_refused(self):
        original = self.command
        def mutate(root, *args, **kw):
            result = original(root, *args, **kw)
            if args[0] == 'run': self.guard['Config']['Env'].append('CHANGED=1')
            return result
        self.docker.side_effect = mutate; self.failure('changed during inspection')
        self.assertEqual(json.loads((self.rt / images.FAILURE).read_bytes())['observed_gateway_image'], GATEWAY)

    def test_duplicate_docker_metadata_keys_are_refused(self):
        self.docker.side_effect = lambda *a, **kw: '[{"Id": "a", "Id": "b"}]'
        self.failure('Duplicate'); self.assertEqual(self.contexts, [])

    def test_symlinked_source_refused_before_docker(self):
        path = self.root / 'stage2/matched_repeat_gateway.py'
        path.unlink(); path.symlink_to(STAGE / path.name)
        self.failure(); self.docker.assert_not_called()

    def test_source_mutation_after_build_refuses_completion_and_invalidates_handle(self):
        original = self.command
        def mutate(root, *args, **kw):
            result = original(root, *args, **kw)
            if args[0] == 'build': (root / 'stage2/matched_repeat_images.py').write_bytes(b'Changed')
            return result
        self.docker.side_effect = mutate; self.failure()

    def test_intent_mutation_during_build_is_refused(self):
        original = self.command
        def mutate(root, *args, **kw):
            result = original(root, *args, **kw)
            if args[0] == 'build': (self.rt / images.INTENT).write_text('{}')
            return result
        self.docker.side_effect = mutate; self.failure('input changed')

    def test_failure_records_type_only_and_never_retries_or_prunes(self):
        self.docker.side_effect = RuntimeError('PRIVATE_DIAGNOSTIC_MUST_NOT_BE_RETAINED')
        self.failure()
        text = (self.rt / images.FAILURE).read_text()
        self.assertNotIn('PRIVATE_DIAGNOSTIC', text)
        self.assertEqual(json.loads(text)['exception_type'], 'RuntimeError')
        self.assertEqual(json.loads(text)['stage'], 'prepare_fixed_image_context')
        self.assertIsNone(json.loads(text)['observed_gateway_image'])
        self.assertEqual(self.docker.call_count, 1)
        with self.assertRaises(ValueError): asyncio.run(self.build())
        self.assertEqual(self.docker.call_count, 1)

    def test_failed_build_invalidates_its_session(self):
        self.docker.side_effect = RuntimeError('Failed')
        async def check():
            with self.q.invalidated() as active:
                with self.assertRaises(RuntimeError): images.build(active)
                with self.assertRaises(ValueError): session.describe(active)
        asyncio.run(check())

    def test_retained_probe_container_is_not_removed_or_replaced(self):
        original = self.command
        self.docker.side_effect = lambda root, *args, **kw: ('retained' if args[:2] == ('container', 'ls')
            else original(root, *args, **kw))
        self.failure('Retained image inspection'); self.assertFalse(any(c[0] == 'run' for c in self.commands))

    def test_probe_cleanup_is_checked(self):
        original = self.command; reads = []
        def leftover(root, *args, **kw):
            if args[:2] == ('container', 'ls'):
                reads.append(1); return '' if len(reads) == 1 else 'retained'
            return original(root, *args, **kw)
        self.docker.side_effect = leftover; self.failure('not removed')

    def test_verification_rereads_actual_private_evidence_and_images(self):
        asyncio.run(self.build()); self.gateway['Config']['WorkingDir'] = '/changed'
        async def check():
            with self.q.invalidated() as active:
                with self.assertRaises(ValueError): images.verify(active)
                with self.assertRaises(ValueError): session.describe(active)
        asyncio.run(check()); self.assertEqual(len(self.contexts), 1)

    def test_symlinked_or_public_build_record_cannot_be_verified(self):
        asyncio.run(self.build()); path = self.rt / images.RESULT; raw = path.read_bytes()
        async def check():
            with self.q.invalidated() as active:
                with self.assertRaises(ValueError): images.verify(active)
        path.chmod(0o644); asyncio.run(check()); path.chmod(0o600)
        path.unlink(); other = self.rt / 'synthetic-copy.json'; other.write_bytes(raw); other.chmod(0o600)
        path.symlink_to(other); asyncio.run(check())

    def test_config_cannot_contain_credentials_or_be_symlinked(self):
        path = images._config(self.root, create=True)
        (path / 'config.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'credential-free'): images._config(self.root)
        (path / 'config.json').unlink(); path.rmdir(); path.symlink_to(self.rt)
        with self.assertRaises(ValueError): images._config(self.root)

    def test_real_command_builder_clears_environment_and_pins_local_daemon(self):
        images._config(self.root, create=True)
        # Call the unpatched function retained before fixture patching.
        command = self._command_original
        self.q.process.side_effect = None
        self.q.process.return_value = SimpleNamespace(returncode=0, stdout=b'{}', stderr=b'')
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'DO_NOT_FORWARD', 'DOCKER_HOST':'tcp://untrusted'}):
            self.assertEqual(command(self.root, 'image', 'inspect', PARENT), '{}')
        args, kw = self.q.process.call_args
        self.assertIn('--host=unix:///var/run/docker.sock', args[0])
        self.assertEqual(kw['env'], {'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8', 'DOCKER_BUILDKIT':'0'})
        self.q.process.return_value = SimpleNamespace(returncode=1, stdout=b'', stderr=b'SECRET')
        with self.assertRaisesRegex(RuntimeError, '^Pinned local Docker command failed$'):
            command(self.root, 'image', 'inspect', PARENT)

    _command_original = staticmethod(images._command)


class ContextAndProbeTests(unittest.TestCase):
    def test_exact_static_import_closure_and_inventory(self):
        seen = set(); todo = ['matched_repeat_gateway', 'matched_repeat_fixture']
        while todo:
            name = todo.pop()
            if name in seen: continue
            seen.add(name)
            for node in ast.walk(ast.parse((STAGE / (name + '.py')).read_text())):
                names = ([node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module
                    else [n.name.split('.')[0] for n in node.names] if isinstance(node, ast.Import) else [])
                todo.extend(n for n in names if (STAGE / (n + '.py')).is_file())
        self.assertEqual({name + '.py' for name in seen}, set(images.IMAGE_FILES))
        self.assertTrue({'matched_repeat_images.py', 'test_matched_repeat_images.py', images.DOCKERFILE}
            <= policy.REQUIRED_SOURCE_FILES)
        self.assertIn('test_matched_repeat_images', policy.TEST_MODULES)
        self.assertEqual((STAGE / images.DOCKERFILE).read_bytes(), images._dockerfile())

    def test_real_source_context_excludes_credentials_archives_and_native_tools(self):
        sources = {name:hashlib.sha256((STAGE / name).read_bytes()).hexdigest()
            for name in (*images.IMAGE_FILES, images.DOCKERFILE)}
        raw = images._context(STAGE.parent, sources)
        self.assertEqual(raw, images._context(STAGE.parent, sources))
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            self.assertEqual(len(archive.getmembers()), len(images.COPY_FILES) + 1)
            self.assertFalse(any(name.startswith(('.runtime/', 'native_agents', 'scored_trial', 'custom_tools'))
                for name in archive.getnames()))

    def test_even_source_bound_unsafe_dockerfile_is_not_a_build_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root / 'stage2/fixtures').mkdir(parents=True)
            sources = {}
            for name in (*images.COPY_FILES, images.DOCKERFILE):
                raw = b'FROM scratch\nCOPY . /\n' if name == images.DOCKERFILE else (STAGE / name).read_bytes()
                (root / 'stage2' / name).write_bytes(raw); sources[name] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, 'fixed allowlisted'):
                images._context(root, sources)

    def probe(self, folder, sources):
        return subprocess.run([sys.executable, '-I', '-B', '-X',
            'pycache_prefix=' + str(folder / 'absent-cache'), '-c', images._probe_script(sources, str(folder))],
            capture_output=True, text=True, env={'PATH':'/usr/bin:/bin'})

    def test_actual_lean_import_from_temporary_context_without_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve(); sources = {}
            for name in images.IMAGE_FILES:
                raw = (STAGE / name).read_bytes(); (folder / name).write_bytes(raw)
                sources[name] = hashlib.sha256(raw).hexdigest()
            result = self.probe(folder, sources)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout); self.assertEqual(report['installed'], sources)
            self.assertIn('matched_repeat_gateway', report['loaded']); self.assertEqual(report['live_api_calls'], 0)
            self.assertEqual(set(p.name for p in folder.iterdir()), set(images.IMAGE_FILES))
            (folder / 'matched_repeat_gateway.py').write_text('raise RuntimeError("changed")')
            self.assertNotEqual(self.probe(folder, sources).returncode, 0)

    def test_probe_refuses_cached_or_symlinked_sources_and_import_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve(); sources = {}
            for name in images.IMAGE_FILES:
                raw = (STAGE / name).read_bytes(); (folder / name).write_bytes(raw)
                sources[name] = hashlib.sha256(raw).hexdigest()
            (folder / 'absent-cache').mkdir()
            self.assertNotEqual(self.probe(folder, sources).returncode, 0)
            (folder / 'absent-cache').rmdir()
            path = folder / 'matched_repeat_gateway.py'; path.unlink(); path.symlink_to(STAGE / path.name)
            self.assertNotEqual(self.probe(folder, sources).returncode, 0); path.unlink()
            path.write_text('import socket\nsocket.socket()\n')
            sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            value = self.probe(folder, sources)
            self.assertNotEqual(value.returncode, 0); self.assertIn('forbids external effects', value.stderr)
