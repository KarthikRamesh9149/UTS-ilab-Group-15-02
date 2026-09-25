"""Audit/export the completed recovery diagnostic without running any trial.

Only outcome, timing and integrity metadata leave the server in the snapshot.
Raw evidence travels separately into a private, ignored archive. This module
is not part of the frozen execution source and cannot change its scores.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

from progress_dashboard import REPO, ssh_command

REMOTE_ROOT = '/opt/uts-capstone-timeout-diagnostic-20260925'
PRIVATE = REPO / '.runtime/netcup/timeout-diagnostic-final-20260925'
OUTPUT = REPO / 'stage2/results/timeout-diagnostic-20260925'
HARNESS = ('terminus-2', 'openhands')
EXPECTED = {'terminus-2': 11, 'openhands': 19}
HASH_KEYS = ('registration_sha256', 'qualification_sha256',
             'parent_registration_sha256', 'model_protocol_sha256')
CHECKS = ('exact_registered_coverage', 'qualification_and_source_bindings',
          'original_178_results_unchanged', 'frozen_dataset_bytes',
          'official_deadlines_unchanged', 'resource_audit_in_unchanged_runtime',
          'trace_identities_and_rewards', 'cleanup_and_model_revocation',
          'service_exited_successfully', 'no_remaining_trial_resources')
EXCLUDED = {'token', '.env', '.jwt_secret', 'id_ed25519', 'id_rsa',
            '__pycache__', '.DS_Store'}

COLLECT = r'''
from collections import Counter
from datetime import datetime,timezone
import json,subprocess,sys
from pathlib import Path
root=Path('/opt/uts-capstone-timeout-diagnostic-20260925');rt=root/'.runtime/stage2'
sys.path.insert(0,str(root/'stage2'))
from run_timeout_diagnostic import report,bindings
from timeout_diagnostic import EXPECTED
from retry_policy import SETTINGS,require_policy
from credit_only_experiment import digest,coverage,cleanup_complete
from credit_only_accounting import call_records
from local_trace import validate
from qualify_oracle import frozen_dataset
from harbor.models.task.task import Task
require_policy(rt)
payload=report(root)
reg_path=rt/'timeout-diagnostic-matrix.json';reg=json.loads(reg_path.read_text())
assert payload['summary']['completed']==30 and not payload['started_without_result']
assert Counter(c['harness'] for c in reg['cells'])==EXPECTED
assert len({(c['harness'],c['task_id']) for c in reg['cells']})==30
assert digest(rt/'timeout-diagnostic-qualification.json')==reg['qualification_sha256']
completed,partial=coverage(rt,reg['cells']);assert len(completed)==30 and not partial
service=subprocess.check_output(['systemctl','show','uts-stage2-timeout-diagnostic-20260925.service',
 '--property=ActiveState','--property=SubState','--property=MainPID','--property=ExecMainStatus'],text=True)
state=dict(line.split('=',1) for line in service.splitlines() if '=' in line)
assert state['ActiveState']=='inactive' and state['MainPID']=='0' and state['ExecMainStatus']=='0'
assert not subprocess.check_output(['docker','ps','-aq','--filter','name=uts-scored-'],text=True).strip()
dataset=frozen_dataset(root);rows=[]
for observed in payload['rows']:
 name=observed['trial_id'];trial=rt/'scored-trials'/name;evidence=rt/'scored-attempts'/name
 result=completed[name];reward=observed['reward']
 assert type(reward) in (int,float) and reward in (0,1)
 assert result['status']=='verified' and result['model_revoked'] is True and cleanup_complete(result)
 assert not result.get('verifier_error_type') and not result.get('trace_errors') and not result.get('cleanup_errors')
 assert result['model_protocol_sha256']==SETTINGS.fingerprint()
 assert result.get('gateway_image_id')==reg['gateway_image']
 assert not (evidence/'provider-stop.json').exists()
 for command in (['ps','-aq'],['network','ls','-q'],['volume','ls','-q']):
  assert not subprocess.check_output(['docker',*command,'--filter',
   'label=com.docker.compose.project='+result['project']],text=True).strip()
 events=[validate(json.loads(p.read_text())) for p in (trial/'traces').glob('*.json')]
 assert all(e['trial_id']==name and e['task_id']==observed['task_id'] and e['harness']==observed['harness']
  and e['protocol_sha256']==SETTINGS.fingerprint() for e in events)
 phases={k:[e for e in events if e['kind']==k] for k in ('trial','setup','agent','verifier','cleanup')}
 assert all(len(v)==1 for v in phases.values()) and phases['verifier'][0]['reward']==reward
 cfg=Task(dataset/observed['task_id']).config
 lifecycle=json.loads((rt/'retry-lifecycle'/(name+'.json')).read_text())
 assert lifecycle['model_protocol_sha256']==SETTINGS.fingerprint()
 assert abs(lifecycle['deadline_utc']-phases['agent'][0]['started_ns']/1e9-cfg.agent.timeout_sec)<.1
 if observed['agent_error_type']=='TimeoutError':
  assert result['phase_seconds']['agent']>=cfg.agent.timeout_sec-.1
 calls=call_records(evidence);accepted=[c for c in calls if c.get('accepted_for_agent') is True]
 unsettled=[c for c in calls if c.get('accepted_for_agent') is not True]
 interruptions=[c for c in unsettled if c.get('status')=='interrupted']
 errors=[c for c in unsettled if c.get('status')=='error']
 error_codes=Counter(str(c.get('error_code') or 'unrecorded') for c in unsettled)
 durations=[];end_offsets=[]
 for c in calls:
  timing_path=evidence/(c['prefix']+'.timing.json')
  if not timing_path.exists():continue
  timing=json.loads(timing_path.read_text())
  assert phases['trial'][0]['started_ns']<=timing['started_ns']<=timing['ended_ns']<=phases['trial'][0]['ended_ns']
  if c.get('accepted_for_agent') is True:durations.append(timing['seconds'])
  else:end_offsets.append(timing['ended_ns']/1e9-lifecycle['deadline_utc'])
 interrupted_last_call_at_deadline=bool(interruptions) and (
  len(unsettled)==len(interruptions)==1 and calls[-1]['prefix']==interruptions[0]['prefix']
  and observed['agent_error_type']=='TimeoutError' and len(end_offsets)==1
  and abs(end_offsets[0])<5)
 row={k:v for k,v in observed.items() if k not in {'phase_seconds','model_protocol_sha256'}}
 row.update(reward=int(reward),original_reward=0,original_agent_error_type='TimeoutError',
  started_utc=result['started_utc'],
  completed_utc=datetime.fromtimestamp(phases['trial'][0]['ended_ns']/1e9,timezone.utc).isoformat(),
  setup_seconds=result['phase_seconds']['setup'],agent_seconds=result['phase_seconds']['agent'],
  verifier_seconds=result['phase_seconds']['verifier'],
  official_agent_timeout_seconds=cfg.agent.timeout_sec,official_verifier_timeout_seconds=cfg.verifier.timeout_sec,
  official_cpus=cfg.environment.cpus,official_memory_mb=cfg.environment.memory_mb,
  accepted_model_responses=len(accepted),interrupted_model_requests=len(interruptions),
  error_outcome_requests=len(errors),other_unaccepted_requests=len(unsettled)-len(interruptions)-len(errors),
  unaccepted_error_codes=dict(error_codes),interrupted_last_call_at_deadline=interrupted_last_call_at_deadline,
  last_unaccepted_end_minus_deadline_seconds=end_offsets[-1] if end_offsets else None,
  accepted_request_timing_count=len(durations),accepted_request_seconds=sum(durations),
  max_accepted_request_seconds=max(durations) if durations else None,
  mean_accepted_request_seconds=sum(durations)/len(durations) if durations else None,
  cleanup_complete=True,model_revoked=True)
 for key in ('input_tokens','output_tokens'):
  counts=[c[key] for c in calls if c[key] is not None]
  row['known_'+key]=sum(counts);row[key]=sum(counts) if len(counts)==len(calls) else None
 rows.append(row)
assert digest(reg_path)==payload['registration_sha256'] and bindings(root)==reg['sources']
assert all(digest(rt/'scored-trials'/r['trial_id']/'result.json')==r['result_sha256'] for r in rows)
parent=Path('/opt/uts-capstone-corrected-20260923/.runtime/stage2')
assert len(reg['parent_results_sha256'])==178
assert all(digest(parent/'scored-trials'/n/'result.json')==v for n,v in reg['parent_results_sha256'].items())
print(json.dumps(dict(experiment=payload['experiment'],collected_utc=datetime.now(timezone.utc).isoformat(),
 rows=rows,model_protocol=SETTINGS.document(),policy=payload['policy'],service=state,
 registration_sha256=payload['registration_sha256'],qualification_sha256=reg['qualification_sha256'],
 parent_registration_sha256=reg['parent_registration_sha256'],model_protocol_sha256=SETTINGS.fingerprint(),
 sources_sha256=reg['sources'],gateway_image=reg['gateway_image'],guard_image=reg['guard_image'],
 frozen_summary=payload['summary'],
 audit_checks=dict(exact_registered_coverage=True,qualification_and_source_bindings=True,
  original_178_results_unchanged=True,frozen_dataset_bytes=True,official_deadlines_unchanged=True,
  resource_audit_in_unchanged_runtime=True,trace_identities_and_rewards=True,
  cleanup_and_model_revocation=True,service_exited_successfully=True,no_remaining_trial_resources=True),
 resource_evidence='Every trial passed the source-bound Docker CPU/memory inspection before agent execution; completed containers were removed.'),allow_nan=False))
'''

BACKUP = r'''
import hashlib,json,sys,tarfile
from pathlib import Path
root=Path('/opt/uts-capstone-timeout-diagnostic-20260925');rt=root/'.runtime/stage2'
proof=json.loads((rt/'corrected-qualification.json').read_text())
names=['stage2','.runtime/stage2/scored-trials','.runtime/stage2/scored-attempts',
 '.runtime/stage2/retry-lifecycle']
names+=['.runtime/stage2/'+n for n in ('timeout-diagnostic-matrix.json','timeout-diagnostic-qualification.json',
 'corrected-qualification.json','model-protocol.json','corrected-policy.json','credit-only-policy.json',proof['evidence_folder'])]
excluded={'token','.env','.jwt_secret','id_ed25519','id_rsa','__pycache__','.DS_Store'}
stats={'files':0,'bytes':0,'excluded':0}
class HashedWriter:
 def __init__(self):self.digest=hashlib.sha256()
 def write(self,data):self.digest.update(data);return sys.stdout.buffer.write(data)
 def flush(self):sys.stdout.buffer.flush()
def select(info):
 if any(x in excluded for x in Path(info.name).parts) or info.issym() or info.islnk() or not (info.isfile() or info.isdir()):
  stats['excluded']+=1;return None
 if info.isfile():stats['files']+=1;stats['bytes']+=info.size
 return info
writer=HashedWriter()
with tarfile.open(fileobj=writer,mode='w|gz') as archive:
 for name in names:
  path=root/name
  if not path.exists() or path.is_symlink():raise ValueError('Unsafe backup target')
  archive.add(path,arcname=name,filter=select)
writer.flush()
print('UTS_BACKUP_RECEIPT '+json.dumps(dict(sha256=writer.digest.hexdigest(),**stats)),file=sys.stderr)
'''


def remote_command():
    command = ssh_command()
    command[-2] = REMOTE_ROOT + '/.venv/bin/python'
    return command


def api_observation(row):
    """Do not turn incomplete calls at a deadline into invented provider errors."""
    if row['http_429_requests']:
        return 'recorded_http_429'
    if row['transport_error_requests']:
        return 'recorded_other_transport_error'
    if not row['model_requests']:
        return 'no_model_request'
    if row['no_recorded_api_errors']:
        return 'all_responses_accepted_no_recorded_api_error'
    if row['error_outcome_requests']:
        return 'request_error_origin_unestablished'
    if row['interrupted_last_call_at_deadline']:
        return 'last_request_interrupted_at_task_deadline'
    return 'incomplete_or_unaccepted_response'


def cohort():
    with (OUTPUT / 'cohort.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row['original_http_429_requests'] = int(row['original_http_429_requests'])
    return rows


def validate_snapshot(data, expected=None):
    expected = cohort() if expected is None else expected
    rows = data['rows']
    if len(rows) != 30 or Counter(r['harness'] for r in rows) != EXPECTED:
        raise ValueError('Exactly 30 outcomes, 11 Terminus and 19 OpenHands required')
    if len({(r['harness'], r['task_id']) for r in rows}) != 30 or len({r['trial_id'] for r in rows}) != 30:
        raise ValueError('Duplicate diagnostic identity')
    identity = {r['trial_id']: r for r in expected}
    if set(identity) != {r['trial_id'] for r in rows}:
        raise ValueError('Unexpected or missing registered diagnostic cell')
    for row in rows:
        if any(row.get(k) != v for k, v in identity[row['trial_id']].items()):
            raise ValueError('Registered cohort or parent result binding changed')
        if type(row['reward']) is not int or row['reward'] not in (0, 1):
            raise ValueError('Missing binary verifier score')
        if row['original_reward'] != 0 or row['original_agent_error_type'] != 'TimeoutError':
            raise ValueError('Original failure changed')
        if row['cleanup_complete'] is not True or row['model_revoked'] is not True or row['verifier_error_type']:
            raise ValueError('Incomplete cleanup or verifier')
        if row['unknown_cost_requests'] and row['total_cost_usd'] is not None:
            raise ValueError('Unknown costs concealed')
        counts = ('accepted_model_responses', 'interrupted_model_requests',
                  'error_outcome_requests', 'other_unaccepted_requests')
        if sum(row[k] for k in counts) != row['model_requests'] or any(row[k] < 0 for k in counts):
            raise ValueError('Invalid physical request accounting')
        strict = bool(row['model_requests']) and row['accepted_model_responses'] == row['model_requests'] \
            and not any(row[k] for k in ('transport_error_requests', 'retry_records', 'missing_call_outcomes'))
        if row['no_recorded_api_errors'] is not strict:
            raise ValueError('Strict API observation does not match requests')
    if any(data.get('audit_checks', {}).get(k) is not True for k in CHECKS):
        raise ValueError('Evidence audit incomplete')
    launch = json.loads((OUTPUT / 'launch.json').read_text())
    if any(data[k] != launch[k] for k in HASH_KEYS):
        raise ValueError('Launch evidence binding mismatch')


def aggregate(rows):
    known = str(sum((Decimal(r['known_cost_usd']) for r in rows), Decimal(0)))
    unknown = sum(r['unknown_cost_requests'] for r in rows)
    result = dict(attempted=len(rows), passed=sum(r['reward'] for r in rows),
        failed=sum(r['reward'] == 0 for r in rows), no_verifier_result=0,
        passed_all_responses_accepted=sum(r['reward'] == 1 and r['no_recorded_api_errors'] for r in rows),
        failed_all_responses_accepted=sum(r['reward'] == 0 and r['no_recorded_api_errors'] for r in rows),
        passed_despite_agent_timeout=sum(r['reward'] == 1 and r['agent_error_type'] == 'TimeoutError' for r in rows),
        failed_agent_error_types=dict(Counter(r['agent_error_type'] or 'none' for r in rows if r['reward'] == 0)),
        api_observations=dict(Counter(api_observation(r) for r in rows)),
        known_cost_usd=known, total_cost_usd=None if unknown else known, unknown_cost_requests=unknown,
        causal_additional_original_passes=None, original_scores_replaced=False)
    for key in ('model_requests', 'accepted_model_responses', 'interrupted_model_requests',
                'error_outcome_requests', 'http_429_requests', 'transport_error_requests',
                'retry_records', 'known_input_tokens', 'known_output_tokens'):
        result[key] = sum(r[key] for r in rows)
    for key in ('input_tokens', 'output_tokens'):
        result[key] = sum(r[key] for r in rows) if all(r[key] is not None for r in rows) else None
    return result


def read_snapshot():
    result = subprocess.run(remote_command(), input=COLLECT, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Read-only audit failed: ' + result.stderr[-1800:])
    data = json.loads(result.stdout)
    validate_snapshot(data)
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (PRIVATE / 'snapshot.json').open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
    os.chmod(PRIVATE / 'snapshot.json', 0o600)
    return data


def expected_archive_hashes(data):
    paths = {'.runtime/stage2/scored-trials/' + r['trial_id'] + '/result.json': r['result_sha256']
             for r in data['rows']}
    paths.update({'stage2/' + name: value for name, value in data['sources_sha256'].items()})
    paths.update({'.runtime/stage2/timeout-diagnostic-matrix.json': data['registration_sha256'],
                  '.runtime/stage2/timeout-diagnostic-qualification.json': data['qualification_sha256']})
    return paths


def verify_archive(path, data, receipt):
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['sha256']:
            raise ValueError('Archive differs from source stream')
    expected = expected_archive_hashes(data)
    seen = set()
    files = 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            parts = Path(member.name).parts
            if member.name.startswith('/') or '..' in parts or member.issym() or member.islnk() \
                    or not (member.isfile() or member.isdir()) or any(p in EXCLUDED for p in parts):
                raise ValueError('Unsafe or credential-bearing archive member')
            if member.isfile():
                files += 1
            if member.name in expected:
                if member.name in seen:
                    raise ValueError('Duplicate bound evidence member')
                seen.add(member.name)
                if hashlib.sha256(archive.extractfile(member).read()).hexdigest() != expected[member.name]:
                    raise ValueError('Archived result/source binding changed')
    if seen != set(expected) or files != receipt['files']:
        raise ValueError('Incomplete private backup')
    return dict(receipt, compressed_bytes=path.stat().st_size, verified_result_files=len(data['rows']),
        verified_bound_files=len(seen), private_archive_not_published=True,
        restore_test='All registered results, execution sources and diagnostic bindings read and hash-verified inside archive; full runtime restore not exercised.')


def private_backup(data):
    validate_snapshot(data)
    PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = PRIVATE / 'evidence.tar.gz'
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        process = subprocess.run(remote_command(), input=BACKUP.encode(), stdout=stream,
                                 stderr=subprocess.PIPE, timeout=900)
    if process.returncode:
        raise RuntimeError('Backup transfer failed; partial archive retained for inspection')
    receipts = [line.removeprefix('UTS_BACKUP_RECEIPT ') for line in process.stderr.decode().splitlines()
                if line.startswith('UTS_BACKUP_RECEIPT ')]
    if len(receipts) != 1:
        raise ValueError('Missing independent archive checksum')
    receipt = verify_archive(path, data, json.loads(receipts[0]))
    with (PRIVATE / 'backup.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    os.chmod(PRIVATE / 'backup.json', 0o600)
    return receipt


def export(data, backup):
    validate_snapshot(data)
    if backup.get('verified_result_files') != 30 or backup.get('private_archive_not_published') is not True:
        raise ValueError('Verified private backup required')
    rows = [dict(r, api_observation=api_observation(r)) for r in data['rows']]
    summary = {k: v for k, v in data.items() if k != 'rows'}
    earliest = min(datetime.fromisoformat(r['started_utc']) for r in rows)
    latest = max(datetime.fromisoformat(r['completed_utc']) for r in rows)
    summary.update(intended=30, completed=30, unique_tasks=25,
        conditions={h: aggregate([r for r in rows if r['harness'] == h]) for h in HARNESS},
        all_attempts=aggregate(rows), first_trial_started_utc=earliest.isoformat(),
        last_trial_completed_utc=latest.isoformat(), elapsed_hours=round((latest-earliest).total_seconds()/3600, 3),
        accounting_source='Response usage cost when present, not independently reconciled with provider billing.',
        private_backup=backup, original_baseline_passes={'terminus-2': 52, 'openhands': 44},
        original_baseline_tasks_per_harness=89, custom_evaluation_status='unfinished',
        interpretation='Observed recovery on fresh stochastic attempts; not a causal estimate or replacement score. Accepted calls can still be slow.',
        strict_api_definition='At least one request, every response accepted, no recorded transport errors or retry decisions, and no missing outcome records.',
        interrupted_definition='Last request interrupted within five seconds of the official deadline during an agent TimeoutError; not evidence of an independent provider failure.')
    with (OUTPUT / 'trials.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v, dict) else v for k, v in r.items()} for r in rows)
    with (OUTPUT / 'summary.json').open('x') as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['collect', 'backup', 'export'])
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'collect':
        data = read_snapshot()
        print(json.dumps({'audit': 'passed', 'rows': len(data['rows']), 'summary': aggregate(data['rows'])}, indent=2))
    else:
        data = json.loads((PRIVATE / 'snapshot.json').read_text())
        if args.action == 'backup':
            print(json.dumps(private_backup(data), indent=2))
        else:
            result = export(data, json.loads((PRIVATE / 'backup.json').read_text()))
            print(json.dumps({k: result[k] for k in ('intended', 'completed', 'conditions', 'elapsed_hours')}, indent=2))
