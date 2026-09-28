"""Synthetic private files and actual shared phase traces, never paid evidence."""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_final_phase_audit as audit
from local_trace import observation

STAGE = Path(__file__).resolve().parent
BASE = 1_800_000_000_000_000_000


class PhaseFiles(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.trial_id = 'customfinal2-c0-nc-01-synthetic'
        self.task_id = 'synthetic'
        self.trial = audit.RT + 'scored-trials/' + self.trial_id
        self.accounting = audit.RT + 'scored-attempts/' + self.trial_id
        self.life = audit.RT + 'retry-lifecycle/' + self.trial_id + '.json'
        sources = {n: self.write('stage2/' + n, (STAGE / n).read_bytes()) for n in audit.FROZEN_HELPERS}
        self.host = dict(task_inventory={self.task_id: dict(agent_timeout_seconds=7200.0,
            verifier_timeout_seconds=900.0, image_id='sha256:' + '2' * 64)})
        self.proof = dict(sources=sources, sources_sha256=audit.fingerprint(sources), setup_timeout_seconds=900,
            runtime_identity_sha256=audit.fingerprint(self.host), gateway_image='sha256:' + '1' * 64)
        qualification = audit.fingerprint(self.proof)
        self.block = dict(qualification_sha256=qualification, sources_sha256=self.proof['sources_sha256'],
            cells=[dict(trial_id=self.trial_id, task_id=self.task_id, harness='C0-NC')])
        registration = audit.fingerprint(self.block)
        pins = dict(SOURCE_SET=self.proof['sources_sha256'], QUALIFICATION=qualification, REGISTRATION=registration,
            QUALIFICATION_FILE=self.save(audit.RT + 'no-cutoff-final-qualification.json', self.proof),
            REGISTRATION_FILE=self.save(audit.RT + 'no-cutoff-final-matrix.json', self.block))
        pins['RUNTIME_FILE'] = self.save(audit.RT + 'no-cutoff-final-runtime.json', self.host)
        for name, value in pins.items(): self.enterContext(patch.object(audit, name, value))
        self.identity = dict(trial_id=self.trial_id, task_id=self.task_id, harness='C0-NC', stage='final',
            custom_study='custom-no-cutoff-final-20260928', custom_registration_sha256=registration,
            model_protocol_sha256=audit.MODEL, gateway_image_id=self.proof['gateway_image'],
            accounting_mode='provider-credit-only', started_utc='2026-09-28T00:00:00+00:00',
            project='uts-scored-' + 'a' * 12)
        self.save(self.trial + '/started.json', dict(self.identity, status='starting'))
        self.result = dict(self.identity, status='verified', task_image_id=self.host['task_inventory'][self.task_id]['image_id'],
            agent_error_type=None, verifier_error_type=None, verifier_result={'rewards': {'reward': 1.0}},
            model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
            cleanup_errors=[], phase_seconds={'setup': 1.0, 'agent': 2.0, 'verifier': 1.0},
            billing={'requests': 0, 'unknown_cost_requests': 0, 'charged_usd': '0'})
        self.events = [self.event('trial', 0, 0, 5), self.event('setup', 1, 0, 1),
            self.event('agent', 2, 1, 3), self.event('verifier', 3, 3, 4, reward=1.0), self.event('cleanup', 4, 4, 5)]
        self.save(self.life, dict(trial_id=self.trial_id, model_protocol_sha256=audit.MODEL, boot_id='synthetic-boot',
            deadline_monotonic=7200.0, deadline_utc=BASE / 1e9 + 1 + 7200.0))
        self.save(self.accounting + '/started.json', {'trial_id': self.trial_id})
        self.flush()

    def write(self, name, raw):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw); path.chmod(0o600)
        return hashlib.sha256(raw).hexdigest()

    def save(self, name, value):
        return self.write(name, json.dumps(value, allow_nan=False).encode())

    def event(self, kind, sequence, start, end, *, status='ok', reward=None):
        return observation(trial_id=self.trial_id, task_id=self.task_id, harness='C0-NC', protocol_sha256=audit.MODEL,
            kind=kind, sequence=sequence, started_ns=BASE + int(start * 1e9), ended_ns=BASE + int(end * 1e9),
            status=status, reward=reward, metrics={'duration_seconds': float(end - start)})

    def flush(self, *, summary=True):
        if summary:
            count = sum(e['kind'] == 'generation' for e in self.events)
            for e in self.events:
                if e['kind'] == 'trial': e['metrics']['requests'] = self.result['billing']['requests']
            self.result['trace'] = dict(status='metadata_spool_not_cloud_export', events=len(self.events),
                generations=count, missing_generation_timings=self.result['billing']['requests'] - count,
                unknown_cost_requests=self.result['billing']['unknown_cost_requests'])
        self.save(self.trial + '/result.json', self.result)
        folder = self.root / self.trial / 'traces'; folder.mkdir(exist_ok=True, mode=0o700)
        for p in folder.iterdir(): p.unlink()  # Only this temporary synthetic spool.
        for event in self.events: self.save(self.trial + '/traces/' + event['event_id'] + '.json', event)

    def setup_only(self):
        self.result.update(status='setup_failed', agent_error_type='RuntimeError', verifier_result=None,
            phase_seconds={'setup': 1.0})
        self.events = [self.event('trial', 0, 0, 2, status='error'),
            self.event('setup', 1, 0, 1, status='error'), self.event('cleanup', 2, 1, 2)]
        (self.root / self.life).unlink()
        self.flush()

    def read(self):
        return audit.read_phase_evidence(self.root, self.trial_id)

    def test_measured_phases_and_zero_reward_are_retained_without_score_inheritance(self):
        for reward in (1.0, 0.0):
            self.result['verifier_result']['rewards']['reward'] = reward
            self.events[3]['reward'] = reward; self.flush()
            r = self.read(); self.assertEqual(r['row']['reward'], int(reward))
            self.assertEqual(r['row']['agent_seconds'], 2.0)
            self.assertEqual(r['row']['official_agent_timeout_seconds'], 7200.0)
            self.assertTrue(all(v == 'measured' for v in r['row']['phase_observation'].values()))
            self.assertFalse(r['paid_launch_ready']); self.assertFalse(r['completed_final_audit'])

    def test_setup_failure_preserves_null_phases_reward_and_actual_deadline_absence(self):
        self.setup_only(); before = (self.root / self.trial / 'result.json').read_bytes()
        r = self.read()
        self.assertIsNone(r['row']['reward']); self.assertIsNone(r['row']['agent_seconds'])
        self.assertIsNone(r['row']['verifier_seconds']); self.assertEqual(r['row']['setup_seconds'], 1.0)
        self.assertEqual(r['row']['phase_observation']['agent'], 'not_run_setup_failed')
        self.assertIn(self.life, r['absent_paths'])
        self.assertEqual(before, (self.root / self.trial / 'result.json').read_bytes())
        audit.recheck(self.root, r)

    def test_missing_accounting_directory_is_recorded_as_absent_not_recreated(self):
        self.setup_only(); folder = self.root / self.accounting
        (folder / 'started.json').unlink(); folder.rmdir()
        r = self.read(); self.assertIn(self.accounting, r['absent_paths']); self.assertFalse(folder.exists())

    def test_setup_only_is_uniform_not_an_exception_for_observed_task_numbers(self):
        self.setup_only()
        self.assertEqual(self.read()['row']['trial_id'], 'customfinal2-c0-nc-01-synthetic')
        self.assertNotIn('schemelike', json.dumps(audit.contract()))

    def test_missing_executed_phase_cannot_be_labelled_not_run(self):
        for kind in ('setup', 'agent', 'verifier', 'cleanup', 'trial'):
            with self.subTest(kind=kind):
                original = self.events; self.events = [e for e in original if e['kind'] != kind]
                self.flush()
                with self.assertRaises(ValueError): self.read()
                self.events = original

    def test_setup_failure_cannot_gain_zero_timings_or_a_reward(self):
        self.setup_only()
        for change in ({'phase_seconds': {'setup': 1.0, 'agent': 0, 'verifier': 0}},
                {'verifier_result': {'rewards': {'reward': 0}}}, {'agent_error_type': None},
                {'verifier_error_type': 'RuntimeError'}):
            before = deepcopy(self.result); self.result.update(change); self.flush()
            with self.subTest(change=change), self.assertRaises(ValueError): self.read()
            self.result = before

    def test_setup_only_refuses_request_artifacts_even_with_claimed_zero_requests(self):
        self.setup_only()
        for suffix in ('request', 'outcome', 'timing', 'transport-error', 'retry', 'response'):
            name = self.accounting + '/000001.' + suffix + '.json'; self.save(name, {})
            with self.subTest(suffix=suffix), self.assertRaises(ValueError): self.read()
            (self.root / name).unlink()

    def test_setup_only_refuses_an_agent_deadline_even_without_a_request(self):
        self.setup_only(); self.save(self.life, {'trial_id': self.trial_id})
        with self.assertRaises(ValueError): self.read()

    def test_setup_only_refuses_generation_tool_or_graph_observations(self):
        self.setup_only()
        for kind in ('generation', 'tool', 'graph'):
            self.events.append(self.event(kind, 3, .2, .3)); self.flush()
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.read()
            self.events.pop()

    def test_normal_missing_agent_deadline_is_rejected_not_synthesised(self):
        (self.root / self.life).unlink()
        with self.assertRaises(ValueError): self.read()
        self.assertFalse((self.root / self.life).exists())

    def test_shortened_or_mismatched_deadline_is_rejected(self):
        name = self.life; original = json.loads((self.root / name).read_text())
        for change in ({'deadline_utc': BASE / 1e9 + 2}, {'model_protocol_sha256': 'f' * 64},
                {'trial_id': 'other'}, {'deadline_monotonic': True}, {'boot_id': ''}):
            self.save(name, original | change)
            with self.subTest(change=change), self.assertRaises(ValueError): self.read()

    def test_unconsumed_timeout_cannot_claim_official_allowance(self):
        for phase, error_key in (('agent', 'agent_error_type'), ('verifier', 'verifier_error_type')):
            before = deepcopy(self.result); events = deepcopy(self.events)
            self.result[error_key] = 'TimeoutError'
            next(e for e in self.events if e['kind'] == phase)['status'] = 'timeout'
            if phase == 'verifier':
                self.result.update(status='verifier_failed', verifier_result=None)
                self.events[0]['status'] = 'error'; self.events[3]['reward'] = None
            self.flush()
            with self.subTest(phase=phase), self.assertRaises(ValueError): self.read()
            self.result = before; self.events = events

    def test_setup_timeout_must_use_qualified_900_seconds(self):
        self.setup_only(); self.result['agent_error_type'] = 'TimeoutError'; self.events[1]['status'] = 'timeout'; self.flush()
        with self.assertRaises(ValueError): self.read()

    def test_verifier_failure_keeps_null_reward_but_measured_phases(self):
        self.result.update(status='verifier_failed', verifier_error_type='RuntimeError', verifier_result=None)
        self.events[0]['status'] = 'error'; self.events[3].update(status='error', reward=None); self.flush()
        r = self.read(); self.assertIsNone(r['row']['reward']); self.assertEqual(r['row']['verifier_seconds'], 1.0)

    def test_true_missing_reward_in_verified_result_is_preserved(self):
        self.result['verifier_result'] = {'rewards': {}}; self.events[3]['reward'] = None; self.flush()
        self.assertIsNone(self.read()['row']['reward'])

    def test_no_cleanup_or_revocation_admission_relaxation(self):
        for key in ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed'):
            self.result[key] = False; self.flush()
            with self.subTest(key=key), self.assertRaises(ValueError): self.read()
            self.result[key] = True
        for change in ({'cleanup_errors': ['synthetic']}, {'trace_errors': ['setup:RuntimeError']},
                {'error_type': 'RuntimeError'}, {'bridge_error_type': 'RuntimeError'}):
            before = deepcopy(self.result); self.result.update(change); self.flush()
            with self.subTest(change=change), self.assertRaises(ValueError): self.read()
            self.result = before

    def test_wrong_status_or_exception_text_is_not_reported(self):
        for change in ({'status': 'interrupted'}, {'status': 'infrastructure_failed'},
                {'agent_error_type': 'PRIVATE RAW EXCEPTION'}, {'verifier_error_type': True}):
            before = deepcopy(self.result); self.result.update(change); self.flush()
            with self.subTest(change=change), self.assertRaises(ValueError): self.read()
            self.result = before

    def test_missing_boolean_negative_nonfinite_and_changed_duration_refused(self):
        for value in (None, True, -1, float('nan'), float('inf'), 3.0, 2):
            self.result['phase_seconds']['agent'] = value
            # Invalid JSON constants are written only in this negative fixture.
            self.write(self.trial + '/result.json', json.dumps(self.result).encode())
            with self.subTest(value=value), self.assertRaises(ValueError): self.read()

    def test_trace_status_order_identity_and_duplicate_sequence_refused(self):
        for change in ('status', 'outside', 'overlap', 'identity', 'duplicate', 'reward'):
            old = deepcopy(self.events)
            if change == 'status': self.events[4]['status'] = 'error'
            elif change == 'outside': self.events[2]['ended_ns'] = BASE + 10**10
            elif change == 'overlap': self.events[3]['started_ns'] = BASE
            elif change == 'identity': self.events[2]['task_id'] = 'other'
            elif change == 'duplicate': self.events.append(self.event('agent', 2, 1, 3))
            else: self.events[3]['reward'] = 0
            self.flush()
            if change == 'duplicate':
                # Different filename cannot conceal a duplicate event ID.
                self.save(self.trial + '/traces/duplicate.json', self.events[-1])
            with self.subTest(change=change), self.assertRaises(ValueError): self.read()
            self.events = old

    def add_requests(self):
        self.save(self.accounting + '/000001.request.json', {'messages': 'PRIVATE MODEL TEXT'})
        self.save(self.accounting + '/000001.outcome.json', {'cost_usd': None, 'status': 'ok'})
        self.save(self.accounting + '/000002.request.json', {'messages': 'PRIVATE INTERRUPTED TEXT'})
        timing = dict(started_ns=BASE + 10**9, ended_ns=BASE + 2 * 10**9, seconds=1.0, status='ok')
        self.save(self.accounting + '/000001.timing.json', timing)
        self.events.append(self.event('generation', 5, 1, 2))
        self.result['billing'].update(requests=2, unknown_cost_requests=2, charged_usd=None)
        self.flush()

    def test_unknown_cost_and_missing_generation_timing_remain_actual_unknowns(self):
        self.add_requests(); raw = (self.root / self.trial / 'result.json').read_bytes()
        report = self.read(); row = report['row']
        self.assertEqual((row['model_requests'], row['generation_timings'], row['missing_generation_timings']), (2, 1, 1))
        self.assertNotIn('PRIVATE', json.dumps(report)); self.assertNotIn('charged_usd', row)
        self.assertIsNone(json.loads(raw)['billing']['charged_usd'])
        self.assertEqual(raw, (self.root / self.trial / 'result.json').read_bytes())

    def test_missing_or_orphaned_timing_cannot_replace_generation_trace(self):
        self.add_requests(); (self.root / self.accounting / '000001.timing.json').unlink()
        with self.assertRaises(ValueError): self.read()
        self.save(self.accounting + '/other.timing.json', {'seconds': 1.0})
        with self.assertRaises(ValueError): self.read()

    def test_trace_summary_cannot_claim_missing_events_or_requests_are_zero(self):
        self.add_requests()
        for key in ('events', 'generations', 'missing_generation_timings', 'unknown_cost_requests'):
            before = deepcopy(self.result); self.result['trace'][key] = True; self.flush(summary=False)
            with self.subTest(key=key), self.assertRaises(ValueError): self.read()
            self.result = before
        self.result['billing']['requests'] = 0; self.flush(summary=False)
        with self.assertRaises(ValueError): self.read()

    def test_root_request_and_billing_unknown_counts_must_match_actual_metadata(self):
        self.add_requests(); original = deepcopy(self.result)
        self.result['billing']['unknown_cost_requests'] = 1; self.flush(summary=False)
        with self.assertRaises(ValueError): self.read()
        self.result = original; self.events[0]['metrics']['requests'] = 1; self.flush(summary=False)
        with self.assertRaises(ValueError): self.read()

    def test_null_or_nonobject_trace_and_accounting_summaries_are_refused(self):
        for field in ('trace', 'billing'):
            old = self.result[field]
            for value in (None, [], 'PRIVATE'):
                self.result[field] = value
                self.save(self.trial + '/result.json', self.result)
                with self.subTest(field=field, value=value), self.assertRaises(ValueError): self.read()
            self.result[field] = old

    def test_required_duration_on_trial_cleanup_and_generation_cannot_disappear(self):
        self.add_requests()
        for kind in ('trial', 'cleanup', 'generation'):
            event = next(e for e in self.events if e['kind'] == kind)
            old = event['metrics'].pop('duration_seconds'); self.flush()
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.read()
            event['metrics']['duration_seconds'] = old

    def test_qualified_anchor_or_source_drift_refused(self):
        for name in (audit.RT + 'no-cutoff-final-qualification.json', audit.RT + 'no-cutoff-final-matrix.json',
                audit.RT + 'no-cutoff-final-runtime.json', 'stage2/export_no_cutoff_final.py', 'stage2/local_trace.py'):
            path = self.root / name; raw = path.read_bytes(); path.write_bytes(raw + b' ')
            with self.subTest(name=name), self.assertRaises(ValueError): self.read()
            path.write_bytes(raw)

    def test_start_result_registration_model_image_and_project_identity_refused(self):
        for key in ('trial_id', 'task_id', 'harness', 'stage', 'custom_study', 'custom_registration_sha256',
                'model_protocol_sha256', 'gateway_image_id', 'task_image_id', 'accounting_mode', 'project', 'started_utc'):
            old = self.result[key]; self.result[key] = 'different'; self.flush()
            with self.subTest(key=key), self.assertRaises(ValueError): self.read()
            self.result[key] = old
        with self.assertRaises(ValueError): audit.read_phase_evidence(self.root, 'unregistered')

    def test_duplicate_private_json_fields_refused(self):
        name = self.trial + '/result.json'; raw = (self.root / name).read_bytes()
        self.write(name, raw[:-1] + b',"status":"verified"}')
        with self.assertRaises(ValueError): self.read()

    def test_unsafe_permissions_links_and_hardlinks_refused(self):
        path = self.root / self.trial / 'result.json'; raw = path.read_bytes()
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.read()
        path.chmod(0o600); other = path.with_name('private-copy'); path.rename(other); path.symlink_to(other)
        with self.assertRaises(ValueError): self.read()
        path.unlink(); os.link(other, path)
        with self.assertRaises(ValueError): self.read()
        path.unlink(); other.unlink(); self.write(self.trial + '/result.json', raw)

    def test_symlinked_ancestor_or_evidence_directory_refused(self):
        path = self.root / self.trial / 'traces'; other = path.with_name('saved-traces')
        path.rename(other); path.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError): self.read()

    def test_unsafe_unexpected_or_pending_trace_member_refused(self):
        self.write(self.trial + '/traces/.pending-evidence', b'partial')
        with self.assertRaises(ValueError): self.read()

    def test_provider_stop_not_acknowledged_or_erased(self):
        self.save(self.accounting + '/provider-stop.json', {'reason': 'synthetic'})
        with self.assertRaises(ValueError): self.read()
        self.assertTrue((self.root / self.accounting / 'provider-stop.json').exists())

    def test_recheck_detects_raw_bytes_after_read_without_rewriting(self):
        report = self.read(); path = self.root / self.trial / 'result.json'; path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(ValueError): audit.recheck(self.root, report)

    def test_recheck_detects_new_file_and_new_previously_absent_deadline(self):
        self.setup_only(); report = self.read()
        self.save(self.life, {})
        with self.assertRaises(ValueError): audit.recheck(self.root, report)
        (self.root / self.life).unlink(); self.save(self.accounting + '/extra.json', {})
        with self.assertRaises(ValueError): audit.recheck(self.root, report)

    def test_recheck_detects_dangling_symlink_in_previously_absent_path(self):
        self.setup_only(); report = self.read(); (self.root / self.life).symlink_to(self.root / 'absent')
        with self.assertRaises(ValueError): audit.recheck(self.root, report)

    def test_recheck_refuses_paid_or_complete_flags_private_fields_and_reporting_source_drift(self):
        report = self.read()
        for change in ({'paid_launch_ready': True}, {'completed_final_audit': True}, {'raw': 'PRIVATE'},
                {'amendment_sha256': 'f' * 64}, {'reporting_source_files': {}}):
            with self.subTest(change=change), self.assertRaises(ValueError): audit.recheck(self.root, report | change)

    def test_raw_mutation_during_final_reread_is_detected(self):
        original = audit._phase_row
        def changed(*args):
            row = original(*args)
            path = self.root / self.accounting / 'started.json'; path.write_bytes(path.read_bytes() + b' ')
            return row
        with patch.object(audit, '_phase_row', changed), self.assertRaises(ValueError): self.read()

    def test_frozen_collector_and_actual_trace_validator_are_not_patched(self):
        for name, sha in audit.FROZEN_HELPERS.items():
            self.assertEqual(hashlib.sha256((STAGE / name).read_bytes()).hexdigest(), sha)
        import export_no_cutoff_final as old
        self.assertIn("all(len(v)==1 for v in phases.values())", old.COLLECT)
        self.assertIn("names+=['.runtime/stage2/scored-trials/'", old.BACKUP)
        self.assertFalse(audit.contract()['results_rewritten']); self.assertFalse(audit.contract()['task_replay'])


class SharedLifecycleTests(unittest.TestCase):
    def test_actual_shared_normal_and_failed_verifier_traces_keep_measured_phases(self):
        import test_trial_execution as fixtures
        from credit_only_accounting import PassiveTrialTrace
        for options in ({'reward': 1}, {'reward': 0, 'agent_error': True}, {'verifier_error': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                trace = PassiveTrialTrace(Path(folder) / 'traces', trial_id='customfinal2-c0-nc-01-synthetic',
                    task_id='synthetic', harness='C0-NC', protocol_sha256=audit.MODEL)
                result, calls = asyncio.run(fixtures.LifecycleTests().run_case(**options, phase_observer=trace))
                result.update(trial_id='customfinal2-c0-nc-01-synthetic', task_id='synthetic', harness='C0-NC',
                    model_protocol_sha256=audit.MODEL, containers_removed=True, networks_removed=True, volumes_removed=True,
                    billing={'requests': 0, 'unknown_cost_requests': 0, 'charged_usd': '0'})
                result['trace'] = trace.finish(Path(folder) / 'no-requests', result['billing'])
                events = trace.spool.events()
                started = next(e['started_ns'] for e in events if e['kind'] == 'agent')
                # This is synthetic deadline input for a local fake lifecycle, not a native producer.
                lifecycle = dict(trial_id=result['trial_id'], model_protocol_sha256=audit.MODEL,
                    boot_id='synthetic', deadline_monotonic=1.0, deadline_utc=started / 1e9 + 1.0)
                row = audit._phase_row(result, events, lifecycle, [], 0,
                    dict(agent_timeout_seconds=1.0, verifier_timeout_seconds=1.0))
                self.assertIn('agent', calls); self.assertIn('verify', calls)
                self.assertEqual(row['reward'], options.get('reward'))
                self.assertTrue(all(value == 'measured' for value in row['phase_observation'].values()))
                self.assertGreater(row['agent_seconds'], 0); self.assertGreater(row['verifier_seconds'], 0)

    def test_actual_shared_setup_failure_trace_passes_without_agent_or_verifier_execution(self):
        import test_trial_execution as fixtures
        from credit_only_accounting import PassiveTrialTrace
        with tempfile.TemporaryDirectory() as folder:
            trace = PassiveTrialTrace(Path(folder) / 'traces', trial_id='customfinal2-c0-nc-01-synthetic',
                task_id='synthetic', harness='C0-NC', protocol_sha256=audit.MODEL)
            case = fixtures.LifecycleTests()
            result, calls = asyncio.run(case.run_case(setup_error=True, phase_observer=trace))
            result.update(trial_id='customfinal2-c0-nc-01-synthetic', task_id='synthetic', harness='C0-NC',
                model_protocol_sha256=audit.MODEL, containers_removed=True, networks_removed=True, volumes_removed=True,
                billing={'requests': 0, 'unknown_cost_requests': 0, 'charged_usd': '0'})
            result['trace'] = trace.finish(Path(folder) / 'no-requests', result['billing'])
            row = audit._phase_row(result, trace.spool.events(), None, [], 0,
                dict(agent_timeout_seconds=1.0, verifier_timeout_seconds=1.0))
            self.assertNotIn('agent', calls); self.assertNotIn('verify', calls)
            self.assertIsNone(row['agent_seconds']); self.assertIsNone(row['verifier_seconds'])
            self.assertIsNone(row['reward']); self.assertGreater(row['setup_seconds'], 0)


if __name__ == '__main__': unittest.main()
