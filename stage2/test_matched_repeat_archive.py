"""Real synthetic89 archives and protected files, not native qualification."""
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile
from unittest.mock import patch

import matched_repeat_archive as archive
import matched_repeat_baseline as baseline
import matched_repeat_policy as policy
import matched_repeat_report as report
import no_cutoff_recovery_files as files
import test_matched_repeat_report as fixture
from test_matched_repeat_policy import qualification, predecessors
from test_no_cutoff_recovery_runtime import save

STAGE = Path(__file__).resolve().parent


class ArchiveTests(fixture.ReportTests):
    """Inherited report regressions also run with complete synthetic bindings."""
    def setUp(self):
        super().setUp()
        self.sources = {}
        for name in set(self.f.final['sources']) | policy.REQUIRED_SOURCE_FILES:
            raw = (STAGE / name).read_bytes()
            save(self.root, 'stage2/' + name, raw)
            self.sources[name] = hashlib.sha256(raw).hexdigest()
        for name in self.f.final['sources']:
            if name != 'scored_trial.py': self.f.final['sources'][name] = self.sources[name]
        for name in self.f.original['sources']:
            if name not in policy.INHERITED_BASELINE_DELTAS:
                self.f.original['sources'][name] = self.f.final['sources'][name]
        self.f.final['sources_sha256'] = policy.fingerprint(self.f.final['sources'])
        for key, value in (('ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(self.f.original)),
                ('CUSTOM_FINAL_QUALIFICATION_SHA256', policy.fingerprint(self.f.final)),
                ('CUSTOM_FINAL_SOURCES_SHA256', self.f.final['sources_sha256'])):
            self.enterContext(patch.object(policy, key, value))
        self.f.predecessor = predecessors(self.f.manifest, self.harness)
        self.proof = qualification(self.f.original, self.f.final, self.f.predecessor, self.f.manifest, self.harness)
        self.proof.update(sources=self.sources, sources_sha256=policy.fingerprint(self.sources),
            runtime_identity_sha256=policy.fingerprint(self.host),
            source_transition=policy.source_transition(self.f.original, self.f.final, self.sources))
        for mapping in (self.proof['evidence_files'], self.proof['image_evidence_files']):
            for name in mapping:
                raw = b'{"synthetic_only_not_native_qualification":true}'
                save(self.root, name, raw); mapping[name] = hashlib.sha256(raw).hexdigest()
        self.block = policy.registration(self.f.original, self.f.final, self.f.predecessor, self.f.manifest, self.proof)
        self.f.proof = self.proof; self.f.block = self.block; self.f.write()
        self.write(policy.RUNTIME_FILE, self.host)
        save(self.root, report.RT + policy.MANIFEST_FILE, (STAGE/'input_manifest.json').read_bytes())
        for name, field in ((policy.BASELINE_FILE, 'ORIGINAL_FILE_SHA256'), (policy.FINAL_FILE, 'FINAL_FILE_SHA256')):
            self.enterContext(patch.object(baseline, field,
                hashlib.sha256((self.rt/name).read_bytes()).hexdigest()))
        self.bound = {'stage2/'+n: h for n,h in self.sources.items()}
        self.bound.update(files.capture(self.root, [report.RT+n for n in
            (*archive.qualification_inputs(), policy.REGISTRATION_FILE)])[0])
        self.bound.update(self.proof['evidence_files']); self.bound.update(self.proof['image_evidence_files'])
        self.live.update(files=self.bound, predecessor={'predecessors': self.f.predecessor})
        self.enterContext(patch.object(archive, '__file__', str(self.root/'stage2/matched_repeat_archive.py')))

    def packed(self, data):
        record, state = archive.inventory(data)
        stream = io.BytesIO(); receipt = archive.pack(stream, record, state)
        framed = io.BytesIO(stream.getvalue()); compressed = bytearray()
        while header := framed.read(8):
            size = struct.unpack('!Q', header)[0]; compressed.extend(framed.read(size))
        path = self.root/'private-backup/evidence.tar.gz'
        save(self.root, path.relative_to(self.root).as_posix(), bytes(compressed))
        return path, record, state, receipt

    def sample(self):
        self.produce(requests=105); data, state = self.collect()
        path, record, inventory_state, receipt = self.packed(data)
        return data, state, path, record, inventory_state, receipt

    def verify(self, path, data, record, receipt):
        return archive.verify(path, data, record, receipt, self.f.manifest, self.sources)

    def test_full_existing_archive_verifies_actual_members_anchors_and_absences(self):
        data, state, path, record, inventory_state, receipt = self.sample()
        verified = self.verify(path, data, record, receipt)
        self.assertEqual(verified['verified_result_files'], 89)
        self.assertEqual(verified['verified_absent_paths'], 1)
        self.assertFalse(verified['paid_launch_ready']); self.assertFalse(verified['full_runtime_restore_exercised'])
        self.assertIsNone(data['aggregate']['total_cost_usd'])
        archive.recheck(record, inventory_state); report.reread(self.root, data, state)

    def test_stream_consumes_exact_archive_and_leaves_commitment_unread(self):
        data, _, path, record, _, receipt = self.sample()
        stream = io.BytesIO(path.read_bytes() + b'actual-caller-commitment')
        actual = archive.verify_stream(stream, data, record, receipt, self.f.manifest, self.sources)
        self.assertEqual(actual, self.verify(path, data, record, receipt))
        self.assertEqual(stream.read(), b'actual-caller-commitment')

    def test_corruption_truncation_and_trailing_bytes_refuse(self):
        data, _, path, record, _, receipt = self.sample(); raw = path.read_bytes()
        for altered in (raw[:-1], bytes([raw[0]^1])+raw[1:], raw+b'extra'):
            path.write_bytes(altered)
            with self.subTest(size=len(altered)), self.assertRaises((ValueError, OSError, EOFError)):
                self.verify(path, data, record, receipt)

    def test_actual_archive_protection_and_same_byte_replacement_refuse(self):
        data, _, path, record, _, receipt = self.sample()
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.verify(path, data, record, receipt)
        path.chmod(0o600); original = archive._anchors
        def replace(*args):
            original(*args); raw = path.read_bytes(); path.rename(path.with_suffix('.retained'))
            save(self.root, path.relative_to(self.root).as_posix(), raw)
        with patch.object(archive, '_anchors', side_effect=replace), self.assertRaises(ValueError):
            self.verify(path, data, record, receipt)

    def test_required_private_evidence_does_not_gain_extra_log_permissions(self):
        self.produce(); data, _ = self.collect()
        path = self.rt/'scored-trials'/self.cells[0]['trial_id']/'result.json'; path.chmod(0o644)
        with self.assertRaises(ValueError): archive.inventory(data)

    def test_registered_extra_logs_are_hash_only_and_do_not_change_permissions(self):
        self.produce(); trial = self.rt/'scored-trials'/self.cells[0]['trial_id']
        agent = trial/'agent'
        save(self.root, (agent/'payload.txt').relative_to(self.root).as_posix(), b'private synthetic payload')
        save(self.root, (trial/'token').relative_to(self.root).as_posix(), b'private synthetic credential')
        agent.chmod(0o777)
        data, _ = self.collect(); path, record, _, receipt = self.packed(data)
        self.verify(path, data, record, receipt)
        self.assertEqual(agent.stat().st_mode & 0o777, 0o777)
        self.assertIn((trial/'token').relative_to(self.root).as_posix(), record['excluded'])
        self.assertNotIn('private synthetic', json.dumps(data))

    def test_late_payload_replacement_tree_growth_and_absence_changes_refuse(self):
        data, _, _, record, state, _ = self.sample()
        trial = self.rt/'scored-trials'/self.cells[0]['trial_id']
        path = trial/'new-file'; save(self.root, path.relative_to(self.root).as_posix(), b'new')
        with self.assertRaises(ValueError): archive.recheck(record, state)
        path.unlink()
        absent = self.root/data['absent_paths'][0]
        save(self.root, absent.relative_to(self.root).as_posix(), b'{}')
        with self.assertRaises(ValueError): archive.recheck(record, state)

    def test_saved_qualification_or_manifest_changes_cannot_pass_anchor_checks(self):
        data, _, _, _, _, _ = self.sample()
        raw = {report.RT+n: (self.rt/n).read_bytes() for n in
            (*archive.qualification_inputs(), policy.REGISTRATION_FILE)}
        archive._anchors(data, raw, self.f.manifest, self.sources)
        for name in (policy.MANIFEST_FILE, policy.BASELINE_FILE, policy.FINAL_FILE):
            altered = dict(raw); altered[report.RT+name] += b' '
            with self.subTest(name=name), self.assertRaises(ValueError):
                archive._anchors(data, altered, self.f.manifest, self.sources)

    def test_inventory_rejects_credentials_dropped_results_and_absence_conflicts(self):
        data, _, _, record, _, _ = self.sample()
        trial = report.RT+'scored-trials/'+self.cells[0]['trial_id']
        for mode in ('secret', 'result', 'absence', 'duplicate-directory'):
            altered = deepcopy(record)
            if mode == 'result': altered['files'].pop(trial+'/result.json'); altered['sizes'].pop(trial+'/result.json')
            elif mode == 'duplicate-directory': altered['directories'].append(altered['directories'][0])
            else:
                name = trial+'/.env.synthetic' if mode == 'secret' else data['absent_paths'][0]
                altered['files'][name] = 'a'*64; altered['sizes'][name] = 1
            with self.subTest(mode=mode), self.assertRaises(ValueError): archive.validate_inventory(altered, data)

    def test_duplicate_tar_member_rejected_even_with_matching_compressed_receipt(self):
        data, _, path, record, _, receipt = self.sample()
        original = tarfile.open(fileobj=io.BytesIO(gzip.decompress(path.read_bytes())), mode='r:')
        output = io.BytesIO()
        with original, tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT) as changed:
            entries = original.getmembers()
            for entry in [*entries, entries[0]]:
                changed.addfile(entry, original.extractfile(entry) if entry.isfile() else None)
        raw = gzip.compress(output.getvalue()); path.write_bytes(raw)
        altered = dict(receipt, sha256=hashlib.sha256(raw).hexdigest(), compressed_bytes=len(raw))
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.verify(path, data, record, altered)


class OpenHandsArchiveTests(ArchiveTests):
    harness = 'openhands'
