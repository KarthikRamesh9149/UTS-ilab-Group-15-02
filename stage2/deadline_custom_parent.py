"""Read-only parent evidence from the unchanged 0.3 deployment, not its answers."""
import json
from pathlib import Path
import subprocess

from deadline_custom_policy import parent_selection, PARENT_FILE, fingerprint
from portable_final_selection import select
from retry_runtime import private_read
from scored_gateway import durable_json

PREVIOUS=Path('/opt/uts-capstone-custom-portable-20260926')
READ_PARENT=r'''
import json,os,subprocess,sys
from pathlib import Path
root=Path('/opt/uts-capstone-custom-portable-20260926');os.chdir(root)
sys.path.insert(0,str(root/'stage2'));rt=root/'.runtime/stage2'
from portable_custom_study import qualified,audited,summary,sources
from portable_custom_policy import require_block,fingerprint
from credit_only_experiment import digest,cleanup_complete
proof=qualified(root);complete,partial=audited(root)
assert not partial and len(complete)==60
assert all(cleanup_complete(r) and r.get('model_revoked') is True for r in complete.values())
assert not subprocess.check_output(['docker','ps','-aq','--filter','name=uts-scored-'],text=True).strip()
registrations={}
for condition in ('C0','C1','C2'):
 state=subprocess.check_output(['systemctl','show',f'uts-stage2-custom-portable-{condition.lower()}-20260926.service','--property=ActiveState','--property=MainPID','--property=ExecMainStatus'],text=True)
 state=dict(line.split('=',1) for line in state.splitlines() if '=' in line)
 assert state==dict(MainPID='0',ExecMainStatus='0',ActiveState='inactive')
 block=require_block(rt,condition)
 registrations[condition]=dict(canonical_sha256=fingerprint(block),file_sha256=digest(rt/f'portable-development-blocks/{condition}.json'))
assert sources(root)==proof['sources']
summaries={c:summary(root,c) for c in ('C0','C1','C2')}
print(json.dumps(dict(kind='audited_portable_parent_for_c3',summaries=summaries,
 results_sha256={n:digest(rt/'scored-trials'/n/'result.json') for n in complete},
 qualification_sha256=fingerprint(proof),qualification_file_sha256=digest(rt/'portable-qualification.json'),
 sources=proof['sources'],sources_sha256=proof['sources_sha256'],dependencies=proof['dependencies'],
 registration_bindings=registrations)))
'''


def collect_parent():
    # Use the predecessor's own interpreter/imports to revalidate its frozen
    # bytes. New candidate code must not reinterpret historical admission.
    result=subprocess.run([str(PREVIOUS/'.venv/bin/python'),'-B','-c',READ_PARENT],
        text=True,capture_output=True,timeout=90)
    if result.returncode:
        raise ValueError('Predecessor source/result/service audit failed; retained evidence needs inspection')
    value=json.loads(result.stdout)
    value['selection']=select(value['summaries'])
    parent_selection(value)
    return value


def bind_parent(runtime):
    value=collect_parent();path=Path(runtime)/PARENT_FILE
    if path.exists() or path.is_symlink():
        if fingerprint(private_read(path))!=fingerprint(value):
            raise ValueError('Immutable C3 parent evidence changed')
    else:
        durable_json(path,value)
    return value


def verify_parent(runtime):
    value=private_read(Path(runtime)/PARENT_FILE)
    parent_selection(value)
    if fingerprint(collect_parent())!=fingerprint(value):
        raise ValueError('Original C0/C1/C2 source or result bindings changed')
    return value
