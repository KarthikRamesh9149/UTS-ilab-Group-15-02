"""Read-only export and private backup of the completed corrected baselines.

Never imports the runner locally, dispatches a trial, calls a model/provider,
reconciles receipts, changes frozen sources or selects replacement outcomes.
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

PRIVATE = REPO / '.runtime/netcup/corrected-final-20260925'
OUTPUT = REPO / 'stage2/results/baseline-corrected-20260923'
REMOTE_ROOT = '/opt/uts-capstone-corrected-20260923'
HARNESS = ('terminus-2', 'openhands')

COLLECT = r'''
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
import hashlib,json,subprocess,sys,tomllib
from pathlib import Path
root=Path('/opt/uts-capstone-corrected-20260923'); rt=root/'.runtime/stage2'
sys.path.insert(0,str(root/'stage2'))
from retry_experiment import sources,cells,coverage,validate_qualification,digest,CLOSED_THIRD
from retry_policy import SETTINGS,require_policy
from credit_only_accounting import call_records
from local_trace import validate
from qualify_oracle import frozen_dataset
require_policy(rt)
proof=validate_qualification(root)
registration=rt/'corrected-matrix.json'; registered_digest=digest(registration)
reg=json.loads(registration.read_text()); manifest=json.loads((root/'stage2/input_manifest.json').read_text())
assert reg['cells']==cells(manifest['all_task_ids'])
assert reg['sources']==sources(root)
assert reg['model_protocol_sha256']==SETTINGS.fingerprint()
assert reg['provider_check_sha256']==digest(rt/'provider-check.json')
assert reg['gateway_image']==proof['gateway_image'] and reg['guard_image']==proof['guard_image']
assert digest(CLOSED_THIRD/'.runtime/stage2/credit-only-matrix.json')==reg['predecessor_registration_sha256']
assert len(reg['predecessor_results_sha256'])==178
assert all(digest(CLOSED_THIRD/'.runtime/stage2/scored-trials'/name/'result.json')==expected
           for name,expected in reg['predecessor_results_sha256'].items())
completed,partial=coverage(rt,reg['cells'])
assert len(completed)==178 and not partial
service=subprocess.check_output(['systemctl','show','uts-stage2-corrected-20260923.service',
 '--property=ActiveState','--property=SubState','--property=MainPID','--property=ExecMainStatus'],text=True)
state=dict(line.split('=',1) for line in service.splitlines() if '=' in line)
assert state['ActiveState']=='inactive' and state['MainPID']=='0' and state['ExecMainStatus']=='0'
assert not subprocess.check_output(['docker','ps','-q','--filter','name=uts-scored-'],text=True).strip()
dataset=frozen_dataset(root)
rows=[]
for cell in reg['cells']:
 name=cell['trial_id']; trial=rt/'scored-trials'/name; evidence=rt/'scored-attempts'/name
 result=completed[name]; reward=result.get('verifier_result',{}).get('rewards',{}).get('reward')
 assert type(reward) in (int,float) and reward in (0,1)
 assert result['model_protocol_sha256']==SETTINGS.fingerprint()
 assert result['model_revoked'] is True and result['status']=='verified'
 assert not result.get('verifier_error_type') and not result.get('trace_errors')
 assert result.get('gateway_image_id')==reg['gateway_image']
 assert not (evidence/'provider-stop.json').exists()
 events=[validate(json.loads(p.read_text())) for p in (trial/'traces').glob('*.json')]
 assert all(e['trial_id']==name and e['task_id']==cell['task_id'] and e['harness']==cell['harness']
            and e['protocol_sha256']==SETTINGS.fingerprint() for e in events)
 bykind={kind:[e for e in events if e['kind']==kind] for kind in ('trial','setup','agent','verifier','cleanup')}
 assert all(len(v)==1 for v in bykind.values())
 assert bykind['verifier'][0]['reward']==reward
 root_event=bykind['trial'][0]
 calls=call_records(evidence)
 known=[Decimal(r['cost_usd']) for r in calls if r['cost_usd'] is not None]
 unknown=len(calls)-len(known); cost=str(sum(known,Decimal(0)))
 statuses=Counter()
 for p in evidence.glob('*.transport-error.json'):
  statuses[str(json.loads(p.read_text()).get('http_status'))]+=1
 cfg=tomllib.loads((dataset/cell['task_id']/'task.toml').read_text())
 row=dict(trial_id=name,task_id=cell['task_id'],harness=cell['harness'],reward=int(reward),
  started_utc=result['started_utc'],completed_utc=datetime.fromtimestamp(root_event['ended_ns']/1e9,timezone.utc).isoformat(),
  agent_error_type=result.get('agent_error_type') or '',verifier_error_type=result.get('verifier_error_type') or '',
  setup_seconds=result['phase_seconds']['setup'],agent_seconds=result['phase_seconds']['agent'],
  verifier_seconds=result['phase_seconds']['verifier'],official_agent_timeout_seconds=cfg['agent']['timeout_sec'],
  model_requests=len(calls),accepted_model_responses=sum(c.get('accepted_for_agent') is True for c in calls),
  request_outcome_missing=sum(not (evidence/(c['prefix']+'.outcome.json')).exists() for c in calls),
  http_429_requests=statuses.get('429',0),transport_error_requests=sum(statuses.values()),
  retry_records=len(list(evidence.glob('*.retry.json'))),
  known_cost_usd=cost,total_cost_usd=cost if not unknown else None,unknown_cost_requests=unknown,
  cleanup_complete=True,model_revoked=True,result_sha256=digest(trial/'result.json'))
 for key in ('input_tokens','output_tokens'):
  counts=[c[key] for c in calls if c[key] is not None]
  row['known_'+key]=sum(counts)
  row[key]=sum(counts) if len(counts)==len(calls) else None
 if row['agent_error_type']=='TimeoutError':
  lifecycle=json.loads((rt/'retry-lifecycle'/(name+'.json')).read_text())
  assert abs(lifecycle['deadline_utc']-bykind['agent'][0]['started_ns']/1e9-cfg['agent']['timeout_sec'])<.1
  assert row['agent_seconds']>=cfg['agent']['timeout_sec']-.1
 rows.append(row)
assert digest(registration)==registered_digest and sources(root)==reg['sources']
assert all(digest(rt/'scored-trials'/r['trial_id']/'result.json')==r['result_sha256'] for r in rows)
print(json.dumps(dict(experiment=reg['experiment'],collected_utc=datetime.now(timezone.utc).isoformat(),
 rows=rows,model_protocol=SETTINGS.document(),service=state,
 registration_sha256=registered_digest,qualification_sha256=digest(rt/'corrected-qualification.json'),
 provider_check_sha256=digest(rt/'provider-check.json'),model_protocol_sha256=SETTINGS.fingerprint(),
 sources_sha256=reg['sources'],gateway_image=reg['gateway_image'],guard_image=reg['guard_image'],
 audit_checks=dict(exact_registered_coverage=True,qualification_binding=True,source_binding=True,
  provider_check_binding=True,predecessor_results_unchanged=True,frozen_dataset_bytes=True,
  task_timeouts_unchanged=True,trace_identities_and_rewards=True,cleanup_and_model_revocation=True,
  service_exited_successfully=True,no_active_trial_containers=True),
 development_ids=manifest['development_ids']),allow_nan=False))
'''

BACKUP = r'''
import hashlib,json,sys,tarfile
from pathlib import Path
root=Path('/opt/uts-capstone-corrected-20260923');rt=root/'.runtime/stage2'
proof=json.loads((rt/'corrected-qualification.json').read_text())
names=['stage2','.runtime/stage2/scored-trials','.runtime/stage2/scored-attempts',
 '.runtime/stage2/retry-lifecycle']
names += ['.runtime/stage2/'+n for n in ('corrected-matrix.json','corrected-qualification.json',
 'provider-check.json','model-protocol.json','corrected-policy.json','credit-only-policy.json',proof['evidence_folder'])]
excluded={'token','.env','.jwt_secret','id_ed25519','id_rsa','__pycache__','.DS_Store'}
stats={'files':0,'bytes':0,'excluded':0}
class HashedWriter:
 def __init__(self):self.digest=hashlib.sha256()
 def write(self,data):self.digest.update(data);return sys.stdout.buffer.write(data)
 def flush(self):sys.stdout.buffer.flush()
def select(info):
 p=Path(info.name)
 if any(x in excluded for x in p.parts) or info.issym() or info.islnk() or not (info.isfile() or info.isdir()):
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
    command=ssh_command()
    command[-2]=REMOTE_ROOT+'/.venv/bin/python'
    return command


def read_snapshot():
    result=subprocess.run(remote_command(),input=COLLECT,text=True,capture_output=True,timeout=60)
    if result.returncode:
        raise RuntimeError('Read-only audit failed: '+result.stderr[-1800:])
    data=json.loads(result.stdout)
    validate_snapshot(data)
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (PRIVATE/'snapshot.json').open('x') as stream:json.dump(data,stream,indent=2,allow_nan=False)
    os.chmod(PRIVATE/'snapshot.json',0o600)
    return data


def validate_snapshot(data, task_ids=None):
    if task_ids is None:
        task_ids=json.loads((REPO/'stage2/input_manifest.json').read_text())['all_task_ids']
    rows=data['rows']
    expected={(h,t) for h in HARNESS for t in task_ids}
    if len(task_ids)!=89 or len(expected)!=178 or len(rows)!=178:
        raise ValueError('Exactly 89 tasks and 178 outcomes required')
    if {(r['harness'],r['task_id']) for r in rows}!=expected or len({r['trial_id'] for r in rows})!=178:
        raise ValueError('Unexpected, duplicated or missing result cell')
    for row in rows:
        if type(row['reward']) is not int or row['reward'] not in (0,1):raise ValueError('Missing binary score')
        if row['cleanup_complete'] is not True or row['model_revoked'] is not True:raise ValueError('Incomplete cleanup')
        if row['verifier_error_type']:raise ValueError('Verifier failure cannot be counted as clean score')
        if row['unknown_cost_requests'] and row['total_cost_usd'] is not None:raise ValueError('Unknown cost concealed')
        if row['accepted_model_responses']>row['model_requests']:raise ValueError('Invalid response count')
    checks=data.get('audit_checks')
    if not checks or any(value is not True for value in checks.values()):raise ValueError('Failed evidence audit')
    launch=json.loads((OUTPUT/'launch.json').read_text())
    for key in ('registration_sha256','qualification_sha256','provider_check_sha256','model_protocol_sha256'):
        if data[key]!=launch['hashes'][key]:raise ValueError('Launch evidence binding mismatch')


def aggregate(rows):
    cost=sum((Decimal(r['known_cost_usd']) for r in rows),Decimal(0))
    unknown=sum(r['unknown_cost_requests'] for r in rows)
    result=dict(attempted=len(rows),passed=sum(r['reward'] for r in rows),
        failed=sum(r['reward']==0 for r in rows),no_verifier_result=0,
        known_cost_usd=str(cost),total_cost_usd=None if unknown else str(cost),unknown_cost_requests=unknown,
        agent_error_types=dict(Counter(r['agent_error_type'] or 'none' for r in rows)),
        failed_agent_error_types=dict(Counter(r['agent_error_type'] or 'none' for r in rows if r['reward']==0)),
        failed_timeouts_with_http_429=sum(r['reward']==0 and r['agent_error_type']=='TimeoutError'
                                        and r['http_429_requests']>0 for r in rows))
    for key in ('model_requests','accepted_model_responses','request_outcome_missing','http_429_requests',
                'transport_error_requests','retry_records','known_input_tokens','known_output_tokens'):
        result[key]=sum(r[key] for r in rows)
    for key in ('input_tokens','output_tokens'):
        result[key]=sum(r[key] for r in rows) if all(r[key] is not None for r in rows) else None
    result['mean_agent_seconds']=round(sum(r['agent_seconds'] for r in rows)/len(rows),3)
    return result


def private_backup(data):
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=PRIVATE/'evidence.tar.gz'
    with path.open('xb') as stream:
        os.chmod(path,0o600)
        process=subprocess.run(remote_command(),input=BACKUP.encode(),stdout=stream,stderr=subprocess.PIPE,timeout=900)
    if process.returncode:raise RuntimeError('Private backup transfer failed; retain partial file for inspection')
    receipts=[line.removeprefix('UTS_BACKUP_RECEIPT ') for line in process.stderr.decode().splitlines()
              if line.startswith('UTS_BACKUP_RECEIPT ')]
    if len(receipts)!=1:raise ValueError('Missing independent archive checksum')
    receipt=json.loads(receipts[0])
    with path.open('rb') as stream: checksum=hashlib.file_digest(stream,'sha256').hexdigest()
    if receipt['sha256']!=checksum:raise ValueError('Transferred archive differs from source stream')
    expected={'.runtime/stage2/scored-trials/'+r['trial_id']+'/result.json':r['result_sha256'] for r in data['rows']}
    seen=set(); files=0
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            parts=Path(member.name).parts
            if member.name.startswith('/') or '..' in parts or member.issym() or member.islnk():
                raise ValueError('Unsafe member in private evidence archive')
            if any(p in {'token','.env','.jwt_secret','id_ed25519','id_rsa','__pycache__'} for p in parts):
                raise ValueError('Credential/runtime cache included in backup')
            if member.isfile():files+=1
            if member.name in expected:
                if member.name in seen:raise ValueError('Duplicate result in backup')
                seen.add(member.name)
                if hashlib.sha256(archive.extractfile(member).read()).hexdigest()!=expected[member.name]:
                    raise ValueError('Archived result mismatch')
    if len(seen)!=178 or files!=receipt['files']:raise ValueError('Incomplete backup')
    receipt.update(compressed_bytes=path.stat().st_size,verified_result_files=178,
        restore_test='all result files read directly from archive and hashes matched; full runtime restore not exercised',
        private_archive_not_published=True)
    with (PRIVATE/'backup.json').open('x') as stream:json.dump(receipt,stream,indent=2)
    os.chmod(PRIVATE/'backup.json',0o600)
    return receipt


def export(data, backup):
    validate_snapshot(data)
    if backup.get('verified_result_files')!=178:raise ValueError('Verified private backup required')
    rows=sorted(data['rows'],key=lambda r:(r['task_id'],r['harness']))
    earliest=min(datetime.fromisoformat(r['started_utc']) for r in rows)
    latest=max(datetime.fromisoformat(r['completed_utc']) for r in rows)
    summary={k:v for k,v in data.items() if k not in {'rows','development_ids'}}
    summary.update(intended=178,completed=178,conditions={h:aggregate([r for r in rows if r['harness']==h]) for h in HARNESS},
        all_calls=aggregate(rows),first_trial_started_utc=earliest.isoformat(),last_trial_completed_utc=latest.isoformat(),
        elapsed_hours=round((latest-earliest).total_seconds()/3600,3),
        accounting_source='response_usage_cost; not independently receipt-reconciled',
        private_backup=backup,custom_evaluation_status='unfinished')
    with (OUTPUT/'trials.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    with (OUTPUT/'summary.json').open('x') as stream:json.dump(summary,stream,indent=2,allow_nan=False)
    # Explicit separate input for custom development: no held-out trial rows.
    dev=[r for r in rows if r['task_id'] in data['development_ids']]
    if len(dev)!=40:raise ValueError('Expected exactly 20 per-harness development rows')
    with (OUTPUT/'development-baselines.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(dev)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['collect','backup','export'])
    action=parser.parse_args().action
    if action=='collect':
        data=read_snapshot();print(json.dumps({'audit':'passed','rows':len(data['rows']),
            'conditions':{h:aggregate([r for r in data['rows'] if r['harness']==h]) for h in HARNESS}},indent=2))
    else:
        data=json.loads((PRIVATE/'snapshot.json').read_text())
        if action=='backup':print(json.dumps(private_backup(data),indent=2))
        else:
            value=export(data,json.loads((PRIVATE/'backup.json').read_text()))
            print(json.dumps({k:value[k] for k in ('intended','completed','conditions','elapsed_hours')},indent=2))
