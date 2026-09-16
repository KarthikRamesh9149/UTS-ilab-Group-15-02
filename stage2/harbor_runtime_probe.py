"""Deterministic real Harbor Docker fixture, not a benchmark task or agent."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import uuid

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths


async def main():
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime' / 'stage2'
    runtime.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix='harbor-fixture-', dir=runtime))
    paths = TrialPaths(trial_dir=trial)
    name = 'uts-isolation-' + uuid.uuid4().hex[:10]
    environment = DockerEnvironment(
        environment_dir=root / 'stage2' / 'fixtures', environment_name=name,
        session_id=name, trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image='node:24.19.0-bookworm-slim',cpus=4,memory_mb=8192),
        extra_docker_compose=[root / 'stage2' / 'fixtures' / 'docker-compose-isolation.yaml'])
    evidence = {'kind':'real_harbor_docker_fixture_not_scored', 'session':name,
                'time_utc':datetime.now(timezone.utc).isoformat(), 'checks':{}}
    try:
        await environment.start(force_build=False)
        result = await environment.exec("node -e 'const f=require(\"fs\");console.log(JSON.stringify({cpu:f.readFileSync(\"/sys/fs/cgroup/cpu.max\",\"utf8\").trim(),memory:f.readFileSync(\"/sys/fs/cgroup/memory.max\",\"utf8\").trim(),hostHome:f.existsSync(\"/Users/karthikramesh\"),socket:f.existsSync(\"/var/run/docker.sock\"),upstreamKey:!!process.env.OPENROUTER_API_KEY,interfaces:Object.keys(require(\"os\").networkInterfaces())}))'",timeout_sec=20)
        if result.return_code != 0:
            raise RuntimeError('Inspection command failed')
        observed = json.loads(result.stdout)
        evidence['observed'] = observed
        evidence['checks'].update(cpu_limit=observed['cpu']=='400000 100000',
            memory_limit=observed['memory']=='8589934592',
            host_home_hidden=not observed['hostHome'],docker_socket_hidden=not observed['socket'],
            upstream_key_absent=not observed['upstreamKey'],network_disabled=observed['interfaces']==['lo'])
        write = await environment.exec('printf UTS_FIXTURE > /tmp/uts-fixture.txt',timeout_sec=20)
        read = await environment.exec('cat /tmp/uts-fixture.txt',timeout_sec=20)
        evidence['checks']['file_persists'] = write.return_code == 0 and read.stdout == 'UTS_FIXTURE'
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    except Exception as exc:
        evidence.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1000])
    finally:
        await environment.stop(delete=True)
    with (root/'stage2'/'harbor_runtime_probe_result.json').open('x') as output:
        json.dump(evidence,output,indent=2)
        output.write('\n')
    print(json.dumps(evidence,indent=2))


if __name__ == '__main__':
    asyncio.run(main())
