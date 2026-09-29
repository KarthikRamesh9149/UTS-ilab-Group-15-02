"""Local stdlib child/pipes and synthetic metadata; no native audit or SSH."""
import ast
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
import sys
import unittest
from unittest.mock import Mock, patch

import no_cutoff_final_transport as transport
import no_cutoff_final_reporting as launch
import no_cutoff_final_backup_operator as receiver
import matched_repeat_amended_handoff as handoff
import matched_repeat_connection as connection
import matched_repeat_service as service


ALIASES = {'<reporting-bootstrap>': 'bootstrap', '<stdin>': 'transport'}


def program(body):
    original = 'import json,sys\nc={"operation":"collect"}\n' + body + '\n' + transport.FOOTER
    return transport._wrap(original, ALIASES), original


def metadata(raw):
    return dict(status='transport_finished', error_type=None, returncode=0, elapsed_seconds=1.0,
        stdout_bytes=len(raw), automatic_resume=False, native_state_requires_inspection=False,
        diagnostics=dict(records=[dict(event='started', elapsed_seconds=0.0, pid=7, start_ticks=4),
            dict(event='returned', elapsed_seconds=1.0, stdout_sha256=transport._hash(raw))],
            redacted_stderr_records=0, samples_are_not_passed_checks=True))


class TransportTests(unittest.TestCase):
    def run_source(self, body, sample=0.02):
        with patch.object(transport, 'SAMPLE_SECONDS', sample): source, _ = program(body)
        with redirect_stderr(io.StringIO()):
            return transport._exchange(source, ALIASES, [sys.executable, '-I', '-B', '-'],
                {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})

    def test_source_bound_original_body_is_byte_preserved(self):
        source, original = program('def main(): return {}')
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == '_program' for t in n.targets))
        self.assertEqual(ast.literal_eval(node.value), original[:-len(transport.FOOTER)])
        for value in ('def main(): return {}', transport.FOOTER * 2):
            with self.assertRaises(ValueError): transport._wrap(value, ALIASES)

    def test_one_main_call_preserves_float_null_and_validated_terminal_bytes(self):
        raw, meta = self.run_source('calls=0\ndef main():\n global calls\n calls+=1\n assert calls==1\n return {"v":1.0,"n":None}')
        self.assertEqual(raw, b'{"n":null,"v":1.0}\n'); transport._completed(raw, meta)

    def test_failure_trace_is_bound_metadata_not_raw_exception_text(self):
        with self.assertRaises(transport.AuditTransportError) as caught:
            self.run_source('def main(): raise ValueError("PRIVATE SECRET")')
        value = caught.exception.metadata
        self.assertEqual(value['returncode'], 1); self.assertNotIn('PRIVATE', json.dumps(value))
        error = value['diagnostics']['records'][-1]['exceptions'][0]
        self.assertEqual(error['type'], 'ValueError'); self.assertTrue(error['frames'])
        self.assertTrue(all(set(f) == {'source', 'line'} for f in error['frames']))

    def test_samples_are_not_passed_checks(self):
        raw, meta = self.run_source('import time\ndef main():\n time.sleep(0.12)\n return {}')
        transport._completed(raw, meta)
        self.assertTrue(any(v['event'] == 'sample' for v in meta['diagnostics']['records']))
        self.assertTrue(meta['diagnostics']['samples_are_not_passed_checks'])

    def test_unknown_stderr_is_counted_without_contents(self):
        raw, meta = self.run_source('import os\ndef main():\n os.write(2,b"PRIVATE\\n")\n return {}')
        self.assertEqual(meta['diagnostics']['redacted_stderr_records'], 1)
        self.assertNotIn('PRIVATE', json.dumps(meta)); transport._completed(raw, meta)

    def test_invalid_diagnostics_are_redacted_and_not_accepted_as_completion(self):
        sink = transport._Diagnostics(ALIASES)
        for raw in (b'{"event":"sample","elapsed_seconds":NaN}',
                b'{"event":"sample","event":"returned","elapsed_seconds":1}',
                b'{"event":"sample","elapsed_seconds":1,"frames":[{"source":"PRIVATE","line":1}]}'):
            sink.feed(transport.PREFIX + raw + b'\n')
        self.assertEqual(sink.finish()['redacted_stderr_records'], 3)
        data = metadata(b'{}'); data['diagnostics']['records'] = []
        with self.assertRaises(ValueError): transport._completed(b'{}', data)

    def test_return_without_final_guard_cannot_be_saved(self):
        base = metadata(b'{}')
        for change in (lambda d: d.update(returncode=1),
                lambda d: d['diagnostics']['records'].pop(),
                lambda d: d['diagnostics']['records'].append(dict(event='failed')),
                lambda d: d['diagnostics']['records'][-1].update(stdout_sha256='0' * 64)):
            value = deepcopy(base); change(value)
            with self.assertRaises(ValueError): transport._completed(b'{}', value)

    def test_timeout_is_classified_and_owned_client_cleanup_only(self):
        with patch.object(transport, 'TRANSPORT_SECONDS', 0.08), self.assertRaises(transport.AuditTransportError) as caught:
            self.run_source('import time\ndef main():\n time.sleep(0.5)\n return {}')
        self.assertEqual(caught.exception.metadata['status'], 'transport_timeout')
        fake = Mock(stdin=None, stdout=None, stderr=None); fake.poll.return_value = None
        transport._close_client(fake, native_child=True)
        fake.terminate.assert_not_called(); fake.kill.assert_not_called()

    def test_parser_windows_do_not_become_task_deadlines(self):
        self.assertEqual(transport.TRANSPORT_SECONDS, 1800)
        self.assertEqual(receiver.TRANSPORT_SECONDS, 2700)
        self.assertEqual(connection.TIMEOUT, 4500); self.assertEqual(service.TRANSPORT_SECONDS, 4500)

    def test_native_handoff_uses_same_diagnostics_and_original_interpreter(self):
        value = dict(native={}, data={'reporting_source_files': {}}, document={'operator_commit': 'a' * 40})
        raw = b'{"value":1.0}'
        source, _ = program('def main(): return {}')
        with patch.object(launch, '_program', return_value=source), patch.object(transport, '_wrap', return_value=source), \
                patch.object(transport, '_exchange', return_value=(raw, metadata(raw))) as exchange:
            self.assertEqual(handoff._native_audit(value), {'value': 1.0})
        self.assertEqual(exchange.call_args.args[2], [str(handoff.report.ROOT / '.venv/bin/python'), '-I', '-B', '-'])
        self.assertEqual(exchange.call_args.kwargs, {'cwd': handoff.report.ROOT})
        self.assertEqual(exchange.call_args.args[3], handoff.report.ENVIRONMENT)

    def test_mac_actual_audit_validates_all_returned_schema_and_bytes(self):
        bindings = dict(native={}, reporting={}, local={}, anchors={}, commit='a' * 40)
        raw = b'{"reporting_source_files":{}}'; source, _ = program('def main(): return {}')
        with patch.object(launch, '_program', return_value=source), patch.object(transport, '_wrap', return_value=source), \
                patch.object(launch, '_recheck') as checked, patch.object(transport, '_exchange', return_value=(raw, metadata(raw))), \
                patch.object(launch.archive, 'validate_snapshot') as validate:
            data, observed, _ = launch._audit(bindings)
        validate.assert_called_once_with(data, {}); self.assertEqual(observed, raw)
        self.assertEqual(checked.call_count, 3)

    def test_late_schema_failure_retains_actual_transport_diagnostics(self):
        bindings = dict(native={}, reporting={}, local={}, anchors={}, commit='a' * 40)
        raw = b'{"reporting_source_files":{}}'; source, _ = program('def main(): return {}')
        with patch.object(launch, '_program', return_value=source), patch.object(transport, '_wrap', return_value=source), \
                patch.object(launch, '_recheck'), patch.object(transport, '_exchange', return_value=(raw, metadata(raw))), \
                patch.object(launch.archive, 'validate_snapshot', side_effect=ValueError('PRIVATE SCHEMA CONTENT')):
            with self.assertRaises(transport.AuditTransportError) as caught: launch._audit(bindings)
        value = caught.exception.metadata
        self.assertEqual(value['status'], 'transport_finished')
        self.assertEqual(value['operator_failure_stage'], 'snapshot_schema_validation')
        self.assertEqual(value['diagnostics']['records'][-1]['event'], 'returned')
        self.assertIn('transmitted_program_sha256', value)
        self.assertFalse(value['completed_final_audit_verified'])
        self.assertNotIn('PRIVATE', json.dumps(value))
