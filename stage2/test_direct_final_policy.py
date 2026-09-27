"""Synthetic final registration and fake-provider sessions; no paid calls."""
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

import deadline_evidence_freeze as evidence
import deadline_candidate_freeze as candidate_contract
from deadline_candidate_freeze import freeze
import direct_final_candidate as reader
from direct_final_gateway import DirectFinalSession
import direct_final_policy as policy
from credit_only_accounting import summarise
from credit_only_gateway import CreditOnlyError
from retry_runtime import activate
from scored_gateway import private_directory, durable_json
from test_deadline_custom_policy import parent_fixture
from test_deadline_final_selection import c3_block
from test_portable_final_selection import block as development_block
from test_retry_gateway import Clock, Event, Flaky, REQUEST
from test_credit_only_gateway import TOKEN


def candidate(passes=16):
    value = freeze(parent_fixture(), c3_block(passes), registration_sha256='a' * 64,
        qualification_sha256='b' * 64,
        sources={'scored_trial.py': 'c' * 64, 'custom_model.py': 'd' * 64,
                 'custom_deadline_execution.py': 'e' * 64},
        dependencies={'python': '3.12.13', 'packages': {'harbor': '0.22.0'}})
    return dict(evidence.FIXED, candidate=value,
        anchor_files=dict.fromkeys(evidence.ANCHOR_PATHS, 'f' * 64),
        selection_logic_sources=dict.fromkeys(evidence.LOGIC_FILES, 'f' * 64),
        original_audit_sha256='0' * 64, selected_execution=evidence._execution(value))


def qualification(document):
    sources = dict(document['selected_execution']['sources'])
    sources.update(document['selection_logic_sources'])
    sources.update(dict.fromkeys(policy.REQUIRED_SOURCE_FILES, '1' * 64))
    sources['scored_trial.py'] = '2' * 64
    return dict(kind='native_direct_final_qualification', experiment=policy.EXPERIMENT,
        status='passed', live_api_calls=0, candidate_version=policy.CANDIDATE_VERSION,
        candidate_sha256=policy.fingerprint(document), policy_sha256=policy.fingerprint(policy.POLICY),
        original_authentication_sha256='9' * 64, runtime_identity_sha256='8' * 64,
        model_protocol_sha256=policy.SETTINGS.fingerprint(), input_manifest_sha256=policy.INPUT_SHA256,
        manifest_canonical_sha256=policy.MANIFEST_SHA256,
        python_runtime_sha256=policy.PYTHON_SHA256, execution_contract=policy.execution_contract(),
        dependencies=document['selected_execution']['dependencies'], setup_timeout_seconds=900,
        sources=sources, sources_sha256=policy.fingerprint(sources),
        orchestration_changes=policy.source_transition(document, sources),
        checks=dict.fromkeys(policy.QUALIFICATION_CHECKS, True),
        offline=dict(passed=True, tests=1, skipped=0, errors=0, failures=0),
        gateway_image='sha256:' + '3' * 64, guard_image='sha256:' + '4' * 64)


class Fixture:
    def __init__(self, root):
        self.root = Path(root)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.candidate = candidate()
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())
        self.proof = qualification(self.candidate)
        self.block = policy.registration(self.candidate, self.manifest, self.proof)
        self.write()

    def write(self):
        values = {policy.POLICY_FILE: policy.POLICY, policy.CANDIDATE_FILE: self.candidate,
            policy.MANIFEST_FILE: self.manifest, policy.QUALIFICATION_FILE: self.proof,
            policy.REGISTRATION_FILE: self.block}
        for name, value in values.items():
            path = self.runtime / name
            if path.exists():
                path.write_text(json.dumps(value))  # Synthetic fixture reset only.
            else:
                durable_json(path, value)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.fixture = Fixture(folder.name)
        self.rt = self.fixture.runtime
        self.trial = self.fixture.block['cells'][0]['trial_id']

    def test_exact_eighty_nine_fresh_cells_and_original_order(self):
        block = policy.require_trial(self.rt, self.trial, 'final')
        rows = block['cells']
        self.assertEqual(len(rows), 89)
        self.assertEqual(len({r['trial_id'] for r in rows}), 89)
        self.assertEqual({r['task_id'] for r in rows}, set(self.fixture.manifest['all_task_ids']))
        self.assertEqual([r['task_id'] for r in rows[:20]], self.fixture.manifest['development_ids'])
        self.assertTrue(all(r['stage'] == 'final' and r['harness'] == 'C3' and r['parent'] == 'C0'
                            and len(r['trial_id']) <= 120 for r in rows))
        old = set(self.fixture.candidate['candidate']['result_bindings'])
        self.assertFalse(old & {r['trial_id'] for r in rows})

    def test_lightweight_reader_matches_original_frozen_schema_and_selections(self):
        from portable_evaluation_schedule import MANIFEST_SHA256
        self.assertEqual(reader.MANIFEST_SHA256, MANIFEST_SHA256)
        self.assertEqual(reader.CANDIDATE_KIND, candidate_contract.KIND)
        self.assertEqual(reader.CANDIDATE_FIELDS, candidate_contract.FIELDS)
        self.assertEqual(reader.FIXED, evidence.FIXED)
        self.assertEqual(reader.VARIABLE_FIELDS, evidence.VARIABLE_FIELDS)
        self.assertEqual(reader.ANCHOR_PATHS, set(evidence.ANCHOR_PATHS))
        self.assertEqual(reader.LOGIC_FILES, set(evidence.LOGIC_FILES))
        for passes in range(21):
            document = candidate(passes)
            with self.subTest(passes=passes):
                self.assertEqual(reader.validate_document(document), evidence.validate_document(document))

    def test_lightweight_reader_rejects_schema_result_and_execution_tampering(self):
        for change in ('admission', 'boolean_schema', 'private', 'candidate_field', 'protocol',
                       'selection', 'result', 'count', 'lineage', 'execution', 'anchor', 'logic',
                       'hash', 'source', 'dependencies'):
            document = deepcopy(self.fixture.candidate)
            value = document['candidate']
            if change == 'admission': document['paid_launch_ready'] = True
            elif change == 'boolean_schema': document['schema_version'] = True
            elif change == 'private': document['raw_messages'] = ['not allowed']
            elif change == 'candidate_field': value.pop('c3_registration_sha256')
            elif change == 'protocol': value['model_protocol_sha256'] = '8' * 64
            elif change == 'selection': value['selection']['selected'] = 'C0'
            elif change == 'result': value['result_bindings'].pop(next(iter(value['result_bindings'])))
            elif change == 'count': value['c3_summary']['passes'] += 1
            elif change == 'lineage': value['c3_summary']['parent'] = 'C1'
            elif change == 'execution': document['selected_execution']['sources_sha256'] = '8' * 64
            elif change == 'anchor': document['anchor_files'].pop(next(iter(document['anchor_files'])))
            elif change == 'logic': document['selection_logic_sources']['unknown.py'] = '8' * 64
            elif change == 'hash': document['original_audit_sha256'] = 'bad'
            elif change == 'source': value['c3_sources']['../escape'] = '8' * 64
            else: value['c3_dependencies']['python'] = 'latest'
            for validate in (reader.validate_document, evidence.validate_document):
                with self.subTest(change=change, validator=validate.__module__), self.assertRaises(ValueError):
                    validate(document)

    def test_other_whole_winners_keep_their_original_runtime_and_c3_lineage(self):
        from portable_final_selection import select
        for winner in ('C1', 'C2'):
            parent = parent_fixture()
            summaries = dict(C0=development_block('C0', 15, unknown=True),
                C1=development_block('C1', 16),
                C2=development_block('C2', 17 if winner == 'C2' else 14, 'C1'))
            parent.update(summaries=summaries, selection=select(summaries),
                results_sha256={row['trial_id']: row['result_sha256']
                    for summary in summaries.values() for row in summary['rows']})
            for passes in (0, 20):
                c3 = c3_block(passes)
                c3.update(parent=winner, base_parent='C1' if winner == 'C2' else None,
                    complexity=parent['selection']['summaries'][winner]['complexity'] + 1)
                document = deepcopy(self.fixture.candidate)
                original = document['candidate']
                document['candidate'] = freeze(parent, c3,
                    registration_sha256=original['c3_registration_sha256'],
                    qualification_sha256=original['c3_qualification_sha256'],
                    sources=original['c3_sources'], dependencies=original['c3_dependencies'])
                document['selected_execution'] = evidence._execution(document['candidate'])
                with self.subTest(winner=winner, passes=passes):
                    self.assertEqual(reader.validate_document(document), evidence.validate_document(document))
                    if passes == 0:
                        with self.assertRaises(ValueError): policy.candidate_execution(document)
                    else:
                        self.assertEqual(policy.candidate_execution(document)['parent'], winner)

    def test_gateway_registration_reads_without_host_or_agent_dependencies(self):
        # The native gateway image intentionally lacks Harbor/Deep Agents.
        # A fresh interpreter catches imports masked by the full host venv.
        script = '''
import importlib.abc, sys
class RejectHostStack(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {
            'harbor', 'deepagents', 'langgraph', 'langchain', 'langchain_core',
            'langchain_openai', 'deadline_evidence_freeze', 'deadline_candidate_freeze',
            'portable_candidate_freeze', 'export_deadline_custom', 'progress_dashboard',
            'scored_trial', 'run_deadline_custom', 'run_portable_custom'}:
            raise ImportError('Host-only dependency: ' + name)
sys.meta_path.insert(0, RejectHostStack())
from direct_final_gateway import DirectFinalSession
from direct_final_policy import require_block
block = require_block(sys.argv[1])
assert len(block['cells']) == 89
assert block['condition'] == 'C3'
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.rt)],
            text=True, capture_output=True, timeout=20,
            env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent)))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_financial_and_artificial_execution_caps_absent(self):
        p = policy.require_policy(self.rt)
        for name in ('project_cap_usd', 'stage_cap_usd', 'per_task_cap_usd', 'model_call_cap',
                     'physical_request_count_cap', 'provider_max_price'):
            self.assertIsNone(p[name])
        self.assertEqual(p['reserve_usd'], '0')
        self.assertFalse(p['accounting_blocks_dispatch'])
        for name in ('automatic_top_up', 'automatic_purchase', 'automatic_credit_limit_increase'):
            self.assertFalse(p[name])
        execution = p['execution_contract']
        self.assertEqual(execution['default_command_timeout'], 'remaining-official-task-time')
        for name in ('model_call_cap', 'completion_repair_count_cap',
                     'background_active_count_cap', 'background_lifetime_count_cap'):
            self.assertIsNone(execution[name])
        self.assertEqual(p['confirmation'], 'deferred-not-completed')
        self.assertEqual(p['diagnostic'], 'deferred-not-completed')

    def test_original_file_hash_and_canonical_private_copy_hash_are_distinct(self):
        raw = (Path(__file__).parent / 'input_manifest.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), policy.INPUT_SHA256)
        self.assertEqual(policy.fingerprint(self.fixture.manifest), policy.MANIFEST_SHA256)
        self.assertNotEqual(policy.INPUT_SHA256, policy.MANIFEST_SHA256)
        path = self.rt / policy.MANIFEST_FILE
        path.write_text(json.dumps(self.fixture.manifest, indent=4))
        self.assertEqual(policy.require_block(self.rt), self.fixture.block)

    def test_older_winner_is_not_promoted_as_newer_uncapped_agent(self):
        for count in (0, 14, 15):
            document = candidate(count)
            self.assertEqual(document['candidate']['selection']['selected'], 'C0')
            with self.subTest(passes=count), self.assertRaises(ValueError):
                policy.cells(document, self.fixture.manifest)

    def test_mutated_full_manifest_rejected(self):
        for change in ('order', 'identity', 'resource'):
            manifest = deepcopy(self.fixture.manifest)
            if change == 'order': manifest['development_ids'].reverse()
            elif change == 'identity': manifest['outside_development_ids'][0] = 'different-task'
            else: manifest['tasks'][0]['memory_mb'] += 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.cells(self.fixture.candidate, manifest)

    def test_original_agent_and_gateway_behaviour_cannot_drift(self):
        current = deepcopy(self.fixture.proof['sources'])
        for name in ('custom_model.py', 'custom_deadline_execution.py'):
            changed = dict(current, **{name: '5' * 64})
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.source_transition(self.fixture.candidate, changed)
        for name in ('custom_model.py', 'direct_final_gateway.py'):
            changed = dict(current); changed.pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.source_transition(self.fixture.candidate, changed)

    def test_only_explicit_trusted_orchestration_delta_is_bound(self):
        delta = policy.source_transition(self.fixture.candidate, self.fixture.proof['sources'])
        self.assertEqual(delta, {'scored_trial.py': {
            'original_sha256': 'c' * 64, 'qualified_sha256': '2' * 64}})
        proof = deepcopy(self.fixture.proof); proof['orchestration_changes'] = {}
        with self.assertRaises(ValueError):
            policy.validate_qualification(proof, self.fixture.candidate, self.fixture.manifest)

    def test_operator_authentication_sources_are_bound_as_well_as_agent(self):
        for name in self.fixture.candidate['selection_logic_sources']:
            for missing in (True, False):
                sources = deepcopy(self.fixture.proof['sources'])
                if missing: sources.pop(name)
                else: sources[name] = '8' * 64
                with self.subTest(name=name, missing=missing), self.assertRaises(ValueError):
                    policy.source_transition(self.fixture.candidate, sources)

    def test_native_proof_cannot_be_old_development_or_partial_local_evidence(self):
        for change in ('kind', 'stage', 'checks', 'check_false', 'calls', 'bool_calls',
                       'offline_failed', 'offline_skip', 'zero_tests', 'bool_tests',
                       'dependencies', 'image', 'source_hash', 'runtime', 'model', 'contract',
                       'authentication', 'current_runtime'):
            proof = deepcopy(self.fixture.proof)
            if change == 'kind': proof['kind'] = 'synthetic-probe-only-not-paid-admission'
            elif change == 'stage': proof['experiment'] = 'custom-deadline-development-20260927'
            elif change == 'checks': proof['checks'].pop(next(iter(proof['checks'])))
            elif change == 'check_false': proof['checks']['native_tracing_and_revocation'] = False
            elif change == 'calls': proof['live_api_calls'] = 1
            elif change == 'bool_calls': proof['live_api_calls'] = False
            elif change == 'offline_failed': proof['offline']['passed'] = False
            elif change == 'offline_skip': proof['offline']['skipped'] = 1
            elif change == 'zero_tests': proof['offline']['tests'] = 0
            elif change == 'bool_tests': proof['offline']['tests'] = True
            elif change == 'dependencies': proof['dependencies']['packages']['harbor'] = '0.99.0'
            elif change == 'image': proof['gateway_image'] = 'mutable:tag'
            elif change == 'source_hash': proof['sources_sha256'] = '6' * 64
            elif change == 'runtime': proof['python_runtime_sha256'] = '6' * 64
            elif change == 'model': proof['model_protocol_sha256'] = '6' * 64
            elif change == 'authentication': proof.pop('original_authentication_sha256')
            elif change == 'current_runtime': proof.pop('runtime_identity_sha256')
            else: proof['execution_contract']['model_call_cap'] = 100
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.validate_qualification(proof, self.fixture.candidate, self.fixture.manifest)

    def test_registration_mutation_or_extra_private_field_rejected(self):
        original = deepcopy(self.fixture.block)
        for change in ('partial', 'duplicate', 'order', 'identity', 'replay', 'parallel',
                       'comparator', 'private', 'boolean_schema'):
            block = deepcopy(original)
            if change == 'partial': block['cells'].pop()
            elif change == 'duplicate': block['cells'][1] = block['cells'][0]
            elif change == 'order': block['cells'].reverse()
            elif change == 'identity': block['cells'][0]['trial_id'] = 'customdev3-c3-01-video-processing'
            elif change == 'replay': block['automatic_task_replay'] = True
            elif change == 'parallel': block['parallel_trials'] = 2
            elif change == 'comparator': block['primary_comparator'] = 'openhands'
            elif change == 'private': block['raw_messages'] = ['not allowed']
            else: block['schema_version'] = True
            (self.rt / policy.REGISTRATION_FILE).write_text(json.dumps(block))
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.require_trial(self.rt, self.trial, 'final')

    def test_wrong_stage_unregistered_cell_and_old_trial_refused(self):
        for trial, stage in ((self.trial, 'development'), ('customdev3-c3-01-video-processing', 'final'),
                             ('customfinal1-c3-01-other', 'final'), ('../escape', 'final')):
            with self.subTest(trial=trial), self.assertRaises(ValueError):
                policy.require_trial(self.rt, trial, stage)

    def test_changed_candidate_or_policy_cannot_reuse_registration(self):
        document = deepcopy(self.fixture.candidate)
        document['original_audit_sha256'] = '7' * 64
        (self.rt / policy.CANDIDATE_FILE).write_text(json.dumps(document))
        with self.assertRaises(ValueError): policy.require_block(self.rt)
        self.fixture.write()
        (self.rt / policy.POLICY_FILE).write_text(json.dumps(dict(policy.POLICY, reserve_usd='1')))
        with self.assertRaises(ValueError): policy.require_block(self.rt)

    def test_private_metadata_permissions_and_symlinks(self):
        for name in (policy.CANDIDATE_FILE, policy.MANIFEST_FILE, policy.QUALIFICATION_FILE,
                     policy.REGISTRATION_FILE, policy.POLICY_FILE):
            path = self.rt / name; path.chmod(0o644)
            with self.subTest(name=name), self.assertRaises(ValueError): policy.require_block(self.rt)
            path.chmod(0o600)
            moved = path.with_suffix('.saved'); path.rename(moved); path.symlink_to(moved)
            with self.subTest(name=name), self.assertRaises((OSError, ValueError)): policy.require_block(self.rt)
            path.unlink(); moved.rename(path)

    def test_source_paths_and_missing_source_map_refused(self):
        for current in (None, {}, {'../escape': 'a' * 64}, {'bad.py': 'not-a-hash'}):
            with self.subTest(current=current), self.assertRaises(ValueError):
                policy.source_transition(self.fixture.candidate, current)

    def test_no_files_or_mutable_alias_created_by_registration_builder(self):
        before = deepcopy((self.fixture.candidate, self.fixture.manifest, self.fixture.proof))
        files = sorted(p.relative_to(self.rt).as_posix() for p in self.rt.rglob('*'))
        block = policy.registration(*before)
        block['cells'][0]['task_id'] = 'changed-output'
        self.assertEqual((self.fixture.candidate, self.fixture.manifest, self.fixture.proof), before)
        self.assertEqual(sorted(p.relative_to(self.rt).as_posix() for p in self.rt.rglob('*')), files)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.fixture = Fixture(folder.name)
        self.rt = self.fixture.runtime

    def session(self, failures=(), timeout=10000, index=0):
        clock = Clock(); name = self.fixture.block['cells'][index]['trial_id']
        activate(self.rt, name, timeout, policy.SETTINGS, clock)
        session = DirectFinalSession(self.fixture.root, name, 'final', TOKEN,
            Flaky(clock, failures), settings=policy.SETTINGS, clock=clock)
        session.cancelled = Event(clock)
        return session

    def test_over_one_hundred_unknown_cost_calls_without_billing_gate(self):
        with patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No reservation')), self.session() as s:
            s.client.response.pop('usage')
            for _ in range(105): s.complete(TOKEN, REQUEST)
            bill = summarise(self.rt, s.trial_id)
            self.assertEqual((bill['requests'], bill['unknown_cost_requests']), (105, 105))
            self.assertIsNone(bill['charged_usd'])
            self.assertFalse(list(self.rt.glob('*.sqlite')))

    def test_shared_retry_more_than_one_hundred_physical_calls(self):
        with self.session([(429, ['0'])] * 105) as s:
            s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 106)
            self.assertIsNone(summarise(self.rt, s.trial_id)['charged_usd'])

    def test_registration_drift_blocks_before_another_provider_call(self):
        with self.session() as s:
            s.complete(TOKEN, REQUEST)
            block = deepcopy(self.fixture.block); block['cells'].pop()
            (self.rt / policy.REGISTRATION_FILE).write_text(json.dumps(block))
            with self.assertRaises(ValueError): s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 1)

    def test_credit_auth_and_identity_failures_are_not_bypassed(self):
        for index, status in enumerate((401, 402, 403)):
            with self.session([(status, [])], index=index) as s:
                with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
                self.assertEqual(len(s.client.calls), 1)
                self.assertTrue((s.evidence / 'provider-stop.json').exists())
        with self.session(index=3) as s:
            s.client.response['model'] = 'wrong'
            with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 1)

    def test_official_deadline_and_revocation_still_prevent_dispatch(self):
        with self.session(timeout=1) as s:
            s.clock.now += 2
            with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
            self.assertEqual(s.client.calls, [])
        with self.session(index=1) as s:
            s.cancelled.set()
            with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
            self.assertEqual(s.client.calls, [])

    def test_attempt_cannot_restart_and_completed_calls_are_not_retried(self):
        with self.session() as s:
            s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 1)
        with self.assertRaises((ValueError, FileExistsError)): self.session()

    def test_gateway_owner_lock_prevents_an_overlapping_attempt(self):
        with self.session():
            with self.assertRaises(BlockingIOError): self.session(index=1)
        name = self.fixture.block['cells'][1]['trial_id']
        self.assertFalse((self.rt / 'scored-attempts' / name).exists())

    def test_shared_cooldown_survives_to_next_registered_task(self):
        with self.session([(429, ['50'])], timeout=1) as first:
            with self.assertRaises(CreditOnlyError): first.complete(TOKEN, REQUEST)
            self.assertEqual(len(first.client.calls), 1)
            self.assertIsNone(summarise(self.rt, first.trial_id)['charged_usd'])
        with self.session(index=1, timeout=100) as second:
            second.complete(TOKEN, REQUEST)
            self.assertEqual(second.clock.now, 150.)
            self.assertEqual(len(second.client.calls), 1)


if __name__ == '__main__':
    unittest.main()
