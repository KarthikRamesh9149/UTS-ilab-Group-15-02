"""Real local evidence and lean imports; native Docker/host observations mocked."""
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
import unittest
from unittest.mock import patch

import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_session as session
import no_cutoff_recovery_files as files
import test_no_cutoff_recovery_execution as local
import test_no_cutoff_recovery_session as fixtures
from test_no_cutoff_recovery_runtime import save

STAGE = Path(__file__).resolve().parent
GATEWAY = 'sha256:' + '3' * 64


class ImageTests(local.LocalFiles, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.q = q = fixtures.SessionTests('runTest')
        q._callCleanup = lambda function, *args, **kwargs: function(*args, **kwargs)
        self.addCleanup(q.doCleanups); q.setUp()
        self.protect(q.root); self.rt = q.root / '.runtime/stage2'
        q.f.final.update(gateway_image='sha256:'+'1'*64,guard_image='sha256:'+'2'*64)
        raw=json.dumps(q.f.final).encode()
        self.enterContext(patch.object(policy,'ORIGINAL_QUALIFICATION',policy.fingerprint(q.f.final)))
        self.enterContext(patch.object(policy,'ORIGINAL_QUALIFICATION_FILE_SHA256',hashlib.sha256(raw).hexdigest()))
        save(self.root,'.runtime/stage2/'+policy.ORIGINAL_FILE,raw)
        q.host['original_qualification_sha256']=policy.fingerprint(q.f.final)
        for name in (*images.IMAGE_FILES, images.DOCKERFILE):
            raw = (STAGE / name).read_bytes(); save(self.root, 'stage2/' + name, raw)
            q.bound[name] = hashlib.sha256(raw).hexdigest()
        q.original = session._inputs(self.root)
        q.pred.update(current_sources_sha256=policy.fingerprint(q.bound), copied_files=q.original['files'])
        q.host.update(sources=q.bound, sources_sha256=policy.fingerprint(q.bound))
        self.parent = q.f.final['gateway_image']; self.guard_id = q.f.final['guard_image']
        for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE):
            (self.rt / name).unlink()  # Only this synthetic temporary fixture.
        self.native = dict(Id=self.parent, Os='linux', Architecture='amd64',
            RootFS=dict(Type='layers', Layers=['sha256:' + 'a' * 64]),
            Config=dict(Entrypoint=['python', '/study/stage2/no_cutoff_final_gateway.py'],
                Env=['LANG=C.UTF-8'], OnBuild=None, Volumes=None, WorkingDir='/study/stage2'))
        self.guard = dict(deepcopy(self.native), Id=self.guard_id)
        self.gateway = dict(deepcopy(self.native), Id=GATEWAY)
        self.gateway['RootFS']['Layers'].append('sha256:'+'c'*64)
        self.gateway['Config']['Entrypoint'] = images.ENTRYPOINT[:]
        self.tagged = False; self.commands = []; self.contexts = []; self.report = None
        self.enterContext(patch.object(images, '_command', side_effect=self.command))

    def command(self, root, *args, data=None):
        self.assertEqual(root, self.root)
        self.assertTrue(all(self.q.is_locked(p) for p in self.q.paths))
        images._config(root); self.commands.append(args)
        if args[:2] == ('image','inspect'):
            value = self.native if args[2].startswith('uts-no-cutoff-recovery-parent-') else {
                self.parent:self.native, self.guard_id:self.guard, GATEWAY:self.gateway}[args[2]]
            return json.dumps([value])
        if args[:2] == ('image','ls'): return self.parent+'\n' if self.tagged else ''
        if args[:2] == ('image','tag'):
            self.assertEqual(args[2],self.parent); self.tagged=True; return ''
        if args[0] == 'build': self.contexts.append(data); return GATEWAY+'\n'
        if args[:2] == ('container','ls'): return ''
        if args[0] == 'run':
            expected = {n:self.q.bound[n] for n in images.IMAGE_FILES}
            return json.dumps(self.report if self.report is not None else dict(installed=expected,
                loaded={n:expected[n+'.py'] for n in ('no_cutoff_recovery_gateway','no_cutoff_recovery_fixture','retry_gateway')},
                import_only=True, live_api_calls=0))
        self.fail('Unexpected Docker operation: '+repr(args))

    def open(self): return session.open_session(self.q.stream)

    async def test_build_verify_and_binding_use_one_context_original_parent_and_actual_private_files(self):
        with self.open() as active:
            result = images.build(active)
            self.assertEqual(images.verify(active),result)
            binding = images.qualification_binding(active)
        self.assertEqual(len(self.contexts),1)
        self.assertEqual(binding['gateway_image'],GATEWAY)
        self.assertEqual(binding['guard_image'],self.guard_id)
        self.assertEqual(binding['image_build_sha256'],policy.fingerprint(result))
        self.assertEqual(set(binding['image_evidence_files']), {'.runtime/stage2/'+n for n in (images.INTENT,images.RESULT)})
        with tarfile.open(fileobj=io.BytesIO(self.contexts[0])) as archive:
            self.assertEqual(set(archive.getnames()),set(images.COPY_FILES)|{'Dockerfile'})
            self.assertTrue(all(m.isfile() and m.mode==0o644 for m in archive.getmembers()))
        build = next(c for c in self.commands if c[0]=='build')
        self.assertIn('--pull=false',build); self.assertIn('--network=none',build)
        run = next(c for c in self.commands if c[0]=='run')
        for option in ('--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges'):
            self.assertIn(option,run)
        for name in (images.INTENT,images.RESULT): self.assertEqual((self.rt/name).stat().st_mode & 0o777,0o600)
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['recovery_execution_qualified'])
        with self.open() as active:
            with self.assertRaises(ValueError): images.build(active)

    async def test_saved_or_child_task_cannot_build(self):
        with self.assertRaises(ValueError): images.build({'paid_launch_ready':True})
        with self.assertRaises(ValueError), self.open() as active:
            async def child(): return images.build(active)
            with self.assertRaises(ValueError): await asyncio.create_task(child())

    async def test_observed_linux_legacy_args_escaped_omission_preserves_raw_identity(self):
        self.native['Config']['ArgsEscaped'] = True
        with self.open() as active:
            result = images.build(active)
            self.assertEqual(images.verify(active), result)
        self.assertEqual(result['observations']['parent_metadata_sha256'], policy.fingerprint(self.native))
        self.assertEqual(result['observations']['gateway_metadata_sha256'], policy.fingerprint(self.gateway))
        self.assertNotIn('ArgsEscaped', self.gateway['Config'])

    async def test_windows_null_numeric_and_wider_config_changes_are_not_normalized(self):
        self.native['Config']['ArgsEscaped'] = True
        self.assertTrue(images._same_linux_config(self.native, self.gateway))
        for value in (False, None, 0, 1, 'true', [], {}):
            with self.subTest(value=value):
                changed = deepcopy(self.gateway)
                changed['Config']['ArgsEscaped'] = value
                self.assertFalse(images._same_linux_config(self.native, changed))
        for key, value in (('Cmd', ['unexpected']), ('Env', ['CHANGED=1']),
                ('User', 'other'), ('WorkingDir', '/other'), ('Entrypoint', ['sh']),
                ('OnBuild', ['RUN unexpected']), ('Volumes', {'/data': {}})):
            with self.subTest(key=key):
                changed = deepcopy(self.gateway); changed['Config'][key] = value
                self.assertFalse(images._same_linux_config(self.native, changed))
        for key, value in (('Os', 'windows'), ('Architecture', 'arm64')):
            changed = deepcopy(self.gateway); changed[key] = value
            self.assertFalse(images._same_linux_config(self.native, changed))

    async def test_false_parent_omission_is_not_the_observed_exception(self):
        self.native['Config']['ArgsEscaped'] = False
        self.assertFalse(images._same_linux_config(self.native, self.gateway))
        self.native['Config']['ArgsEscaped'] = 0
        self.gateway['Config']['ArgsEscaped'] = False
        self.assertFalse(images._same_linux_config(self.native, self.gateway))

    async def test_later_args_escaped_drift_still_refuses_bound_build(self):
        self.native['Config']['ArgsEscaped'] = True
        with self.open() as active: images.build(active)
        self.gateway['Config']['ArgsEscaped'] = True
        with self.assertRaises(ValueError), self.open() as active:
            images.verify(active)

    async def test_parent_build_triggers_refuse_without_build(self):
        self.native['Config']['OnBuild']=['RUN unapproved']
        with self.assertRaises(ValueError), self.open() as active: images.build(active)
        self.assertFalse(self.contexts); self.assertTrue((self.rt/images.FAILURE).exists())
        self.assertEqual(json.loads((self.rt/images.FAILURE).read_bytes())['stage'], 'prepare_fixed_image_context')

    async def test_installed_source_mismatch_retains_failure_not_qualification(self):
        self.report = dict(installed={},loaded={},import_only=True,live_api_calls=0)
        with self.assertRaises(ValueError), self.open() as active: images.build(active)
        self.assertTrue((self.rt/images.FAILURE).exists()); self.assertFalse((self.rt/images.RESULT).exists())
        self.assertEqual(json.loads((self.rt/images.FAILURE).read_bytes())['stage'], 'verify_built_gateway_image')

    async def test_extra_layer_or_changed_configuration_refuses(self):
        self.gateway['RootFS']['Layers'].append('sha256:'+'d'*64)
        with self.assertRaises(ValueError), self.open() as active: images.build(active)

    async def test_same_byte_intent_replacement_during_build_refuses(self):
        real = images._observations
        def replaced(*args):
            value = real(*args); path=self.rt/images.INTENT; raw=path.read_bytes()
            path.rename(path.with_suffix('.retained')); save(self.root,str(path.relative_to(self.root)),raw)
            return value
        with patch.object(images,'_observations',side_effect=replaced), self.assertRaises(ValueError), self.open() as active:
            images.build(active)
        self.assertFalse((self.rt/images.RESULT).exists())

    async def test_same_byte_producer_replacement_across_binding_refuses(self):
        with self.open() as active: images.build(active)
        real=images.verify
        def replaced(active):
            value=real(active); path=self.rt/images.RESULT; raw=path.read_bytes()
            path.rename(path.with_suffix('.retained')); save(self.root,str(path.relative_to(self.root)),raw)
            return value
        with patch.object(images,'verify',side_effect=replaced), self.assertRaises(ValueError), self.open() as active:
            images.qualification_binding(active)

    async def test_failed_existing_build_never_admits_even_if_result_remains(self):
        with self.open() as active: images.build(active)
        files.save(self.rt/images.FAILURE,{'synthetic_failure':True})
        with self.assertRaises(ValueError), self.open() as active: images.qualification_binding(active)

    async def test_local_isolated_effect_guarded_actual_lean_import(self):
        # This is a real local child, not a Docker/native observation.
        code=images._probe_script(self.q.bound,base=str(self.root/'stage2'))
        environment=dict(PATH='/usr/bin:/bin',PYTHON_DOTENV_DISABLED='1',
            LITELLM_LOCAL_MODEL_COST_MAP='True',LITELLM_MODE='PRODUCTION')
        child=subprocess.run([sys.executable,'-I','-B','-X',
            'pycache_prefix='+str(self.root/'.absent-cache'),'-c',code],
            env=environment,capture_output=True,text=True)
        self.assertEqual(child.returncode,0,child.stderr)
        report=json.loads(child.stdout)
        self.assertEqual(report['installed'],{n:self.q.bound[n] for n in images.IMAGE_FILES})
        self.assertTrue(report['import_only']); self.assertEqual(report['live_api_calls'],0)
        self.assertFalse((self.root/'.absent-cache').exists())


if __name__=='__main__': unittest.main()
