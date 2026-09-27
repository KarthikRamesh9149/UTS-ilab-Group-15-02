"""Synthetic admission/retry contracts. No native or paid execution evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_custom_policy as policy
from no_cutoff_custom_gateway import NoCutoffRetrySession
from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError
from retry_runtime import activate
from scored_gateway import private_directory, durable_json
from test_direct_final_policy import candidate
from test_retry_gateway import Clock, Event, Flaky, REQUEST
from test_credit_only_gateway import TOKEN


def document_fixture():
    document = candidate(13)
    inherited = document['candidate']['c3_sources']
    inherited.update(document['selected_execution']['sources'])
    inherited.update({'local_trace.py': '8' * 64, 'input_manifest.json': policy.INPUT_SHA256,
                      'dataset_provenance.json': '7' * 64})
    return document


def qualification_fixture(document):
    sources = dict(document['candidate']['c3_sources'], **document['selection_logic_sources'])
    sources.update(dict.fromkeys(policy.REQUIRED_SOURCE_FILES, '1' * 64))
    sources.update({'scored_trial.py': '2' * 64, 'local_trace.py': '3' * 64})
    regression = '.runtime/stage2/native-no-cutoff-qualification-test'
    evidence = {regression + '/regression.json': 'a' * 64, regression + '/regression.txt': 'b' * 64}
    for mode in policy.PROBE_MODES:
        path = '.runtime/stage2/native-no-cutoff-C0-NC-' + mode + '-test'
        evidence[path + '/evidence.json'] = 'c' * 64
        evidence[path + '/.runtime/stage2/scored-trials/synthetic-nc-' + mode + '/result.json'] = 'd' * 64
    return dict(kind='native_no_cutoff_development_qualification', experiment=policy.EXPERIMENT,
        status='passed', condition=policy.CONDITION, parent='C0', base_parent=None,
        candidate_version=policy.CANDIDATE_VERSION, original_candidate_sha256=policy.fingerprint(document),
        policy_sha256=policy.fingerprint(policy.POLICY), model_protocol_sha256=policy.SETTINGS.fingerprint(),
        input_manifest_sha256=policy.INPUT_SHA256, execution_contract=policy.execution_contract(),
        dependencies=deepcopy(document['selected_execution']['dependencies']), live_api_calls=0,
        setup_timeout_seconds=900, sources=sources, sources_sha256=policy.fingerprint(sources),
        source_transition=policy.source_transition(document, sources),
        python_runtime={'sha256': policy.PYTHON_SHA256},
        original_authentication_sha256=policy.fingerprint({'synthetic': True}), runtime_identity_sha256='5' * 64,
        offline=dict(modules=list(policy.TEST_MODULES), passed=True, tests=100, skipped=0, errors=0, failures=0),
        synthetic=[dict(condition=policy.CONDITION, parent='C0', base_parent=None, mode=mode,
            kind='actual_harbor_no_cutoff_graph_synthetic_provider_not_benchmark_score',
            runtime_path='.runtime/stage2/native-no-cutoff-C0-NC-' + mode + '-test',
            status='passed', live_api_calls=0, checks=dict.fromkeys(policy.probe_checks(mode), True))
            for mode in policy.PROBE_MODES],
        regression_path=regression, evidence_files=evidence,
        gateway_image='sha256:' + '6' * 64, guard_image='sha256:' + '7' * 64,
        image_sources_match=True, host_environment={'execution_mode': 'native_linux_x86_64'})


class Fixture:
    def __init__(self, owner, root):
        self.root = Path(root)
        self.rt = private_directory(self.root / '.runtime/stage2')
        self.document = document_fixture()
        # Only this synthetic test's immutable anchor is substituted. Runtime
        # code has no environment/CLI escape from the real selected freeze.
        owner.enterContext(patch.object(policy, 'ORIGINAL_FREEZE_SHA256', policy.fingerprint(self.document)))
        self.proof = qualification_fixture(self.document)
        self.tasks = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())['development_ids']
        self.block = policy.registration(self.document, self.proof, self.tasks)
        self.write()

    def write(self):
        values = {policy.POLICY_FILE: policy.POLICY, policy.CANDIDATE_FILE: self.document,
            policy.QUALIFICATION: self.proof, policy.AUTHENTICATION_FILE: {'synthetic': True},
            policy.RUNTIME_FILE: {'development_ids': self.tasks}}
        for name, value in values.items():
            path = self.rt / name
            if path.exists(): path.write_text(json.dumps(value))
            else: durable_json(path, value)
        path = policy.block_path(self.rt); private_directory(path.parent)
        if path.exists(): path.write_text(json.dumps(self.block))
        else: durable_json(path, self.block)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, folder.name)
        self.trial = self.f.block['cells'][0]['trial_id']

    def test_exact_new_twenty_cells_all_eighty_old_results_bound(self):
        block = policy.require_trial(self.f.rt, self.trial, 'development')
        self.assertEqual(len(block['cells']), 20)
        self.assertEqual(len({r['trial_id'] for r in block['cells']}), 20)
        self.assertEqual([r['task_id'] for r in block['cells']], self.f.tasks)
        self.assertFalse(set(r['trial_id'] for r in block['cells']) & set(self.f.document['candidate']['result_bindings']))
        self.assertEqual(len(self.f.document['candidate']['result_bindings']), 80)
        self.assertEqual(block['condition'], 'C0-NC')
        self.assertNotIn('passes', block)

    def test_original_c0_is_not_the_revised_runtime_or_score(self):
        execution = policy.candidate_execution(self.f.document)
        self.assertEqual(execution['candidate_version'], 'stage2-candidate-0.3.0')
        self.assertEqual(self.f.block['candidate_version'], 'stage2-candidate-0.5.0')
        self.assertFalse(self.f.document['paid_launch_ready'])
        for trial, stage in ((self.trial, 'final'), ('customdev3-c3-01-video-processing', 'development'),
                ('customdev4-c1-nc-01-video-processing', 'development'), (self.trial + '-new', 'development')):
            with self.subTest(trial=trial, stage=stage), self.assertRaises(ValueError):
                policy.require_trial(self.f.rt, trial, stage)

    def test_other_or_changed_selection_cannot_authorise_more_revisions(self):
        document = deepcopy(self.f.document)
        document['original_audit_sha256'] = '9' * 64
        with self.assertRaises(ValueError): policy.candidate_execution(document)
        document = candidate(20)
        with patch.object(policy, 'ORIGINAL_FREEZE_SHA256', policy.fingerprint(document)):
            with self.assertRaises(ValueError): policy.candidate_execution(document)

    def test_no_financial_request_or_artificial_execution_caps(self):
        value = policy.require_policy(self.f.rt)
        for field in ('project_cap_usd', 'stage_cap_usd', 'per_task_cap_usd', 'model_call_cap',
                      'physical_request_count_cap', 'provider_max_price'):
            self.assertIsNone(value[field])
        self.assertEqual(value['reserve_usd'], '0')
        for name in ('automatic_top_up', 'automatic_purchase', 'automatic_credit_limit_increase', 'accounting_blocks_dispatch'):
            self.assertFalse(value[name])
        contract = value['execution_contract']
        for name in ('model_call_cap', 'completion_repair_count_cap', 'background_active_count_cap', 'background_lifetime_count_cap'):
            self.assertIsNone(contract[name])
        self.assertEqual(contract['default_command_timeout'], 'remaining-official-task-time')
        self.assertFalse(contract['remaining_time_guidance'])

    def test_exact_source_delta_and_original_selection_helpers(self):
        current = self.f.proof['sources']
        transition = policy.source_transition(self.f.document, current)
        self.assertEqual(set(transition['orchestration_changes']), {'scored_trial.py', 'local_trace.py'})
        for name in ('custom_model.py', 'custom_deadline_execution.py', 'deadline_evidence_freeze.py'):
            changed = dict(current, **{name: 'a' * 64})
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.source_transition(self.f.document, changed)
        for name in ('no_cutoff_capture_backend.py', 'direct_final_evidence.py'):
            changed = dict(current); changed.pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.source_transition(self.f.document, changed)

    def test_qualification_requires_new_complete_native_cases_and_runtime(self):
        for name, value in (('kind', 'local-tests'), ('experiment', 'custom-deadline-development-20260927'),
                ('live_api_calls', False), ('live_api_calls', 1), ('setup_timeout_seconds', 60),
                ('original_authentication_sha256', None), ('runtime_identity_sha256', None),
                ('gateway_image', 'latest'), ('image_sources_match', False), ('source_transition', {}),
                ('synthetic', self.f.proof['synthetic'][:-1]), ('sources_sha256', '0' * 64)):
            with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                policy.validate_qualification(self.f.document, self.f.proof | {name: value})
        for name, value in (('tests', 0), ('tests', True), ('skipped', 1), ('errors', 1), ('modules', [])):
            proof = deepcopy(self.f.proof); proof['offline'][name] = value
            with self.subTest(field=name), self.assertRaises(ValueError): policy.validate_qualification(self.f.document, proof)
        for change in ('time_advice', 'encoded_capture', 'boolean_calls'):
            proof = deepcopy(self.f.proof)
            if change == 'boolean_calls': proof['synthetic'][0]['live_api_calls'] = False
            else:
                key = 'no_dynamic_time_advice' if change == 'time_advice' else 'encoded_capture_process_matching'
                proof['synthetic'][0]['checks'][key] = False
            with self.subTest(change=change), self.assertRaises(ValueError): policy.validate_qualification(self.f.document, proof)

    def test_mutated_registry_or_split_rejected(self):
        for key, value in (('parent', 'C1'), ('condition', 'C0'), ('stage', 'final'), ('cells', self.f.block['cells'][:-1]),
                ('primary_comparator', 'openhands'), ('qualification_sha256', 'a' * 64),
                ('original_results_sha256', 'b' * 64), ('raw_messages', ['not permitted'])):
            policy.block_path(self.f.rt).write_text(json.dumps(self.f.block | {key: value}))
            with self.subTest(key=key), self.assertRaises(ValueError): policy.require_block(self.f.rt)
        for tasks in (self.f.tasks[::-1], self.f.tasks[:-1], self.f.tasks + self.f.tasks[:1]):
            with self.assertRaises(ValueError): policy.cells(tasks)

    def test_private_permissions_and_symlinks_rejected(self):
        path = self.f.rt / policy.QUALIFICATION
        path.chmod(0o644)
        with self.assertRaises(ValueError): policy.require_block(self.f.rt)
        path.chmod(0o600); saved = self.f.rt / 'saved'; path.rename(saved); path.symlink_to(saved)
        with self.assertRaises((OSError, ValueError)): policy.require_block(self.f.rt)

    def test_gateway_imports_without_agent_or_host_authentication_stack(self):
        script = '''
import importlib.abc, sys
class RejectHost(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {'harbor', 'deepagents', 'langgraph', 'langchain',
            'langchain_core', 'langchain_openai', 'direct_final_evidence', 'direct_final_runtime',
            'deadline_evidence_freeze', 'deadline_candidate_freeze', 'portable_candidate_freeze',
            'scored_trial', 'no_cutoff_custom_study', 'no_cutoff_custom_runtime'}:
            raise ImportError('Host dependency: ' + name)
sys.meta_path.insert(0, RejectHost())
import no_cutoff_custom_policy as policy
from no_cutoff_custom_gateway import NoCutoffRetrySession
policy.ORIGINAL_FREEZE_SHA256 = sys.argv[2]
assert len(policy.require_block(sys.argv[1])['cells']) == 20
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.f.rt), policy.fingerprint(self.f.document)],
            capture_output=True, text=True, timeout=20, env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)))
        self.assertEqual(result.returncode, 0, result.stderr)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, folder.name)
        self.trial = self.f.block['cells'][0]['trial_id']

    def session(self, failures=(), *, timeout=10000):
        clock = Clock(); activate(self.f.rt, self.trial, timeout, policy.SETTINGS, clock)
        session = NoCutoffRetrySession(self.f.root, self.trial, 'development', TOKEN,
            Flaky(clock, failures), settings=policy.SETTINGS, clock=clock)
        session.cancelled = Event(clock)
        return session

    def test_one_hundred_five_calls_unknown_costs_no_reservation(self):
        with patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No reserve')), self.session() as session:
            session.client.response.pop('usage')
            for _ in range(105): session.complete(TOKEN, REQUEST)
            bill = summarise(self.f.rt, self.trial)
            self.assertEqual(bill['requests'], 105); self.assertEqual(bill['unknown_cost_requests'], 105)
            self.assertIsNone(bill['charged_usd'])

    def test_one_hundred_five_retries_use_shared_cooldown_not_request_cap(self):
        with self.session([(429, ['0'])] * 105) as session:
            session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 106)

    def test_credit_auth_identity_remain_real_stops(self):
        for i, status in enumerate((401, 402, 403)):
            self.trial = self.f.block['cells'][i]['trial_id']
            with self.subTest(status=status), self.session([(status, [])]) as session:
                with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
                self.assertEqual(len(session.client.calls), 1)
        # Each status is a distinct synthetic trial, never replay a session.
        self.trial = self.f.block['cells'][3]['trial_id']
        with self.session() as session:
            session.client.response['model'] = 'wrong'
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertEqual(len(session.client.calls), 1)

    def test_deadline_revocation_and_no_replay(self):
        with self.session(timeout=1) as session:
            session.clock.now += 2
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, REQUEST)
            self.assertFalse(session.client.calls)
        with self.assertRaises((ValueError, FileExistsError)): self.session()

    def test_registration_mutation_between_calls_blocks(self):
        with self.session() as session:
            session.complete(TOKEN, REQUEST)
            policy.block_path(self.f.rt).write_text(json.dumps(self.f.block | {'parent': 'C3'}))
            with self.assertRaises(ValueError): session.complete(TOKEN, REQUEST)


if __name__ == '__main__':
    unittest.main()
