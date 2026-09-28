"""Actual temporary tar bytes, with synthetic89 and mocked native observations."""
from copy import deepcopy
import gzip
import hashlib
import io
import json
import os
import tarfile
import unittest
from unittest.mock import patch

import no_cutoff_final_archive as archive
import credit_only_accounting as accounting
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import test_no_cutoff_final_report as fixtures


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CompletedAuditTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        block = self.f.f.block
        block.update(model_protocol_sha256=phase.fingerprint({'synthetic': True}),
            policy_sha256=phase.fingerprint({'synthetic': True}))
        registration = phase.fingerprint(block)
        sha = self.f.f.save(phase.RT + 'no-cutoff-final-matrix.json', block)
        self.enterContext(patch.object(phase, 'REGISTRATION', registration))
        self.enterContext(patch.object(phase, 'REGISTRATION_FILE', sha))
        report.INPUTS['no-cutoff-final-matrix.json'] = sha  # The enclosing fixture patches this dictionary.
        for trial_id in self.f.ids:
            for filename in ('result.json', 'started.json'):
                name = phase.RT + 'scored-trials/' + trial_id + '/' + filename
                value = json.loads((self.root / name).read_bytes()); value['custom_registration_sha256'] = registration
                self.f.f.save(name, value)
        self.load_data()
        self.path = self.root / 'evidence.tar.gz'

    def load_data(self):
        self.data = report.collect()
        # The shared synthetic trace fixture deliberately uses a future epoch.
        self.data['collected_utc'] = '2027-01-16T00:00:00+00:00'
        self.anchors = {n: (self.root / n).read_bytes() for n in archive.anchor_hashes()}
        self.members = {n: (self.root / n).read_bytes() for n in self.data['supporting_file_sha256']}
        self.members.update({'reporting/' + n: (self.f.reporting / n).read_bytes() for n in self.data['reporting_source_files']})

    def packed(self, *, extra=(), omit=(), changed=None, tar_tail=b'', omit_dirs=(), fmt=tarfile.USTAR_FORMAT):
        changed = changed or {}; stream = io.BytesIO(); files = unpacked = 0
        with tarfile.open(fileobj=stream, mode='w', format=fmt) as tar:
            for name in self.data['directory_entries']:
                if name in omit_dirs: continue
                member = tarfile.TarInfo(name); member.type = tarfile.DIRTYPE; tar.addfile(member)
            for name, raw in self.members.items():
                if name in omit: continue
                raw = changed.get(name, raw)
                member = tarfile.TarInfo(name); member.size = len(raw)
                member.mtime = 0.5 if fmt == tarfile.PAX_FORMAT else 0
                tar.addfile(member, io.BytesIO(raw))
                files += 1; unpacked += len(raw)
            for member, raw in extra:
                tar.addfile(member, io.BytesIO(raw) if member.isfile() else None)
                if member.isfile(): files += 1; unpacked += len(raw)
        raw = gzip.compress(stream.getvalue() + tar_tail)
        receipt = dict(kind=archive.KIND, sha256=hashlib.sha256(raw).hexdigest(), compressed_bytes=len(raw),
            files=files, bytes=unpacked, excluded=0, snapshot_sha256=phase.fingerprint(self.data),
            reporting_sources_sha256=phase.fingerprint(self.data['reporting_source_files']),
            absent_paths_sha256=phase.fingerprint(self.data['absent_paths']))
        return raw, receipt

    def member(self, name, raw=b'x', kind=tarfile.REGTYPE):
        member = tarfile.TarInfo(name); member.size = len(raw) if kind == tarfile.REGTYPE else 0; member.type = kind
        if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): member.linkname = 'target'
        return member, raw

    def verify(self, **kwargs):
        raw, receipt = self.packed(**kwargs)
        self.path.write_bytes(raw); self.path.chmod(0o600)
        return archive.verify_archive(self.path, self.data, receipt)

    def invalid(self, change):
        data = deepcopy(self.data); change(data)
        with self.assertRaises(ValueError): archive.validate_snapshot(data, self.anchors)

    def test_exact_amended_schema_is_not_native_audit_or_admission(self):
        value = archive.validate_snapshot(self.data, self.anchors)
        self.assertFalse(value['completed_final_audit']); self.assertFalse(value['paid_launch_ready'])
        self.assertEqual(self.data['aggregates']['full89']['no_verifier_result'], 3)
        self.assertIsNone(self.data['rows'][0]['agent_seconds'])

    def test_actual_archive_hashes_every_bound_file_and_all_three_absences(self):
        before = dict(self.members); value = self.verify()
        self.assertEqual(value['verified_bound_files'], len(self.members)); self.assertEqual(value['verified_absent_paths'], 3)
        self.assertEqual(value['verified_result_files'], 89)
        for key in ('completed_final_audit', 'paid_launch_ready', 'off_server_location_verified', 'full_runtime_restore_exercised'):
            self.assertIs(value[key], False)
        self.assertEqual(self.members, before)

    def test_path_and_chunked_stream_verification_return_identical_metadata(self):
        raw, receipt = self.packed()
        class Short(io.BytesIO):
            def read(self, size=-1): return super().read(min(size, 29) if size >= 0 else 29)
        streamed = archive.verify_stream(Short(raw), self.data, receipt)
        self.path.write_bytes(raw); self.path.chmod(0o600)
        self.assertEqual(streamed, archive.verify_archive(self.path, self.data, receipt))

    def test_exact_frame_leaves_external_commitment_for_authenticated_caller(self):
        raw, receipt = self.packed(); stream = io.BytesIO(raw + b'caller-commitment')
        value = archive.verify_stream(stream, self.data, receipt)
        self.assertEqual(stream.read(), b'caller-commitment'); self.assertFalse(value['off_server_location_verified'])

    def test_extra_or_missing_snapshot_fields_refused(self):
        self.invalid(lambda d: d.update(raw_exchange='private'))
        self.invalid(lambda d: d.pop('amendment'))

    def test_old_snapshot_schema_refused(self):
        self.invalid(lambda d: d.pop('absent_paths'))
        self.invalid(lambda d: d.update(kind='old_completed_final'))

    def test_all_authority_flags_and_service_state_are_exact(self):
        for key in ('paid_launch_ready', 'off_server_backup_verified', 'archive_export_and_handoff_integrated'):
            with self.subTest(key=key): self.invalid(lambda d: d.update({key: True}))
        self.invalid(lambda d: d.update(completed_final_audit=1))
        self.invalid(lambda d: d['service'].update(SubState='running'))
        self.invalid(lambda d: d['audit_checks'].update(official_limits=1))

    def test_anchor_raw_whitespace_canonical_substitution_and_duplicates_refused(self):
        for name in self.anchors:
            raw = dict(self.anchors); raw[name] += b' '
            with self.subTest(name=name), self.assertRaises(ValueError): archive.validate_snapshot(self.data, raw)
        with self.assertRaises(ValueError): phase._loads(b'{"a":1,"a":1}')

    def test_original_sources_registration_policy_and_runtime_bindings_cannot_drift(self):
        self.invalid(lambda d: d['sources'].update({'local_trace.py': '0' * 64}))
        self.invalid(lambda d: d['registration'].update(extra='new'))
        self.invalid(lambda d: d['policy'].update(unknown_cost_is_zero=True))
        self.invalid(lambda d: d['model_protocol'].update(extra=True))
        self.invalid(lambda d: d['bindings'].update({phase.RT + 'no-cutoff-final-runtime.json': '0' * 64}))

    def test_all_178_original_and_four_stopped_hashes_are_required(self):
        base = next(iter(self.data['preserved_result_files']))
        self.invalid(lambda d: d['preserved_result_files'][base].pop(next(iter(d['preserved_result_files'][base]))))
        self.invalid(lambda d: d['preserved_result_files'].update({'another-root': {'result': '0' * 64}}))

    def test_rows_cannot_be_removed_duplicated_reordered_or_rescored_without_detection(self):
        self.invalid(lambda d: d['rows'].pop())
        self.invalid(lambda d: d['rows'].__setitem__(1, d['rows'][0]))
        self.invalid(lambda d: d['rows'].reverse())
        self.invalid(lambda d: d['rows'][0].update(reward=0))

    def test_null_phase_cannot_be_zero_or_measured(self):
        self.invalid(lambda d: d['rows'][0].update(agent_seconds=0))
        self.invalid(lambda d: d['rows'][0]['phase_observation'].update(agent='measured'))
        self.invalid(lambda d: d['rows'][3].update(agent_seconds=None))

    def test_unknown_lifecycle_and_contradictory_errors_refused(self):
        self.invalid(lambda d: d['rows'][0].update(status='agent_never_ran'))
        self.invalid(lambda d: d['rows'][0].update(agent_error_type=''))
        self.invalid(lambda d: d['rows'][0].update(verifier_error_type='RuntimeError'))
        self.invalid(lambda d: d['rows'][3].update(verifier_error_type='RuntimeError'))

    def test_missing_verifier_reward_with_all_measured_phases_is_not_setup_only(self):
        row = self.data['rows'][3]; row.update(reward=None)
        self.data['aggregates'] = dict(full89=report.aggregate(self.data['rows']),
            development20=report.aggregate(self.data['rows'][:20]), remaining69=report.aggregate(self.data['rows'][20:]))
        value = archive.validate_snapshot(self.data, self.anchors)
        self.assertFalse(value['completed_final_audit'])  # Metadata alone never proves the changed row.
        self.assertEqual(row['phase_observation']['agent'], 'measured'); self.assertIsNotNone(row['agent_seconds'])

    def test_105_actual_synthetic_requests_preserve_unknown_costs_and_missing_timings(self):
        f = self.f.f; f.result['custom_registration_sha256'] = phase.REGISTRATION
        for i in range(105): f.write(f.accounting + '/%06d.request.json' % i, b'PRIVATE-RAW-SENTINEL')
        f.save(f.accounting + '/000000.outcome.json', dict(status='ok', accepted_for_agent=True,
            cost_usd='0.25', input_tokens=2, output_tokens=3))
        f.save(f.accounting + '/000001.transport-error.json', {'http_status': 429})
        f.save(f.accounting + '/000001.retry.json', {'synthetic': True})
        f.result['billing'] = accounting.summarise(self.root / phase.RT, f.trial_id); f.flush(); self.load_data()
        value = self.verify(); row = self.data['rows'][-1]
        self.assertEqual(row['unknown_cost_requests'], 104); self.assertEqual(row['missing_generation_timings'], 105)
        self.assertIsNone(self.data['aggregates']['full89']['total_cost_usd'])
        self.assertNotIn('PRIVATE-RAW-SENTINEL', json.dumps(value))

    def test_limits_and_python_numeric_types_preserved(self):
        self.invalid(lambda d: d['rows'][3].update(official_agent_timeout_seconds=7200))
        self.invalid(lambda d: d['rows'][3].update(setup_timeout_seconds=900.0))
        self.invalid(lambda d: d['rows'][3].update(reward=True))
        self.invalid(lambda d: d['rows'][3].update(official_cpus=2))
        self.invalid(lambda d: d['rows'][3].update(agent_seconds=float('nan')))

    def test_timestamps_and_timeout_evidence_refused_when_inconsistent(self):
        self.invalid(lambda d: d['rows'][0].update(completed_utc='2026-09-27T00:00:00+00:00'))
        self.invalid(lambda d: d['rows'][0].update(started_utc='2026-09-28T00:00:00'))
        self.invalid(lambda d: d['rows'][0].update(agent_error_type='TimeoutError'))

    def test_accounting_counts_and_unknown_cost_cannot_be_coerced(self):
        self.invalid(lambda d: d['rows'][3].update(model_requests=1))
        self.invalid(lambda d: d['rows'][3].update(accepted_model_responses=True))
        self.invalid(lambda d: d['rows'][3].update(unknown_cost_requests=1, total_cost_usd='0'))
        self.invalid(lambda d: d['rows'][3].update(known_cost_usd='NaN'))
        self.invalid(lambda d: d['rows'][3].update(input_tokens=10))

    def test_phase_denominators_subtotals_and_fixed_subsets_are_recomputed(self):
        self.invalid(lambda d: d['aggregates']['full89']['phase_durations']['agent'].update(measured_attempts=89))
        self.invalid(lambda d: d['aggregates']['full89']['phase_durations']['agent'].update(all_attempts_measured=True))
        self.invalid(lambda d: d['aggregates'].update(development20=d['aggregates']['remaining69']))

    def test_missing_required_support_and_unbound_extra_paths_refused(self):
        result = phase.RT + 'scored-trials/' + self.f.ids[0] + '/result.json'
        self.invalid(lambda d: d['supporting_file_sha256'].pop(result))
        self.invalid(lambda d: d['supporting_file_sha256'].update({'private-extra.json': '0' * 64}))

    def test_absence_cannot_be_removed_added_or_attached_to_executed_attempt(self):
        self.invalid(lambda d: d['absent_paths'].clear())
        self.invalid(lambda d: d['absent_paths'].append('somewhere'))
        self.invalid(lambda d: d['absent_paths'].__setitem__(0, phase.RT + 'retry-lifecycle/' + self.f.ids[3] + '.json'))

    def test_inventory_cannot_be_removed_duplicated_or_replaced_by_arbitrary_paths(self):
        name = next(iter(self.data['directory_entries']))
        self.invalid(lambda d: d['directory_entries'].pop(name))
        self.invalid(lambda d: d['directory_entries'][name].append(d['directory_entries'][name][0]))
        self.invalid(lambda d: d['directory_entries'].update({'another-directory': []}))

    def test_malformed_inventory_types_fail_before_stream_members_are_read(self):
        name = next(iter(self.data['directory_entries']))
        for value in ({}, [None], [True], 'started.json'):
            with self.subTest(value=value): self.invalid(lambda d: d['directory_entries'].update({name: value}))
        self.invalid(lambda d: d['absent_paths'].append({}))

    def test_empty_directory_presence_is_verified_not_assumed(self):
        folder = phase.RT + 'scored-attempts/' + self.f.ids[0]
        self.members.pop(folder + '/started.json'); self.data['supporting_file_sha256'].pop(folder + '/started.json')
        self.data['directory_entries'][folder] = []
        archive.validate_snapshot(self.data, self.anchors)
        with self.assertRaises(ValueError): self.verify(omit_dirs=(folder,))
        self.verify()

    def test_missing_phase_inventory_is_not_an_absence_category(self):
        name = phase.RT + 'scored-trials/' + self.f.ids[3] + '/traces'
        self.invalid(lambda d: d['directory_entries'].update({name: []}))

    def test_missing_and_modified_result_archive_bytes_rejected(self):
        name = phase.RT + 'scored-trials/' + self.f.ids[0] + '/result.json'
        with self.assertRaises(ValueError): self.verify(omit=(name,))
        with self.assertRaises(ValueError): self.verify(changed={name: b'{}'})

    def test_missing_source_input_or_actual_producer_archive_bytes_rejected(self):
        for name in ('stage2/local_trace.py', phase.RT + 'no-cutoff-final-runtime.json', next(iter(self.f.f.proof['evidence_files']))):
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify(omit=(name,))

    def test_reporting_bundle_is_archived_separately_and_must_match_current_bytes(self):
        name = 'reporting/stage2/no_cutoff_final_archive.py'
        with self.assertRaises(ValueError): self.verify(changed={name: b'changed'})
        self.invalid(lambda d: d['reporting_source_files'].update({'stage2/no_cutoff_final_archive.py': '0' * 64}))

    def test_fabricated_deadline_and_absent_accounting_descendants_refused(self):
        with self.assertRaisesRegex(ValueError, 'actually absent'):
            self.verify(extra=[self.member(self.data['absent_paths'][0], b'{}')])
        trial = self.f.ids[0]; folder = phase.RT + 'scored-attempts/' + trial
        self.data['directory_entries'].pop(folder); self.members.pop(folder + '/started.json')
        self.data['supporting_file_sha256'].pop(folder + '/started.json')
        self.data['absent_paths'] = sorted([*self.data['absent_paths'], folder])
        archive.validate_snapshot(self.data, self.anchors)
        with self.assertRaisesRegex(ValueError, 'actually absent'): self.verify(extra=[self.member(folder + '/new.json')])

    def test_additional_trace_or_accounting_file_cannot_evade_exact_inventory(self):
        folder = next(iter(self.data['directory_entries']))
        with self.assertRaisesRegex(ValueError, 'inventory'): self.verify(extra=[self.member(folder + '/new.json')])

    def test_unregistered_extra_private_paths_refused(self):
        with self.assertRaises(ValueError): self.verify(extra=[self.member('.runtime/stage2/scored-trials/unregistered/log.json')])

    def test_registered_private_extra_logs_are_hashed_but_never_returned_or_extracted(self):
        name = phase.RT + 'scored-trials/' + self.f.ids[3] + '/agent/private.log'
        value = self.verify(extra=[self.member(name, b'PRIVATE-RAW-SENTINEL')])
        self.assertNotIn('PRIVATE-RAW-SENTINEL', json.dumps(value))
        self.assertFalse((self.root / name).exists())

    def test_duplicate_credential_traversal_absolute_and_noncanonical_paths_refused(self):
        for name in (next(iter(self.members)), '../result', '/result', '.runtime//result', './result',
                phase.RT + 'scored-trials/' + self.f.ids[3] + '/token'):
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify(extra=[self.member(name)])

    def test_archive_links_devices_and_fifos_refused(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.verify(extra=[self.member('unsafe', kind=kind)])

    def test_standard_pax_timestamps_and_long_registered_private_paths_are_supported(self):
        name = phase.RT + 'scored-trials/' + self.f.ids[3] + '/agent/' + 'long' * 65 + '.log'
        value = self.verify(fmt=tarfile.PAX_FORMAT, extra=[self.member(name)])
        self.assertEqual(value['verified_result_files'], 89)

    def test_pax_linkpath_and_sparse_extensions_are_not_accepted_as_regular_files(self):
        member, raw = self.member(phase.RT + 'scored-trials/' + self.f.ids[3] + '/private.log')
        member.pax_headers = {'linkpath': 'unsafe'}
        with self.assertRaises(ValueError): self.verify(fmt=tarfile.PAX_FORMAT, extra=[(member, raw)])

    def test_extension_header_window_is_checked_before_reading_its_body(self):
        member = tarfile.TarInfo('extended'); member.type = tarfile.XHDTYPE; member.size = archive.ANCHOR_WINDOW + 1
        with self.assertRaisesRegex(ValueError, 'parser window'):
            archive._TarInfo.frombuf(member.tobuf(), 'utf-8', 'strict')
        member.type = tarfile.REGTYPE
        self.assertEqual(archive._TarInfo.frombuf(member.tobuf(), 'utf-8', 'strict').size, archive.ANCHOR_WINDOW + 1)

    def test_global_pax_and_gnu_sparse_headers_are_rejected_before_body_processing(self):
        for kind in (tarfile.XGLTYPE, tarfile.GNUTYPE_SPARSE):
            member = tarfile.TarInfo('extended'); member.type = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                archive._TarInfo.frombuf(member.tobuf(), 'utf-8', 'strict')

    def test_fake_archive_receipt_checksum_sizes_counts_and_binding_flags_refused(self):
        raw, receipt = self.packed()
        for key, value in (('sha256', '0' * 64), ('files', receipt['files'] + 1), ('bytes', receipt['bytes'] + 1),
                ('compressed_bytes', receipt['compressed_bytes'] + 1), ('snapshot_sha256', '0' * 64),
                ('absent_paths_sha256', '0' * 64), ('excluded', True)):
            changed = dict(receipt, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): archive.verify_stream(io.BytesIO(raw), self.data, changed)

    def test_truncated_and_corrupt_gzip_trailer_refused(self):
        raw, receipt = self.packed()
        for changed in (raw[:-7], raw[:-4] + b'xxxx'):
            bound = dict(receipt, sha256=hashlib.sha256(changed).hexdigest(), compressed_bytes=len(changed))
            with self.assertRaises(ValueError): archive.verify_stream(io.BytesIO(changed), self.data, bound)

    def test_hidden_tar_members_after_end_marker_refused(self):
        with self.assertRaisesRegex(ValueError, 'end marker'): self.verify(tar_tail=b'hidden-member-nonpadding')

    def test_incomplete_tar_terminator_with_valid_gzip_crc_is_refused(self):
        raw, receipt = self.packed(); plain = gzip.decompress(raw)
        with tarfile.open(fileobj=io.BytesIO(plain), mode='r:') as tar:
            list(tar); end = tar.offset
        changed = gzip.compress(plain[:end + tarfile.BLOCKSIZE])
        bound = dict(receipt, sha256=hashlib.sha256(changed).hexdigest(), compressed_bytes=len(changed))
        with self.assertRaises(ValueError): archive.verify_stream(io.BytesIO(changed), self.data, bound)

    def test_report_mutation_during_archive_read_is_refused(self):
        raw, receipt = self.packed(); target = self.data
        class Mutating(io.BytesIO):
            def read(self, size=-1):
                target['paid_launch_ready'] = True
                return super().read(size)
        with self.assertRaises(ValueError): archive.verify_stream(Mutating(raw), self.data, receipt)

    def test_nonprivate_symlink_hardlink_and_symlinked_ancestor_refused(self):
        raw, receipt = self.packed(); self.path.write_bytes(raw); self.path.chmod(0o644)
        with self.assertRaises(ValueError): archive.verify_archive(self.path, self.data, receipt)
        self.path.chmod(0o600); other = self.root / 'linked'; other.symlink_to(self.path)
        with self.assertRaises(ValueError): archive.verify_archive(other, self.data, receipt)
        other.unlink(); os.link(self.path, other)
        with self.assertRaises(ValueError): archive.verify_archive(self.path, self.data, receipt)
        other.unlink(); other.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): archive.verify_archive(other / self.path.name, self.data, receipt)

    def test_file_replacement_after_read_is_detected(self):
        raw, receipt = self.packed(); self.path.write_bytes(raw); self.path.chmod(0o600)
        original = archive.verify_stream
        def changed(*args):
            value = original(*args); self.path.rename(self.root / 'old-archive')
            self.path.write_bytes(raw); self.path.chmod(0o600); return value
        with patch.object(archive, 'verify_stream', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed'):
            archive.verify_archive(self.path, self.data, receipt)

    def test_fifo_is_refused_without_waiting_for_any_writer(self):
        _, receipt = self.packed(); os.mkfifo(self.path, mode=0o600)
        original_open = os.open
        def nonblocking(path, flags):
            self.assertTrue(flags & os.O_NONBLOCK)  # Fail immediately, never hang this regression.
            return original_open(path, flags)
        with patch.object(archive.os, 'open', side_effect=nonblocking), self.assertRaisesRegex(ValueError, 'single-link'):
            archive.verify_archive(self.path, self.data, receipt)

    def test_no_writer_cli_native_collector_or_dispatch_entry(self):
        for name in ('collect', 'backup', 'export', 'run', 'register', 'main'):
            self.assertFalse(hasattr(archive, name))
        with patch.object(report, 'collect', side_effect=AssertionError('native audit forbidden')):
            self.verify()


if __name__ == '__main__': unittest.main()
