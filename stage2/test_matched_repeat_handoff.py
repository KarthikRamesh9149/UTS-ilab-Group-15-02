"""Real pipes and private archives, mocked native services and collectors."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import export_no_cutoff_final as exporter
import matched_repeat_handoff as handoff
import matched_repeat_policy as policy
import matched_repeat_predecessor as operator
import matched_repeat_stream as wire
from test_matched_repeat_predecessor import Fixture


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        for module, name, value in ((exporter, 'REPO', self.repo),
                (exporter, 'OUTPUT', self.repo / operator.PUBLIC),
                (operator, '__file__', str(self.repo / 'stage2/matched_repeat_predecessor.py')),
                (exporter, '__file__', str(self.repo / 'stage2/export_no_cutoff_final.py'))):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.object(operator.platform, 'system', return_value='Darwin'))
        self.f = Fixture(self, self.repo)
        self.operator_audit = self.enterContext(patch.object(operator, '_read_native',
            side_effect=lambda files: deepcopy(self.f.data)))
        self.native = self.repo / 'native-final'; self.native.mkdir()
        for name, content in self.f.content.items(): self.put(self.native, name, content)
        for row in self.f.data['rows']:
            name = row['trial_id']
            self.put(self.native, '.runtime/stage2/scored-trials/' + name + '/traces/phase.json', b'{"fixture":true}')
            self.put(self.native, '.runtime/stage2/scored-attempts/' + name + '/0001.request.json', b'{"raw":"private-fixture"}')
            self.put(self.native, '.runtime/stage2/scored-attempts/' + name + '/0001.outcome.json', b'{"cost":null}')
            self.put(self.native, '.runtime/stage2/retry-lifecycle/' + name + '.json', b'{"fixture":true}')
        original_raw = (self.repo / operator.ORIGINAL).read_bytes()
        final_raw = self.f.content['.runtime/stage2/no-cutoff-final-qualification.json']
        self.put(self.repo, '.runtime/stage2/' + policy.BASELINE_FILE, original_raw)
        self.put(self.repo, '.runtime/stage2/' + policy.FINAL_FILE, final_raw)
        for module, name, value in ((handoff.baseline, 'FINAL_ROOT', self.native),
                (exporter, 'REMOTE', str(self.native)),
                (handoff.baseline, 'ORIGINAL_FILE_SHA256', hashlib.sha256(original_raw).hexdigest()),
                (handoff.baseline, 'FINAL_FILE_SHA256', hashlib.sha256(final_raw).hexdigest())):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.dict(handoff.runtime.DEPLOYMENTS, {'terminus-2': self.repo}))
        self.context = self.enterContext(patch.object(handoff, '_context', side_effect=self.native_context))
        self.loaded = self.enterContext(patch.object(handoff.runtime, 'loaded_sources'))
        self.inactive = self.enterContext(patch.object(handoff.baseline, 'inactive_ancestors'))
        self.audit = self.enterContext(patch.object(handoff, '_native_audit',
            side_effect=lambda files: deepcopy(self.f.data)))
        self.no_native = self.enterContext(patch('subprocess.run', side_effect=AssertionError('No actual native calls')))

    def native_context(self, root, harness):
        handoff._first(harness)
        if Path(root) != self.repo: raise ValueError('Wrong root')
        return self.repo

    @staticmethod
    def put(root, name, raw):
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(0o600)

    def header(self):
        document = operator.capture(self.repo)
        return dict(kind=handoff.TRANSFER_KIND, schema_version=1, harness='terminus-2', operator=document,
            snapshot=(self.repo / operator.COMPLETED / 'snapshot.json').read_text(),
            backup=(self.repo / operator.COMPLETED / 'backup.json').read_text())

    def packet(self, header=None, *, commit=True):
        header = self.header() if header is None else header
        packet = io.BytesIO(); header_digest = wire.write_header(packet, header)
        raw = self.f.archive.read_bytes()
        wire.copy_archive(io.BytesIO(raw), packet, len(raw), self.f.backup['sha256'])
        if commit: wire.commit(packet, header_digest, self.f.backup['sha256'])
        return packet.getvalue()

    def receive(self, packet=None, *, send=False):
        if packet is None and not send: packet = self.packet()
        incoming, outgoing = os.pipe(); errors = []; sent = []
        def produce():
            try:
                with os.fdopen(outgoing, 'wb') as destination:
                    if send: sent.append(handoff.send(self.repo, destination))
                    else: wire._write(destination, packet)
            except BaseException as error:
                errors.append(error)
        producer = threading.Thread(target=produce, daemon=True); producer.start()
        try:
            with os.fdopen(incoming, 'rb') as stream:
                value = handoff.authenticate(self.repo, self.f.original, self.f.proof, 'terminus-2', stream)
        finally:
            producer.join(timeout=10)
            self.assertFalse(producer.is_alive(), 'Local test pipe must close without a background worker')
        if errors: raise errors[0]
        return value, sent

    def recheck(self, witness):
        return handoff.recheck(self.repo, self.f.original, self.f.proof, 'terminus-2', witness)

    def test_real_operator_capture_pipe_stream_and_native_audit_are_required(self):
        before = self.f.archive.read_bytes()
        with patch.object(exporter, 'verify_archive', wraps=exporter.verify_archive) as actual_archive:
            witness, sent = self.receive(send=True)
        actual_archive.assert_called_once(); self.operator_audit.assert_called_once(); self.audit.assert_called_once()
        record = handoff.describe(witness)
        self.assertEqual(record['streamed_backup'], self.f.backup)
        self.assertEqual(record['predecessors']['blocks'][0]['results_sha256'],
            {r['trial_id']: r['result_sha256'] for r in self.f.data['rows']})
        self.assertFalse(record['paid_launch_ready']); self.assertFalse(sent[0]['paid_launch_ready'])
        self.assertIsNone(self.f.data['rows'][0]['reward']); self.assertIsNone(self.f.data['rows'][1]['total_cost_usd'])
        self.assertNotIn('private-fixture', json.dumps(record))
        self.assertEqual(self.f.archive.read_bytes(), before)
        self.assertFalse((self.repo / '.runtime/finalisation' / operator.FILE).exists())

    def test_no_archive_or_snapshot_file_can_replace_live_native_pipe(self):
        with self.f.archive.open('rb') as stream:
            with self.assertRaisesRegex(ValueError, 'pipe'):
                handoff.authenticate(self.repo, self.f.original, self.f.proof, 'terminus-2', stream)
        self.audit.assert_not_called()

    def test_sender_refuses_regular_file_output_before_capture(self):
        with tempfile.TemporaryFile('w+b') as destination:
            with self.assertRaisesRegex(ValueError, 'pipe'): handoff.send(self.repo, destination)
        self.operator_audit.assert_not_called()

    def test_active_state_refuses_before_reading_stream_or_auditing(self):
        self.inactive.side_effect = ValueError('active final')
        packet = self.packet()
        with self.assertRaisesRegex(ValueError, 'active final'): self.receive(packet)
        self.audit.assert_not_called()

    def test_persistent_native_or_final_stop_refused(self):
        packet = self.packet()
        for root in (self.repo, self.native):
            for marker in ('operator-stop-request.json', 'provider-stop.json'):
                path = root / '.runtime/stage2' / marker
                self.put(root, '.runtime/stage2/' + marker, b'{"automatic_resume":false}')
                with self.subTest(root=root, marker=marker), self.assertRaisesRegex(ValueError, 'stop'):
                    self.receive(packet)
                path.unlink()
        self.audit.assert_not_called()

    def test_missing_commitment_fails_before_native_collector(self):
        with self.assertRaises(ValueError): self.receive(self.packet(commit=False))
        self.audit.assert_not_called()

    def test_bad_envelope_schema_paid_flags_or_identity_refused(self):
        base = self.header()
        for change in ('schema', 'kind', 'harness', 'paid', 'extra', 'original'):
            header = deepcopy(base)
            if change == 'schema': header['schema_version'] = True
            elif change == 'kind': header['kind'] = 'saved_checks'
            elif change == 'harness': header['harness'] = 'openhands'
            elif change == 'paid': header['operator']['paid_launch_ready'] = True
            elif change == 'extra': header['operator']['authority'] = 'grant'
            else: header['operator']['original_qualification_sha256'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(ValueError): self.receive(self.packet(header))
        self.audit.assert_not_called()

    def test_exact_snapshot_and_receipt_bytes_cannot_be_reserialised(self):
        base = self.header()
        for field in ('snapshot', 'backup'):
            header = deepcopy(base); header[field] = json.dumps(json.loads(header[field]), sort_keys=True)
            with self.subTest(field=field), self.assertRaises(ValueError): self.receive(self.packet(header))
        self.audit.assert_not_called()

    def test_original_proof_current_source_and_native_binding_changes_refused(self):
        packet = self.packet()
        for root, name in ((self.repo, '.runtime/stage2/' + policy.BASELINE_FILE),
                (self.repo, '.runtime/stage2/' + policy.FINAL_FILE),
                (self.repo, 'stage2/matched_repeat_handoff.py'),
                (self.native, '.runtime/stage2/no-cutoff-final-runtime.json'),
                (self.native, next(n for n in self.f.content if n.endswith('/result.json')))):
            path = root / name; raw = path.read_bytes(); path.write_bytes(raw + b'\n')
            with self.subTest(name=name), self.assertRaises(ValueError): self.receive(packet)
            path.write_bytes(raw)
        self.audit.assert_not_called()

    def test_invented_source_map_results_and_receipt_hash_refused(self):
        base = self.header()
        for change in ('native', 'source', 'result', 'receipt'):
            header = deepcopy(base); document = header['operator']
            if change == 'native': document['native_files'].pop(next(iter(document['native_files'])))
            elif change == 'source': document['local_files']['stage2/matched_repeat_stream.py'] = '0' * 64
            elif change == 'result':
                results = document['predecessors']['blocks'][0]['results_sha256']
                results[next(iter(results))] = '0' * 64
            else: document['predecessors']['blocks'][0]['backup_record_sha256'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(ValueError): self.receive(self.packet(header))
        self.audit.assert_not_called()

    def test_fresh_audit_cannot_be_replaced_with_old_checks_true(self):
        self.audit.side_effect = ValueError('Actual fresh audit failed')
        with self.assertRaisesRegex(ValueError, 'Actual fresh audit'): self.receive()
        self.audit.assert_called_once()

    def test_native_changed_outcome_phase_or_extra_metadata_refused(self):
        packet = self.packet()
        for change in ('result', 'phase', 'extra'):
            data = deepcopy(self.f.data)
            if change == 'result': data['rows'][0]['result_sha256'] = '0' * 64
            elif change == 'phase': data['rows'][0]['agent_seconds'] = None
            else: data['raw_transcript'] = 'must not pass'
            self.audit.side_effect = lambda files: data
            with self.subTest(change=change), self.assertRaises(ValueError): self.receive(packet)

    def test_only_collection_timestamp_can_differ_in_fresh_audit(self):
        data = deepcopy(self.f.data); data['collected_utc'] = '2026-09-29T02:00:00+00:00'
        self.audit.side_effect = lambda files: data
        witness, _ = self.receive()
        self.assertEqual(handoff.describe(witness)['predecessors']['blocks'][0]['audit_sha256'],
            operator._audit_hash(self.f.data))

    def test_file_and_support_inventory_mutation_during_audit_refused(self):
        packet = self.packet()
        trial = self.f.data['rows'][0]['trial_id']
        name = '.runtime/stage2/scored-attempts/' + trial + '/0002.request.json'
        def mutate(files):
            self.put(self.native, name, b'{"private":"new"}')
            return deepcopy(self.f.data)
        self.audit.side_effect = mutate
        with self.assertRaisesRegex(ValueError, 'supporting'): self.receive(packet)

    def test_recheck_uses_actual_files_without_new_audit_stream_or_locks(self):
        witness, _ = self.receive(); self.audit.reset_mock(); self.operator_audit.reset_mock()
        with patch.object(wire, 'verify_archive', side_effect=AssertionError('No recursive transfer')):
            self.assertEqual(self.recheck(witness), handoff.describe(witness))
        self.audit.assert_not_called(); self.operator_audit.assert_not_called()
        name = next(iter(handoff.describe(witness)['support_files']))
        self.put(self.native, name, b'changed')
        with self.assertRaises(ValueError): self.recheck(witness)

    def test_record_or_fabricated_witness_is_not_live_authentication(self):
        witness, _ = self.receive()
        for value in (handoff.describe(witness), handoff._Witness(), {'checks': True}, None):
            with self.subTest(value=type(value)), self.assertRaises(ValueError): self.recheck(value)
        with self.assertRaises(TypeError): pickle.dumps(witness)
        with self.assertRaises(TypeError): deepcopy(witness)
        with patch.object(handoff.os, 'getpid', return_value=os.getpid() + 1):
            with self.assertRaises(ValueError): self.recheck(witness)

    def test_metadata_projection_mutation_does_not_change_witness(self):
        witness, _ = self.receive(); record = handoff.describe(witness)
        record['predecessors']['blocks'].clear(); record['copied_files'].clear()
        record['paid_launch_ready'] = True
        self.assertEqual(len(self.recheck(witness)['predecessors']['blocks']), 1)
        self.assertFalse(handoff.describe(witness)['paid_launch_ready'])

    def test_missing_lifecycle_or_provider_stop_cannot_be_invented_as_zero(self):
        packet = self.packet(); name = self.f.data['rows'][0]['trial_id']
        life = self.native / '.runtime/stage2/retry-lifecycle' / (name + '.json')
        retained = life.with_suffix('.retained'); life.rename(retained)
        with self.assertRaises(ValueError): self.receive(packet)
        retained.rename(life)
        self.put(self.native, '.runtime/stage2/scored-attempts/' + name + '/provider-stop.json', b'{}')
        with self.assertRaisesRegex(ValueError, 'provider stop'): self.receive(packet)
        self.audit.assert_not_called()

    def test_private_native_permissions_and_symlinks_refused(self):
        packet = self.packet(); path = self.native / '.runtime/stage2/no-cutoff-final-runtime.json'
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.receive(packet)
        path.chmod(0o600); retained = path.with_suffix('.retained'); path.rename(retained); path.symlink_to(retained)
        with self.assertRaises(ValueError): self.receive(packet)
        self.audit.assert_not_called()

    def test_sender_mutation_withholds_commitment(self):
        actual = wire.copy_archive
        def mutate(source, destination, size, sha):
            actual(source, destination, size, sha)
            (self.repo / 'stage2/matched_repeat_handoff.py').write_text('# changed source')
        with patch.object(wire, 'copy_archive', side_effect=mutate):
            with self.assertRaises(ValueError): self.receive(send=True)
        self.audit.assert_not_called()

    def test_openhands_fails_closed_before_any_sender_or_native_reader(self):
        for harness in ('openhands', 'C0-NC', None):
            with self.assertRaises(ValueError): handoff.send(self.repo, io.BytesIO(), harness)
            with self.assertRaises(ValueError):
                handoff.authenticate(self.repo, self.f.original, self.f.proof, harness, io.BytesIO())
        self.operator_audit.assert_not_called(); self.audit.assert_not_called()

    def test_changed_public_copy_is_rejected_before_native_audit(self):
        packet = self.packet()
        path = self.repo / operator.PUBLIC / 'lineage.json'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(ValueError): self.receive(packet)
        self.audit.assert_not_called()

    def test_sender_never_uses_saved_predecessor_record_as_capture(self):
        self.f.put('.runtime/finalisation/' + operator.FILE, b'{"checks":true,"paid_launch_ready":true}')
        witness, _ = self.receive(send=True)
        self.operator_audit.assert_called_once()
        self.assertFalse(handoff.describe(witness)['paid_launch_ready'])


class NativeProgramTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        (self.root / '.venv').mkdir(); (self.root / '.runtime/stage2').mkdir(parents=True)
        self.path = self.root / '.runtime/stage2/evidence.json'; self.path.write_bytes(b'{}'); self.path.chmod(0o600)
        self.files = {'.runtime/stage2/evidence.json': hashlib.sha256(b'{}').hexdigest()}
        self.enterContext(patch.object(handoff.baseline, 'FINAL_ROOT', self.root))
        self.enterContext(patch.object(exporter, 'REMOTE', str(self.root)))
        self.collect = self.enterContext(patch.object(exporter, 'COLLECT', "collected.append(True)\n"))

    def run_guard(self, *, active=False, isolated=True):
        program = handoff._native_program(self.files)
        calls = []; collected = []
        def status(*args, **kwargs):
            calls.append(args)
            return 'ActiveState=' + ('active' if active else 'inactive') + '\nMainPID=0\nExecMainStatus=0\n'
        with (patch.object(sys, 'prefix', str(self.root / '.venv')),
                patch.object(sys, 'flags', NS(isolated=isolated)), patch.object(sys, 'dont_write_bytecode', True),
                patch.object(sys, 'pycache_prefix', None), patch('subprocess.check_output', side_effect=status)):
            exec(program, {'collected': collected})
        return collected, calls

    def test_generated_preimport_guard_runs_both_sides_of_unchanged_collector(self):
        collected, calls = self.run_guard()
        self.assertEqual(collected, [True]); self.assertEqual(len(calls), 2)

    def test_guard_refuses_active_changed_private_or_existing_cache_before_collector(self):
        with self.assertRaises(ValueError): self.run_guard(active=True)
        with self.assertRaises(ValueError): self.run_guard(isolated=False)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError): self.run_guard()
        self.path.chmod(0o600); self.path.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.run_guard()
        self.path.write_bytes(b'{}')
        (self.root / '.runtime/unused-matched-handoff-bytecode').mkdir()
        with self.assertRaises(ValueError): self.run_guard()

    def test_guard_refuses_symlinked_venv(self):
        path = self.root / '.venv'; renamed = self.root / '.venv-retained'
        path.rename(renamed); path.symlink_to(renamed)
        with self.assertRaises(ValueError): self.run_guard()

    def test_postimport_guard_catches_collector_side_source_or_permission_change(self):
        for code in ("_handoff_root.joinpath('.runtime/stage2/evidence.json').write_bytes(b'changed')",
                "_handoff_root.joinpath('.runtime/stage2/evidence.json').chmod(0o644)"):
            self.path.write_bytes(b'{}'); self.path.chmod(0o600)
            with patch.object(exporter, 'COLLECT', code + '\n'):
                with self.assertRaises(ValueError): self.run_guard()

    def test_native_context_cannot_be_moved_to_an_old_root_or_other_checkout(self):
        with (patch.dict(handoff.runtime.DEPLOYMENTS, {'terminus-2': self.root}),
                patch.object(handoff.platform, 'system', return_value='Linux'),
                patch.object(handoff, '__file__', str(self.root / 'stage2/matched_repeat_handoff.py'))):
            self.assertEqual(handoff._context(self.root, 'terminus-2'), self.root)
            with self.assertRaises(ValueError): handoff._context(self.root / 'old-study', 'terminus-2')
            with patch.object(handoff.platform, 'system', return_value='Darwin'):
                with self.assertRaises(ValueError): handoff._context(self.root, 'terminus-2')
            with patch.object(handoff, '__file__', str(self.root / 'other/matched_repeat_handoff.py')):
                with self.assertRaises(ValueError): handoff._context(self.root, 'terminus-2')

    def test_native_collector_uses_own_isolated_interpreter_and_no_credentials(self):
        with (patch.dict(os.environ, {'OPENROUTER_API_KEY': 'must-not-forward', 'PYTHONPATH': '/wrong'}),
                patch('subprocess.run', return_value=NS(returncode=0, stdout='{"allowlisted":true}')) as call):
            self.assertEqual(handoff._native_audit(self.files), {'allowlisted': True})
        args, kwargs = call.call_args
        self.assertEqual(args[0], [str(self.root / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertEqual(kwargs['cwd'], self.root)
        self.assertEqual(set(kwargs['env']), {'PATH', 'LANG', 'DO_NOT_TRACK', 'LITELLM_LOCAL_MODEL_COST_MAP'})
        self.assertNotIn('must-not-forward', repr(call.call_args))

    def test_native_transport_failure_never_echoes_private_output(self):
        for value in (NS(returncode=1, stdout='secret', stderr='private'),
                NS(returncode=0, stdout='not-json-private'), subprocess.TimeoutExpired('private', 1), OSError('private')):
            with patch('subprocess.run') as call:
                if isinstance(value, Exception): call.side_effect = value
                else: call.return_value = value
                with self.assertRaises(ValueError) as failure: handoff._native_audit(self.files)
            self.assertNotIn('secret', str(failure.exception)); self.assertNotIn('not-json-private', str(failure.exception))


if __name__ == '__main__':
    unittest.main()
