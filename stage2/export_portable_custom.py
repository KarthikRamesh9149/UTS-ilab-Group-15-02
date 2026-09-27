"""Read-only block audit and private backup; never dispatches model calls.

The frozen execution source is unchanged. Only allowlisted metadata is public;
private trajectories travel in a separate, ignored, hash-verified archive.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tarfile

from progress_dashboard import REPO, ssh_command

REMOTE = '/opt/uts-capstone-custom-portable-20260926'
OUTPUT = REPO / 'stage2/results/custom-portable-20260926'
EXCLUDED = {'token', '.env', '.jwt_secret', 'id_ed25519', 'id_rsa', '__pycache__', '.DS_Store'}
CHECKS = ('exact_registered_coverage', 'qualification_source_runtime_binding',
          'original_results_unchanged', 'frozen_dataset_bytes', 'official_limits',
          'trace_identities_and_rewards', 'cleanup_and_revocation', 'service_exited',
          'no_owned_resources')
ROW_FIELDS = ('trial_id', 'task_id', 'harness', 'reward', 'status', 'started_utc', 'completed_utc',
              'agent_error_type', 'verifier_error_type', 'setup_seconds', 'agent_seconds',
              'verifier_seconds', 'official_agent_timeout_seconds', 'official_verifier_timeout_seconds',
              'official_cpus', 'official_memory_mb', 'model_requests', 'accepted_model_responses',
              'interrupted_requests', 'error_requests', 'other_unaccepted_requests',
              'http_429_requests', 'transport_error_requests', 'retry_records',
              'known_cost_usd', 'total_cost_usd', 'unknown_cost_requests',
              'known_input_tokens', 'input_tokens', 'known_output_tokens', 'output_tokens',
              'cleanup_complete', 'model_revoked', 'result_sha256')

COLLECT = r'''
from collections import Counter
from contextlib import ExitStack
from datetime import datetime,timezone
import csv,json,os,subprocess,sys
from pathlib import Path
root=Path('/opt/uts-capstone-custom-portable-20260926');rt=root/'.runtime/stage2'
os.chdir(root);sys.path.insert(0,str(root/'stage2'))
from portable_custom_study import qualified,audited,summary,sources
from portable_custom_policy import SETTINGS,POLICY,fingerprint,require_block
from run_portable_custom import lock_all
from credit_only_experiment import digest,cleanup_complete
from credit_only_accounting import call_records,summarise
from local_trace import validate
from qualify_oracle import frozen_dataset
from harbor.models.task.task import Task
with ExitStack() as stack:
 lock_all(stack,root)
 proof=qualified(root);block=require_block(rt,condition)
 complete,partial=audited(root)
 report=summary(root,condition)
 assert report['attempted']==20 and not partial
 service=subprocess.check_output(['systemctl','show',f'uts-stage2-custom-portable-{condition.lower()}-20260926.service',
  '--property=ActiveState','--property=SubState','--property=MainPID','--property=ExecMainStatus'],text=True,timeout=8)
 state=dict(line.split('=',1) for line in service.splitlines() if '=' in line)
 assert state['ActiveState']=='inactive' and state['MainPID']=='0' and state['ExecMainStatus']=='0'
 assert not subprocess.check_output(['docker','ps','-aq','--filter','name=uts-scored-'],text=True).strip()
 dataset=frozen_dataset(root);rows=[]
 for cell in block['cells']:
  name=cell['trial_id'];trial=rt/'scored-trials'/name;evidence=rt/'scored-attempts'/name
  result=complete[name];reward=((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
  assert reward is None or type(reward) in (int,float) and reward in (0,1)
  assert result['model_revoked'] is True and cleanup_complete(result)
  assert not result.get('trace_errors') and not result.get('cleanup_errors')
  assert result['gateway_image_id']==proof['gateway_image']
  assert result['task_image_id']==proof['image_compatibility']['images'][cell['task_id']]
  assert not (evidence/'provider-stop.json').exists()
  for command in (['ps','-aq'],['network','ls','-q'],['volume','ls','-q']):
   assert not subprocess.check_output(['docker',*command,'--filter','label=com.docker.compose.project='+result['project']],text=True).strip()
  events=[validate(json.loads(p.read_text())) for p in (trial/'traces').glob('*.json')]
  assert all(e['trial_id']==name and e['task_id']==cell['task_id'] and e['harness']==condition
   and e['protocol_sha256']==SETTINGS.fingerprint() for e in events)
  phases={k:[e for e in events if e['kind']==k] for k in ('trial','setup','agent','verifier','cleanup')}
  assert all(len(v)==1 for v in phases.values()) and phases['verifier'][0].get('reward')==reward
  cfg=Task(dataset/cell['task_id']).config
  lifecycle=json.loads((rt/'retry-lifecycle'/(name+'.json')).read_text())
  assert lifecycle['model_protocol_sha256']==SETTINGS.fingerprint()
  assert abs(lifecycle['deadline_utc']-phases['agent'][0]['started_ns']/1e9-cfg.agent.timeout_sec)<.1
  if result.get('agent_error_type')=='TimeoutError':assert result['phase_seconds']['agent']>=cfg.agent.timeout_sec-.1
  calls=call_records(evidence);billing=summarise(rt,name)
  statuses=Counter(str(json.loads(p.read_text()).get('http_status')) for p in evidence.glob('*.transport-error.json'))
  accepted=sum(c.get('accepted_for_agent') is True for c in calls)
  interrupted=sum(c.get('accepted_for_agent') is not True and c.get('status')=='interrupted' for c in calls)
  errors=sum(c.get('accepted_for_agent') is not True and c.get('status')=='error' for c in calls)
  row=dict(cell,reward=int(reward) if reward is not None else None,status=result['status'],
   started_utc=result['started_utc'],completed_utc=datetime.fromtimestamp(phases['trial'][0]['ended_ns']/1e9,timezone.utc).isoformat(),
   agent_error_type=result.get('agent_error_type') or '',verifier_error_type=result.get('verifier_error_type') or '',
   setup_seconds=result['phase_seconds']['setup'],agent_seconds=result['phase_seconds']['agent'],verifier_seconds=result['phase_seconds']['verifier'],
   official_agent_timeout_seconds=cfg.agent.timeout_sec,official_verifier_timeout_seconds=cfg.verifier.timeout_sec,
   official_cpus=cfg.environment.cpus,official_memory_mb=cfg.environment.memory_mb,
   model_requests=len(calls),accepted_model_responses=accepted,interrupted_requests=interrupted,error_requests=errors,
   other_unaccepted_requests=len(calls)-accepted-interrupted-errors,http_429_requests=statuses.get('429',0),
   transport_error_requests=sum(statuses.values()),retry_records=len(list(evidence.glob('*.retry.json'))),
   known_cost_usd=billing['known_charged_usd'],total_cost_usd=billing['charged_usd'],unknown_cost_requests=billing['unknown_cost_requests'],
   cleanup_complete=True,model_revoked=True,result_sha256=digest(trial/'result.json'))
  for key in ('input_tokens','output_tokens'):
   counts=[c[key] for c in calls if c[key] is not None]
   row['known_'+key]=sum(counts);row[key]=sum(counts) if len(counts)==len(calls) else None
  rows.append(row)
 baseline=Path('/opt/uts-capstone-corrected-20260923/.runtime/stage2/scored-trials')
 with (root/'stage2/results/baseline-corrected-20260923/trials.csv').open() as stream:
  old=list(csv.DictReader(stream))
 assert len(old)==178 and all(digest(baseline/r['trial_id']/'result.json')==r['result_sha256'] for r in old)
 stopped=json.loads((root/'stage2/results/custom-development-20260926/stopped.json').read_text())
 oldroot=Path('/opt/uts-capstone-custom-development-20260926/.runtime/stage2/scored-trials')
 assert len(stopped['rows'])==4 and all(digest(oldroot/r['trial_id']/'result.json')==r['result_sha256'] for r in stopped['rows'])
 assert sources(root)==proof['sources']
 assert all(digest(rt/'scored-trials'/r['trial_id']/'result.json')==r['result_sha256'] for r in rows)
 bindings={f'.runtime/stage2/portable-development-blocks/{condition}.json':digest(rt/f'portable-development-blocks/{condition}.json'),
  '.runtime/stage2/portable-qualification.json':digest(rt/'portable-qualification.json'),
  '.runtime/stage2/portable-credit-policy.json':digest(rt/'portable-credit-policy.json'),
  '.runtime/stage2/python-runtime.tar.gz':digest(rt/'python-runtime.tar.gz')}
 print(json.dumps(dict(condition=condition,registration=block,qualification_sha256=fingerprint(proof),
  sources=proof['sources'],bindings=bindings,service=state,model_protocol=SETTINGS.document(),policy=POLICY,
  rows=rows,collected_utc=datetime.now(timezone.utc).isoformat(),audit_checks=dict.fromkeys(checks,True)),allow_nan=False))
'''

BACKUP = r'''
import hashlib,json,sys,tarfile
from pathlib import Path
root=Path('/opt/uts-capstone-custom-portable-20260926');rt=root/'.runtime/stage2'
block=json.loads((rt/f'portable-development-blocks/{condition}.json').read_text())
proof=json.loads((rt/'portable-qualification.json').read_text())
names=['stage2/'+n for n in proof['sources']]
names+=['.runtime/stage2/'+n for n in ('portable-qualification.json','portable-credit-policy.json','python-runtime.tar.gz',f'portable-development-blocks/{condition}.json')]
for cell in block['cells']:
 name=cell['trial_id']
 names+=['.runtime/stage2/scored-trials/'+name,'.runtime/stage2/scored-attempts/'+name,'.runtime/stage2/retry-lifecycle/'+name+'.json']
stats={'files':0,'bytes':0,'excluded':0}
class Writer:
 def __init__(self):self.digest=hashlib.sha256()
 def write(self,data):self.digest.update(data);return sys.stdout.buffer.write(data)
 def flush(self):sys.stdout.buffer.flush()
def select(info):
 if any(p in excluded for p in Path(info.name).parts) or info.issym() or info.islnk() or not (info.isfile() or info.isdir()):
  stats['excluded']+=1;return None
 if info.isfile():stats['files']+=1;stats['bytes']+=info.size
 return info
writer=Writer()
with tarfile.open(fileobj=writer,mode='w|gz') as archive:
 for name in names:
  path=root/name
  if not path.exists() or path.is_symlink():raise ValueError('Unsafe backup target')
  archive.add(path,arcname=name,filter=select)
writer.flush()
print('UTS_BACKUP_RECEIPT '+json.dumps(dict(sha256=writer.digest.hexdigest(),**stats)),file=sys.stderr)
'''


def condition_name(value):
    if value not in ('C0', 'C1', 'C2'):
        raise ValueError('Registered development condition required')
    return value


def private_dir(condition):
    return REPO / ('.runtime/netcup/custom-portable-' + condition_name(condition).lower() + '-final-20260926')


def remote_command():
    command = ssh_command()
    command[1:1] = ['-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2']
    command[-2] = REMOTE + '/.venv/bin/python'
    return command


def program(source, condition):
    return ('condition=' + repr(condition_name(condition)) + '\nchecks=' + repr(CHECKS)
            + '\nexcluded=' + repr(EXCLUDED) + '\n' + source)


def validate_snapshot(data, registration=None):
    condition = condition_name(data['condition'])
    registration = registration or json.loads((OUTPUT / ('registration-' + condition.lower() + '.json')).read_text())
    block = data['registration']
    if any(block.get(k) != v for k, v in registration.items()
           if k not in ('kind', 'registration_sha256', 'registration_file_sha256')):
        raise ValueError('Registration differs from published binding')
    canonical = hashlib.sha256(json.dumps(block, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if canonical != registration['registration_sha256'] or data['qualification_sha256'] != block['qualification_sha256']:
        raise ValueError('Registration or qualification hash mismatch')
    for field, bound in (('model_protocol', 'model_protocol_sha256'), ('policy', 'policy_sha256')):
        value = hashlib.sha256(json.dumps(data[field], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if value != block[bound]:
            raise ValueError('Model or spending policy differs from registration')
    if data['bindings'].get(f'.runtime/stage2/portable-development-blocks/{condition}.json') != registration['registration_file_sha256']:
        raise ValueError('Registration file binding mismatch')
    proof = json.loads((OUTPUT / 'qualification.json').read_text())
    if data['sources'] != proof['sources'] or block['sources_sha256'] != proof['sources_sha256']:
        raise ValueError('Qualified execution source changed')
    if data['bindings'].get('.runtime/stage2/portable-qualification.json') != proof['qualification_file_sha256']:
        raise ValueError('Qualification file changed')
    if data['bindings'].get('.runtime/stage2/python-runtime.tar.gz') != block['python_runtime_sha256']:
        raise ValueError('Runtime archive changed')
    if data.get('service', {}).get('ActiveState') != 'inactive' or data['service'].get('MainPID') != '0' \
            or data['service'].get('ExecMainStatus') != '0':
        raise ValueError('Completed service evidence required')
    rows = data['rows']
    if len(rows) != 20 or [tuple(r.get(k) for k in ('trial_id', 'task_id', 'harness')) for r in rows] != [
            tuple(c[k] for k in ('trial_id', 'task_id', 'harness')) for c in block['cells']]:
        raise ValueError('Exactly the 20 registered cells in order required')
    for row in rows:
        if set(row) != set(ROW_FIELDS):
            raise ValueError('Unexpected or missing public metadata field')
        if row['reward'] is not None and (type(row['reward']) is not int or row['reward'] not in (0, 1)):
            raise ValueError('Invalid verifier reward')
        if row['cleanup_complete'] is not True or row['model_revoked'] is not True:
            raise ValueError('Cleanup or revocation unverified')
        for field in ('agent_error_type', 'verifier_error_type', 'status'):
            if not isinstance(row[field], str) or not re.fullmatch(r'[A-Za-z_0-9]*', row[field]):
                raise ValueError('Only error class names and status codes may be exported')
        if row['reward'] is not None and (row['status'] != 'verified' or row['verifier_error_type']):
            raise ValueError('Verifier score conflicts with recorded status')
        counts = ('model_requests', 'accepted_model_responses', 'interrupted_requests', 'error_requests',
                  'other_unaccepted_requests', 'unknown_cost_requests', 'http_429_requests',
                  'transport_error_requests', 'retry_records', 'known_input_tokens', 'known_output_tokens')
        if any(type(row[k]) is not int or row[k] < 0 for k in counts):
            raise ValueError('Invalid physical request or token count')
        if sum(row[k] for k in counts[1:5]) != row['model_requests'] or row['unknown_cost_requests'] > row['model_requests']:
            raise ValueError('Physical requests do not balance')
        known = Decimal(row['known_cost_usd'])
        if not known.is_finite() or known < 0 or row['total_cost_usd'] != (None if row['unknown_cost_requests'] else row['known_cost_usd']):
            raise ValueError('Incomplete or invalid cost presented as complete')
        for field in ('input_tokens', 'output_tokens'):
            if row[field] is not None and (type(row[field]) is not int or row[field] != row['known_' + field]):
                raise ValueError('Invalid complete token count')
        for field in ('setup_seconds', 'agent_seconds', 'verifier_seconds', 'official_agent_timeout_seconds',
                      'official_verifier_timeout_seconds', 'official_cpus', 'official_memory_mb'):
            if type(row[field]) not in (int, float) or not math.isfinite(row[field]) or row[field] < 0:
                raise ValueError('Invalid timing or resource metadata')
        if not re.fullmatch('[a-f0-9]{64}', row['result_sha256']):
            raise ValueError('Result hash required')
    if any(data.get('audit_checks', {}).get(k) is not True for k in CHECKS):
        raise ValueError('Incomplete evidence audit')


def aggregate(rows):
    known = str(sum((Decimal(r['known_cost_usd']) for r in rows), Decimal(0)))
    unknown = sum(r['unknown_cost_requests'] for r in rows)
    result = dict(attempted=len(rows), passed=sum(r['reward'] == 1 for r in rows),
        failed=sum(r['reward'] == 0 for r in rows), no_verifier_result=sum(r['reward'] is None for r in rows),
        passed_despite_agent_timeout=sum(r['reward'] == 1 and r['agent_error_type'] == 'TimeoutError' for r in rows),
        failed_agent_error_types=dict(Counter(r['agent_error_type'] or 'none' for r in rows if r['reward'] == 0)),
        known_cost_usd=known, total_cost_usd=None if unknown else known, unknown_cost_requests=unknown,
        independent_receipts_verified=False, full_benchmark_win_claimed=False)
    for key in ('model_requests', 'accepted_model_responses', 'interrupted_requests', 'error_requests',
                'http_429_requests', 'transport_error_requests', 'known_input_tokens', 'known_output_tokens', 'agent_seconds'):
        result[key] = sum(r[key] for r in rows)
    return result


def read_snapshot(condition):
    result = subprocess.run(remote_command(), input=program(COLLECT, condition), text=True,
                            capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Read-only audit failed: ' + result.stderr[-1600:])
    data = json.loads(result.stdout)
    validate_snapshot(data)
    folder = private_dir(condition)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (folder / 'snapshot.json').open('x') as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
    os.chmod(folder / 'snapshot.json', 0o600)
    return data


def expected_archive_hashes(data):
    return dict(data['bindings'], **{'stage2/' + k: v for k, v in data['sources'].items()},
        **{'.runtime/stage2/scored-trials/' + r['trial_id'] + '/result.json': r['result_sha256'] for r in data['rows']})


def verify_archive(path, data, receipt):
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['sha256']:
            raise ValueError('Archive differs from remote source stream')
    expected = expected_archive_hashes(data)
    seen, names, files = set(), set(), 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            parts = Path(member.name).parts
            if member.name.startswith('/') or '..' in parts or member.name in names or member.issym() or member.islnk() \
                    or not (member.isfile() or member.isdir()) or any(p in EXCLUDED for p in parts):
                raise ValueError('Unsafe, duplicate or credential-bearing archive member')
            names.add(member.name)
            if member.isfile():
                files += 1
            if member.name in expected:
                seen.add(member.name)
                if hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest() != expected[member.name]:
                    raise ValueError('Archived evidence binding changed')
    if seen != set(expected) or files != receipt['files']:
        raise ValueError('Incomplete private backup')
    return dict(receipt, compressed_bytes=path.stat().st_size, verified_result_files=len(data['rows']),
        verified_bound_files=len(seen), private_archive_not_published=True,
        restore_test='Bound results, source, registration, qualification and Python archive read and hash-verified; full runtime restore not exercised.')


def private_backup(data):
    validate_snapshot(data)
    folder = private_dir(data['condition']); path = folder / 'evidence.tar.gz'
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        result = subprocess.run(remote_command(), input=program(BACKUP, data['condition']).encode(),
                                stdout=stream, stderr=subprocess.PIPE, timeout=900)
    if result.returncode:
        # Transfer diagnostics contain only our own archive program's errors,
        # but stay private alongside any partial bytes, not in public reports.
        with (folder / 'backup-transfer-error.txt').open('xb') as handle:
            handle.write(result.stderr)
        os.chmod(folder / 'backup-transfer-error.txt', 0o600)
        raise RuntimeError('Backup transfer failed; partial evidence retained')
    receipts = [s.removeprefix('UTS_BACKUP_RECEIPT ') for s in result.stderr.decode().splitlines()
                if s.startswith('UTS_BACKUP_RECEIPT ')]
    if len(receipts) != 1:
        raise ValueError('Missing source-stream checksum')
    receipt = verify_archive(path, data, json.loads(receipts[0]))
    with (folder / 'backup.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    os.chmod(folder / 'backup.json', 0o600)
    return receipt


def export(data, backup):
    validate_snapshot(data)
    if backup.get('verified_result_files') != 20 or backup.get('verified_bound_files') != len(expected_archive_hashes(data)) \
            or backup.get('private_archive_not_published') is not True:
        raise ValueError('Verified complete private backup required')
    # Explicit output allowlist. No arbitrary remote fields flow to GitHub.
    summary = {k: data[k] for k in ('condition', 'collected_utc', 'service', 'bindings', 'audit_checks', 'model_protocol')}
    summary.update(intended=20, results=aggregate(data['rows']), private_backup=backup,
        baseline_comparison=dict(primary={'harness': 'terminus-2', 'passed': 14, 'intended': 20},
                                 secondary={'harness': 'openhands', 'passed': 10, 'intended': 20}),
        accounting_source='Response-reported usage cost, not independent provider receipt verification.',
        interpretation='Development result only. Same frozen 20 tasks; no replacement of the stopped 0.2 attempts or the original baseline scores. Final confirmation and custom89 remain unfinished.')
    folder = OUTPUT / data['condition'].lower()
    folder.mkdir(mode=0o755, exist_ok=False)
    with (folder / 'trials.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator='\n')
        writer.writeheader(); writer.writerows(data['rows'])
    with (folder / 'summary.json').open('x') as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('collect', 'backup', 'export'))
    parser.add_argument('--condition', choices=('C0', 'C1', 'C2'), required=True)
    args = parser.parse_args(); os.umask(0o077)
    if args.action == 'collect':
        print(json.dumps(aggregate(read_snapshot(args.condition)['rows']), indent=2))
    else:
        data = json.loads((private_dir(args.condition) / 'snapshot.json').read_text())
        if args.action == 'backup':
            print(json.dumps(private_backup(data), indent=2))
        else:
            receipt = json.loads((private_dir(args.condition) / 'backup.json').read_text())
            print(json.dumps(export(data, receipt)['results'], indent=2))
