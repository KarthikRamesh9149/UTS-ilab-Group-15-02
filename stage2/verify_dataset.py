"""Verify canonical dataset bytes without displaying task/solution/test text."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import Request, urlopen

REVISION = '7131e4375048a0e408a8fb404b5f499d726b695b'
REPOSITORY = 'harbor-framework/terminal-bench-2-1'
PREFIX = 'terminal-bench-2-1-' + REVISION


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def compare(directory, tree, task_ids):
    if tree.get('truncated'):
        raise ValueError('Incomplete official tree')
    expected = {row['path'][6:]: row for row in tree['tree']
                if row['type'] == 'blob' and row['path'].startswith('tasks/')
                and (row['path'].split('/')[1] in task_ids
                     or row['path'] in {'tasks/README.md', 'tasks/dataset.toml'})}
    local = {str(path.relative_to(directory)): path for path in directory.rglob('*') if path.is_file() or path.is_symlink()}
    differences, hashes = [], []
    for name, row in sorted(expected.items()):
        path = local.get(name)
        if path is None:
            differences.append({'path': name, 'reason': 'missing'})
        elif path.is_symlink() or row['mode'] not in {'100644', '100755'}:
            differences.append({'path': name, 'reason': 'unsupported_file_type'})
        else:
            raw = path.read_bytes()
            digest = git_blob(raw)
            hashes.append({'path': name, 'git_blob': digest,
                           'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
            if digest != row['sha']:
                differences.append({'path': name, 'reason': 'modified'})
    differences.extend({'path': name, 'reason': 'extra'} for name in sorted(set(local) - set(expected)))
    return {'expected_files': len(expected), 'local_files': len(local),
            'differences': differences, 'file_hashes': hashes}


def main(root):
    output = root / 'stage2' / 'dataset_provenance.json'
    if output.exists():
        raise ValueError('Refusing to overwrite provenance evidence')
    source = root / '.cache' / 'stage2-source'
    archive = source / 'terminal-bench-2-1-7131e437.tar.gz'
    destination = source / PREFIX
    if destination.is_symlink():
        raise ValueError('Refusing a symlinked dataset destination')
    url = f'https://api.github.com/repos/{REPOSITORY}/git/trees/{REVISION}?recursive=1'
    with urlopen(Request(url, headers={'User-Agent': 'UTS-study-provenance'}), timeout=30) as response:
        tree = json.load(response)
    if not destination.exists():
        with tarfile.open(archive, 'r:gz') as handle:
            members = handle.getmembers()
            if any(not m.name.startswith(PREFIX + '/') or '..' in Path(m.name).parts
                   or not (m.isfile() or m.isdir()) for m in members if m.name != PREFIX):
                raise ValueError('Unexpected archive member')
            handle.extractall(source, filter='data')
    dataset = destination / 'tasks'
    manifest = json.loads((root / 'stage2' / 'input_manifest.json').read_text())
    ids = set(manifest['all_task_ids'])
    actual_ids = {p.parent.name for p in dataset.glob('*/task.toml')}
    if len(ids) != 89 or actual_ids != ids:
        raise ValueError('Task IDs changed; frozen selection cannot be reused')
    verified = compare(dataset, tree, ids)
    if verified['differences']:
        raise ValueError('Canonical extraction does not match official Git tree')
    # Config hashes must match the already registered development selection.
    for task in manifest['tasks']:
        digest = hashlib.sha256((dataset / task['task_id'] / 'task.toml').read_bytes()).hexdigest()
        if digest != task['task_config_sha256']:
            raise ValueError('Frozen task configuration differs')
    historical = compare(root / '.cache' / 'datasets' / 'terminal-bench-2-1', tree, ids)
    evidence = {'status': 'canonical_task_file_bytes_verified_not_runtime_qualified',
        'repository': 'https://github.com/' + REPOSITORY, 'revision': REVISION,
        'time_utc': datetime.now(timezone.utc).isoformat(),
        'dataset_path': str(dataset.relative_to(root)),
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'task_count': len(ids), 'frozen_task_configs_match': True,
        'development_ids_unchanged': manifest['development_ids'],
        'canonical': verified,
        'historical_cache_audit': {k:v for k,v in historical.items() if k != 'file_hashes'},
        'limitations': ['Byte matching does not qualify images, runtimes or task outcomes.',
                       'Old pilot files were not modified; Stage 2 must use dataset_path above.',
                       'Only file hashes were inspected; no solution or verifier text was displayed.']}
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'status': evidence['status'], 'revision': REVISION,
        'verified_files': verified['local_files'], 'task_count': len(ids),
        'historical_differences': len(historical['differences']), 'output': str(output)}, indent=2))


if __name__ == '__main__':
    main(Path(__file__).resolve().parents[1])
