"""Real synthetic files/archive bytes; native audit, SSH and Git are mocked."""
from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_reporting as launch
import test_no_cutoff_final_archive as fixtures


class PublicExportTests(unittest.TestCase):
    def test_owned_readable_runtime_parent_is_not_chmodded(self):
        (self.root / '.runtime').chmod(0o755)
        self.run_export()
        self.assertEqual((self.root / '.runtime').stat().st_mode & 0o777, 0o755)

    def test_backup_parent_identity_change_during_fresh_audit_refuses_export(self):
        def changed(*args):
            (self.root / '.runtime').chmod(0o755)
            return deepcopy(self.fresh)
        with patch.object(launch, 'collect', side_effect=changed), self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.target.exists())

    def setUp(self):
        self.f = fixtures.ArchiveTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.commit = 'a' * 40
        self.enterContext(patch.object(launch, 'REPO', self.root))
        for module in (export, producer, receiver):
            self.enterContext(patch.object(module, '__file__', str(self.root / 'stage2' / (module.__name__ + '.py'))))
        (self.root / '.runtime').chmod(0o700); (self.root / '.runtime/netcup').mkdir(mode=0o700)
        self.folder = self.root / receiver.DESTINATION; self.folder.mkdir(mode=0o700)
        self.target = self.root / export.DESTINATION; self.target.parent.mkdir(parents=True)
        self.state = self.root / export.STATE
        prerequisite_raw = {n: json.dumps({'synthetic_prerequisite': n}).encode() for n in export.PREREQUISITES}
        for name, raw in prerequisite_raw.items(): self.save(name, raw)
        self.enterContext(patch.object(export, 'PREREQUISITES', {n: export._hash(raw) for n, raw in prerequisite_raw.items()}))
        self.bindings = dict(commit=self.commit, reporting=self.f.data['reporting_source_files'],
            anchors=self.f.anchors, local=self.f.data['reporting_source_files'])
        source_raw = {n: (self.f.f.reporting / n).read_bytes() for n in self.bindings['local']}
        self.git = self.enterContext(patch.object(launch, '_git', side_effect=lambda operation, ref:
            {**source_raw, **prerequisite_raw}[ref.split(':', 1)[1]]))
        self.prepare = self.enterContext(patch.object(launch, '_prepare', return_value=self.bindings))
        self.recheck = self.enterContext(patch.object(launch, '_recheck'))
        self.fresh = deepcopy(self.f.data); self.fresh['collected_utc'] = '2027-01-16T00:01:00+00:00'
        self.collect = self.enterContext(patch.object(launch, 'collect', side_effect=lambda _: deepcopy(self.fresh)))
        self.seed_backup()

    def save(self, name, raw):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(0o600)

    def seed_backup(self):
        raw, receipt = self.f.packed()
        self.save(receiver.DESTINATION + '/evidence.tar.gz', raw)
        snapshot = json.dumps(self.f.data, indent=1, allow_nan=False).encode()
        self.save(receiver.DESTINATION + '/snapshot.json', snapshot)
        intent = dict(kind='exclusive_amended_final_backup_operator_intent', operator_commit=self.commit,
            created_utc='2027-01-16T00:00:00+00:00', reporting_source_files=self.bindings['reporting'],
            automatic_resume=False, paid_launch_ready=False)
        self.save(receiver.DESTINATION + '/intent.json', producer._json(intent))
        backup = dict(kind='verified_mac_amended_final_backup_not_admission', operator_commit=self.commit,
            snapshot_file_sha256=export._hash(snapshot), receipt=receipt,
            verification=archive.verify_archive(self.folder / 'evidence.tar.gz', self.f.data, receipt),
            off_server_backup_verified=True, archive_export_and_handoff_integrated=False,
            full_runtime_restore_exercised=False, automatic_resume=False, paid_launch_ready=False)
        self.save(receiver.DESTINATION + '/backup.json', producer._json(backup))

    def metadata(self, name, change):
        path = self.folder / name; data = phase._loads(path.read_bytes()); change(data)
        path.write_bytes(producer._json(data))

    def run_export(self):
        return export.export(self.commit)

    def test_actual_archive_reread_and_fresh_audit_precede_exclusive_export(self):
        original = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        with patch.object(archive, 'verify_archive', wraps=archive.verify_archive) as verify:
            result = self.run_export()
        self.collect.assert_called_once_with(self.commit); verify.assert_called_once()
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['archive_export_and_handoff_integrated'])
        self.assertEqual({p.name for p in self.target.iterdir()}, export.OUTPUTS)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.folder.iterdir()})
        self.assertEqual({p.name for p in self.state.iterdir()}, {'intent.json', 'result.json'})
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        for path in self.state.iterdir(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_null_phase_reward_and_official_allowances_remain_distinct(self):
        self.run_export(); rows = json.loads((self.target / 'trials.json').read_bytes())
        self.assertEqual(len(rows), 89)
        self.assertIsNone(rows[0]['reward']); self.assertIsNone(rows[0]['agent_seconds'])
        self.assertEqual(rows[0]['phase_observation']['agent'], 'not_run_setup_failed')
        self.assertEqual(rows[0]['official_agent_timeout_seconds'], 7200.0)
        self.assertIs(type(rows[0]['official_agent_timeout_seconds']), float)
        self.assertEqual(sum(r['reward'] == 0 for r in rows), 43)
        self.assertEqual(sum(r['reward'] is None for r in rows), 3)
        table = list(csv.DictReader(io.StringIO((self.target / 'trials.csv').read_text())))
        self.assertEqual(table[0]['reward'], ''); self.assertEqual(table[0]['agent_seconds'], '')
        self.assertEqual(table[0]['agent_observation'], 'not_run_setup_failed')
        self.assertEqual(tuple(table[0]), export.CSV_FIELDS)

    def test_full89_development20_remaining69_keep_measured_denominators(self):
        self.run_export(); summary = phase._loads((self.target / 'summary.json').read_bytes())
        self.assertEqual([summary[k]['attempted'] for k in ('results', 'development_subset', 'outside_development_subset')], [89, 20, 69])
        self.assertEqual(summary['results']['phase_durations']['agent'], dict(measured_attempts=86,
            not_run_attempts=3, measured_subtotal_seconds=172.0, all_attempts_measured=False))
        self.assertEqual(summary['original_baselines']['primary']['passed'], 52)
        self.assertEqual(summary['original_baselines']['secondary']['passed'], 44)
        self.assertFalse(summary['recovery_attempts_included']); self.assertFalse(summary['full_benchmark_win_claimed'])
        self.assertFalse(summary['private_backup']['verification']['completed_final_audit'])
        self.assertFalse(summary['private_backup']['verification']['off_server_location_verified'])

    def test_private_payloads_paths_inventories_and_arbitrary_fields_not_published(self):
        self.run_export(); raw = b''.join(p.read_bytes() for p in self.target.iterdir())
        for forbidden in (b'"supporting_file_sha256":', b'"directory_entries":', b'"absent_paths":', b'/opt/',
                b'.runtime/stage2/scored', b'private": true', b'credential', b'PRIVATE-SENTINEL'):
            self.assertFalse(forbidden in raw, 'Private content escaped allowlist: ' + repr(forbidden))
        rows = json.loads((self.target / 'trials.json').read_bytes())
        self.assertEqual(set(rows[0]), export.report.ROW_FIELDS)

    def test_existing_or_partial_export_or_intent_prevents_audit(self):
        self.target.mkdir()
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_unknown_cost_and_105_requests_remain_uncapped_and_unpublished_payloads(self):
        f = self.f.f.f
        f.result = phase._loads((self.root / f.trial / 'result.json').read_bytes())
        for i in range(105): f.write(f.accounting + '/%06d.request.json' % i, b'PRIVATE-SENTINEL')
        f.save(f.accounting + '/000000.outcome.json', dict(status='ok', accepted_for_agent=True,
            cost_usd='0.25', input_tokens=2, output_tokens=3))
        f.save(f.accounting + '/000001.transport-error.json', {'http_status': 429})
        f.save(f.accounting + '/000001.retry.json', {'synthetic': True})
        f.result['billing'] = fixtures.accounting.summarise(self.root / phase.RT, f.trial_id); f.flush()
        self.f.load_data(); self.fresh = deepcopy(self.f.data); self.seed_backup()
        self.run_export(); summary = phase._loads((self.target / 'summary.json').read_bytes())
        rows = json.loads((self.target / 'trials.json').read_bytes())
        self.assertEqual(rows[-1]['model_requests'], 105); self.assertEqual(rows[-1]['unknown_cost_requests'], 104)
        self.assertEqual(rows[-1]['missing_generation_timings'], 105)
        self.assertIsNone(rows[-1]['total_cost_usd']); self.assertEqual(summary['results']['known_cost_usd'], '0.25')
        self.assertIsNone(summary['results']['total_cost_usd'])
        self.assertFalse(summary['results']['independent_receipts_verified'])
        for path in self.target.iterdir(): self.assertFalse(b'PRIVATE-SENTINEL' in path.read_bytes())

    def test_csv_allowlist_is_exactly_the_validated_row_contract(self):
        flattened = export.report.ROW_FIELDS - {'phase_observation'} | {p + '_observation' for p in phase.PHASES}
        self.assertEqual(set(export.CSV_FIELDS), flattened)
        self.assertEqual(len(export.CSV_FIELDS), len(flattened))

    def test_duplicate_private_metadata_fields_refuse_before_audit(self):
        self.save(receiver.DESTINATION + '/backup.json', b'{"kind":1,"kind":2}')
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_private_metadata_fifo_refuses_without_waiting_for_writer(self):
        path = self.folder / 'snapshot.json'; path.unlink(); os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_existing_private_export_intent_prevents_audit(self):
        self.state.mkdir(mode=0o700)
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called(); self.assertFalse(self.target.exists())

    def test_success_is_not_repeatable_and_archive_not_recreated(self):
        self.run_export(); original = (self.folder / 'evidence.tar.gz').read_bytes()
        with self.assertRaises(ValueError): self.run_export()
        self.assertEqual(self.collect.call_count, 1); self.assertEqual((self.folder / 'evidence.tar.gz').read_bytes(), original)

    def test_active_unknown_or_failed_native_audit_prevents_export_state(self):
        self.collect.side_effect = ValueError('active')
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.state.exists()); self.assertFalse(self.target.exists())

    def test_only_collection_timestamp_may_change_in_fresh_audit(self):
        self.fresh['rows'][3]['known_input_tokens'] += 1
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.target.exists())

    def test_stale_fresh_audit_is_refused_even_when_other_metadata_matches(self):
        self.fresh['collected_utc'] = '2027-01-15T23:59:00+00:00'
        with self.assertRaises(ValueError): self.run_export()

    def test_fabricated_zero_for_not_run_phase_fails_before_native_audit(self):
        self.metadata('snapshot.json', lambda d: d['rows'][0].update(agent_seconds=0))
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_added_raw_payload_field_fails_before_native_audit(self):
        self.metadata('snapshot.json', lambda d: d['rows'][0].update(response='PRIVATE-SENTINEL'))
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_missing_or_extra_private_files_refuse_before_audit(self):
        self.save(receiver.DESTINATION + '/failure.json', b'{}')
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_old_or_self_consistent_backup_flag_is_not_evidence(self):
        self.metadata('backup.json', lambda d: d['verification'].update(verified_bound_files=1))
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.target.exists())

    def test_wrong_backup_kind_or_numeric_boolean_fails_before_audit(self):
        self.metadata('backup.json', lambda d: d.update(off_server_backup_verified=1))
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_corrupt_archive_refuses_without_recreating_it(self):
        path = self.folder / 'evidence.tar.gz'; path.write_bytes(b'corrupt')
        with self.assertRaises((ValueError, OSError, EOFError)): self.run_export()
        self.assertEqual(path.read_bytes(), b'corrupt'); self.assertFalse(self.target.exists())

    def test_member_hash_verifier_is_mandatory(self):
        with patch.object(archive, 'verify_archive', side_effect=ValueError('missing member')) as check:
            with self.assertRaises(ValueError): self.run_export()
        check.assert_called_once(); self.assertFalse(self.state.exists())

    def test_symlinked_archive_or_metadata_refuses(self):
        path = self.folder / 'snapshot.json'; moved = self.root / 'moved'; path.rename(moved); path.symlink_to(moved)
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_nonprivate_backup_directory_or_file_refuses(self):
        (self.folder / 'backup.json').chmod(0o644)
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_unprotected_public_parent_refuses_before_audit(self):
        self.target.parent.chmod(0o777)
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_wrong_operator_or_helper_origin_refuses_before_audit(self):
        with patch.object(export, '__file__', str(self.root / 'elsewhere.py')), self.assertRaises(ValueError): self.run_export()
        with patch.object(producer, '__file__', str(self.root / 'other.py')), self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_changed_committed_bundle_and_changed_public_prerequisite_refuse(self):
        self.git.side_effect = None; self.git.return_value = b'changed'
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_prerequisite_raw_byte_change_refuses_before_audit(self):
        self.save(next(iter(export.PREREQUISITES)), b'{}')
        with self.assertRaises(ValueError): self.run_export()
        self.collect.assert_not_called()

    def test_current_commit_must_bind_public_prerequisites_not_only_old_backup_commit(self):
        current = 'b' * 40; self.bindings['commit'] = current; real = self.git.side_effect
        self.git.side_effect = lambda op, ref: b'changed' if ref.startswith(current + ':' + export.PUBLIC) else real(op, ref)
        with self.assertRaisesRegex(ValueError, 'current committed'): export.export(current)
        self.collect.assert_not_called()

    def test_snapshot_raw_mutation_after_native_audit_refuses(self):
        def mutate(_):
            self.save(receiver.DESTINATION + '/snapshot.json', b'{}'); return deepcopy(self.fresh)
        self.collect.side_effect = mutate
        with self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.target.exists())

    def test_archive_mutation_after_actual_member_read_refuses(self):
        real = archive.verify_archive
        def mutate(*args):
            result = real(*args)
            with (self.folder / 'evidence.tar.gz').open('ab') as stream: stream.write(b'changed')
            return result
        with patch.object(archive, 'verify_archive', side_effect=mutate), self.assertRaises(ValueError): self.run_export()
        self.assertFalse(self.target.exists())

    def test_failure_after_private_intent_retains_evidence_and_no_retry(self):
        with patch.object(receiver, '_raw_save', side_effect=OSError('PRIVATE-SENTINEL')):
            with self.assertRaisesRegex(ValueError, 'inspect retained'): self.run_export()
        self.assertTrue((self.state / 'intent.json').exists()); self.assertTrue((self.state / 'failure.json').exists())
        self.assertFalse((self.state / 'result.json').exists())
        self.assertNotIn('PRIVATE-SENTINEL', (self.state / 'failure.json').read_text())
        with self.assertRaises(ValueError): self.run_export()
        self.assertEqual(self.collect.call_count, 1)

    def test_public_mutation_at_final_reread_leaves_failure_not_success(self):
        def mutate(_):
            if (self.target / 'trials.json').exists(): (self.target / 'trials.json').write_bytes(b'[]')
        self.recheck.side_effect = mutate
        with self.assertRaisesRegex(ValueError, 'inspect retained'): self.run_export()
        self.assertTrue((self.state / 'failure.json').exists()); self.assertFalse((self.state / 'result.json').exists())

    def test_extra_public_file_appearing_during_final_recheck_withholds_commitment(self):
        def mutate(_):
            if self.target.exists(): (self.target / 'unapproved.json').write_bytes(b'{}')
        self.recheck.side_effect = mutate
        with self.assertRaisesRegex(ValueError, 'inspect retained'): self.run_export()
        self.assertTrue((self.state / 'failure.json').exists()); self.assertFalse((self.state / 'result.json').exists())

    def test_verify_rechecks_inventory_after_reading_public_bytes(self):
        self.run_export(); real = launch._raw
        def mutate(name, expected=None):
            value = real(name, expected)
            if name == export.DESTINATION + '/trials.csv': (self.target / 'unapproved.json').write_bytes(b'{}')
            return value
        with patch.object(launch, '_raw', side_effect=mutate), self.assertRaises(ValueError): export.verify_export(self.commit)

    def test_verify_export_repeats_fresh_audit_and_actual_archive_read_without_writing(self):
        result = self.run_export(); before = {str(p): p.read_bytes() for d in (self.target, self.folder, self.state) for p in d.iterdir()}
        with patch.object(archive, 'verify_archive', wraps=archive.verify_archive) as verify:
            self.assertEqual(export.verify_export(self.commit), result)
        verify.assert_called_once(); self.assertEqual(self.collect.call_count, 2)
        self.assertEqual(before, {str(p): p.read_bytes() for d in (self.target, self.folder, self.state) for p in d.iterdir()})

    def test_verify_refuses_changed_export_and_self_consistent_saved_result(self):
        self.run_export(); path = self.target / 'trials.json'; path.write_bytes(b'[]')
        result = phase._loads((self.state / 'result.json').read_bytes())
        result['public_files'][export.DESTINATION + '/trials.json'] = export._hash(b'[]')
        (self.state / 'result.json').write_bytes(producer._json(result))
        with self.assertRaises(ValueError): export.verify_export(self.commit)

    def test_verify_never_accepts_saved_audit_flag_when_current_native_audit_fails(self):
        self.run_export(); self.collect.side_effect = ValueError('native evidence changed')
        with self.assertRaises(ValueError): export.verify_export(self.commit)

    def test_verify_requires_completed_state_and_no_failure_marker(self):
        self.run_export(); (self.state / 'failure.json').write_bytes(b'{}')
        with self.assertRaises(ValueError): export.verify_export(self.commit)
        self.assertEqual(self.collect.call_count, 1)

    def test_later_git_commit_allowed_only_with_same_actual_reporting_sources(self):
        self.run_export(); later = 'b' * 40; self.bindings['commit'] = later
        value = export.verify_export(later)
        self.assertEqual(value['operator_commit'], self.commit)
        self.collect.assert_called_with(later)
        self.git.side_effect = lambda *args: b'changed'
        with self.assertRaises(ValueError): export.verify_export(later)

    def test_no_cli_root_callback_or_supplied_report_entry(self):
        import inspect
        for entry in (export.export, export.verify_export): self.assertEqual(list(inspect.signature(entry).parameters), ['commit'])
        self.assertNotIn('__main__', Path(__file__).with_name('no_cutoff_final_export.py').read_text())


if __name__ == '__main__': unittest.main()
