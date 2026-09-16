"""Offline post-run metrics and pinned-image inventory; no provider requests."""
import json
from pathlib import Path
import subprocess


def audit(root):
    from harbor.agents.installed.openhands import OpenHands
    from harbor.models.agent.context import AgentContext
    evidence = json.loads((root / 'stage2/openhands_agent_probe_v2.json').read_text())
    image = evidence['image_id']
    packages = json.loads(subprocess.check_output([
        'docker', 'run', '--rm', '--network=none', '--cap-drop=ALL',
        '--security-opt=no-new-privileges:true', '--memory=256m', '--cpus=1',
        image, '/opt/openhands-venv/bin/python', '-c',
        'import importlib.metadata as m,json; print(json.dumps(sorted('
        '[(d.metadata["Name"],d.version) for d in m.distributions()])))'], text=True))
    logs = root / evidence['trial_path'] / 'agent'
    agent = OpenHands(logs_dir=logs, model_name='openai/deepseek/deepseek-v4-flash-0731', version='0.62.0')
    context = AgentContext()
    agent.populate_context_post_run(context)
    trajectory = json.loads((logs / 'trajectory.json').read_text())
    result = {
        'kind': 'offline_audit_of_scripted_openhands_fixture_not_scored',
        'source_evidence': 'openhands_agent_probe_v2.json',
        'image_id': image, 'installed_packages': packages,
        'dependency_inventory_is_not_a_hashed_rebuild_lock': True,
        'native_trajectory_steps': len(trajectory['steps']),
        'native_context': context.model_dump(exclude={'rollout_details'}),
        'live_api_calls': 0,
        'limitations': ['Model replies and token usage were scripted.',
                       'Native cost estimates are not authoritative gateway billing.',
                       'No scored task or live OpenHands provider run is claimed.'],
    }
    with (root / 'stage2/openhands_fixture_audit.json').open('x') as handle:
        json.dump(result, handle, indent=2, default=str)
        handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'installed_packages'}, indent=2, default=str))


if __name__ == '__main__':
    audit(Path(__file__).resolve().parents[1])
