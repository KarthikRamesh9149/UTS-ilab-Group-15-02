"""Exact admission, no-overlap dispatch and source-bound synthetic evidence."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,AsyncMock

from deadline_custom_agent import agent_factory
from deadline_custom_policy import *
from deadline_custom_study import qualified,register,admit_trial,audited,summary,TEST_MODULES,PROBE_MODES,probe_checks
from run_deadline_custom import dispatch,lock_all
from scored_trial import run_trial
from scored_gateway import private_directory,durable_json
from test_deadline_custom_policy import fixture,parent_fixture,TASKS


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.rt,self.block,self.proof=fixture(self.root)
        self.image='sha256:'+'f'*64

    def proof_images(self):
        self.proof.update(gateway_image=self.image,guard_image=self.image,
            matched_scope={'input_manifest_sha256':INPUT_SHA256,'development_ids':TASKS},
            parent='C0',base_parent=None)
        (self.rt/QUALIFICATION).write_text(json.dumps(self.proof))
        self.block['qualification_sha256']=fingerprint(self.proof)
        block_path(self.rt).write_text(json.dumps(self.block))

    def test_exact_factory_and_admission(self):
        self.proof_images();cell=self.block['cells'][0]
        factory=agent_factory(self.root,'C0')
        args=dict(trial_id=cell['trial_id'],task_id=cell['task_id'],stage='development',factory=factory,
            settings=SETTINGS,gateway_image=self.image,guard_image=self.image)
        with patch('deadline_custom_study.qualified',return_value=self.proof):
            self.assertEqual(admit_trial(self.root,**args),fingerprint(self.block))
            for changes in ({'task_id':'held-out'},{'stage':'final'},
                    {'factory':agent_factory(self.root,'C1')},{'gateway_image':'other'}):
                with self.assertRaises(ValueError):admit_trial(self.root,**(args|changes))

    def test_every_native_case_and_current_dependency_is_required(self):
        current=self.proof|dict(dependencies={'version':'pinned'},parent='C0',base_parent=None)
        proof=current|dict(live_api_calls=0,host_environment={},gateway_image=self.image,guard_image=self.image,
            image_sources_match=True,setup_timeout_seconds=900,
            offline=dict(modules=list(TEST_MODULES),tests=20,passed=True,skipped=0,errors=0,failures=0),
            synthetic=[dict(condition='C3',parent='C0',base_parent=None,mode=m,status='passed',live_api_calls=0,
                checks={k:True for k in probe_checks(m)}) for m in PROBE_MODES])
        with patch('deadline_custom_study.identity',return_value=current),patch('host_environment.snapshot',return_value={}),patch('scored_trial.docker',return_value=self.image):
            for change in ({},{'synthetic':proof['synthetic'][:-1]},{'dependencies':{}},{'live_api_calls':True},
                           {'image_sources_match':False},{'setup_timeout_seconds':9000},
                           {'offline':proof['offline']|{'skipped':1}}):
                (self.rt/QUALIFICATION).write_text(json.dumps(proof|change))
                if not change:self.assertEqual(qualified(self.root),proof)
                else:
                    with self.assertRaises(ValueError):qualified(self.root)

    def test_registration_is_exclusive_idempotent_and_bound_to_parent(self):
        self.proof_images()
        with patch('deadline_custom_study.qualified',return_value=self.proof),patch('deadline_custom_study.verify_parent',return_value=parent_fixture()):
            value=register(self.root);self.assertEqual(value,self.block)
            self.assertEqual(register(self.root),value)
            with patch('deadline_custom_study.qualified',return_value=self.proof|{'sources_sha256':'b'*64}):
                with self.assertRaises(ValueError):register(self.root)

    def test_started_attempt_is_not_replayed(self):
        cell=self.block['cells'][0];folder=private_directory(self.rt/'scored-trials'/cell['trial_id'])
        durable_json(folder/'started.json',cell)
        completed,partial=audited(self.root)
        self.assertFalse(completed);self.assertEqual(partial,[cell['trial_id']])

    def test_no_partial_block_cost_or_runtime_claim(self):
        value=summary(self.root)
        self.assertIsNone(value['charged_usd']);self.assertIsNone(value['agent_seconds'])
        self.assertEqual(value['attempted'],0)

    def test_all_predecessor_locks_are_held(self):
        from contextlib import ExitStack
        with ExitStack() as stack,patch('run_deadline_custom.hold') as hold:
            lock_all(stack,self.root)
        paths=[str(call.args[1]) for call in hold.call_args_list]
        self.assertIn('/opt/uts-capstone-custom-portable-20260926/.runtime/stage2',paths)
        self.assertIn('/opt/uts-capstone-custom-development-20260926/.runtime/stage2',paths)


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.rt,self.block,self.proof=fixture(self.root)

    async def test_actual_scored_entry_requires_new_admission(self):
        cell=self.block['cells'][0]
        with patch('deadline_custom_study.admit_trial',side_effect=ValueError('not qualified')) as admit, \
             patch('scored_trial.check_host',side_effect=AssertionError('No runtime launch')):
            with self.assertRaises(ValueError):
                await run_trial(root=self.root,trial_id=cell['trial_id'],task_id=cell['task_id'],stage='development',
                    agent_factory=agent_factory(self.root,'C0'),gateway_image='bad',guard_image='bad',
                    setup_timeout_seconds=900,model_settings=SETTINGS,accounting_mode='provider-credit-only',custom_study=EXPERIMENT)
            admit.assert_called_once()

    async def test_persistent_stop_precedes_dispatch(self):
        from custom_dispatch_stop import BoundaryStop
        stop=BoundaryStop(self.rt)
        durable_json(stop.marker,dict(source='test',automatic_resume=False))
        with patch('run_deadline_custom.audited',side_effect=AssertionError('No dispatch')):
            await dispatch(self.root,self.block,stop=stop)

    async def test_started_key_stops_before_launch(self):
        with patch('run_deadline_custom.audited',return_value=({},['partial'])),patch('run_deadline_custom.run_trial',new_callable=AsyncMock) as run:
            with self.assertRaises(ValueError):await dispatch(self.root,self.block)
            run.assert_not_awaited()

    async def test_completed_all_never_replayed(self):
        completed={c['trial_id']:{} for c in self.block['cells']}
        with patch('run_deadline_custom.audited',return_value=(completed,[])),patch('run_deadline_custom.pending_stops',return_value=[]),patch('run_deadline_custom.run_trial',new_callable=AsyncMock) as run:
            await dispatch(self.root,self.block)
            run.assert_not_awaited()


if __name__=='__main__':unittest.main()
