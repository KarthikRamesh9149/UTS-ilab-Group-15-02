"""Synthetic contracts and fake transport only; never real native evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import matched_repeat_policy as policy
from matched_repeat_gateway import MatchedRepeatSession
from matched_repeat_schedule import schedule
from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError
from retry_runtime import activate
from scored_gateway import durable_json, private_directory
from test_retry_gateway import Clock, Event, Flaky, REQUEST
from test_credit_only_gateway import TOKEN


def predecessors(manifest, harness):
    plan = schedule(manifest)
    blocks = []
    for index in range(1 + policy.HARNESSES.index(harness)):
        trials = ([f'customfinal2-c0-nc-{i:02d}-{cell["task_id"]}'
            for i, cell in enumerate(plan['blocks'][0]['cells'], 1)] if index == 0 else [
                cell['trial_id'] for cell in plan['blocks'][0]['cells']])
        blocks.append(dict(experiment=policy.CUSTOM_FINAL_EXPERIMENT if index == 0 else policy.EXPERIMENT,
            harness='C0-NC' if index == 0 else 'terminus-2',
            qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256 if index == 0 else '8' * 64,
            registration_sha256=policy.CUSTOM_FINAL_REGISTRATION_SHA256 if index == 0 else '9' * 64,
            sources_sha256=policy.CUSTOM_FINAL_SOURCES_SHA256 if index == 0 else 'a' * 64,
            results_sha256=dict.fromkeys(trials, 'b' * 64), audit_sha256='c' * 64,
            archive_sha256='d' * 64, backup_record_sha256='e' * 64))
    return dict(kind='authenticated_matched_repeat_predecessors_not_paid_admission',
        successor_harness=harness, schedule_sha256=policy.fingerprint(plan), blocks=blocks,
        paid_launch_ready=False)


def qualification(original, final, predecessor, manifest, harness):
    """Fabricated test metadata, not a host-authenticated production proof."""
    sources = dict(final['sources'])
    sources.update(dict.fromkeys(policy.REQUIRED_SOURCE_FILES, '3' * 64))
    sources['scored_trial.py'] = '4' * 64
    folder = '.runtime/stage2/native-matched-repeat-' + harness
    regression = folder + '-qualification-test'
    files = {regression + '/regression.json': 'a' * 64, regression + '/regression.txt': 'b' * 64}
    cases = []
    for mode in policy.PROBE_MODES:
        path = folder + '-' + mode + '-test'
        files.update({path + '/evidence.json': 'c' * 64,
            path + '/.runtime/stage2/scored-trials/synthetic-matched-repeat-' + harness + '-' + mode
                + '/result.json': 'd' * 64})
        cases.append(dict(mode=mode, harness=harness, status='passed', live_api_calls=0,
            kind='actual_native_matched_baseline_synthetic_provider_not_benchmark_score',
            runtime_path=path, checks=dict.fromkeys(policy.probe_checks(mode), True)))
    return dict(schema_version=1, kind='native_matched_baseline_repeat_qualification',
        experiment=policy.EXPERIMENT, status='passed', harness=harness, live_api_calls=0,
        setup_timeout_seconds=900, policy_sha256=policy.fingerprint(policy.POLICY),
        schedule_sha256=policy.fingerprint(schedule(manifest)), manifest_canonical_sha256=policy.MANIFEST_SHA256,
        model_protocol_sha256=policy.MODEL_SHA256, original_baseline_csv_sha256=policy.BASELINE_CSV_SHA256,
        original_qualification_sha256=policy.ORIGINAL_QUALIFICATION_SHA256,
        custom_final_qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256,
        predecessor_authentication_sha256=policy.fingerprint(predecessor),
        inherited_baseline_turn_guards=deepcopy(policy.POLICY['inherited_baseline_turn_guards']),
        dependencies=deepcopy(final['dependencies']), sources=sources, sources_sha256=policy.fingerprint(sources),
        source_transition=policy.source_transition(original, final, sources),
        baseline_behaviour_authentication_sha256='5' * 64, runtime_identity_sha256='6' * 64,
        host_environment={'execution_mode': 'native_linux_x86_64'},
        offline=dict(modules=list(policy.TEST_MODULES), passed=True, tests=100, skipped=0, errors=0, failures=0),
        regression_path=regression, synthetic=cases, evidence_files=files,
        gateway_image='sha256:' + '7' * 64, guard_image='sha256:' + '8' * 64, image_sources_match=True)


class Fixture:
    def __init__(self, owner, root, harness='terminus-2'):
        self.root = Path(root)
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())
        self.original = dict(sources=dict.fromkeys(policy.BASELINE_BEHAVIOUR_FILES | policy.INHERITED_BASELINE_DELTAS,
            '1' * 64), model_protocol_sha256=policy.MODEL_SHA256,
            policy=dict(terminus_default_max_turns=1000000, openhands_max_iterations=1000000))
        self.final = dict(sources=dict(self.original['sources'], **{
            name: '2' * 64 for name in policy.INHERITED_BASELINE_DELTAS}),
            model_protocol_sha256=policy.MODEL_SHA256,
            dependencies=dict(python='3.12.13', packages={'harbor': '0.1.45'}))
        self.final['sources']['no_cutoff_final_policy.py'] = '2' * 64
        self.final['sources'].update({name + '.py': '2' * 64 for name in policy.TEST_MODULES
            if name + '.py' not in policy.REQUIRED_SOURCE_FILES})
        self.final['sources_sha256'] = policy.fingerprint(self.final['sources'])
        for key, value in (('ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(self.original)),
                ('CUSTOM_FINAL_QUALIFICATION_SHA256', policy.fingerprint(self.final)),
                ('CUSTOM_FINAL_SOURCES_SHA256', self.final['sources_sha256'])):
            p = patch.object(policy, key, value); p.start(); owner.addCleanup(p.stop)
        self.predecessor = predecessors(self.manifest, harness)
        self.proof = qualification(self.original, self.final, self.predecessor, self.manifest, harness)
        self.block = policy.registration(self.original, self.final, self.predecessor, self.manifest, self.proof)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.write()

    def write(self):
        for name, value in {policy.POLICY_FILE:policy.POLICY, policy.MANIFEST_FILE:self.manifest,
                policy.BASELINE_FILE:self.original, policy.FINAL_FILE:self.final,
                policy.PREDECESSOR_FILE:self.predecessor, policy.QUALIFICATION_FILE:self.proof,
                policy.REGISTRATION_FILE:self.block}.items():
            path = self.runtime / name
            if path.exists(): path.write_text(json.dumps(value))
            else: durable_json(path, value)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.rt = self.f.runtime
        self.trial = self.f.block['cells'][0]['trial_id']

    def test_exact_eighty_nine_fresh_ids_per_baseline_and_original_order(self):
        ids = set()
        for harness in policy.HARNESSES:
            predecessor = predecessors(self.f.manifest, harness)
            proof = qualification(self.f.original, self.f.final, predecessor, self.f.manifest, harness)
            block = policy.registration(self.f.original, self.f.final, predecessor, self.f.manifest, proof)
            self.assertEqual(block['cells'], schedule(self.f.manifest)['blocks'][policy.HARNESSES.index(harness)]['cells'])
            self.assertEqual(len(block['cells']), 89)
            self.assertEqual([c['task_id'] for c in block['cells'][:20]], self.f.manifest['development_ids'])
            self.assertTrue(all(c['trial_id'].startswith('matchedrepeat1-' + harness + '-')
                and len(c['trial_id']) <= 120 for c in block['cells']))
            ids.update(c['trial_id'] for c in block['cells'])
        self.assertEqual(len(ids), 178)
        self.assertFalse(ids & set(self.f.predecessor['blocks'][0]['results_sha256']))

    def test_no_financial_or_added_model_request_caps_but_native_guards_disclosed(self):
        value = policy.require_policy(self.rt)
        for name in ('project_cap_usd', 'stage_cap_usd', 'per_task_cap_usd', 'provider_max_price',
                'model_call_cap', 'physical_request_count_cap', 'retry_count_cap'):
            self.assertIsNone(value[name])
        self.assertEqual(value['reserve_usd'], '0')
        for name in ('accounting_blocks_dispatch', 'unknown_cost_is_zero', 'automatic_top_up',
                'automatic_purchase', 'automatic_credit_limit_increase', 'native_guards_are_benchmark_rules'):
            self.assertFalse(value[name])
        self.assertEqual(value['inherited_baseline_turn_guards'], {'terminus-2':1000000, 'openhands':1000000})
        self.assertEqual(value['baseline_agent_behaviour'], 'original-corrected-unchanged')

    def test_original_scores_comparators_and_deferred_phases_not_replaced(self):
        block = policy.require_block(self.rt)
        self.assertEqual(block['original_scores'], {'terminus-2':52, 'openhands':44})
        self.assertEqual(block['primary_comparator'], 'terminus-2')
        self.assertEqual(block['secondary_comparator'], 'openhands')
        self.assertFalse(block['original_results_replaced'])
        self.assertFalse(block['automatic_task_replay'])
        self.assertEqual((block['parallel_trials'], block['attempts_per_task']), (1, 1))
        for name in ('confirmation60_status', 'diagnostic20_status'):
            self.assertEqual(block[name], 'deferred_not_run')
        self.assertNotIn('passes', block)

    def test_openhands_requires_both_custom_and_completed_terminus_not_just_a_label(self):
        value = predecessors(self.f.manifest, 'openhands')
        self.assertEqual([b['harness'] for b in value['blocks']], ['C0-NC', 'terminus-2'])
        policy.validate_predecessors(value, self.f.manifest, 'openhands')
        for change in ('no-terminus', 'reverse', 'only-terminus', 'old-baseline', 'missing-result', 'no-archive'):
            altered = deepcopy(value)
            if change == 'no-terminus': altered['blocks'].pop()
            elif change == 'reverse': altered['blocks'].reverse()
            elif change == 'only-terminus': altered['blocks'].pop(0)
            elif change == 'old-baseline': altered['blocks'][1]['experiment'] = 'baseline-corrected-credit-only-20260923'
            elif change == 'missing-result': altered['blocks'][1]['results_sha256'].pop(next(iter(altered['blocks'][1]['results_sha256'])))
            else: altered['blocks'][1].pop('archive_sha256')
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.validate_predecessors(altered, self.f.manifest, 'openhands')

    def test_predecessor_result_coverage_backups_and_exact_final_bindings_required(self):
        for change in ('kind', 'successor', 'plan', 'paid', 'results', 'extra-result', 'old-task', 'qual',
                'registry', 'source', 'audit', 'archive', 'receipt', 'scores', 'raw', 'extra-block'):
            value = deepcopy(self.f.predecessor); block = value['blocks'][0]
            if change == 'kind': value['kind'] = 'checks-true'
            elif change == 'successor': value['successor_harness'] = 'openhands'
            elif change == 'plan': value['schedule_sha256'] = '0' * 64
            elif change == 'paid': value['paid_launch_ready'] = True
            elif change == 'results': block['results_sha256'] = {}
            elif change == 'extra-result': block['results_sha256']['extra'] = '0' * 64
            elif change == 'old-task': block['results_sha256']['corrected1-old'] = block['results_sha256'].pop(next(iter(block['results_sha256'])))
            elif change == 'qual': block['qualification_sha256'] = '0' * 64
            elif change == 'registry': block['registration_sha256'] = '0' * 64
            elif change == 'source': block['sources_sha256'] = '0' * 64
            elif change == 'audit': block['audit_sha256'] = True
            elif change == 'archive': block['archive_sha256'] = None
            elif change == 'receipt': block.pop('backup_record_sha256')
            elif change == 'scores': block['passes'] = 89
            elif change == 'raw': value['raw_exchange'] = 'forbidden'
            else: value['blocks'].append(deepcopy(block))
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.validate_predecessors(value, self.f.manifest, 'terminus-2')

    def test_final_manifest_cannot_be_reordered_or_resource_changed(self):
        for change in ('order', 'resource', 'coverage'):
            manifest = deepcopy(self.f.manifest)
            if change == 'order': manifest['development_ids'].reverse()
            elif change == 'resource': manifest['tasks'][0]['memory_mb'] += 1
            else: manifest['all_task_ids'].pop()
            with self.subTest(change=change), self.assertRaises(ValueError): policy.cells(manifest, 'terminus-2')

    def test_original_and_final_anchors_cannot_be_substituted_or_relabelled(self):
        for where, key in (('original', 'sources'), ('final', 'sources'), ('original', 'model_protocol_sha256'),
                ('original', 'policy'), ('final', 'dependencies')):
            original, final = deepcopy(self.f.original), deepcopy(self.f.final)
            target = original if where == 'original' else final
            target[key] = {}
            with self.subTest(where=where, key=key), self.assertRaises(ValueError): policy.anchors(original, final)

    def test_all_seven_inherited_deltas_and_new_orchestration_are_explicit(self):
        delta = policy.source_transition(self.f.original, self.f.final, self.f.proof['sources'])
        self.assertEqual(set(delta['inherited_baseline_changes']), policy.INHERITED_BASELINE_DELTAS)
        self.assertFalse(set(delta['inherited_baseline_changes']) & policy.BASELINE_BEHAVIOUR_FILES)
        self.assertEqual(set(delta['orchestration_changes']), {'scored_trial.py'})
        self.assertEqual(delta['original_sources_sha256'], policy.fingerprint(self.f.original['sources']))
        for name, record in delta['inherited_baseline_changes'].items():
            self.assertEqual(record['original_sha256'], self.f.original['sources'][name])
            self.assertEqual(record['final_sha256'], self.f.final['sources'][name])

    def test_native_behaviour_retry_and_original_evidence_cannot_change(self):
        for name in set(self.f.final['sources']) - policy.ORCHESTRATION_FILES:
            current = dict(self.f.proof['sources'], **{name: 'f' * 64})
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.source_transition(self.f.original, self.f.final, current)

    def test_exact_inventory_paths_and_hashes_required(self):
        for name in self.f.proof['sources']:
            current = dict(self.f.proof['sources']); current.pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.source_transition(self.f.original, self.f.final, current)
        for extra in ('extra.py', '../escape', '/absolute', 'x//y', '.private', 'x/./y'):
            current = dict(self.f.proof['sources'], **{extra: '0' * 64})
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                policy.source_transition(self.f.original, self.f.final, current)
        for value in (True, None, '', 'x' * 64):
            current = dict(self.f.proof['sources'], **{'scored_trial.py': value})
            with self.assertRaises(ValueError): policy.source_transition(self.f.original, self.f.final, current)

    def test_native_qualification_has_no_local_or_checks_only_shortcut(self):
        for change in ('kind', 'schema', 'harness', 'paid', 'calls', 'bool-calls', 'setup', 'policy', 'plan', 'protocol',
                'baseline', 'final', 'prior', 'controls', 'dependencies', 'sources', 'transition', 'auth', 'runtime',
                'host', 'offline', 'skip', 'modules', 'cases', 'mode', 'case-harness', 'check', 'path',
                'producer', 'extra-producer', 'regression', 'image', 'image-source'):
            proof = deepcopy(self.f.proof)
            if change == 'kind': proof['kind'] = 'local-qualification'
            elif change == 'schema': proof['schema_version'] = True
            elif change == 'harness': proof['harness'] = 'C0-NC'
            elif change == 'paid': proof['paid_launch_ready'] = True
            elif change == 'calls': proof['live_api_calls'] = 1
            elif change == 'bool-calls': proof['live_api_calls'] = False
            elif change == 'setup': proof['setup_timeout_seconds'] = 60
            elif change == 'policy': proof['policy_sha256'] = '0' * 64
            elif change == 'plan': proof['schedule_sha256'] = '0' * 64
            elif change == 'protocol': proof['model_protocol_sha256'] = '0' * 64
            elif change == 'baseline': proof['original_qualification_sha256'] = '0' * 64
            elif change == 'final': proof['custom_final_qualification_sha256'] = '0' * 64
            elif change == 'prior': proof['predecessor_authentication_sha256'] = '0' * 64
            elif change == 'controls': proof['inherited_baseline_turn_guards']['openhands'] = 100
            elif change == 'dependencies': proof['dependencies']['python'] = '3.12.14'
            elif change == 'sources': proof['sources_sha256'] = '0' * 64
            elif change == 'transition': proof['source_transition'] = {}
            elif change == 'auth': proof.pop('baseline_behaviour_authentication_sha256')
            elif change == 'runtime': proof.pop('runtime_identity_sha256')
            elif change == 'host': proof['host_environment']['execution_mode'] = 'local-mocked'
            elif change == 'offline': proof['offline']['tests'] = True
            elif change == 'skip': proof['offline']['skipped'] = 1
            elif change == 'modules': proof['offline']['modules'].pop()
            elif change == 'cases': proof['synthetic'].pop()
            elif change == 'mode': proof['synthetic'][0]['mode'] = 'smoke'
            elif change == 'case-harness': proof['synthetic'][0]['harness'] = 'openhands'
            elif change == 'check': proof['synthetic'][0]['checks']['model_revoked'] = False
            elif change == 'path': proof['synthetic'][0]['runtime_path'] = '../old'
            elif change == 'producer': proof['evidence_files'].pop(next(iter(proof['evidence_files'])))
            elif change == 'extra-producer': proof['evidence_files']['.runtime/stage2/unbound'] = '0' * 64
            elif change == 'regression': proof['regression_path'] = 'old-tests'
            elif change == 'image': proof['gateway_image'] = 'mutable:tag'
            else: proof['image_sources_match'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.validate_qualification(self.f.original, self.f.final, self.f.predecessor, self.f.manifest, proof)

    def test_registration_and_comparison_tampering_is_rejected(self):
        for change in ('partial', 'order', 'replay', 'parallel', 'comparator', 'scores', 'extra', 'identity', 'auth'):
            block = deepcopy(self.f.block)
            if change == 'partial': block['cells'].pop()
            elif change == 'order': block['cells'].reverse()
            elif change == 'replay': block['automatic_task_replay'] = True
            elif change == 'parallel': block['parallel_trials'] = 2
            elif change == 'comparator': block['primary_comparator'] = 'openhands'
            elif change == 'scores': block['original_scores']['terminus-2'] = 89
            elif change == 'extra': block['raw_exchange'] = 'forbidden'
            elif change == 'identity': block['cells'][0]['trial_id'] = 'corrected1-terminus-2-01-video-processing'
            else: block['predecessor_authentication_sha256'] = '0' * 64
            (self.rt / policy.REGISTRATION_FILE).write_text(json.dumps(block))
            with self.subTest(change=change), self.assertRaises(ValueError): policy.require_trial(self.rt, self.trial, 'final')

    def test_changed_policy_cannot_add_a_cap_or_remove_native_guard_silently(self):
        for key, value in (('model_call_cap', 100), ('reserve_usd', '1'),
                ('inherited_baseline_turn_guards', {}), ('parallel_trials', 2)):
            (self.rt / policy.POLICY_FILE).write_text(json.dumps(dict(policy.POLICY, **{key: value})))
            with self.subTest(key=key), self.assertRaises(ValueError): policy.require_block(self.rt)

    def test_other_harness_original_custom_synthetic_and_wrong_stage_refused(self):
        for trial, stage in ((self.trial, 'development'), ('matchedrepeat1-openhands-01-video-processing', 'final'),
                ('corrected1-terminus-2-01-video-processing', 'final'), ('customfinal2-c0-nc-01-video-processing', 'final'),
                ('synthetic-matched-repeat-terminus-2-tools', 'final'), ('../escape', 'final')):
            with self.subTest(trial=trial), self.assertRaises(ValueError): policy.require_trial(self.rt, trial, stage)
        for harness in ('C0-NC', 'C3', 'terminus', 'other', None):
            with self.assertRaises(ValueError): policy.cells(self.f.manifest, harness)

    def test_private_files_must_not_be_public_or_symlinked(self):
        for name in (policy.POLICY_FILE, policy.MANIFEST_FILE, policy.BASELINE_FILE, policy.FINAL_FILE,
                policy.PREDECESSOR_FILE, policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE):
            path = self.rt / name; path.chmod(0o644)
            with self.subTest(name=name), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.chmod(0o600); moved = path.with_suffix('.saved'); path.rename(moved); path.symlink_to(moved)
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)): policy.require_block(self.rt)
            path.unlink(); moved.rename(path)

    def test_pure_builders_do_not_mutate_inputs_write_or_grant_paid_permission(self):
        before = deepcopy((self.f.original, self.f.final, self.f.predecessor, self.f.manifest, self.f.proof))
        files = sorted(p.relative_to(self.rt) for p in self.rt.rglob('*'))
        block = policy.registration(*before)
        block['source_transition']['orchestration_changes']['scored_trial.py']['repeat_sha256'] = 'f' * 64
        block['inherited_baseline_turn_guards']['openhands'] = 1
        block['cells'][0]['task_id'] = 'changed'
        self.assertEqual(before, (self.f.original, self.f.final, self.f.predecessor, self.f.manifest, self.f.proof))
        self.assertEqual(sorted(p.relative_to(self.rt) for p in self.rt.rglob('*')), files)
        self.assertNotIn('paid_launch_ready', block)
        self.assertFalse(self.f.predecessor['paid_launch_ready'])

    def test_gateway_imports_no_host_operator_or_agent_stack(self):
        script = '''
import importlib.abc,json,sys
class Reject(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'harbor','deepagents','langgraph','langchain','langchain_core','langchain_openai',
   'scored_trial','progress_dashboard','no_cutoff_final_policy','no_cutoff_final_evidence','no_cutoff_final_runtime',
   'no_cutoff_final_study','export_no_cutoff_final','deadline_evidence_freeze','direct_final_evidence'}:
   raise ImportError('Host dependency: '+name)
sys.meta_path.insert(0,Reject())
import matched_repeat_policy as policy
from matched_repeat_gateway import MatchedRepeatSession
rt=sys.argv[1]
original=json.load(open(rt+'/'+policy.BASELINE_FILE)); final=json.load(open(rt+'/'+policy.FINAL_FILE))
policy.ORIGINAL_QUALIFICATION_SHA256=policy.fingerprint(original)
policy.CUSTOM_FINAL_QUALIFICATION_SHA256=policy.fingerprint(final)
policy.CUSTOM_FINAL_SOURCES_SHA256=final['sources_sha256']
assert len(policy.require_block(rt)['cells'])==89
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.rt)],
            capture_output=True, text=True, timeout=20, env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)))
        self.assertEqual(result.returncode, 0, result.stderr)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.rt = self.f.runtime

    def session(self, failures=(), timeout=10000, index=0):
        clock = Clock(); name = self.f.block['cells'][index]['trial_id']
        activate(self.rt, name, timeout, policy.SETTINGS, clock)
        session = MatchedRepeatSession(self.f.root, name, 'final', TOKEN,
            Flaky(clock, failures), settings=policy.SETTINGS, clock=clock)
        session.cancelled = Event(clock)
        return session

    def test_over_one_hundred_unknown_cost_calls_never_reserve_or_hit_a_study_cap(self):
        with patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No reservation')), self.session() as session:
            session.client.response.pop('usage')
            for _ in range(105): session.complete(TOKEN, REQUEST)
            bill = summarise(self.rt, session.trial_id)
            self.assertEqual((bill['requests'], bill['unknown_cost_requests']), (105, 105))
            self.assertIsNone(bill['charged_usd']); self.assertFalse(list(self.rt.glob('*.sqlite')))

    def test_shared_retry_over_one_hundred_physical_requests_uses_identical_payload(self):
        with self.session([(429, ['0'])] * 105) as session:
            session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 106)
            self.assertTrue(all(call == session.client.calls[0] for call in session.client.calls))
            self.assertEqual(summarise(self.rt, session.trial_id)['unknown_cost_requests'], 105)

    def test_openhands_gateway_requires_its_own_block_and_retains_unknown_cost(self):
        self.f = Fixture(self, self.f.root / 'second-baseline', 'openhands')
        self.rt = self.f.runtime
        with self.session([(429, ['1'])]) as session:
            session.complete(TOKEN, REQUEST)
            self.assertTrue(session.trial_id.startswith('matchedrepeat1-openhands-'))
            self.assertEqual(len(session.client.calls), 2)
            self.assertIsNone(summarise(self.rt, session.trial_id)['charged_usd'])
        predecessor = deepcopy(self.f.predecessor); predecessor['blocks'].pop()
        (self.rt / policy.PREDECESSOR_FILE).write_text(json.dumps(predecessor))
        with self.assertRaises(ValueError): self.session(index=1)

    def test_registration_and_predecessor_drift_stop_before_next_call(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST)
            altered = deepcopy(self.f.predecessor); altered['blocks'][0]['archive_sha256'] = '0' * 64
            (self.rt / policy.PREDECESSOR_FILE).write_text(json.dumps(altered))
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)

    def test_valid_but_different_reregistration_is_also_refused_mid_attempt(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST)
            self.f.proof['runtime_identity_sha256'] = 'f' * 64
            self.f.block = policy.registration(self.f.original, self.f.final, self.f.predecessor,
                self.f.manifest, self.f.proof)
            self.f.write()
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)

    def test_actual_credit_authentication_and_model_identity_stops_remain(self):
        for index, status in enumerate((401, 402, 403)):
            with self.session([(status, [])], index=index) as session:
                with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
                self.assertEqual(len(session.client.calls), 1)
                self.assertTrue((session.evidence / 'provider-stop.json').exists())
        with self.session(index=3) as session:
            session.client.response['model'] = 'wrong'
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)

    def test_official_deadline_cancellation_and_token_still_gate_dispatch(self):
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

    def test_started_attempt_is_not_replayed(self):
        with self.session() as session: session.complete(TOKEN, REQUEST)
        with self.assertRaises((ValueError, FileExistsError)): self.session()

    def test_real_gateway_lock_prevents_overlap(self):
        with self.session():
            with self.assertRaises(BlockingIOError): self.session(index=1)
        name = self.f.block['cells'][1]['trial_id']
        self.assertFalse((self.rt / 'scored-attempts' / name).exists())

    def test_shared_retry_after_survives_to_next_task(self):
        with self.session([(429, ['50'])], timeout=1) as first:
            with self.assertRaises(CreditOnlyError): first.complete(TOKEN, REQUEST)
            self.assertEqual(len(first.client.calls), 1)
        with self.session(index=1, timeout=100) as second:
            second.complete(TOKEN, REQUEST)
            self.assertEqual(second.clock.now, 150.)
            self.assertEqual(len(second.client.calls), 1)


if __name__ == '__main__': unittest.main()
