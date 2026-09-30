"""Run source-bound fake checks and an actual Harbor/Docker synthetic lifecycle."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from langchain_core.messages import AIMessage
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from custom_python_runtime import PythonBundle
from custom_runner_tests import SequenceModel, completion
from gemini_laptop_agent import GeminiAgent
from gemini_laptop_policy import MODEL, atomic_json
from gemini_laptop_run import environment_for, audit, STUDY
from scored_gateway import durable_json
from trial_execution import execute_phases


class FakeGateway:
    url = 'http://127.0.0.1:9/v1'
    token = 'synthetic-only'
    active = False
    revoked = False
    def activate(self, *args): self.active = True
    async def revoke(self): self.active = False; self.revoked = True


async def fixture(root, private):
    prep = json.loads((private / 'preparation.json').read_text())
    task = Task(root / 'stage2/fixtures/lifecycle')
    task.config.environment.docker_image = subprocess.check_output(
        ['docker','image','inspect','uts-gemini-controller:20260930','--format','{{.Id}}'],text=True).strip()
    task.config.environment.memory_mb = 512
    paths = TrialPaths(private / ('qualification-trial-' + str(time.time_ns())))
    paths.trial_dir.mkdir(parents=True,exist_ok=False,mode=0o700)
    env = environment_for(task,paths,'uts-gemini-fixture-' + str(time.time_ns()))
    gateway = FakeGateway()
    bundle = PythonBundle(private / 'python-runtime.tar.gz',prep['python_bundle']['sha256'])
    agent = GeminiAgent(paths.agent_dir,gateway,bundle,task.config.agent.timeout_sec)
    model = SequenceModel(model_name=MODEL)
    model._sequence = [AIMessage(content='',tool_calls=[dict(name='execute',id='synthetic-command',args={
        'command': 'test ! -S /var/run/docker.sock && test ! -e /run/openrouter-key && printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result'})]),completion('Synthetic fixture complete')]
    agent.model = model
    try:
        await asyncio.wait_for(env.start(force_build=False),task.config.environment.build_timeout_sec)
        inspected = audit(env,task)
        result = await execute_phases(agent=agent,environment=env,task=task,paths=paths,
            revoke_model=gateway.revoke,setup_timeout_seconds=180)
        names = subprocess.check_output(['docker','ps','-aq','--filter',
            'label=com.docker.compose.project=' + env.session_id],text=True).strip()
        passed = (result['status']=='verified' and result['verifier_result']['rewards']['reward']==1
            and not result['cleanup_errors'] and not names and gateway.revoked and len(model._calls)==2)
        return dict(passed=passed,scope='synthetic_lifecycle_not_benchmark',paid_generations=0,
            model_calls=len(model._calls),resource_audit=inspected,model_revoked=gateway.revoked,
            task_container_removed=not bool(names),lifecycle_status=result['status'],
            agent_error_type=result.get('agent_error_type'),verifier_error_type=result.get('verifier_error_type'),
            cleanup_errors=result['cleanup_errors'])
    finally:
        await env.stop(delete=True)


def main():
    root = Path.cwd()
    os.umask(0o077)
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'test_gemini_laptop','custom_runner_tests','test_no_cutoff_custom_agent',
        'test_trial_execution','test_custom_python_runtime','test_local_study',
        'local_graph_callbacks_tests','test_paid_trace'])
    tested = unittest.TextTestRunner(verbosity=1).run(suite)
    private = root / '.runtime' / STUDY
    result = dict(scope='fake_model_and_synthetic_docker_qualification_not_benchmark',
        tests_run=tested.testsRun,tests_passed=tested.wasSuccessful(),paid_generations=0)
    if tested.wasSuccessful():
        result['docker_fixture'] = asyncio.run(fixture(root,private))
    result['passed'] = tested.wasSuccessful() and result.get('docker_fixture',{}).get('passed') is True
    result['source_hashes'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / 'stage2').glob('*.py') if not p.name.startswith('test_')}
    atomic_json(private / 'qualification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k != 'source_hashes'}),flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
