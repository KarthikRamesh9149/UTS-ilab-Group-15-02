"""Static environment inventory. Never opens instructions, solutions or tests."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib


def inventory(root):
    rows = []
    for config in sorted(Path(root).glob('*/task.toml')):
        data = tomllib.loads(config.read_text())
        env = data.get('environment', {})
        directory = config.parent / 'environment'
        files = sorted(p for p in directory.rglob('*') if p.is_file())
        compose = [p.name for p in files if 'compose' in p.name.lower()]
        rows.append({
            'task': config.parent.name,
            'image': env.get('docker_image'),
            'cpus': env.get('cpus'), 'memory_mb': env.get('memory_mb'),
            'storage_mb': env.get('storage_mb'), 'gpus': env.get('gpus', 0),
            'compose_files': compose,
            'environment_hashes': {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'qualification': 'not_runtime_qualified',
            'image_missing': not bool(env.get('docker_image')),
        })
    if len(rows) != 89:
        raise ValueError('Expected the frozen 89-task inventory')
    return {'status': 'static_only_no_execution_or_compatibility_claim',
            'count': len(rows),
            'missing_images': [r['task'] for r in rows if r['image_missing']],
            'compose_tasks': [r['task'] for r in rows if r['compose_files']],
            'max_declared_cpus': max(r['cpus'] or 0 for r in rows),
            'max_declared_memory_mb': max(r['memory_mb'] or 0 for r in rows),
            'tasks': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = inventory(args.dataset)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'tasks'}, indent=2))
