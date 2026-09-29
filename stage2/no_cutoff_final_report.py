"""Separate completed-final audit implementing the explicit phase amendment.

No CLI, dispatcher, backup writer or saved-proof entry is provided. The future
trusted launcher must bind this separate reporting bundle before importing it;
it must not install it into the frozen execution tree. Native invocation is
forbidden until the registered final service has completed successfully.
"""
from collections import Counter
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from types import SimpleNamespace

import no_cutoff_final_phase_audit as phase

ROOT = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
REPORTING = Path('/opt/uts-capstone-custom-no-cutoff-final-reporting-20260928')
SERVICE = 'uts-stage2-custom-no-cutoff-final-20260928.service'
KIND = 'completed_c0_nc_final89_phase_amendment_v1'
REPORTING_FILES = ('no_cutoff_final_report.py', 'test_no_cutoff_final_report.py',
    'no_cutoff_final_backup.py', 'test_no_cutoff_final_backup.py',
    'no_cutoff_final_backup_operator.py', 'test_no_cutoff_final_backup_operator.py',
    'no_cutoff_final_reporting.py', 'test_no_cutoff_final_reporting.py',
    'no_cutoff_final_archive.py', 'test_no_cutoff_final_archive.py',
    'no_cutoff_final_phase_audit.py', 'test_no_cutoff_final_phase_audit.py',
    'protocols/custom_final_phase_reporting_20260928.md')
INPUTS = {
    'no-cutoff-final-qualification.json': phase.QUALIFICATION_FILE,
    'no-cutoff-final-matrix.json': phase.REGISTRATION_FILE,
    'no-cutoff-final-runtime.json': phase.RUNTIME_FILE,
    'no-cutoff-final-candidate.json': 'd6d2125ad5df295aff2c098a1d2516a79e6584f78199fde56ba7cb8f3f94dd56',
    'no-cutoff-final-credit-policy.json': '14c6d05e0758283403283244653e719383c11f33bb534f40602383c2ccee079b',
    'no-cutoff-final-authentication.json': 'bafd72b8555217fdeb7f0fe40632ee02c4b3d8a1b6cecfefd0cf2798abb4aed3',
    'no-cutoff-final-manifest.json': 'e9a36d29245faf2353a6d219a95c0c8b838fec0dfda0ba624c4e7854e210bae7',
    'python-runtime.tar.gz': '7226bdfba69e2fda71033da1d47661b3fc5844e06c1361976d920cde7b64164e'}
BASELINE = Path('/opt/uts-capstone-corrected-20260923')
STOPPED = Path('/opt/uts-capstone-custom-development-20260926')
BASELINE_CSV = 'stage2/results/baseline-corrected-20260923/trials.csv'
STOPPED_JSON = 'stage2/results/custom-development-20260926/stopped.json'
HISTORICAL_INPUTS = {BASELINE_CSV: '8769a865d19bc81132166d67f85a5fb84725f2cda8f5b2a45f98b1d9993d5429',
    STOPPED_JSON: '0bb9379df382d22ee167f356dad1c84ff1075a54e2b4a538ba00797a0540234c'}
CHECKS = ('exact_registered_coverage', 'qualification_source_runtime_binding',
    'original_results_unchanged', 'frozen_dataset_bytes', 'official_limits',
    'trace_identities_and_rewards', 'cleanup_and_revocation', 'service_exited',
    'no_owned_resources', 'corroborated_phase_absence', 'supporting_bytes_reread',
    'actual_passive_accounting', 'separate_reporting_sources')
ROW_FIELDS = phase.ROW_FIELDS | {'started_utc', 'official_cpus', 'official_memory_mb',
    'accepted_model_responses', 'interrupted_requests', 'error_requests', 'other_unaccepted_requests',
    'http_429_requests', 'transport_error_requests', 'retry_records', 'known_cost_usd',
    'total_cost_usd', 'unknown_cost_requests', 'known_input_tokens', 'input_tokens',
    'known_output_tokens', 'output_tokens', 'cleanup_complete', 'model_revoked'}
ENVIRONMENT = dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    LANG='C.UTF-8', DOCKER_HOST='unix:///var/run/docker.sock', DOCKER_CONFIG='/dev/null',
    LITELLM_LOCAL_MODEL_COST_MAP='True')


def _context():
    if (sys.platform != 'linux' or os.getuid() != 0 or not sys.dont_write_bytecode or not sys.flags.isolated
            or threading.current_thread() is not threading.main_thread()
            or Path.cwd() != ROOT or Path(sys.prefix).resolve() != ROOT / '.venv'
            or Path(__file__).resolve() != REPORTING / 'stage2/no_cutoff_final_report.py'
            or Path(phase.__file__).resolve() != REPORTING / 'stage2/no_cutoff_final_phase_audit.py'
            or Path(phase.local_trace.__file__).resolve() != ROOT / 'stage2/local_trace.py'):
        raise ValueError('Use the separately bound reporter and original final native interpreter')
    if (dict(os.environ) != ENVIRONMENT or sys.pycache_prefix != str(REPORTING / '.absent-bytecode-cache')
            or (REPORTING / '.absent-bytecode-cache').exists()
            or (REPORTING / '.absent-bytecode-cache').is_symlink()):
        raise ValueError('Credential-free fixed environment and absent bytecode prefix required')
    for directory in (ROOT, REPORTING):
        phase._path(directory, 'stage2')


def _reporting_sources():
    files = {}
    for name in REPORTING_FILES:
        phase._file(REPORTING, 'stage2/' + name, files)
    return files


def _command(args):
    # Only fixed read-only systemctl/Docker calls use this helper. No provider
    # credential, user Docker config or remote daemon is forwarded.
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30, env=dict(ENVIRONMENT))
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Read-only native observation failed; no automatic retry') from None
    if result.returncode:
        raise ValueError('Read-only native observation failed; no automatic retry')
    return result.stdout


def _service():
    output = _command(['systemctl', 'show', SERVICE, '--property=ActiveState', '--property=SubState',
        '--property=MainPID', '--property=ExecMainStatus'])
    pairs = [line.split('=', 1) for line in output.splitlines() if '=' in line]
    state = phase._pairs(pairs)
    if state != dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0'):
        raise ValueError('Successful inactive final service required before any completed audit')
    return state


def _stops():
    for name in ('operator-stop-request.json', 'provider-stop.json'):
        if phase._path(ROOT, phase.RT + name).exists():
            raise ValueError('Persistent stop requires inspection, not completed reporting')


def _resources(project=None):
    if project is not None and (not isinstance(project, str) or not re.fullmatch(r'uts-scored-[a-f0-9]{12}', project)):
        raise ValueError('Exact retained owned project identity required')
    commands = (['ps', '-aq'],) if project is None else (['ps', '-aq'], ['network', 'ls', '-q'], ['volume', 'ls', '-q'])
    selector = 'name=uts-scored-' if project is None else 'label=com.docker.compose.project=' + project
    for command in commands:
        if _command(['docker', *command, '--filter', selector]).strip():
            raise ValueError('Owned native resources remain; no deletion or replay is permitted')


def _anchors():
    files = {}
    for name, sha in INPUTS.items():
        phase._file(ROOT, phase.RT + name, files, expected=sha)
    proof = phase._file(ROOT, phase.RT + 'no-cutoff-final-qualification.json', files, parse=True)
    block = phase._file(ROOT, phase.RT + 'no-cutoff-final-matrix.json', files, parse=True)
    host = phase._file(ROOT, phase.RT + 'no-cutoff-final-runtime.json', files, parse=True)
    if (phase.fingerprint(proof) != phase.QUALIFICATION or phase.fingerprint(block) != phase.REGISTRATION
            or proof['sources_sha256'] != phase.SOURCE_SET or phase.fingerprint(proof['sources']) != phase.SOURCE_SET
            or phase.fingerprint(host) != proof['runtime_identity_sha256']
            or block['qualification_sha256'] != phase.QUALIFICATION or block['sources_sha256'] != phase.SOURCE_SET
            or proof['setup_timeout_seconds'] != 900):
        raise ValueError('Exact frozen final source, inputs and registration required')
    if any(proof['sources'].get(name) != sha for name, sha in phase.FROZEN_HELPERS.items()):
        raise ValueError('Frozen collector and execution helpers must remain unchanged')
    for name, sha in proof['sources'].items():
        phase._file(ROOT, 'stage2/' + name, files, expected=sha)
    if len(proof['evidence_files']) != 8:
        raise ValueError('All eight actual final qualification producers required')
    for name, sha in proof['evidence_files'].items():
        phase._file(ROOT, name, files, expected=sha)
    return proof, block, host, files


def _native():
    # Fixed imports only, after service/stop/source preflight. These are the
    # original deployed readers, not callbacks or replacement admission code.
    import no_cutoff_final_study as study
    import no_cutoff_final_runtime as runtime
    import no_cutoff_final_policy as policy
    import no_cutoff_final_evidence as original
    import run_no_cutoff_final as runner
    import credit_only_accounting as accounting
    from qualify_oracle import frozen_dataset
    from harbor.models.task.task import Task
    return SimpleNamespace(study=study, runtime=runtime, policy=policy, original=original,
        runner=runner, accounting=accounting, frozen_dataset=frozen_dataset, Task=Task)


def _coverage(native, block):
    cells = block['cells']
    if (len(cells) != 89 or len({c['trial_id'] for c in cells}) != 89
            or len({c['task_id'] for c in cells}) != 89 or any(c['harness'] != 'C0-NC' for c in cells)):
        raise ValueError('Exactly the registered 89 distinct final cells required')
    complete, partial = native.study.audited(ROOT)
    if partial or set(complete) != {c['trial_id'] for c in cells}:
        raise ValueError('Exact completed89 coverage required; partial attempts cannot be replayed')
    return complete


def _preserved(files):
    """Actual historical result hashes, never their private contents."""
    phase._file(ROOT, BASELINE_CSV, files, expected=HISTORICAL_INPUTS[BASELINE_CSV])
    old = list(csv.DictReader(io.StringIO((ROOT / BASELINE_CSV).read_text())))
    stopped = phase._file(ROOT, STOPPED_JSON, files, parse=True, expected=HISTORICAL_INPUTS[STOPPED_JSON])['rows']
    result = {}
    for base, rows, count in ((BASELINE, old, 178), (STOPPED, stopped, 4)):
        if len(rows) != count or len({r['trial_id'] for r in rows}) != count:
            raise ValueError('Every original178 and stopped-four outcome must be retained')
        saved = {}
        for row in rows:
            name = phase.RT + 'scored-trials/' + row['trial_id'] + '/result.json'
            phase._file(base, name, saved, expected=row['result_sha256'])
        result[str(base)] = saved
    return result


def _merge(target, values):
    for key, value in values.items():
        if key in target and target[key] != value:
            raise ValueError('Overlapping actual producer bindings disagree')
        target[key] = value


def _utc(value):
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('Actual UTC lifecycle timestamp required') from None
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError('Actual UTC lifecycle timestamp required')


def _row(native, evidence, result, cfg, host):
    row = dict(evidence['row']); name = row['trial_id']
    limits = host['task_inventory'][row['task_id']]
    values = dict(agent_timeout_seconds=cfg.agent.timeout_sec, verifier_timeout_seconds=cfg.verifier.timeout_sec,
        cpus=cfg.environment.cpus, memory_mb=cfg.environment.memory_mb)
    for key, value in values.items():
        phase._number(value, positive=True)
        if phase.fingerprint(limits.get(key)) != phase.fingerprint(value):
            raise ValueError('Actual official task configuration differs from qualified limits')
    folder = ROOT / phase.RT / 'scored-attempts' / name
    # Validate metadata JSON before the unchanged accounting reader uses it;
    # raw requests and responses remain hash-only, never parsed or returned.
    statuses = Counter()
    for filename in evidence['file_sha256']:
        if filename.startswith(phase.RT + 'scored-attempts/' + name + '/') and filename.endswith(
                ('.outcome.json', '.transport-error.json', '.retry.json')):
            item = phase._file(ROOT, filename, {}, parse=True, expected=evidence['file_sha256'][filename])
            if filename.endswith('.transport-error.json'):
                statuses[str(item.get('http_status'))] += 1
    calls = native.accounting.call_records(folder)
    billing = native.accounting.summarise(ROOT / phase.RT, name)
    if (phase.fingerprint(billing) != phase.fingerprint(result.get('billing'))
            or len(calls) != row['model_requests'] or billing.get('provider_stop') is not None):
        raise ValueError('Retained passive accounting differs from actual request outcomes')
    accepted = sum(c.get('accepted_for_agent') is True for c in calls)
    interrupted = sum(c.get('accepted_for_agent') is not True and c.get('status') == 'interrupted' for c in calls)
    errors = sum(c.get('accepted_for_agent') is not True and c.get('status') == 'error' for c in calls)
    row.update(started_utc=result['started_utc'], official_cpus=values['cpus'], official_memory_mb=values['memory_mb'],
        accepted_model_responses=accepted, interrupted_requests=interrupted, error_requests=errors,
        other_unaccepted_requests=len(calls) - accepted - interrupted - errors,
        http_429_requests=statuses.get('429', 0), transport_error_requests=sum(statuses.values()),
        retry_records=len(list(folder.glob('*.retry.json'))), known_cost_usd=billing['known_charged_usd'],
        total_cost_usd=billing['charged_usd'], unknown_cost_requests=billing['unknown_cost_requests'],
        cleanup_complete=True, model_revoked=True)
    for key in ('input_tokens', 'output_tokens'):
        counts = [c[key] for c in calls if c[key] is not None]
        row['known_' + key] = sum(counts)
        row[key] = sum(counts) if len(counts) == len(calls) else None
    if set(row) != ROW_FIELDS:
        raise ValueError('Only explicit amended row metadata is permitted')
    _utc(row['started_utc']); _utc(row['completed_utc'])
    return row


def aggregate(rows):
    """Metadata arithmetic only, never a completed-audit or backup witness."""
    known = str(sum((Decimal(r['known_cost_usd']) for r in rows), Decimal(0)))
    unknown = sum(r['unknown_cost_requests'] for r in rows)
    result = dict(attempted=len(rows), passed=sum(r['reward'] == 1 for r in rows),
        failed=sum(r['reward'] == 0 for r in rows), no_verifier_result=sum(r['reward'] is None for r in rows),
        known_cost_usd=known, total_cost_usd=None if unknown else known, unknown_cost_requests=unknown,
        independent_receipts_verified=False, full_benchmark_win_claimed=False, phase_durations={})
    for key in ('model_requests', 'accepted_model_responses', 'interrupted_requests', 'error_requests',
            'other_unaccepted_requests', 'http_429_requests', 'transport_error_requests', 'retry_records',
            'known_input_tokens', 'known_output_tokens', 'generation_timings', 'missing_generation_timings'):
        result[key] = sum(r[key] for r in rows)
    for kind in phase.PHASES:
        measured = [r[kind + '_seconds'] for r in rows if r['phase_observation'][kind] == 'measured']
        not_run = [r for r in rows if r['phase_observation'][kind] == 'not_run_setup_failed']
        if (len(measured) + len(not_run) != len(rows)
                or any(r[kind + '_seconds'] is not None for r in not_run)):
            raise ValueError('Every duration needs its actual measured or proven not-run category')
        for value in measured:
            phase._number(value)
        result['phase_durations'][kind] = dict(measured_attempts=len(measured),
            not_run_attempts=len(not_run), measured_subtotal_seconds=sum(measured),
            all_attempts_measured=not not_run)
    return result


def collect():
    """Actual fixed-root completed audit. Never call on an active/unknown final."""
    _context(); state = _service(); _stops()
    reporting = _reporting_sources()
    proof, block, host, files = _anchors()
    native = _native()
    native.runtime.loaded_sources(ROOT, proof['sources'])
    # authenticate takes its own ancestor locks. Never move it inside lock_all.
    document = native.study.read_candidate(ROOT)
    authenticated = native.original.authenticate(ROOT, document)
    with ExitStack() as stack:
        native.runner.lock_all(stack, ROOT)
        _service(); _stops(); _resources()
        if _anchors() != (proof, block, host, files):
            raise ValueError('Frozen final inputs changed across authentication')
        native.original.recheck(ROOT, document, authenticated)
        if (phase.fingerprint(native.study.qualified(ROOT)) != phase.fingerprint(proof)
                or phase.fingerprint(native.policy.require_block(ROOT / phase.RT)) != phase.fingerprint(block)):
            raise ValueError('Actual qualified runtime and registration differ from bound inputs')
        complete = _coverage(native, block)
        dataset = native.frozen_dataset(ROOT)
        preserved = _preserved(files)
        rows = []; reports = []; directories = {}; absent = set()
        for cell in block['cells']:
            evidence = phase.read_phase_evidence(ROOT, cell['trial_id'])
            result_name = phase.RT + 'scored-trials/' + cell['trial_id'] + '/result.json'
            result = phase._file(ROOT, result_name, {}, parse=True, expected=evidence['file_sha256'][result_name])
            if phase.fingerprint(result) != phase.fingerprint(complete[cell['trial_id']]):
                raise ValueError('Retained result changed during completed audit')
            _resources(result['project'])
            rows.append(_row(native, evidence, result, native.Task(dataset / cell['task_id']).config, host))
            reports.append(evidence)
            _merge(files, evidence['file_sha256']); _merge(directories, evidence['directory_entries'])
            absent.update(evidence['absent_paths'])
        if phase.fingerprint(_coverage(native, block)) != phase.fingerprint(complete):
            raise ValueError('Completed coverage changed during reporting')
        # Repeat the real runtime/image/producer reader, not a saved success flag.
        if phase.fingerprint(native.study.qualified(ROOT)) != phase.fingerprint(proof):
            raise ValueError('Qualified native runtime changed during reporting')
        native.original.recheck(ROOT, document, authenticated)
        _stops(); _resources()
        for result in complete.values():
            _resources(result['project'])
        if _service() != state:
            raise ValueError('Final service state changed during audit')
        if phase.fingerprint(_coverage(native, block)) != phase.fingerprint(complete):
            raise ValueError('Completed coverage changed at the final read boundary')
        if native.runtime.sources(ROOT, document) != proof['sources'] or _preserved(files) != preserved:
            raise ValueError('Execution sources or historical outcomes changed during reporting')
        # Reread after the final native observations too. No saved leaf report
        # or successful earlier phase classification can replace these reads.
        for report in reports:
            phase.recheck(ROOT, report)
        for name, sha in files.items():
            phase._file(ROOT, name, {}, expected=sha)
        if reporting != _reporting_sources():
            raise ValueError('Separate reporting bundle changed during audit')
        native.runtime.loaded_sources(ROOT, proof['sources']); _stops()
        return dict(kind=KIND, condition='C0-NC', registration=block,
            qualification_sha256=phase.QUALIFICATION, sources=proof['sources'],
            bindings={n: files[n] for n in files if n in proof['evidence_files'] or n in {phase.RT + k for k in INPUTS}},
            supporting_file_sha256=files, absent_paths=sorted(absent), directory_entries=directories,
            reporting_source_files=reporting, amendment=phase.contract(),
            amendment_sha256=phase.fingerprint(phase.contract()), preserved_result_files=preserved,
            service=state, model_protocol=native.policy.SETTINGS.document(), policy=native.policy.POLICY,
            rows=rows, aggregates=dict(full89=aggregate(rows), development20=aggregate(rows[:20]),
                remaining69=aggregate(rows[20:])),
            collected_utc=datetime.now(timezone.utc).isoformat(), audit_checks=dict.fromkeys(CHECKS, True),
            completed_final_audit=True, paid_launch_ready=False, off_server_backup_verified=False,
            archive_export_and_handoff_integrated=False)
