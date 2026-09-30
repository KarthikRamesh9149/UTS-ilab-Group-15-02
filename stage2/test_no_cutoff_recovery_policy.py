"""Synthetic metadata/private files and fake providers; no native qualification."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_recovery_policy as policy
from no_cutoff_recovery_gateway import NoCutoffRecoverySession
from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError
from retry_runtime import activate
from scored_gateway import private_directory
from test_retry_gateway import Clock, Event, Flaky, REQUEST
from test_credit_only_gateway import TOKEN


def qualification(final, predecessor, manifest):
    """Fabricated TEST-ONLY metadata; never write it into a real native root."""
    sources = dict(final['sources'])
    for name in policy.REQUIRED_SOURCE_FILES:
        sources.setdefault(name, '3' * 64)  # Explicit current inventory may also name inherited sources.
    sources['scored_trial.py'] = '4' * 64
    regression = '.runtime/stage2/native-no-cutoff-recovery-qualification-test'
    files = {regression + '/regression.json': 'a' * 64, regression + '/regression.txt': 'b' * 64}
    cases = []
    for mode in policy.PROBE_MODES:
        path = '.runtime/stage2/native-no-cutoff-recovery-' + mode + '-test'
        files.update({path + '/evidence.json': 'c' * 64,
            path + '/.runtime/stage2/scored-trials/synthetic-nc-recovery-' + mode + '/result.json': 'd' * 64})
        cases.append(dict(mode=mode, condition='C0-NC', status='passed', live_api_calls=0,
            kind='actual_native_recovery_synthetic_provider_not_benchmark_score',
            preparation_outcome=policy.PREPARATION_OUTCOMES[mode], runtime_path=path,
            preparation_observation_sha256='e' * 64, checks=dict.fromkeys(policy.probe_checks(mode), True)))
    return dict(schema_version=1, kind='native_separate_C0_NC_recovery_qualification',
        experiment=policy.EXPERIMENT, status='passed', condition='C0-NC', parent='C0', base_parent=None,
        live_api_calls=0, paid_launch_ready=False, setup_timeout_seconds=900,
        package_command_timeout_seconds=180, preparation_source_sha256=policy.PREPARATION_SHA256,
        preparation_command_sha256=policy.COMMAND_SHA256, plan_sha256=policy.PLAN_SHA256,
        policy_sha256=policy.fingerprint(policy.POLICY), original_qualification_sha256=policy.ORIGINAL_QUALIFICATION,
        original_candidate_sha256=policy.ORIGINAL_CANDIDATE, candidate_version=policy.CANDIDATE_VERSION,
        predecessor_authentication_sha256=policy.fingerprint(predecessor),
        model_protocol_sha256=policy.MODEL_SHA256, manifest_canonical_sha256=policy.MANIFEST_SHA256,
        input_manifest_sha256=policy.INPUT_SHA256, python_runtime_sha256=policy.PYTHON_SHA256,
        execution_contract=policy.execution_contract(), dependencies=deepcopy(final['dependencies']),
        python_runtime=deepcopy(final['python_runtime']), host_environment=deepcopy(final['host_environment']),
        guard_image=final['guard_image'], gateway_image='sha256:' + '8' * 64, image_sources_match=True,
        sources=sources, sources_sha256=policy.fingerprint(sources),
        orchestration_changes=policy.source_transition(final, sources),
        runtime_identity_sha256='5' * 64, image_build_sha256='6' * 64,
        image_evidence_files=dict.fromkeys(policy.IMAGE_EVIDENCE_FILES, '7' * 64),
        offline=dict(modules=list(policy.test_modules(final)), tests=100, passed=True, skipped=0, errors=0, failures=0),
        regression_path=regression, synthetic=cases, evidence_files=files)


class Fixture:
    def __init__(self, owner, root):
        self.root = Path(root).resolve()
        self.manifest_raw = (Path(__file__).parent / 'input_manifest.json').read_bytes()
        self.manifest = json.loads(self.manifest_raw)
        self.final = dict(experiment=policy.plan.ORIGINAL_EXPERIMENT, condition='C0-NC', parent='C0',
            base_parent=None, candidate_version=policy.CANDIDATE_VERSION,
            candidate_sha256=policy.ORIGINAL_CANDIDATE, model_protocol_sha256=policy.MODEL_SHA256,
            execution_contract=policy.execution_contract(),
            sources=dict.fromkeys(('custom_model.py', 'custom_runner.py', 'local_trace.py',
                'scored_trial.py', 'retry_gateway.py', 'model_protocol.py', 'test_retry_gateway.py',
                'no_cutoff_custom_agent.py', 'no_cutoff_custom_contract.py', 'trial_execution.py'), '1' * 64),
            dependencies=dict(python='3.12.13', packages={'harbor': '0.1.45'}),
            python_runtime=dict(sha256=policy.PYTHON_SHA256),
            host_environment=dict(execution_mode='native_linux_x86_64'),
            guard_image='sha256:' + '9' * 64, offline=dict(modules=['test_retry_gateway']))
        self.final['sources']['task_preparation.py'] = policy.PREPARATION_SHA256
        self.final['sources_sha256'] = policy.fingerprint(self.final['sources'])
        for key, value in (('ORIGINAL_QUALIFICATION', policy.fingerprint(self.final)),
                ('ORIGINAL_SOURCE_SET', self.final['sources_sha256']),
                ('ORIGINAL_QUALIFICATION_FILE_SHA256', hashlib.sha256(json.dumps(self.final).encode()).hexdigest())):
            p = patch.object(policy, key, value); p.start(); owner.addCleanup(p.stop)
        results = {policy.plan.original_id(i, task): 'b' * 64
            for i, task in enumerate(policy.plan.task_order(self.manifest), 1)}
        for ordinal, task, digest in policy.plan.TARGETS:
            results[policy.plan.original_id(ordinal, task)] = digest
        p = patch.object(policy, 'ORIGINAL_RESULTS_SHA256', policy.fingerprint(results)); p.start(); owner.addCleanup(p.stop)
        self.predecessor = dict(kind='recovery_original_final_evidence_not_admission', schema_version=1,
            successor_experiment=policy.EXPERIMENT, plan_sha256=policy.PLAN_SHA256,
            original_experiment=policy.plan.ORIGINAL_EXPERIMENT, harness='C0-NC',
            qualification_sha256=policy.ORIGINAL_QUALIFICATION,
            registration_sha256=policy.plan.ORIGINAL_REGISTRATION, sources_sha256=policy.ORIGINAL_SOURCE_SET,
            retained_snapshot_sha256=policy.SNAPSHOT_SHA256, audit_sha256=policy.AUDIT_SHA256,
            archive_sha256=policy.ARCHIVE_SHA256,
            backup_record_sha256=policy.BACKUP_SHA256, reporter_commit=policy.REPORTER_COMMIT,
            public_files=deepcopy(policy.PUBLIC_FILES), paid_launch_ready=False,
            results_sha256=results)
        self.proof = qualification(self.final, self.predecessor, self.manifest)
        self.block = policy.registration(self.final, self.predecessor, self.manifest, self.proof)
        self.rt = private_directory(self.root / '.runtime/stage2')
        self.write()

    def values(self):
        return {policy.POLICY_FILE: policy.POLICY, policy.PLAN_FILE: policy.plan.schedule(self.manifest),
            policy.MANIFEST_FILE: self.manifest, policy.ORIGINAL_FILE: self.final,
            policy.PREDECESSOR_FILE: self.predecessor, policy.QUALIFICATION_FILE: self.proof,
            policy.REGISTRATION_FILE: self.block}

    def write(self):
        for name, value in self.values().items():
            self.save(name, value)
        (self.rt / policy.MANIFEST_FILE).write_bytes(self.manifest_raw)

    def save(self, name, value):
        path = self.rt / name
        path.write_text(json.dumps(value)); path.chmod(0o600)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.rt = self.f.rt
        self.trial = self.f.block['cells'][0]['trial_id']

    def validate(self, proof):
        return policy.validate_qualification(self.f.final, self.f.predecessor, self.f.manifest, proof)

    def test_exact_three_original_order_new_keys_and_separate_denominators(self):
        block = policy.require_trial(self.rt, self.trial, 'final')
        self.assertEqual(block['cells'], policy.plan.schedule(self.f.manifest)['cells'])
        self.assertEqual([c['original_ordinal'] for c in block['cells']], [63, 64, 65])
        self.assertEqual((block['intended'], block['parallel_trials'], block['attempts_per_task']), (3, 1, 1))
        self.assertEqual((block['original_full89_denominator'], block['separate_recovery_denominator']), (89, 3))
        self.assertTrue(all(c['trial_id'] != c['original_trial_id'] for c in block['cells']))
        self.assertTrue(all(c['original_reward'] is None for c in block['cells']))
        for key in ('automatic_task_replay', 'original_results_replaced', 'recovery_merged_into_original89',
                'best_of_selection', 'success_guaranteed', 'paid_launch_ready'):
            self.assertIs(block[key], False)

    def test_original_model_contract_preparation_and_setup_rules_unchanged(self):
        import no_cutoff_recovery_setup as setup
        self.assertEqual(policy.PREPARATION_SHA256, setup.PREPARATION_SHA256)
        self.assertEqual(policy.COMMAND_SHA256, setup.COMMAND_SHA256)
        self.assertEqual(policy.POLICY['model'], policy.SETTINGS.document())
        self.assertEqual(policy.POLICY['execution_contract'], self.f.final['execution_contract'])
        self.assertEqual(policy.POLICY['setup_timeout_seconds'], 900)
        self.assertEqual(policy.POLICY['package_command_timeout_seconds'], 180)
        self.assertEqual(policy.POLICY['preparation_command_retries'], 0)
        self.assertFalse(policy.POLICY['speculative_infrastructure_repair'])
        self.assertEqual(policy.PLAN_SHA256, policy.fingerprint(policy.plan.schedule(self.f.manifest)))

    def test_no_financial_or_request_cap_or_unknown_to_zero_conversion(self):
        for key in ('project_cap_usd', 'stage_cap_usd', 'per_task_cap_usd', 'provider_max_price',
                'model_call_cap', 'physical_request_count_cap', 'retry_count_cap'):
            self.assertIsNone(policy.POLICY[key])
        self.assertEqual(policy.POLICY['reserve_usd'], '0')
        for key in ('accounting_blocks_dispatch', 'unknown_cost_is_zero', 'automatic_top_up',
                'automatic_purchase', 'automatic_credit_limit_increase'):
            self.assertIs(policy.POLICY[key], False)

    def test_wrong_original_synthetic_baseline_other_task_stage_refused_before_read(self):
        with patch.object(policy, '_capture', side_effect=AssertionError('Invalid identities must not read inputs')):
            for trial, stage in ((self.trial, 'development'), (self.f.block['cells'][0]['original_trial_id'], 'final'),
                    ('synthetic-nc-recovery-tools', 'final'), ('matchedrepeat1-terminus-2-63-other', 'final'),
                    ('customrecovery1-c0-nc-66-other', 'final'), ('../escape', 'final'), (None, 'final')):
                with self.subTest(trial=trial, stage=stage), self.assertRaises(ValueError):
                    policy.require_trial(self.rt, trial, stage)

    def test_changed_plan_manifest_policy_or_numeric_type_refused(self):
        for name in (policy.PLAN_FILE, policy.MANIFEST_FILE, policy.POLICY_FILE):
            value = deepcopy(self.f.values()[name]); value['extra'] = 'not allowed'
            self.f.save(name, value)
            with self.subTest(name=name), self.assertRaises(ValueError): policy.require_block(self.rt)
            self.f.write()
        for key, value in (('attempts_per_task', True), ('parallel_trials', 2), ('reserve_usd', '1'),
                ('model_call_cap', 100), ('setup_timeout_seconds', 899), ('package_command_timeout_seconds', 181)):
            self.f.save(policy.POLICY_FILE, dict(policy.POLICY, **{key: value}))
            with self.subTest(key=key), self.assertRaises(ValueError): policy.require_block(self.rt)
            self.f.write()

    def test_predecessor_requires_fixed_archive_public_outputs_and_all89_hashes(self):
        for key in ('qualification_sha256', 'registration_sha256', 'sources_sha256', 'retained_snapshot_sha256',
                'archive_sha256', 'backup_record_sha256', 'reporter_commit', 'public_files',
                'successor_experiment', 'original_experiment', 'paid_launch_ready', 'audit_sha256'):
            value = deepcopy(self.f.predecessor); value[key] = None
            with self.subTest(key=key), self.assertRaises(ValueError): policy.validate_predecessor(value, self.f.manifest)
        for change in ('missing', 'extra', 'changed', 'target', 'score', 'diagnosis'):
            value = deepcopy(self.f.predecessor)
            if change == 'missing': value['results_sha256'].pop(next(iter(value['results_sha256'])))
            elif change == 'extra': value['results_sha256']['extra'] = 'a' * 64
            elif change == 'changed': value['results_sha256'][next(iter(value['results_sha256']))] = 'a' * 64
            elif change == 'target': value['results_sha256'][self.f.block['cells'][0]['original_trial_id']] = 'a' * 64
            elif change == 'score': value['passes'] = 89
            else: value['kind'] = 'saved_recovery_diagnosis'
            with self.subTest(change=change), self.assertRaises(ValueError): policy.validate_predecessor(value, self.f.manifest)

    def test_original_qualification_and_candidate_cannot_be_relabelled(self):
        for key in ('candidate_sha256', 'condition', 'sources', 'dependencies', 'model_protocol_sha256'):
            value = deepcopy(self.f.final); value[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError): policy.original_final(value)

    def test_only_scored_orchestration_delta_no_original_behaviour_change(self):
        sources = deepcopy(self.f.proof['sources'])
        change = policy.source_transition(self.f.final, sources)
        self.assertEqual(set(change), {'scored_trial.py'})
        for name in self.f.final['sources']:
            if name == 'scored_trial.py': continue
            value = dict(sources, **{name: 'f' * 64})
            with self.subTest(name=name), self.assertRaises(ValueError): policy.source_transition(self.f.final, value)
        for name in policy.REQUIRED_SOURCE_FILES:
            value = dict(sources); value.pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError): policy.source_transition(self.f.final, value)
        with self.assertRaises(ValueError): policy.source_transition(self.f.final, dict(sources, unexpected='0' * 64))

    def test_qualified_runtime_and_model_identities_cannot_change(self):
        for key in ('experiment', 'condition', 'parent', 'base_parent', 'live_api_calls', 'paid_launch_ready',
                'setup_timeout_seconds', 'package_command_timeout_seconds', 'preparation_source_sha256',
                'preparation_command_sha256', 'plan_sha256', 'policy_sha256', 'model_protocol_sha256',
                'original_candidate_sha256', 'candidate_version', 'predecessor_authentication_sha256',
                'manifest_canonical_sha256', 'python_runtime_sha256', 'execution_contract', 'dependencies',
                'python_runtime', 'host_environment', 'guard_image', 'sources_sha256', 'orchestration_changes',
                'image_sources_match', 'runtime_identity_sha256', 'image_build_sha256', 'gateway_image'):
            value = deepcopy(self.f.proof); value[key] = 'changed'
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)
        value = deepcopy(self.f.proof); value['live_api_calls'] = False
        with self.assertRaises(ValueError): self.validate(value)
        value = deepcopy(self.f.proof); value['raw_exception'] = 'private'
        with self.assertRaises(ValueError): self.validate(value)

    def test_regression_requires_all_modules_nonempty_and_zero_skip_error_failure(self):
        for key, value in (('tests', 0), ('tests', True), ('passed', 1), ('skipped', 1),
                ('errors', 1), ('failures', 1), ('modules', []), ('extra', 'private')):
            proof = deepcopy(self.f.proof); proof['offline'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.validate(proof)
        self.assertEqual(policy.test_modules(self.f.final), ('test_retry_gateway', *policy.RECOVERY_TEST_MODULES))

    def test_all_six_cases_and_exact_preparation_outcomes_are_required(self):
        self.assertEqual(len(self.f.proof['synthetic']), 6)
        for index, case in enumerate(self.f.proof['synthetic']):
            for key, value in (('mode', 'other'), ('status', 'skipped'), ('live_api_calls', 1),
                    ('condition', 'C0'), ('preparation_outcome', 'unknown'),
                    ('preparation_observation_sha256', None), ('checks', {}), ('runtime_path', '../elsewhere')):
                proof = deepcopy(self.f.proof); proof['synthetic'][index][key] = value
                with self.subTest(mode=case['mode'], key=key), self.assertRaises(ValueError): self.validate(proof)
        for operation in ('missing', 'reverse', 'duplicate'):
            proof = deepcopy(self.f.proof)
            if operation == 'missing': proof['synthetic'].pop()
            elif operation == 'reverse': proof['synthetic'].reverse()
            else: proof['synthetic'].append(deepcopy(proof['synthetic'][0]))
            with self.subTest(operation=operation), self.assertRaises(ValueError): self.validate(proof)

    def test_required_cases_corroborate_no_model_no_phases_stop_and_diagnostics(self):
        for mode in policy.PROBE_MODES:
            checks = policy.probe_checks(mode)
            self.assertTrue({'original_C0_NC_controls', 'preparation_callback_once', 'original_preparation_command',
                'preparation_observation_retained', 'preparation_outcome_corroborated', 'no_raw_diagnostics'} <= checks)
            if mode in ('prepare_nonzero', 'prepare_exception', 'cancel_setup'):
                self.assertTrue({'no_model_request', 'agent_and_verifier_not_run'} <= checks)
        self.assertTrue({'no_next_dispatch', 'cooperative_stop_persisted'} <= policy.probe_checks('boundary_stop'))

    def test_all_sixteen_producer_paths_are_exact_private_and_distinct(self):
        self.assertEqual(len(self.f.proof['evidence_files']), 14)
        self.assertEqual(len(self.f.proof['image_evidence_files']), 2)
        for field in ('evidence_files', 'image_evidence_files'):
            for change in ('missing', 'extra', 'unsafe', 'hash'):
                proof = deepcopy(self.f.proof); files = proof[field]
                if change == 'missing': files.pop(next(iter(files)))
                elif change == 'extra': files['.runtime/stage2/extra'] = 'f' * 64
                elif change == 'unsafe': files['.runtime/stage2/../escape'] = files.pop(next(iter(files)))
                else: files[next(iter(files))] = 'not-a-hash'
                with self.subTest(field=field, change=change), self.assertRaises(ValueError): self.validate(proof)

    def test_registration_rejects_omissions_order_replay_scores_or_extra_fields(self):
        for change in ('missing', 'order', 'old-id', 'extra', 'merged', 'parallel', 'qualification'):
            block = deepcopy(self.f.block)
            if change == 'missing': block['cells'].pop()
            elif change == 'order': block['cells'].reverse()
            elif change == 'old-id': block['cells'][0]['trial_id'] = block['cells'][0]['original_trial_id']
            elif change == 'extra': block['passes'] = 3
            elif change == 'merged': block['recovery_merged_into_original89'] = True
            elif change == 'parallel': block['parallel_trials'] = 3
            else: block['qualification_sha256'] = '0' * 64
            self.f.save(policy.REGISTRATION_FILE, block)
            with self.subTest(change=change), self.assertRaises(ValueError): policy.require_block(self.rt)

    def test_builders_are_nonmutating_no_write_and_never_admission(self):
        before = deepcopy((self.f.final, self.f.predecessor, self.f.manifest, self.f.proof))
        files = {p.name: p.read_bytes() for p in self.rt.iterdir()}
        block = policy.registration(*before)
        block['cells'][0]['task_id'] = 'changed'
        block['execution_contract']['version'] = 'changed'
        block['orchestration_changes']['scored_trial.py']['recovery_sha256'] = '0' * 64
        self.assertEqual(before, (self.f.final, self.f.predecessor, self.f.manifest, self.f.proof))
        self.assertEqual(files, {p.name: p.read_bytes() for p in self.rt.iterdir()})
        self.assertFalse(block['paid_launch_ready'])
        self.assertFalse(self.f.predecessor['paid_launch_ready'])

    def test_each_private_input_cannot_be_missing_public_or_symlinked(self):
        for name in policy.INPUT_FILES:
            path = self.rt / name; raw = path.read_bytes()
            path.chmod(0o644)
            with self.subTest(name=name, change='public'), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.chmod(0o600); moved = path.with_suffix('.saved'); path.rename(moved)
            with self.subTest(name=name, change='missing'), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.symlink_to(moved)
            with self.subTest(name=name, change='symlink'), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.unlink(); moved.rename(path)
            self.assertEqual(path.read_bytes(), raw)

    def test_hardlinks_fifo_and_wrong_owner_refused_without_waiting(self):
        path = self.rt / policy.POLICY_FILE; saved = path.with_suffix('.saved'); path.rename(saved)
        os.link(saved, path)
        with self.assertRaises(ValueError): policy.require_block(self.rt)
        path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): policy.require_block(self.rt)
        path.unlink(); saved.rename(path)
        with patch.object(policy.os, 'geteuid', return_value=os.geteuid() + 1), self.assertRaises(ValueError):
            policy.require_block(self.rt)

    def test_private_runtime_and_parent_symlink_refused(self):
        self.rt.chmod(0o755)
        with self.assertRaises(ValueError): policy.require_block(self.rt)
        self.rt.chmod(0o700)
        parent = self.rt.parent; moved = parent.with_name('.saved-runtime'); parent.rename(moved); parent.symlink_to(moved)
        with self.assertRaises(ValueError): policy.require_block(self.rt)
        parent.unlink(); moved.rename(parent)

    def test_duplicate_nested_nonfinite_malformed_and_nonobject_json_refused_privately(self):
        marker = 'PRIVATE-OUTPUT-MUST-NOT-LEAK'
        path = self.rt / policy.POLICY_FILE
        for raw in ('{"a":1,"a":2}', '{"a":{"b":1,"b":2}}', '{"a":NaN}',
                '{"a":Infinity}', '[]', '"' + marker + '"', '{' + marker):
            path.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError) as caught: policy.require_block(self.rt)
            self.assertNotIn(marker, str(caught.exception))

    def test_byte_mutation_across_structural_validation_refused(self):
        real = policy.registration
        def mutate(*args):
            result = real(*args)
            path = self.rt / policy.MANIFEST_FILE; path.write_bytes(path.read_bytes() + b' ')
            return result
        with patch.object(policy, 'registration', side_effect=mutate), self.assertRaises(ValueError):
            policy.require_block(self.rt)

    def test_read_block_binds_raw_bytes_and_file_identities_not_only_json(self):
        block, before = policy.read_block(self.rt)
        path = self.rt / policy.QUALIFICATION_FILE; path.write_bytes(path.read_bytes() + b' ')
        block2, after = policy.read_block(self.rt)
        self.assertEqual(block, block2)
        self.assertNotEqual(before, after)
        self.assertEqual(set(before['files']), set(policy.INPUT_FILES))
        self.assertEqual(before['files'][policy.POLICY_FILE]['sha256'],
            hashlib.sha256((self.rt / policy.POLICY_FILE).read_bytes()).hexdigest())

    def test_original_qualification_and_manifest_copy_bytes_are_independently_pinned(self):
        for name in (policy.ORIGINAL_FILE, policy.MANIFEST_FILE):
            path = self.rt / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.subTest(name=name), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.write_bytes(raw)
        policy.require_block(self.rt)

    def test_predecessor_binding_is_stable_across_fresh_audit_times_not_a_saved_witness(self):
        value = deepcopy(self.f.predecessor)
        self.assertEqual(value['audit_sha256'], policy.AUDIT_SHA256)
        self.assertNotIn('fresh_audit_sha256', value)
        value['collected_utc'] = '2026-09-29T16:00:00+00:00'
        with self.assertRaises(ValueError): policy.validate_predecessor(value, self.f.manifest)

    def test_gateway_import_is_lean_and_effect_free_in_isolated_child(self):
        program = r'''
import importlib.abc,json,os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
class Reject(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'harbor','langgraph','deepagents','langchain','scored_trial',
   'no_cutoff_final_policy','no_cutoff_final_evidence','no_cutoff_final_runtime',
   'no_cutoff_final_reporting','no_cutoff_final_export','no_cutoff_recovery_diagnosis',
   'no_cutoff_recovery_setup','matched_repeat_predecessor','matched_repeat_policy'}:
   raise AssertionError('Host dependency imported')
def guard(event,args):
 if event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or
  isinstance(args[2],int) and args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
  raise AssertionError('Write during import')
 if event.startswith(('socket.','subprocess.','os.spawn','os.exec')) or event in {'os.system','os.fork'}:
  raise AssertionError('External effect during import')
sys.meta_path.insert(0,Reject()); sys.addaudithook(guard)
import no_cutoff_recovery_policy as policy
from no_cutoff_recovery_gateway import NoCutoffRecoverySession
assert policy.PLAN_SHA256 == 'dd46fb43239d1b84ffcf0e387c234f6f8df693852f18bdaeeb7a034bdc3cdd38'
assert not any('API_KEY' in k for k in os.environ)
print('lean guarded import passed')
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(Path(__file__).resolve().parent)],
            env={'PATH': '/usr/bin:/bin', 'PYTHON_DOTENV_DISABLED': '1',
                'LITELLM_MODE': 'PRODUCTION', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'},
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'lean guarded import passed')


class GatewayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.rt = self.f.rt

    def session(self, failures=(), *, index=0, timeout=10000):
        clock = Clock(); name = self.f.block['cells'][index]['trial_id']
        activate(self.rt, name, timeout, policy.SETTINGS, clock)
        session = NoCutoffRecoverySession(self.f.root, name, 'final', TOKEN,
            Flaky(clock, failures), settings=policy.SETTINGS, clock=clock)
        session.cancelled = Event(clock)
        return session

    def test_105_unknown_cost_calls_have_no_reservation_or_count_cap(self):
        with (patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No financial reservation')),
                self.session() as session):
            session.client.response.pop('usage')
            for _ in range(105): session.complete(TOKEN, REQUEST)
            bill = summarise(self.rt, session.trial_id)
            self.assertEqual((bill['requests'], bill['unknown_cost_requests']), (105, 105))
            self.assertIsNone(bill['charged_usd'])
            self.assertFalse(list(self.rt.glob('*.sqlite')))

    def test_105_transients_keep_identical_payload_106_physical_calls(self):
        with self.session([(429, ['0'])] * 105) as session:
            session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 106)
            self.assertTrue(all(c == session.client.calls[0] for c in session.client.calls))
            self.assertEqual(summarise(self.rt, session.trial_id)['unknown_cost_requests'], 105)

    def test_raw_whitespace_change_blocks_even_with_same_registration(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST)
            path = self.rt / policy.MANIFEST_FILE; raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            path.write_bytes(raw)
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            with self.assertRaises(ValueError): session.require_session_policy()
            self.assertEqual(len(session.client.calls), 1)

    def test_invalid_metadata_then_restoration_does_not_revive_gateway(self):
        with self.session() as session:
            path = self.rt / policy.POLICY_FILE; raw = path.read_bytes(); path.write_bytes(b'{}')
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            path.write_bytes(raw)
            with self.assertRaises(ValueError): session.require_recovery_policy()
            self.assertEqual(session.client.calls, [])

    def test_valid_new_registration_is_not_accepted_inside_attempt(self):
        with self.session() as session:
            self.f.proof['runtime_identity_sha256'] = 'f' * 64
            self.f.block = policy.registration(self.f.final, self.f.predecessor, self.f.manifest, self.f.proof)
            self.f.write()
            policy.require_block(self.rt)
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            self.assertEqual(session.client.calls, [])

    def test_same_bytes_replaced_file_is_rejected(self):
        with self.session() as session:
            path = self.rt / policy.MANIFEST_FILE; replacement = path.with_suffix('.new')
            replacement.write_bytes(path.read_bytes()); replacement.chmod(0o600); replacement.replace(path)
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            self.assertEqual(session.client.calls, [])

    def test_shared_retry_checks_actual_inputs_before_every_physical_call(self):
        with self.session([(429, ['1'])]) as session:
            def wait(seconds):
                session.clock.now += seconds
                path = self.rt / policy.PLAN_FILE; path.write_bytes(path.read_bytes() + b' ')
            session.cancelled.wait = wait
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
            self.assertTrue(session._policy_invalid)

    def test_actual_auth_and_credit_stops_are_not_retried(self):
        for index, status in enumerate((401, 402, 403)):
            with self.session([(status, [])], index=index) as session:
                with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
                self.assertEqual(len(session.client.calls), 1)
                self.assertTrue((session.evidence / 'provider-stop.json').exists())

    def test_wrong_model_identity_and_context_bad_request_are_not_retried(self):
        with self.session() as session:
            session.client.response['model'] = 'wrong'
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)
        with self.session([(400, [])], index=1) as session:
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)

    def test_official_deadline_cancel_and_token_still_gate_calls(self):
        with self.session(timeout=1) as session:
            session.clock.now += 2
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(session.client.calls, [])
        with self.session(index=1) as session:
            session.cancelled.set()
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(session.client.calls, [])
        with self.session(index=2) as session:
            with self.assertRaises(CreditOnlyError): session.complete('incorrect', REQUEST)
            self.assertEqual(session.client.calls, [])

    def test_revocation_during_shared_wait_prevents_next_call(self):
        with self.session([(429, ['10'])]) as session:
            session.cancelled.wait = lambda seconds: session.cancelled.set()
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)

    def test_no_gateway_restart_for_started_key_or_parallel_gateway(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST)
            with self.assertRaises(BlockingIOError): self.session(index=1)
            self.assertFalse((self.rt / 'scored-attempts' / self.f.block['cells'][1]['trial_id']).exists())
        with self.assertRaises(FileExistsError):
            NoCutoffRecoverySession(self.f.root, session.trial_id, 'final', TOKEN,
                Flaky(Clock(), []), settings=policy.SETTINGS, clock=Clock())

    def test_shared_retry_after_survives_to_next_fresh_task(self):
        with self.session([(429, ['50'])], timeout=1) as first:
            with self.assertRaises(CreditOnlyError): first.complete(TOKEN, REQUEST)
        with self.session(index=1, timeout=100) as second:
            second.complete(TOKEN, REQUEST)
            self.assertEqual(second.clock.now, 150.)
            self.assertEqual(len(second.client.calls), 1)

    def test_completed_or_revoked_gateway_cannot_send_more(self):
        session = self.session()
        session.complete(TOKEN, REQUEST); session.close()
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
        self.assertEqual(len(session.client.calls), 1)


if __name__ == '__main__': unittest.main()
