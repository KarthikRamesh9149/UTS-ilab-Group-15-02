"""Post-C3 schedules are metadata, never a permission to execute."""
import hashlib
from deadline_candidate_freeze import validate_document
from portable_custom_policy import fingerprint
from portable_evaluation_schedule import MANIFEST_SHA256


def schedule(document,manifest,phase):
    selected=validate_document(document)
    if fingerprint(manifest)!=MANIFEST_SHA256 or phase not in {'confirmation','diagnostic','final'}:
        raise ValueError('Frozen full manifest and explicit phase required')
    development=manifest['development_ids'];rows=[]
    lineage=(selected['selected'],selected['parent'],selected['base_parent'])
    def cell(index,task,role,variant):
        harness,parent,base_parent=variant
        return dict(trial_id=f'custom4-{phase}-{role}-{index:02d}-{task}',task_id=task,
            stage='final' if phase=='final' else 'development',phase=phase,role=role,
            harness=harness,parent=parent,base_parent=base_parent)
    if phase=='confirmation':
        roles=['terminus-2','openhands','custom']
        for i,task in enumerate(development,1):
            offset=(i-1)%3
            for role in roles[offset:]+roles[:offset]:
                rows.append(cell(i,task,role,lineage if role=='custom' else (role,None,None)))
    elif phase=='diagnostic':
        d=selected['diagnostic']
        rows=[cell(i,t,'custom',(d['condition'],d['parent'],None)) for i,t in enumerate(development,1)]
    else:
        outside=sorted(manifest['outside_development_ids'],key=lambda t:(
            hashlib.sha256(('uts-stage2-dev20-v1:42:'+t).encode()).hexdigest(),t))
        rows=[cell(i,t,'custom',lineage) for i,t in enumerate(development+outside,1)]
    return dict(kind='four_variant_schedule_not_admission',phase=phase,candidate_sha256=fingerprint(document),
        manifest_sha256=MANIFEST_SHA256,cells=rows,intended=len(rows),parallel_trials=1,
        attempts_per_registered_cell=1,automatic_task_replay=False,official_task_limits_unchanged=True,
        paid_launch_ready=False,primary_comparator='terminus-2',secondary_comparator='openhands')
