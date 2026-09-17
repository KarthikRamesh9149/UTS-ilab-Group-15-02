"""Offline CETUS study protocol, stratified selection and trial inventory.

This module has no inference transport and never submits a PBS or Harbor job.
It deliberately does not import the separate OpenRouter study configuration.
"""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import tomllib

from cetus_local_probe import MODEL, REVISION, LLAMA_REVISION, SHARDS

DATASET_REVISION = '7131e4375048a0e408a8fb404b5f499d726b695b'
SEED = 'uts-cetus-local-dev20-v1:42'
ID = re.compile(r'[a-z0-9][a-z0-9.-]{0,100}\Z')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class LocalProtocol:
    model: str = MODEL
    model_revision: str = REVISION
    runtime_revision: str = LLAMA_REVISION
    dataset_revision: str = DATASET_REVISION
    context_tokens: int = 32768
    max_output_tokens: int = 8192
    max_model_requests: int = 100
    temperature: float = 1.0
    top_p: float = .95
    top_k: int = 40

    def __post_init__(self):
        # This phase admits exactly the approved protocol. A new protocol is
        # an explicit versioned change, not a fallback selected by a runner.
        defaults = {f.name: f.default for f in self.__dataclass_fields__.values()}
        if asdict(self) != defaults or any(type(getattr(self, key)) is not type(value)
                                           for key, value in defaults.items()):
            raise ValueError('Unregistered local model protocol')

    def document(self):
        return dict(schema_version=1, **asdict(self), external_inference_allowed=False,
                    external_inference_usd=0, compute_cost_usd=None,
                    primary_baseline='openhands', model_shards=[
                        {'bytes': size, 'sha256': digest} for size, digest in SHARDS])

    def validate_request(self, request):
        """Check exact on-wire sampling; messages/tools remain harness-owned."""
        expected = {key: getattr(self, key) for key in ('model', 'temperature', 'top_p', 'top_k')}
        for key, value in expected.items():
            if type(request.get(key)) is not type(value) or request[key] != value:
                raise ValueError('Model request differs from local protocol: ' + key)
        limit = request.get('max_tokens')
        if type(limit) is not int or not 1 <= limit <= self.max_output_tokens:
            raise ValueError('Invalid output limit')
        if any(key in request for key in ('reasoning', 'reasoning_effort', 'provider', 'models')):
            raise ValueError('Provider routing/reasoning options not permitted')
        return True


def rank(value):
    return hashlib.sha256((SEED + ':' + value).encode()).hexdigest()


def quotas(counts, seats, cover=False):
    """Largest remainder, with explicit category coverage where possible."""
    if not counts or seats < 0 or seats > sum(counts.values()):
        raise ValueError('Invalid allocation')
    result = {k: 0 for k in counts}
    if cover:
        for key in sorted(counts, key=lambda k: (-counts[k], rank(k)))[:seats]:
            result[key] = 1
    left = seats - sum(result.values())
    capacities = {k: counts[k] - result[k] for k in counts}
    total = sum(capacities.values())
    if not left:
        return result
    ideals = {k: Fraction(left * capacities[k], total) for k in counts}
    floors = {k: int(ideals[k]) for k in counts}
    for k in counts:
        result[k] += floors[k]
    for k in sorted(counts, key=lambda k: (-(ideals[k] - floors[k]), rank(k))):
        if sum(result.values()) == seats:
            break
        if result[k] < counts[k]:
            result[k] += 1
    return result


def duration_bucket(minutes):
    if minutes is None:
        return 'unknown'
    return 'short' if minutes <= 30 else 'medium' if minutes <= 120 else 'long'


def inventory(root):
    """Reads metadata only; hashes other bytes without displaying their content."""
    root = Path(root)
    proof = json.loads((root / 'stage2/dataset_provenance.json').read_text())
    if proof['revision'] != DATASET_REVISION or proof['canonical']['differences']:
        raise ValueError('Canonical dataset provenance failed')
    dataset = root / proof['dataset_path']
    expected = {row['path']: row['sha256'] for row in proof['canonical']['file_hashes']}
    actual = {str(p.relative_to(dataset)): p for p in dataset.rglob('*') if p.is_file() or p.is_symlink()}
    if actual.keys() != expected.keys():
        raise ValueError('Dataset inventory drift')
    for name, path in actual.items():
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]:
            raise ValueError('Dataset bytes changed: ' + name)
    old = json.loads((root / 'stage2/input_manifest.json').read_text())
    exposure = {r['task_id']: r.get('pilot_exposed', False) for r in old['tasks']}
    rows = []
    for path in sorted(dataset.glob('*/task.toml')):
        doc = tomllib.loads(path.read_text())
        meta, env = doc['metadata'], doc['environment']
        task = path.parent.name
        if not ID.fullmatch(task):
            raise ValueError('Unsafe task identifier')
        rows.append(dict(task_id=task, category=meta['category'], difficulty=meta['difficulty'],
            duration=duration_bucket(meta.get('expert_time_estimate_min')),
            cpus=env['cpus'], memory_mb=env['memory_mb'], storage_mb=env['storage_mb'],
            gpus=env.get('gpus', 0), agent_timeout_sec=doc['agent']['timeout_sec'],
            verifier_timeout_sec=doc['verifier']['timeout_sec'],
            config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            pilot_exposed=exposure.get(task, False)))
    if len(rows) != 89 or len({r['task_id'] for r in rows}) != 89:
        raise ValueError('Exactly 89 unique tasks required')
    return rows


def select(rows):
    if len(rows) != 89 or len({r['task_id'] for r in rows}) != 89:
        raise ValueError('Exactly 89 unique tasks required')
    counts = Counter(r['category'] for r in rows)
    category_quotas = quotas(counts, 20, cover=True)
    selected = []
    for category in sorted(counts):
        pool = [r for r in rows if r['category'] == category]
        difficulty_quotas = quotas(Counter(r['difficulty'] for r in pool), category_quotas[category])
        for difficulty in sorted(difficulty_quotas):
            candidates = [r for r in pool if r['difficulty'] == difficulty]
            target = difficulty_quotas[difficulty]
            for _ in range(target):
                # Cover underrepresented durations and resource profiles, with
                # stable hash ties. No outcome, test or solution enters rank.
                durations = Counter(r['duration'] for r in selected)
                resources = Counter((r['cpus'], r['memory_mb']) for r in selected)
                chosen = min(candidates, key=lambda r: (
                    durations[r['duration']], resources[(r['cpus'], r['memory_mb'])], rank(r['task_id'])))
                selected.append(chosen)
                candidates.remove(chosen)
    return sorted(r['task_id'] for r in selected)


def build(root):
    rows = inventory(root)
    ids = select(rows)
    def coverage(subset):
        return {key: dict(sorted(Counter(r[key] for r in subset).items()))
                for key in ('category', 'difficulty', 'duration')}
    return dict(schema_version=1, study='cetus-local-v1', status='protocol_frozen_runtime_unqualified',
        protocol=LocalProtocol().document(), selection=dict(seed=SEED,
            method='category coverage then largest remainder on remaining capacity; difficulty largest remainder; duration/resource diversity; SHA256 ties',
            development_ids=ids, outside_development_ids=sorted(r['task_id'] for r in rows if r['task_id'] not in ids),
            coverage_full=coverage(rows), coverage_development=coverage([r for r in rows if r['task_id'] in ids]),
            limitations=['Category coverage deliberately oversamples rare categories.',
                        'Historical exposure exists; remaining 69 are not a pristine holdout.',
                        'pilot_exposed records the old manifest, not an exhaustive exposure audit.']),
        tasks=rows, scored_trials=0)


def schedule(manifest, *, finalist=None):
    all_ids = sorted(r['task_id'] for r in manifest['tasks'])
    dev = manifest['selection']['development_ids']
    if len(all_ids) != 89 or len(set(all_ids)) != 89 or len(dev) != 20 or len(set(dev)) != 20 or not set(dev) <= set(all_ids):
        raise ValueError('Invalid frozen task sets')
    if finalist is not None and finalist not in ('C0', 'C1', 'C2', 'C3', 'C4'):
        raise ValueError('Invalid finalist')
    cells = []
    def add(stage, harness, tasks, repetition):
        for task in tasks:
            cells.append(dict(trial_id=f'{stage}-{harness}-r{repetition}-{task}', stage=stage,
                harness=harness, task_id=task, repetition=repetition, seed=42 + repetition,
                status='planned_not_launched'))
    for harness in ('terminus-2', 'openhands'):
        add('baseline', harness, all_ids, 0)
    for harness in ('C0', 'C1', 'C2', 'C3', 'C4'):
        add('development', harness, dev, 0)
    if finalist:
        for repetition in (1, 2):
            for harness in ('terminus-2', 'openhands', finalist):
                add('confirmation', harness, dev, repetition)
        add('final', finalist, all_ids, 0)
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    document = build(args.root)
    document['manifest_sha256'] = fingerprint(document)
    with args.output.open('x') as handle:
        json.dump(document, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({'status': document['status'], 'development_ids': document['selection']['development_ids'],
                      'manifest_sha256': document['manifest_sha256']}))


if __name__ == '__main__':
    main()
