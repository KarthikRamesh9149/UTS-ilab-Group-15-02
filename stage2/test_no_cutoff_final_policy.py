"""Fabricated final contracts and fake-provider sessions, never native proof."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_candidate as candidate
import no_cutoff_final_policy as policy
from no_cutoff_final_gateway import NoCutoffFinalSession
from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError
from retry_runtime import activate
from scored_gateway import durable_json, private_directory
from test_no_cutoff_final_candidate import FinalistFixture
from test_retry_gateway import Clock, Event, Flaky, REQUEST
from test_credit_only_gateway import TOKEN


def qualification(document):
    """Test-only data. It is not accepted as real native evidence by a host."""
    sources = dict(document['selected_execution']['sources'])
    sources.update(document['original_candidate']['selection_logic_sources'])
    sources.update(document['freeze_logic_sources'])
    for name in policy.REQUIRED_SOURCE_FILES: sources.setdefault(name, '1' * 64)
    sources.update({'scored_trial.py': 'e' * 64, 'local_trace.py': 'f' * 64})
    regression = '.runtime/stage2/native-no-cutoff-final-qualification-test'
    files = {regression + '/regression.json': 'a' * 64, regression + '/regression.txt': 'b' * 64}
    cases = []
    for mode in policy.PROBE_MODES:
        path = '.runtime/stage2/native-no-cutoff-final-C0-NC-' + mode + '-test'
        files.update({path + '/evidence.json': 'c' * 64,
            path + '/.runtime/stage2/scored-trials/synthetic-nc-final-' + mode + '/result.json': 'd' * 64})
        cases.append(dict(condition=policy.CONDITION, parent='C0', base_parent=None, status='passed', live_api_calls=0,
            kind='actual_harbor_no_cutoff_final_graph_synthetic_provider_not_benchmark_score',
            mode=mode, runtime_path=path, checks=dict.fromkeys(policy.probe_checks(mode), True)))
    return dict(kind='native_no_cutoff_final_qualification', experiment=policy.EXPERIMENT,
        status='passed', condition=policy.CONDITION, parent='C0', base_parent=None,
        candidate_version=policy.CANDIDATE_VERSION, candidate_sha256=policy.fingerprint(document),
        original_candidate_sha256=policy.fingerprint(document['original_candidate']),
        validation_results_sha256=policy.fingerprint(document['result_bindings']),
        policy_sha256=policy.fingerprint(policy.POLICY), model_protocol_sha256=policy.SETTINGS.fingerprint(),
        input_manifest_sha256=policy.INPUT_SHA256, manifest_canonical_sha256=policy.MANIFEST_SHA256,
        python_runtime_sha256=policy.PYTHON_SHA256, execution_contract=policy.execution_contract(),
        dependencies=deepcopy(document['selected_execution']['dependencies']), setup_timeout_seconds=900, live_api_calls=0,
        finalist_authentication_sha256='4' * 64, runtime_identity_sha256='5' * 64,
        sources=sources, sources_sha256=policy.fingerprint(sources),
        orchestration_changes=policy.source_transition(document, sources),
        offline=dict(modules=list(policy.TEST_MODULES), passed=True, tests=100, skipped=0, errors=0, failures=0),
        synthetic=cases, regression_path=regression, evidence_files=files,
        gateway_image='sha256:' + '6' * 64, guard_image='sha256:' + '7' * 64,
        image_sources_match=True, host_environment={'execution_mode': 'native_linux_x86_64'},
        python_runtime={'sha256': policy.PYTHON_SHA256})


class Fixture:
    def __init__(self, owner, root):
        self.root = Path(root)
        self.lineage = FinalistFixture(owner, self.root)
        self.document = self.lineage.build()
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())
        self.proof = qualification(self.document)
        self.block = policy.registration(self.document, self.manifest, self.proof)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.write()

    def write(self):
        for name, value in {policy.CANDIDATE_FILE:self.document, policy.MANIFEST_FILE:self.manifest,
                policy.POLICY_FILE:policy.POLICY, policy.QUALIFICATION_FILE:self.proof,
                policy.REGISTRATION_FILE:self.block}.items():
            path = self.runtime / name
            if path.exists(): path.write_text(json.dumps(value))
            else: durable_json(path, value)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.rt = self.f.runtime
        self.trial = self.f.block['cells'][0]['trial_id']

    def test_exact_new_eighty_nine_ids_not_any_original_or_revision_attempt(self):
        block = policy.require_trial(self.rt, self.trial, 'final'); cells = block['cells']
        self.assertEqual(len(cells), 89); self.assertEqual(len({c['trial_id'] for c in cells}), 89)
        self.assertEqual({c['task_id'] for c in cells}, set(self.f.manifest['all_task_ids']))
        self.assertEqual([c['task_id'] for c in cells[:20]], self.f.manifest['development_ids'])
        self.assertTrue(all(c['harness'] == 'C0-NC' and c['parent'] == 'C0' and c['base_parent'] is None
            and c['stage'] == 'final' and len(c['trial_id']) <= 120 for c in cells))
        self.assertFalse(set(self.f.document['result_bindings']) & {c['trial_id'] for c in cells})
        self.assertEqual(block['validation_results_sha256'], policy.fingerprint(self.f.document['result_bindings']))
        self.assertEqual(block['attempts_per_task'], 1); self.assertEqual(block['parallel_trials'], 1)
        self.assertFalse(block['automatic_task_replay'])
        self.assertNotIn('passes', block)
        self.assertEqual(block['confirmation60_status'], 'deferred_not_run')
        self.assertEqual(block['diagnostic20_status'], 'deferred_not_run')

    def test_no_financial_call_job_command_or_repair_gate(self):
        value = policy.require_policy(self.rt)
        for name in ('project_cap_usd', 'stage_cap_usd', 'per_task_cap_usd', 'model_call_cap',
                'physical_request_count_cap', 'provider_max_price'):
            self.assertIsNone(value[name])
        self.assertEqual(value['reserve_usd'], '0'); self.assertFalse(value['accounting_blocks_dispatch'])
        for name in ('automatic_top_up', 'automatic_purchase', 'automatic_credit_limit_increase'):
            self.assertFalse(value[name])
        execution = value['execution_contract']
        for name in ('model_call_cap', 'completion_repair_count_cap', 'background_active_count_cap',
                'background_lifetime_count_cap'):
            self.assertIsNone(execution[name])
        self.assertEqual(execution['default_command_timeout'], 'remaining-official-task-time')
        self.assertEqual(execution, self.f.document['selected_execution']['execution_contract'])

    def test_no_original_or_c3_or_unmeasured_revision_can_be_relabelled(self):
        for change in ('original-only', 'version', 'condition', 'source', 'result', 'paid'):
            document = deepcopy(self.f.document)
            if change == 'original-only': document = document['original_candidate']
            elif change == 'version': document['selected_execution']['candidate_version'] = 'stage2-candidate-0.3.0'
            elif change == 'condition': document['selected_execution']['harness'] = 'C3'
            elif change == 'source': document['selected_execution']['sources']['no_cutoff_custom_agent.py'] = 'e' * 64
            elif change == 'result': document['result_bindings'].pop(next(iter(document['result_bindings'])))
            else: document['paid_launch_ready'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): policy.cells(document, self.f.manifest)

    def test_final_order_and_resource_manifest_cannot_be_changed(self):
        for change in ('order', 'identity', 'resource'):
            manifest = deepcopy(self.f.manifest)
            if change == 'order': manifest['development_ids'].reverse()
            elif change == 'identity': manifest['outside_development_ids'][0] = 'other'
            else: manifest['tasks'][0]['memory_mb'] += 1
            with self.subTest(change=change), self.assertRaises(ValueError): policy.cells(self.f.document, manifest)

    def test_only_two_recorded_orchestration_hooks_may_change(self):
        delta = policy.source_transition(self.f.document, self.f.proof['sources'])
        self.assertEqual(set(delta), {'scored_trial.py', 'local_trace.py'})
        for name in delta:
            self.assertEqual(delta[name]['measured_sha256'], self.f.document['selected_execution']['sources'][name])
        for name in ('no_cutoff_custom_agent.py', 'no_cutoff_capture_backend.py', 'custom_deadline_execution.py',
                'custom_model.py', 'retry_gateway.py', 'deadline_evidence_freeze.py'):
            if name not in self.f.proof['sources']: continue  # Minimal synthetic ancestor inventory.
            changed = dict(self.f.proof['sources'], **{name: '8' * 64})
            with self.subTest(name=name), self.assertRaises(ValueError): policy.source_transition(self.f.document, changed)

    def test_exact_source_inventory_and_frozen_evidence_logic_required(self):
        baseline = self.f.proof['sources']
        for name in set(self.f.document['freeze_logic_sources']) | policy.REQUIRED_SOURCE_FILES:
            changed = dict(baseline); changed.pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError): policy.source_transition(self.f.document, changed)
        for name in self.f.document['freeze_logic_sources']:
            changed = dict(baseline, **{name: '9' * 64})
            with self.subTest(name=name), self.assertRaises(ValueError): policy.source_transition(self.f.document, changed)
        for changed in (None, {}, dict(baseline, unbound='a' * 64), {'../escape': 'a' * 64}):
            with self.assertRaises(ValueError): policy.source_transition(self.f.document, changed)

    def test_native_qualification_cannot_be_development_local_or_incomplete(self):
        for change in ('kind', 'experiment', 'condition', 'candidate', 'results', 'model', 'runtime', 'contract',
                'sources', 'changes', 'auth', 'host', 'calls', 'bool-calls', 'offline', 'skip', 'modules',
                'cases', 'case-kind', 'case-check', 'case-path', 'producer', 'extra-producer', 'regression', 'image', 'image-source'):
            proof = deepcopy(self.f.proof)
            if change in ('kind', 'experiment', 'condition'): proof[change] = 'development'
            elif change == 'candidate': proof['candidate_sha256'] = '0' * 64
            elif change == 'results': proof['validation_results_sha256'] = '0' * 64
            elif change == 'model': proof['model_protocol_sha256'] = '0' * 64
            elif change == 'runtime': proof['python_runtime_sha256'] = '0' * 64
            elif change == 'contract': proof['execution_contract']['model_call_cap'] = 100
            elif change == 'sources': proof['sources_sha256'] = '0' * 64
            elif change == 'changes': proof['orchestration_changes'] = {}
            elif change == 'auth': proof.pop('finalist_authentication_sha256')
            elif change == 'host': proof.pop('runtime_identity_sha256')
            elif change == 'calls': proof['live_api_calls'] = 1
            elif change == 'bool-calls': proof['live_api_calls'] = False
            elif change == 'offline': proof['offline']['tests'] = True
            elif change == 'skip': proof['offline']['skipped'] = 1
            elif change == 'modules': proof['offline']['modules'].pop()
            elif change == 'cases': proof['synthetic'].pop()
            elif change == 'case-kind': proof['synthetic'][0]['kind'] = 'local-only'
            elif change == 'case-check': proof['synthetic'][0]['checks']['encoded_capture_process_matching'] = False
            elif change == 'case-path': proof['synthetic'][0]['runtime_path'] = '../other'
            elif change == 'producer': proof['evidence_files'].pop(next(iter(proof['evidence_files'])))
            elif change == 'extra-producer': proof['evidence_files']['.runtime/stage2/unbound'] = '0' * 64
            elif change == 'regression': proof['regression_path'] = 'old-qualification'
            elif change == 'image': proof['gateway_image'] = 'mutable:tag'
            else: proof['image_sources_match'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.validate_qualification(self.f.document, self.f.manifest, proof)
        with self.assertRaises(ValueError):
            policy.validate_qualification(self.f.document, self.f.manifest, self.f.document['revision_qualification'])

    def test_registered_cells_authority_and_comparators_cannot_be_rewritten(self):
        for change in ('partial', 'duplicate', 'order', 'replay', 'parallel', 'comparator', 'schema', 'extra', 'id'):
            block = deepcopy(self.f.block)
            if change == 'partial': block['cells'].pop()
            elif change == 'duplicate': block['cells'][1] = block['cells'][0]
            elif change == 'order': block['cells'].reverse()
            elif change == 'replay': block['automatic_task_replay'] = True
            elif change == 'parallel': block['parallel_trials'] = 2
            elif change == 'comparator': block['primary_comparator'] = 'openhands'
            elif change == 'schema': block['schema_version'] = True
            elif change == 'extra': block['raw_exchange'] = 'not allowed'
            else: block['cells'][0]['trial_id'] = 'customdev4-c0-nc-01-video-processing'
            (self.rt / policy.REGISTRATION_FILE).write_text(json.dumps(block))
            with self.subTest(change=change), self.assertRaises(ValueError): policy.require_trial(self.rt, self.trial, 'final')

    def test_wrong_stage_old_synthetic_or_unregistered_ids_are_not_admitted(self):
        for trial, stage in ((self.trial, 'development'), ('customfinal2-c0-nc-01-other', 'final'),
                ('customfinal1-c3-01-video-processing', 'final'), ('customdev4-c0-nc-01-video-processing', 'final'),
                ('synthetic-nc-final-tools', 'final'), ('../escape', 'final')):
            with self.subTest(trial=trial), self.assertRaises(ValueError): policy.require_trial(self.rt, trial, stage)

    def test_changed_document_and_policy_require_new_registration(self):
        document = deepcopy(self.f.document); document['revision_audit_sha256'] = '0' * 64
        (self.rt / policy.CANDIDATE_FILE).write_text(json.dumps(document))
        with self.assertRaises(ValueError): policy.require_block(self.rt)
        self.f.write()
        (self.rt / policy.POLICY_FILE).write_text(json.dumps(dict(policy.POLICY, model_call_cap=100)))
        with self.assertRaises(ValueError): policy.require_block(self.rt)

    def test_private_permissions_and_symlinks_are_enforced(self):
        for name in (policy.CANDIDATE_FILE, policy.MANIFEST_FILE, policy.QUALIFICATION_FILE,
                policy.REGISTRATION_FILE, policy.POLICY_FILE):
            path = self.rt / name; path.chmod(0o644)
            with self.subTest(name=name), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.chmod(0o600); moved = path.with_suffix('.saved'); path.rename(moved); path.symlink_to(moved)
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)): policy.require_block(self.rt)
            path.unlink(); moved.rename(path)

    def test_gateway_has_no_operator_or_agent_stack_import(self):
        script = '''
import importlib.abc,json,sys
class RejectHost(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'harbor','deepagents','langgraph','langchain','langchain_core',
   'langchain_openai','no_cutoff_final_evidence','no_cutoff_evidence_freeze','export_no_cutoff_custom',
   'no_cutoff_custom_study','no_cutoff_custom_runtime','direct_final_evidence','direct_final_runtime',
   'deadline_evidence_freeze','deadline_candidate_freeze','portable_candidate_freeze','scored_trial','progress_dashboard'}:
   raise ImportError('Host dependency: '+name)
sys.meta_path.insert(0,RejectHost())
import no_cutoff_final_candidate as candidate
import no_cutoff_final_policy as policy
from no_cutoff_final_gateway import NoCutoffFinalSession
document=json.load(open(sys.argv[1]+'/'+policy.CANDIDATE_FILE))
candidate.revision.ORIGINAL_FREEZE_SHA256=policy.fingerprint(document['original_candidate'])
candidate.QUALIFICATION_SHA256=policy.fingerprint(document['revision_qualification'])
candidate.REGISTRATION_SHA256=policy.fingerprint(document['revision_registration'])
block=policy.require_block(sys.argv[1]);assert len(block['cells'])==89
assert block['condition']=='C0-NC'
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.rt)],
            capture_output=True, text=True, timeout=20, env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registration_builder_creates_no_files_or_mutable_input_alias(self):
        before = deepcopy((self.f.document, self.f.manifest, self.f.proof))
        files = sorted(p.relative_to(self.rt) for p in self.rt.rglob('*'))
        block = policy.registration(self.f.document, self.f.manifest, self.f.proof)
        block['cells'][0]['task_id'] = 'changed'
        block['orchestration_changes']['scored_trial.py']['qualified_sha256'] = '0' * 64
        self.assertEqual((self.f.document, self.f.manifest, self.f.proof), before)
        self.assertEqual(sorted(p.relative_to(self.rt) for p in self.rt.rglob('*')), files)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.f = Fixture(self, temporary.name); self.rt = self.f.runtime

    def session(self, failures=(), timeout=10000, index=0):
        clock = Clock(); name = self.f.block['cells'][index]['trial_id']
        activate(self.rt, name, timeout, policy.SETTINGS, clock)
        session = NoCutoffFinalSession(self.f.root, name, 'final', TOKEN,
            Flaky(clock, failures), settings=policy.SETTINGS, clock=clock)
        session.cancelled = Event(clock)
        return session

    def test_over_one_hundred_unknown_cost_calls_without_reservation_or_call_cap(self):
        with patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No reservation')), self.session() as session:
            session.client.response.pop('usage')
            for _ in range(105): session.complete(TOKEN, REQUEST)
            bill = summarise(self.rt, session.trial_id)
            self.assertEqual((bill['requests'], bill['unknown_cost_requests']), (105, 105))
            self.assertIsNone(bill['charged_usd']); self.assertFalse(list(self.rt.glob('*.sqlite')))

    def test_shared_retry_handles_over_one_hundred_physical_requests(self):
        with self.session([(429, ['0'])] * 105) as session:
            session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 106)
            self.assertIsNone(summarise(self.rt, session.trial_id)['charged_usd'])

    def test_registration_drift_stops_before_another_provider_call(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST)
            block = deepcopy(self.f.block); block['cells'].pop()
            (self.rt / policy.REGISTRATION_FILE).write_text(json.dumps(block))
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

    def test_official_deadline_and_cancellation_still_revoke_dispatch(self):
        with self.session(timeout=1) as session:
            session.clock.now += 2
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(session.client.calls, [])
        with self.session(index=1) as session:
            session.cancelled.set()
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(session.client.calls, [])

    def test_started_attempt_and_accepted_call_are_not_replayed(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST); self.assertEqual(len(session.client.calls), 1)
        with self.assertRaises((ValueError, FileExistsError)): self.session()

    def test_real_gateway_lock_prevents_overlap(self):
        with self.session():
            with self.assertRaises(BlockingIOError): self.session(index=1)
        name = self.f.block['cells'][1]['trial_id']
        self.assertFalse((self.rt / 'scored-attempts' / name).exists())

    def test_shared_retry_after_survives_to_next_registered_task(self):
        with self.session([(429, ['50'])], timeout=1) as first:
            with self.assertRaises(CreditOnlyError): first.complete(TOKEN, REQUEST)
            self.assertEqual(len(first.client.calls), 1)
        with self.session(index=1, timeout=100) as second:
            second.complete(TOKEN, REQUEST)
            self.assertEqual(second.clock.now, 150.); self.assertEqual(len(second.client.calls), 1)


if __name__ == '__main__': unittest.main()
