"""Mocked native audit, real private files/archives; no native or paid calls."""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matched_repeat_predecessor as reader
import matched_repeat_policy as policy
import export_no_cutoff_final as exporter
import no_cutoff_final_policy as final_policy
from scored_gateway import private_directory
from run_credit_only import hold
from test_no_cutoff_final_policy import Fixture as FinalFixture


def sha(content):
    return hashlib.sha256(content).hexdigest()


class Fixture:
    """Fabricated anchors and archive contents, never installed on the VPS."""
    def __init__(self, owner, repo):
        self.repo = repo
        final = FinalFixture(owner, repo)
        self.manifest = final.manifest
        self.proof = deepcopy(final.proof)
        self.original = dict(model_protocol_sha256=policy.MODEL_SHA256,
            policy=dict(terminus_default_max_turns=1000000, openhands_max_iterations=1000000), sources={})
        names = (set(self.proof['sources']) | policy.BASELINE_BEHAVIOUR_FILES | policy.INHERITED_BASELINE_DELTAS
            | {name + '.py' for name in policy.TEST_MODULES if name + '.py' not in policy.REQUIRED_SOURCE_FILES})
        self.content = {'stage2/' + name: ('# Synthetic ' + name + '\n').encode() for name in names}
        self.content['stage2/input_manifest.json'] = json.dumps(self.manifest).encode()
        self.proof['sources'] = {name: sha(self.content['stage2/' + name]) for name in names}
        for name in policy.BASELINE_BEHAVIOUR_FILES | policy.INHERITED_BASELINE_DELTAS:
            self.original['sources'][name] = (sha(('old ' + name).encode())
                if name in policy.INHERITED_BASELINE_DELTAS else self.proof['sources'][name])
        for name in policy.REQUIRED_SOURCE_FILES:
            self.put('stage2/' + name, ('# Synthetic current ' + name + '\n').encode())
        for name, content in self.content.items(): self.put(name, content)
        self.proof['sources_sha256'] = policy.fingerprint(self.proof['sources'])
        for name in self.proof['evidence_files']:
            content = ('Synthetic producer ' + name).encode()
            self.content[name] = content
            self.proof['evidence_files'][name] = sha(content)
            self.put(reader.PRIVATE + '/' + name, content)
        values = {'no-cutoff-final-candidate.json': final.document,
            'no-cutoff-final-authentication.json': {'synthetic': True},
            'no-cutoff-final-runtime.json': {'synthetic': True},
            'no-cutoff-final-manifest.json': self.manifest,
            'no-cutoff-final-credit-policy.json': deepcopy(final_policy.POLICY)}
        self.content['.runtime/stage2/python-runtime.tar.gz'] = b'Synthetic Python archive'
        self.proof['python_runtime_sha256'] = sha(self.content['.runtime/stage2/python-runtime.tar.gz'])
        for name, value in values.items(): self.private_input(name, value)
        self.private_input('no-cutoff-final-qualification.json', self.proof)
        self.block = deepcopy(final.block)
        self.block.update(qualification_sha256=policy.fingerprint(self.proof),
            sources_sha256=self.proof['sources_sha256'], python_runtime_sha256=self.proof['python_runtime_sha256'])
        self.private_input('no-cutoff-final-matrix.json', self.block, registration=True)
        self.put(reader.ORIGINAL, json.dumps(self.original).encode())
        pins = ((policy, 'ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(self.original)),
            (policy, 'CUSTOM_FINAL_QUALIFICATION_SHA256', policy.fingerprint(self.proof)),
            (policy, 'CUSTOM_FINAL_REGISTRATION_SHA256', policy.fingerprint(self.block)),
            (policy, 'CUSTOM_FINAL_SOURCES_SHA256', self.proof['sources_sha256']),
            (reader, 'ORIGINAL_FILE_SHA256', reader._digest(repo, reader.ORIGINAL)),
            (reader, 'FINAL_FILE_SHA256', sha(self.content['.runtime/stage2/no-cutoff-final-qualification.json'])),
            (reader, 'REGISTRATION_FILE_SHA256', sha(self.content['.runtime/stage2/no-cutoff-final-matrix.json'])),
            (exporter, 'ORIGINAL_FREEZE_SHA256', self.block['original_candidate_sha256']))
        for module, name, value in pins: owner.enterContext(patch.object(module, name, value))
        projection = dict(self.proof, qualification_sha256=policy.fingerprint(self.proof),
            qualification_file_sha256=reader.FINAL_FILE_SHA256,
            private_file_sha256={name: sha(self.content['.runtime/stage2/' + name]) for name in values
                if name != 'no-cutoff-final-candidate.json'})
        registration = dict(self.block, kind='synthetic_public',
            registration_sha256=policy.fingerprint(self.block),
            registration_file_sha256=reader.REGISTRATION_FILE_SHA256)
        lineage = dict(original_candidate_sha256=self.block['original_candidate_sha256'],
            candidate_sha256=self.block['candidate_sha256'], validation_results_sha256=self.block['validation_results_sha256'],
            candidate_file_sha256=sha(self.content['.runtime/stage2/no-cutoff-final-candidate.json']))
        for name, value in (('qualification.json', projection), ('registration-c0-nc.json', registration),
                ('lineage.json', lineage), ('credit-policy.json', values['no-cutoff-final-credit-policy.json'])):
            self.put(reader.PUBLIC + '/' + name, json.dumps(value).encode())
        self.data = dict(condition='C0-NC', registration=self.block,
            qualification_sha256=policy.fingerprint(self.proof), sources=self.proof['sources'],
            model_protocol=policy.SETTINGS.document(), policy=values['no-cutoff-final-credit-policy.json'],
            collected_utc='2026-09-29T00:02:00Z',
            service=dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'),
            audit_checks=dict.fromkeys(exporter.CHECKS, True),
            bindings={name: sha(content) for name, content in self.content.items() if name.startswith('.runtime/')}, rows=[])
        for i, cell in enumerate(self.block['cells']):
            row = dict.fromkeys(exporter.ROW_FIELDS, 0)
            row.update({k: cell[k] for k in ('trial_id', 'task_id', 'harness')})
            row.update(reward=(None if i == 0 else i % 2), status='verifier_failed' if i == 0 else 'verified',
                started_utc='2026-09-29T00:00:00Z', completed_utc='2026-09-29T00:01:00Z',
                agent_error_type='', verifier_error_type='RuntimeError' if i == 0 else '',
                model_requests=2, accepted_model_responses=1, interrupted_requests=1,
                known_cost_usd='0.01', total_cost_usd=None, unknown_cost_requests=1,
                input_tokens=None, output_tokens=None, cleanup_complete=True, model_revoked=True,
                agent_seconds=60.0, official_agent_timeout_seconds=7200.0)
            content = json.dumps(dict(trial_id=row['trial_id'], reward=row['reward'])).encode()
            self.content['.runtime/stage2/scored-trials/' + row['trial_id'] + '/result.json'] = content
            row['result_sha256'] = sha(content)
            self.data['rows'].append(row)
        self.put(reader.COMPLETED + '/snapshot.json', json.dumps(self.data).encode())
        self.archive = repo / reader.COMPLETED / 'evidence.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name in exporter.expected_archive_hashes(self.data):
                content = self.content[name]
                member = tarfile.TarInfo(name); member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        self.archive.chmod(0o600)
        receipt = dict(sha256=sha(self.archive.read_bytes()), excluded=0,
            files=len(exporter.expected_archive_hashes(self.data)),
            bytes=sum(len(self.content[name]) for name in exporter.expected_archive_hashes(self.data)))
        self.backup = exporter.verify_archive(self.archive, self.data, receipt)
        self.put(reader.COMPLETED + '/backup.json', json.dumps(self.backup).encode())
        exporter.export(self.data, self.backup)

    def put(self, name, content):
        path = self.repo / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if name.startswith('.runtime/'): path.chmod(0o600)

    def private_input(self, name, value, registration=False):
        content = json.dumps(value).encode()
        self.content['.runtime/stage2/' + name] = content
        self.put(reader.PRIVATE + ('/' if registration else '/.runtime/stage2/') + name, content)


class PredecessorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        for module, name, value in ((exporter, 'REPO', self.repo), (exporter, 'OUTPUT', self.repo / reader.PUBLIC),
                (reader, '__file__', str(self.repo / 'stage2/matched_repeat_predecessor.py')),
                (exporter, '__file__', str(self.repo / 'stage2/export_no_cutoff_final.py'))):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.object(reader.platform, 'system', return_value='Darwin'))
        self.f = Fixture(self, self.repo)
        self.fresh = deepcopy(self.f.data)
        self.native = self.enterContext(patch.object(reader, '_read_native', side_effect=lambda bound: deepcopy(self.fresh)))

    def test_capture_authenticates_actual_archive_and_binds_every_predecessor_result(self):
        with patch.object(exporter, 'verify_archive', wraps=exporter.verify_archive) as archive:
            document = reader.capture(self.repo)
        archive.assert_called_once(); self.native.assert_called_once()
        record = document['predecessors']; block = record['blocks'][0]
        self.assertEqual(len(block['results_sha256']), 89)
        self.assertEqual(block['archive_sha256'], sha(self.f.archive.read_bytes()))
        self.assertEqual(block['audit_sha256'], reader._audit_hash(self.f.data))
        self.assertFalse(document['paid_launch_ready']); self.assertFalse(record['paid_launch_ready'])
        self.assertNotIn('score', block); self.assertNotIn('passes', block)
        self.assertEqual(document['native_files'], self.native.call_args.args[0])
        self.assertTrue(all(document['native_files'][name] == digest
            for name, digest in exporter.expected_archive_hashes(self.f.data).items()))
        self.assertFalse((self.repo / '.runtime/finalisation' / reader.FILE).exists())

    def test_preserves_missing_verifier_zeros_and_unknown_cost_without_floor(self):
        document = reader.capture(self.repo)
        rows = self.f.data['rows']; self.assertIsNone(rows[0]['reward'])
        self.assertEqual(rows[2]['reward'], 0); self.assertIsNone(rows[2]['total_cost_usd'])
        self.assertEqual(document['predecessors']['blocks'][0]['results_sha256'],
            {row['trial_id']: row['result_sha256'] for row in rows})

    def test_qualification_and_all_runtime_producer_copies_are_rechecked(self):
        anchors = reader._anchors(self.repo)
        self.assertEqual(len(self.f.proof['evidence_files']), 8)
        for name in (*self.f.proof['evidence_files'], '.runtime/stage2/no-cutoff-final-runtime.json'):
            path = self.repo / reader.PRIVATE / name; content = path.read_bytes()
            path.write_bytes(content + b' ')
            with self.subTest(name=name), self.assertRaises(ValueError): reader._anchors(self.repo)
            path.write_bytes(content)
        self.assertEqual(reader._anchors(self.repo), anchors)

    def test_original_qualification_and_final_registration_raw_bytes_are_pinned(self):
        for name in (reader.ORIGINAL, reader.PRIVATE + '/no-cutoff-final-matrix.json',
                reader.PRIVATE + '/.runtime/stage2/no-cutoff-final-qualification.json'):
            path = self.repo / name; content = path.read_bytes(); path.write_bytes(content + b'\n')
            with self.subTest(name=name), self.assertRaises(ValueError): reader.capture(self.repo)
            path.write_bytes(content)
        self.native.assert_not_called()

    def test_public_qualification_cannot_change_sources_or_numeric_types(self):
        path = self.repo / reader.PUBLIC / 'qualification.json'; original = path.read_text()
        for field, value in (('sources', {}), ('live_api_calls', False), ('qualification_file_sha256', '0' * 64)):
            data = json.loads(original); data[field] = value; path.write_text(json.dumps(data))
            with self.subTest(field=field), self.assertRaises(ValueError): reader.capture(self.repo)
        path.write_text(original); self.native.assert_not_called()

    def test_qualified_collector_and_measured_sources_cannot_change(self):
        for name in ('export_no_cutoff_final.py', 'native_agents.py', 'no_cutoff_custom_agent.py'):
            path = self.repo / 'stage2' / name; original = path.read_bytes(); path.write_bytes(original + b'\n')
            with self.subTest(name=name), self.assertRaises(ValueError): reader.capture(self.repo)
            path.write_bytes(original)
        self.native.assert_not_called()

    def test_missing_backup_refuses_before_any_completed_native_reader(self):
        self.f.archive.rename(self.f.archive.with_suffix('.retained'))
        with self.assertRaisesRegex(ValueError, 'missing'): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_missing_completed_public_export_refuses_before_native_reader(self):
        path = self.repo / reader.PUBLIC / 'c0-nc/trials.csv'; path.rename(path.with_suffix('.retained'))
        with self.assertRaises(ValueError): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_curated_summary_and_csv_cannot_replace_original_outcomes(self):
        for name in ('summary.json', 'trials.csv'):
            path = self.repo / reader.PUBLIC / 'c0-nc' / name; original = path.read_text()
            path.write_text(original.replace('0.01', '0.02') if name.endswith('csv') else original.replace('"intended": 89', '"intended": 88'))
            with self.subTest(name=name), self.assertRaises(ValueError): reader.capture(self.repo)
            path.write_text(original)
        self.native.assert_not_called()

    def test_saved_checks_true_cannot_replace_fresh_native_audit(self):
        self.native.side_effect = ValueError('active final')
        with patch.object(exporter, 'verify_archive', wraps=exporter.verify_archive) as archive:
            with self.assertRaisesRegex(ValueError, 'active final'): reader.capture(self.repo)
        self.native.assert_called_once(); archive.assert_not_called()

    def test_native_active_partial_mutated_or_unallowlisted_metadata_refused(self):
        for change in ('active', 'partial', 'duplicate', 'order', 'result', 'sources', 'raw', 'phase'):
            self.fresh = deepcopy(self.f.data)
            if change == 'active': self.fresh['service']['ActiveState'] = 'active'
            elif change == 'partial': self.fresh['rows'].pop()
            elif change == 'duplicate': self.fresh['rows'][1] = self.fresh['rows'][0]
            elif change == 'order': self.fresh['rows'].reverse()
            elif change == 'result': self.fresh['rows'][0]['result_sha256'] = '0' * 64
            elif change == 'sources': self.fresh['sources']['native_agents.py'] = '0' * 64
            elif change == 'raw': self.fresh['raw_exchange'] = 'must not pass'
            else: self.fresh['rows'][0]['agent_seconds'] = None
            with self.subTest(change=change), self.assertRaises(ValueError): reader.capture(self.repo)

    def test_archive_flags_do_not_substitute_for_bytes(self):
        self.f.archive.write_bytes(b'not the retained archive')
        with self.assertRaisesRegex(ValueError, 'Archive differs'): reader.capture(self.repo)

    def test_archive_checks_all_bound_member_bytes_not_just_archive_checksum(self):
        path = self.f.archive
        contents = dict(self.f.content); name = next(n for n in contents if n.endswith('/result.json'))
        contents[name] += b'altered'
        with tarfile.open(path, 'w:gz') as archive:
            for filename in exporter.expected_archive_hashes(self.f.data):
                content = contents[filename]; member = tarfile.TarInfo(filename); member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        backup = dict(self.f.backup, sha256=sha(path.read_bytes()))
        self.f.put(reader.COMPLETED + '/backup.json', json.dumps(backup).encode())
        with patch.object(reader, '_check_export', return_value={}):
            with self.assertRaisesRegex(ValueError, 'Archived evidence binding changed'): reader.capture(self.repo)

    def test_symlinked_archive_or_parent_refused(self):
        path = self.f.archive; retained = path.with_suffix('.retained'); path.rename(retained); path.symlink_to(retained)
        with self.assertRaisesRegex(ValueError, 'Symlink'): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_archive_mutation_during_native_audit_refused(self):
        def mutate(bound):
            self.f.archive.write_bytes(b'changed during native read')
            return self.fresh
        self.native.side_effect = mutate
        with self.assertRaises(ValueError): reader.capture(self.repo)

    def test_source_mutation_after_native_audit_refused(self):
        def mutate(bound):
            (self.repo / 'stage2/matched_repeat_predecessor.py').write_text('# changed during read')
            return self.fresh
        self.native.side_effect = mutate
        with self.assertRaisesRegex(ValueError, 'changed during verification'): reader.capture(self.repo)

    def test_fresh_verify_repeats_audit_and_archive_check_ignoring_only_observation_time(self):
        document = reader.capture(self.repo)
        self.fresh['collected_utc'] = '2026-09-29T01:00:00+00:00'
        self.assertEqual(reader.verify(document, self.repo), document['predecessors'])
        self.assertEqual(self.native.call_count, 2)
        document['paid_launch_ready'] = True
        with self.assertRaises(ValueError): reader.verify(document, self.repo)

    def test_self_created_or_extra_fields_never_grant_admission(self):
        document = reader.capture(self.repo)
        for change in ('extra', 'archive', 'audit', 'source', 'schema'):
            altered = deepcopy(document)
            if change == 'extra': altered['dispatch_permit'] = True
            elif change == 'archive': altered['predecessors']['blocks'][0]['archive_sha256'] = '0' * 64
            elif change == 'audit': altered['predecessors']['blocks'][0]['audit_sha256'] = '0' * 64
            elif change == 'source': altered['local_files'].pop(next(iter(altered['local_files'])))
            else: altered['schema_version'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): reader.verify(altered, self.repo)

    def test_save_is_private_exclusive_and_does_not_reaudit_existing_document(self):
        path, document = reader.save(self.repo)
        self.assertEqual(path.name, reader.FILE); self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(path.read_text()), document)
        calls = self.native.call_count
        with self.assertRaisesRegex(ValueError, 'existing'): reader.save(self.repo)
        self.assertEqual(self.native.call_count, calls)

    def test_save_failure_does_not_create_a_document(self):
        self.native.side_effect = ValueError('not complete')
        with self.assertRaises(ValueError): reader.save(self.repo)
        self.assertFalse((self.repo / '.runtime/finalisation' / reader.FILE).exists())

    def test_save_refuses_a_real_held_operator_lock_before_native_audit(self):
        folder = private_directory(self.repo / '.runtime/finalisation')
        with ExitStack() as stack:
            hold(stack, folder, 'matched-repeat-predecessor.lock')
            with self.assertRaises(BlockingIOError): reader.save(self.repo)
        self.native.assert_not_called()

    def test_group_readable_archive_is_not_a_private_backup(self):
        self.f.archive.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'Private evidence'): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_nonobject_public_metadata_refused_before_native_audit(self):
        (self.repo / reader.PUBLIC / 'qualification.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'Object evidence'): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_unimplemented_openhands_and_other_successors_fail_closed(self):
        for harness in ('openhands', 'C0', 'C0-NC', '', None):
            with self.subTest(harness=harness), self.assertRaises(ValueError): reader.capture(self.repo, harness)
        self.native.assert_not_called()

    def test_native_host_cannot_claim_off_server_backup_verification(self):
        with patch.object(reader.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(ValueError, 'off-server'): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_wrong_checkout_import_is_rejected(self):
        with patch.object(reader, '__file__', '/tmp/wrong/reader.py'):
            with self.assertRaises(ValueError): reader.capture(self.repo)
        with patch.object(exporter, '__file__', '/tmp/wrong/exporter.py'):
            with self.assertRaises(ValueError): reader.capture(self.repo)
        self.native.assert_not_called()

    def test_no_write_export_or_backup_operation_is_called(self):
        with patch.object(exporter, 'read_snapshot', side_effect=AssertionError('writes snapshot')), \
                patch.object(exporter, 'private_backup', side_effect=AssertionError('creates archive')), \
                patch.object(exporter, 'export', side_effect=AssertionError('writes public output')):
            reader.capture(self.repo)

    def test_private_anchor_permissions_and_path_escape_refused(self):
        path = self.repo / reader.ORIGINAL; path.chmod(0o644)
        with self.assertRaises(ValueError): reader.capture(self.repo)
        for name in ('', '../escape', '/absolute', 'stage2//x', 'stage2/./x'):
            with self.subTest(name=name), self.assertRaises(ValueError): reader._regular(self.repo, name)


class NativeProgramTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.enterContext(patch.object(exporter, 'REMOTE', str(self.root)))
        self.enterContext(patch.object(exporter, 'COLLECT', 'collector_was_called = True\n'))
        (self.root / 'fixture.py').write_bytes(b'synthetic')
        self.bindings = {'fixture.py': sha(b'synthetic')}
        self.state = 'ActiveState=inactive\nMainPID=0\nExecMainStatus=0\n'
        self.service = self.enterContext(patch.object(subprocess, 'check_output', side_effect=lambda *a, **k: self.state))

    def execute(self):
        namespace = {}
        exec(compile(reader._native_program(self.bindings), '<synthetic>', 'exec'), namespace)
        return namespace

    def test_preflight_rechecks_before_and_after_the_unchanged_collector(self):
        self.assertTrue(self.execute()['collector_was_called']); self.assertEqual(self.service.call_count, 2)
        program = reader._native_program(self.bindings)
        self.assertLess(program.index('_predecessor_check()\n'), program.index('collector_was_called'))

    def test_active_failed_or_ambiguous_service_refused_before_collector(self):
        for state in ('ActiveState=active\nMainPID=42\nExecMainStatus=0\n',
                'ActiveState=inactive\nMainPID=0\nExecMainStatus=1\n', ''):
            self.state = state
            with self.subTest(state=state), self.assertRaises(ValueError): self.execute()

    def test_persistent_stop_and_dangling_stop_symlink_refused(self):
        marker = self.root / '.runtime/stage2/operator-stop-request.json'; marker.parent.mkdir(parents=True)
        marker.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'operator stop'): self.execute()
        self.service.assert_not_called()

    def test_source_mutation_and_symlink_refused_before_import(self):
        path = self.root / 'fixture.py'; path.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Pinned native evidence changed'): self.execute()
        path.rename(self.root / 'retained.py'); path.symlink_to(self.root / 'retained.py')
        with self.assertRaisesRegex(ValueError, 'Symlinked native evidence'): self.execute()

    def test_post_audit_mutation_is_detected(self):
        with patch.object(exporter, 'COLLECT', '(Path(' + repr(str(self.root / 'fixture.py')) + ').write_text("changed"))\n'):
            with self.assertRaisesRegex(ValueError, 'Pinned native evidence changed'): self.execute()

    def test_unsafe_or_missing_native_bindings_refused(self):
        for value in ({}, {'../escape': '0' * 64}, {'x//y': '0' * 64}, {'x': True}):
            with self.subTest(value=value), self.assertRaises(ValueError): reader._native_program(value)

    def test_native_audit_uses_exact_interpreter_and_hides_private_failure_output(self):
        with patch.object(exporter, 'remote_command', return_value=['ssh', 'fixed', '/pinned/.venv/bin/python', '-']), \
                patch.object(reader.subprocess, 'run', return_value=SimpleNamespace(returncode=1,
                    stdout='private raw data', stderr='private raw data')) as run:
            with self.assertRaises(ValueError) as caught: reader._read_native(self.bindings)
        self.assertNotIn('private raw', str(caught.exception))
        self.assertEqual(run.call_args.args[0][-2:], ['/pinned/.venv/bin/python', '-'])
        self.assertNotIn('BACKUP', run.call_args.kwargs['input'])

    def test_native_timeout_or_invalid_response_never_produces_record(self):
        for value in (subprocess.TimeoutExpired('synthetic', 1), OSError('private'),
                SimpleNamespace(returncode=0, stdout='not metadata')):
            options = {'side_effect': value} if isinstance(value, Exception) else {'return_value': value}
            with patch.object(reader.subprocess, 'run', **options):
                with self.subTest(value=type(value).__name__), self.assertRaises(ValueError): reader._read_native(self.bindings)


if __name__ == '__main__': unittest.main()
