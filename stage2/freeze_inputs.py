"""Offline input inventory; never calls a model or reads solution/test contents."""
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / '.cache/datasets/terminal-bench-2-1'


def select_dev(task_ids):
    if len(task_ids) != 89 or len(set(task_ids)) != 89:
        raise ValueError('Expected 89 unique task IDs')
    return sorted(task_ids, key=lambda t: (
        hashlib.sha256(('uts-stage2-dev20-v1:42:' + t).encode()).hexdigest(), t
    ))[:20]


def build():
    configs = sorted(DATASET.glob('*/task.toml'))
    ids = [p.parent.name for p in configs]
    dev = select_dev(ids)
    pilot = set((ROOT / 'configs/progress_subset.txt').read_text().splitlines())
    records = []
    for path in configs:
        raw = path.read_bytes()
        env = tomllib.loads(raw.decode()).get('environment', {})
        records.append({
            'task_id': path.parent.name,
            'development': path.parent.name in dev,
            'pilot_exposed': path.parent.name in pilot,
            'task_config_sha256': hashlib.sha256(raw).hexdigest(),
            'docker_image': env.get('docker_image'),
            'cpus': env.get('cpus'), 'memory_mb': env.get('memory_mb'),
            'storage_mb': env.get('storage_mb'), 'gpus': env.get('gpus'),
            'compose_present': (path.parent / 'environment/docker-compose.yaml').exists(),
        })
    return {
        'status': 'input_inventory_only_not_scoring_ready',
        'dataset_revision_verification': 'pending',
        'selection': 'sha256(uts-stage2-dev20-v1:42: + task_id), then task_id',
        'development_ids': dev,
        'all_task_ids': ids,
        'outside_development_ids': [t for t in ids if t not in dev],
        'tasks': records,
    }


if __name__ == '__main__':
    out = ROOT / 'stage2/input_manifest.json'
    if out.exists():
        raise SystemExit('Refusing to overwrite frozen input inventory')
    data = build()
    out.write_text(json.dumps(data, indent=2) + '\n')
    print('Inventoried 89 tasks; selected 20 development tasks; 69 outside development.')
