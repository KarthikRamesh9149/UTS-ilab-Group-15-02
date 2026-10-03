"""Actual private Mac installation state; the SSH result is synthetic only."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import matched_repeat_install as install
import matched_repeat_execution_connection as connection
import test_matched_repeat_execution_connection as fixtures
import test_matched_repeat_install as native_fixtures
import matched_repeat_original as original_reader

COMMIT = fixtures.COMMIT


class InstallationPreparationTests(unittest.TestCase):
    def test_actual_mac_payload_builder_uses_existing_original_anchor_names(self):
        fixture = native_fixtures.PayloadTests('runTest')
        self.addCleanup(fixture.doCleanups); fixture.setUp()
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve(); root.chmod(0o700)
        decoded = fixture.decoded
        baseline = decoded[connection.boot.BASELINE_INPUT]
        final = decoded[connection.boot.FINAL_INPUT]
        self.enterContext(patch.object(connection.boot, 'BASELINE_SHA', install._sha(baseline)))
        self.enterContext(patch.object(connection.boot, 'FINAL_SHA', install._sha(final)))
        self.enterContext(patch.object(original_reader, 'SNAPSHOT_SHA256', install.SNAPSHOT_SHA))
        self.enterContext(patch.object(original_reader.policy, 'BASELINE_CSV_SHA256', install.BASELINE_CSV_SHA))
        aliases = {
            connection.handoff.original.operator.old.ORIGINAL: baseline,
            connection.handoff.original.operator.old.PRIVATE + '/.runtime/stage2/no-cutoff-final-qualification.json': final}
        raw_inputs = dict(decoded, **aliases)
        reads = []
        def read(name, expected=None):
            reads.append(name); raw = raw_inputs[name]
            if expected is not None and install._sha(raw) != expected: raise ValueError('Fixture input changed')
            return raw
        self.enterContext(patch.object(connection.handoff.original.launch, '_raw', side_effect=read))
        self.enterContext(patch.object(connection, 'REPO', root))
        for name in (install.SNAPSHOT, install.LAUNCH, install.BASELINE_CSV):
            path = root / name; path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            path.write_bytes(decoded[name]); path.chmod(0o600)
        public = install._public(); exported = connection.handoff.original.export.DESTINATION
        prerequisites = {n:install._sha(decoded[n]) for n in public if not n.startswith(exported + '/')}
        outputs = {n[len(exported)+1:]:install._sha(decoded[n]) for n in public if n.startswith(exported + '/')}
        self.enterContext(patch.object(connection.handoff.original.export, 'PREREQUISITES', prerequisites))
        self.enterContext(patch.object(connection.handoff.operator.recovery.policy, 'PUBLIC_FILES', outputs))
        source_files = {n:install._sha(raw) for n,raw in decoded.items()
            if n.startswith('stage2/') and n not in public | {install.LAUNCH, install.BASELINE_CSV}}
        source_files.update({connection.boot.BASELINE_INPUT:install._sha(baseline),
            connection.boot.FINAL_INPUT:install._sha(final)})
        value = dict(bindings={n:fixture.payload()[n] for n in ('native','reporter')})
        value['bindings']['reporting'] = value['bindings'].pop('reporter')
        self.enterContext(patch.object(connection, 'prepare', return_value=(value,source_files)))
        current = self.enterContext(patch.object(connection, '_current'))
        actual, payload, extra = install.prepare(COMMIT)
        self.assertIs(actual,value)
        self.assertEqual(set(extra),{install.SNAPSHOT,install.LAUNCH,install.BASELINE_CSV})
        self.assertEqual({n:base64.b64decode(raw) for n,raw in payload['files'].items()},decoded)
        self.assertEqual(base64.b64decode(payload['files'][install.BASELINE_CSV]), fixture.csv)
        self.assertNotIn(install.BASELINE_CSV, source_files)
        self.assertNotIn(install.BASELINE_CSV, prerequisites)
        self.assertTrue(set(aliases) <= set(reads)); current.assert_called_once_with(value)


class InstallationOperatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.OperatorTests('runTest')
        self.addCleanup(self.fixture.doCleanups); self.fixture.setUp()
        self.root = self.fixture.root
        source = Path(install.__file__).read_bytes()
        path = self.root / 'stage2/matched_repeat_install.py'
        path.write_bytes(source); path.chmod(0o600)
        self.hashes = dict(self.fixture.files,
            **{'stage2/matched_repeat_install.py': hashlib.sha256(source).hexdigest()})
        extra = {}
        for name in (install.SNAPSHOT, install.LAUNCH, install.BASELINE_CSV):
            path = self.root / name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            raw = b'{"synthetic_original178_anchor":true}\n'
            path.write_bytes(raw); path.chmod(0o600)
            self.hashes[name] = hashlib.sha256(raw).hexdigest()
            extra[name] = (raw, connection.boot.identity(path.lstat()))
        self.payload = dict(kind=install.KIND, commit=COMMIT, hashes=self.hashes,
            files={name: base64.b64encode((self.root / name).read_bytes()).decode() for name in self.hashes},
            native={'synthetic-native': 'a' * 64}, reporter={'synthetic-reporter': 'b' * 64})
        self.prepare = self.enterContext(patch.object(install, 'prepare', return_value=({}, self.payload, extra)))
        seed = NS(_environment=lambda: {'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8'})
        self.enterContext(patch.object(install, '_payload', return_value=(None, None, None, seed, None, None)))
        self.result = dict(kind=install.KIND, commit=COMMIT, root=str(install.ROOT), harness='terminus-2',
            sources_and_inputs=len(self.hashes), precreated_locks=3,
            copied_current_files=0, original_roots_unchanged=True,
            installed_utc='2026-09-30T00:00:00+00:00', historical_installed_bytes_attested=False,
            paid_launch_ready=False, repeat_execution_qualified=False, automatic_resume=False)
        self.run = self.enterContext(patch.object(install.subprocess, 'run',
            return_value=Mock(returncode=0, stdout=json.dumps(self.result).encode())))
        self.state = self.root / install.STATE

    def test_one_private_operator_installation_preserves_all_pinned_ssh_options(self):
        self.assertEqual(install.deploy(COMMIT), self.result)
        self.run.assert_called_once()
        args, kwargs = self.run.call_args
        fixed=connection.ssh_command(self.root)
        self.assertEqual(args[0][:-1],fixed[:-3]+['-o','ServerAliveInterval=30',
            '-o','ServerAliveCountMax=150']+fixed[-3:-2])
        remote = shlex.split(args[0][-1]); ast.parse(remote[-1])
        self.assertEqual(remote[-5:-1], [str(install.ORIGINAL / '.venv/bin/python'), '-I', '-B', '-c'])
        self.assertEqual(hashlib.sha256(kwargs['input']).hexdigest(),
            json.loads((self.state / 'intent.json').read_bytes())['payload_sha256'])
        self.assertEqual(kwargs['env'], {'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8'})
        self.assertEqual({p.name for p in self.state.iterdir()}, {'intent.json','result.json'})
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.state.iterdir()))
        self.fixture.send.assert_not_called(); self.fixture.popen.assert_not_called()

    def test_completed_or_partial_operator_state_can_never_install_again(self):
        install.deploy(COMMIT)
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        with self.assertRaisesRegex(ValueError, 'terminal'): install.deploy(COMMIT)
        self.run.assert_called_once()
        self.assertEqual({p.name:p.read_bytes() for p in self.state.iterdir()}, before)

    def test_lost_ssh_exit_retains_failure_and_forbids_another_installation(self):
        self.run.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, 'Uncertain'): install.deploy(COMMIT)
        self.assertEqual({p.name for p in self.state.iterdir()}, {'intent.json','failure.json'})
        with self.assertRaisesRegex(ValueError, 'terminal'): install.deploy(COMMIT)
        self.run.assert_called_once()

    def test_timeout_is_not_native_stop_or_permission_to_resume(self):
        self.run.side_effect = install.subprocess.TimeoutExpired('synthetic-ssh', 1800)
        with self.assertRaises(install.subprocess.TimeoutExpired): install.deploy(COMMIT)
        self.assertFalse((self.state / 'result.json').exists())
        self.assertFalse(json.loads((self.state / 'failure.json').read_bytes())['automatic_resume'])
        with self.assertRaisesRegex(ValueError, 'terminal'): install.deploy(COMMIT)
        self.fixture.popen.assert_not_called(); self.run.assert_called_once()

    def test_reply_cannot_claim_qualification_or_change_destination(self):
        for field, changed in (('root','/arbitrary'), ('commit','d'*40), ('harness','openhands'),
                ('paid_launch_ready',True), ('repeat_execution_qualified',True), ('automatic_resume',True)):
            result = dict(self.result, **{field:changed})
            # Each malformed reply gets its own actual private synthetic state;
            # no failed state is deleted or reused.
            with patch.object(install, 'STATE', install.STATE + '-' + field):
                self.run.return_value.stdout = json.dumps(result).encode()
                with self.subTest(field=field), self.assertRaises(ValueError): install.deploy(COMMIT)
                state = self.root / install.STATE
                self.assertTrue((state / 'failure.json').exists()); self.assertFalse((state / 'result.json').exists())

    def test_same_byte_original_anchor_replacement_after_ssh_refuses_success(self):
        def replace(*args, **kwargs):
            path = self.root / install.SNAPSHOT; raw = path.read_bytes()
            path.rename(path.with_suffix('.retained')); path.write_bytes(raw); path.chmod(0o600)
            return Mock(returncode=0, stdout=json.dumps(self.result).encode())
        self.run.side_effect = replace
        with self.assertRaisesRegex(ValueError, 'anchor was replaced'): install.deploy(COMMIT)
        self.assertTrue((self.state / 'failure.json').exists()); self.assertFalse((self.state / 'result.json').exists())

    def test_same_byte_required_csv_replacement_after_ssh_refuses_success(self):
        def replace(*args, **kwargs):
            path = self.root / install.BASELINE_CSV; raw = path.read_bytes()
            path.rename(path.with_suffix('.retained')); path.write_bytes(raw); path.chmod(0o600)
            return Mock(returncode=0, stdout=json.dumps(self.result).encode())
        self.run.side_effect = replace
        with self.assertRaisesRegex(ValueError, 'anchor was replaced'): install.deploy(COMMIT)
        self.assertTrue((self.state / 'failure.json').exists()); self.assertFalse((self.state / 'result.json').exists())
        self.assertEqual((self.root / install.BASELINE_CSV).read_bytes(),
            (self.root / install.BASELINE_CSV).with_suffix('.retained').read_bytes())
        with self.assertRaisesRegex(ValueError, 'terminal'): install.deploy(COMMIT)
        self.run.assert_called_once()

    def test_extra_operator_file_refuses_success_and_is_preserved(self):
        def extra(*args, **kwargs):
            path = self.state / 'extra.json'; path.write_bytes(b'{}'); path.chmod(0o600)
            return Mock(returncode=0, stdout=json.dumps(self.result).encode())
        self.run.side_effect = extra
        with self.assertRaisesRegex(ValueError, 'evidence changed'): install.deploy(COMMIT)
        self.assertEqual((self.state / 'extra.json').read_bytes(), b'{}')
        self.assertTrue((self.state / 'failure.json').exists()); self.assertFalse((self.state / 'result.json').exists())

    def test_same_byte_operator_intent_replacement_refuses_success(self):
        def replace(*args, **kwargs):
            path = self.state / 'intent.json'; raw = path.read_bytes()
            path.rename(path.with_suffix('.retained')); path.write_bytes(raw); path.chmod(0o600)
            return Mock(returncode=0, stdout=json.dumps(self.result).encode())
        self.run.side_effect = replace
        with self.assertRaisesRegex(ValueError, 'evidence changed'): install.deploy(COMMIT)
        self.assertTrue((self.state / 'failure.json').exists()); self.assertFalse((self.state / 'result.json').exists())


if __name__ == '__main__': unittest.main()
