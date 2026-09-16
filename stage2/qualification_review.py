"""Bind a systemic review to the actual first-20 results before expansion."""
import hashlib
import json
from pathlib import Path

from matrix_resume import completed_cell
from qualification_gate import evaluate
from scoring_admission import validate


def assess(root, admission, review):
    root = Path(root)
    settings = validate(root, admission)
    tasks = json.loads((root / 'stage2/input_manifest.json').read_text())['development_ids']
    if len(tasks) != 20 or len(set(tasks)) != 20:
        raise ValueError('Frozen dev20 required')
    if review.get('kind') != 'terminus20_systemic_review' or review.get('model_protocol_sha256') != settings.fingerprint():
        raise ValueError('Explicit matching review required')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('Review attribution required')
    findings = review.get('findings', {})
    if set(findings) != {'parser', 'routing', 'environment'}:
        raise ValueError('All systemic review categories required')
    for finding in findings.values():
        if not isinstance(finding, dict) or type(finding.get('clear')) is not bool or not isinstance(finding.get('notes'), str) or not finding['notes'].strip():
            raise ValueError('Explicit review findings and notes required')
    records, hashes = [], {}
    for index, task in enumerate(tasks):
        identifier = f'dev-terminus-2-{index:02d}-{task}'
        cell = {'trial_id': identifier, 'task_id': task, 'harness': 'terminus-2', 'stage': 'development'}
        # Reaudit receipts and retain real zero outcomes; never run a trial here.
        row = completed_cell(root, cell, settings)
        if row is None:
            raise ValueError('Incomplete first-20 evidence')
        records.append(row)
        path = root / '.runtime/stage2/scored-trials' / identifier / 'result.json'
        hashes[identifier] = hashlib.sha256(path.read_bytes()).hexdigest()
    if review.get('reviewed_result_hashes') != hashes:
        raise ValueError('Review is stale or does not cover exactly the first 20 results')
    return evaluate(records, task_ids=tasks, protocol_sha256=settings.fingerprint(),
                    systemic_review_clear=all(finding['clear'] for finding in findings.values()))
