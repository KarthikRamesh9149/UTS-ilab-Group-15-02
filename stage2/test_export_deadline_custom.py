"""Synthetic C3 reporting checks, with no SSH or provider calls."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import export_deadline_custom as export
from deadline_custom_policy import POLICY, SETTINGS, fingerprint
from test_deadline_custom_policy import fixture,parent_fixture


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        _,block,proof=fixture(self.root)
        sources={'fixture.py':'a'*64}
        block['sources_sha256']=fingerprint(sources)
        registration=dict(block,kind='public',registration_sha256=fingerprint(block),registration_file_sha256='d'*64)
        (self.root/'registration-c3.json').write_text(json.dumps(registration))
        (self.root/'qualification.json').write_text(json.dumps(dict(sources=sources,sources_sha256=fingerprint(sources),qualification_file_sha256='e'*64)))
        (self.root/'parent.json').write_text(json.dumps(dict(evidence=parent_fixture(),file_sha256='f'*64)))
        self.data=dict(condition='C3',registration=block,qualification_sha256=block['qualification_sha256'],
            sources=sources,model_protocol=SETTINGS.document(),policy=POLICY,
            service=dict(ActiveState='inactive',MainPID='0',ExecMainStatus='0'),
            audit_checks=dict.fromkeys(export.CHECKS,True),bindings={
                '.runtime/stage2/deadline-development-blocks/C3.json':'d'*64,
                '.runtime/stage2/deadline-qualification.json':'e'*64,
                '.runtime/stage2/deadline-parent-evidence.json':'f'*64,
                '.runtime/stage2/python-runtime.tar.gz':block['python_runtime_sha256']},rows=[])
        for cell in block['cells']:
            row=dict.fromkeys(export.ROW_FIELDS,0)
            row.update(cell,reward=0,status='verified',started_utc='2026-09-27T00:00:00Z',completed_utc='2026-09-27T00:01:00Z',
                agent_error_type='TimeoutError',verifier_error_type='',model_requests=2,accepted_model_responses=1,
                interrupted_requests=1,known_cost_usd='0.01',total_cost_usd=None,unknown_cost_requests=1,
                input_tokens=None,output_tokens=None,cleanup_complete=True,model_revoked=True,result_sha256='a'*64)
            self.data['rows'].append(row)
        self.patch=patch.object(export,'OUTPUT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def test_valid_zeros_unknown_cost_and_missing_verifier(self):
        export.validate_snapshot(self.data)
        self.data['rows'][0].update(reward=None,status='setup_failed')
        export.validate_snapshot(self.data)
        result=export.aggregate(self.data['rows'])
        self.assertEqual((result['failed'],result['no_verifier_result']),(19,1))
        self.assertIsNone(result['total_cost_usd']);self.assertFalse(result['full_benchmark_win_claimed'])

    def test_changed_coverage_lineage_and_evidence_rejected(self):
        for change in ('duplicate','order','drop','parent','binding','source','active','model'):
            data=deepcopy(self.data)
            if change=='duplicate':data['rows'][1]=data['rows'][0]
            elif change=='order':data['rows'].reverse()
            elif change=='drop':data['rows'].pop()
            elif change=='parent':data['registration']['parent']='C1'
            elif change=='binding':data['bindings']['.runtime/stage2/deadline-parent-evidence.json']='0'*64
            elif change=='source':data['sources']['fixture.py']='0'*64
            elif change=='active':data['service']['ActiveState']='active'
            else:data['model_protocol']['temperature']=0
            with self.subTest(change=change),self.assertRaises(ValueError):export.validate_snapshot(data)

    def test_private_text_false_costs_and_invalid_counts_rejected(self):
        for change in ({'messages':'private'},{'total_cost_usd':'0'},{'reward':True},
                       {'agent_error_type':'private message here'},{'accepted_model_responses':3},
                       {'cleanup_complete':False},{'agent_seconds':float('nan')},{'retry_records':-1}):
            data=deepcopy(self.data);data['rows'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):export.validate_snapshot(data)

    def test_remote_programs_compile_without_execution(self):
        for source in (export.COLLECT,export.BACKUP):compile(export.program(source,'C3'),'<synthetic>','exec')
        for bad in ('C0','../C3',"C3'; exit()"):
            with self.assertRaises(ValueError):export.condition_name(bad)

    def test_private_archive_bound_and_credentials_excluded(self):
        content=b'synthetic';sha=hashlib.sha256(content).hexdigest()
        data=dict(bindings={'parent.json':sha},sources={'fixture.py':sha},rows=[dict(trial_id='fixture',result_sha256=sha)])
        path=self.root/'archive.tar.gz'
        for extra in (None,'.env','../escape'):
            with tarfile.open(path,'w:gz') as archive:
                for name in [*export.expected_archive_hashes(data),*([extra] if extra else [])]:
                    member=tarfile.TarInfo(name);member.size=len(content);archive.addfile(member,io.BytesIO(content))
            receipt=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),files=3+bool(extra))
            if extra:
                with self.assertRaises(ValueError):export.verify_archive(path,data,receipt)
            else:self.assertEqual(export.verify_archive(path,data,receipt)['verified_bound_files'],3)


if __name__=='__main__':unittest.main()
