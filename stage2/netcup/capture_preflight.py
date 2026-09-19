"""Read-only deployment evidence; never reads credentials or calls a model."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'stage2'))
from host_environment import snapshot
from qualify_oracle import check_host, frozen_dataset
from scoring_admission import source_hashes


def inspect():
    dataset = frozen_dataset(ROOT)
    ssh_config = subprocess.check_output(['/usr/sbin/sshd', '-T'], text=True)
    ssh_keys = {'passwordauthentication', 'kbdinteractiveauthentication', 'permitrootlogin', 'pubkeyauthentication'}
    ssh = dict(line.split(maxsplit=1) for line in ssh_config.splitlines() if line.split()[0] in ssh_keys)
    if ssh != {'passwordauthentication': 'no', 'kbdinteractiveauthentication': 'no',
               'permitrootlogin': 'without-password', 'pubkeyauthentication': 'yes'}:
        raise ValueError('Unexpected SSH authentication settings')
    packages = ('harbor', 'litellm', 'openai', 'deepagents', 'langgraph', 'langchain', 'tokenizers')
    return {'kind': 'native_linux_preflight_not_benchmark_scores',
            'time_utc': datetime.now(timezone.utc).isoformat(),
            'host_environment': snapshot(), 'host_health': check_host(),
            'ssh_authentication': ssh, 'dataset_exact_file_hashes_verified': True,
            'dataset_task_count': len(list(dataset.glob('*/task.toml'))),
            'packages': {name: version(name) for name in packages},
            'dependency_lock_sha256': hashlib.sha256((ROOT / 'stage2/custom-requirements.lock').read_bytes()).hexdigest(),
            'source_hashes': source_hashes(ROOT), 'live_api_calls': 0}


if __name__ == '__main__':
    print(json.dumps(inspect(), indent=2))
