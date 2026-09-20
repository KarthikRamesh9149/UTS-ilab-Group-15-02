"""Create a local-only, code-free archive AFTER a fresh complete final audit.

No model calls, report prose, uploads or Git operations. Failed/incomplete
studies cannot be packaged as completed results. Existing outputs stay intact.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from export_final import export
from finalist_freeze import FROZEN_FILES
from model_protocol import read_protocol
from scored_gateway import durable_json

EXPORT_NAMES = ('final_trials.csv', 'comparison.json', 'provenance.json', 'export_complete.json')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def output_path(root, destination):
    destination = Path(destination)
    if not destination.is_absolute():
        destination = root / destination
    allowed = root / 'output/final-evidence'
    if (destination.parent != allowed or '..' in destination.parts
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', destination.name)):
        raise ValueError('Use a new named directory under output/final-evidence')
    if any(path.is_symlink() for path in (root / 'output', allowed, destination)):
        raise ValueError('Symlinked archive destination is forbidden')
    if destination.exists():
        raise FileExistsError('Existing handoff must not be overwritten')
    return destination


def payloads(directory, settings, registration_raw):
    """Accept only the exact fresh exporter contract, never an arbitrary tree."""
    if set(path.name for path in directory.iterdir()) != set(EXPORT_NAMES):
        raise ValueError('Unexpected export contents')
    raw = {}
    for name in EXPORT_NAMES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Unsafe export member')
        raw[name] = path.read_bytes()
    marker = json.loads(raw['export_complete.json'])
    expected_hashes = {name: digest(raw[name]) for name in EXPORT_NAMES[:-1]}
    if type(marker.get('rows')) is not int or marker != {'rows': 267, 'files': expected_hashes}:
        raise ValueError('Incomplete or changed export')
    provenance = json.loads(raw['provenance.json'])
    if (provenance.get('scope') != 'final_267_only_not_project_total'
            or provenance.get('receipt_reaudited') is not True
            or provenance.get('model_protocol_sha256') != settings.fingerprint()
            or provenance.get('final_registration_sha256') != digest(registration_raw)):
        raise ValueError('Reaudited final-only model provenance required')
    freeze = json.loads(registration_raw)['freeze']
    sources = freeze.get('files')
    if (not isinstance(sources, dict) or set(sources) != set(FROZEN_FILES)
            or any(not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value)
                   for value in sources.values())):
        raise ValueError('Exact allowlisted frozen source hashes required')
    rows = list(csv.DictReader(io.StringIO(raw['final_trials.csv'].decode('utf-8'))))
    if (len(rows) != 267
            or Counter(row['role'] for row in rows) != {'terminus-2': 89, 'openhands': 89, 'custom': 89}
            or len({row['trial_id'] for row in rows}) != 267
            or {row['trial_id'] for row in rows} != set(provenance.get('result_sha256', {}))
            or any(row['model_protocol_sha256'] != settings.fingerprint() for row in rows)):
        raise ValueError('Complete unique matched final rows required')
    tasks = [{row['task_id'] for row in rows if row['role'] == role}
             for role in ('terminus-2', 'openhands', 'custom')]
    if len(tasks[0]) != 89 or not tasks[0] == tasks[1] == tasks[2]:
        raise ValueError('All three systems must cover the same 89 tasks')
    conditions = {row['harness'] for row in rows if row['role'] == 'custom'}
    if len(conditions) != 1 or not conditions <= {'C0', 'C1', 'C2'}:
        raise ValueError('One frozen custom condition required')
    condition = next(iter(conditions))
    if freeze.get('selection', {}).get('selected') != condition:
        raise ValueError('Custom condition differs from frozen registration')
    protocol = settings.document()
    raw['METHOD.json'] = json.dumps({
        'benchmark': 'Terminal-Bench 2.1', 'final_trials': 267,
        'model_protocol': protocol, 'custom_condition': condition,
        'frozen_source_sha256': sources,
        'final_registration_sha256': digest(registration_raw)},
        sort_keys=True, indent=2).encode('utf-8') + b'\n'
    readme = (
        '# Final benchmark evidence: code-free handoff\n\n'
        'This is a technical evidence package, not the assignment report.\n'
        'It contains 267 fresh final trials: 89 each for Terminus-2, OpenHands, '
        'and one frozen custom harness. Development and historical pilot scores '
        'are not substituted for final results.\n\n'
        f'Model: {protocol["model"]}\nProvider: {protocol["endpoint"]}\n'
        f'Custom condition: {condition}\n'
        f'Model protocol SHA-256: {settings.fingerprint()}\n\n'
        '## Contents\n\n'
        '- final_trials.csv: per-task reward, cost, tokens, requests, budget stops and agent runtime.\n'
        '- comparison.json: full89 and outside-development69 comparisons and limitations.\n'
        '- provenance.json: final registration and result hashes; available receipts and any registered reservations reaudited at export.\n'
        '- export_complete.json: complete-export checksum marker.\n'
        '- METHOD.json: shared model settings and exact frozen source hashes, without source code.\n'
        '- CHECKSUMS.json: SHA-256 for all other files inside this archive.\n\n'
        '## Interpretation boundaries\n\n'
        'Costs cover final trials only, not total project spending. Setup, development '
        'and corrections need separate accounting. One attempt per condition/task '
        'can have an official accuracy result while billing remains unresolved. '
        'Check all_receipts_verified and coverage fields: unknown costs/tokens '
        'are not zero, reservations are not confirmed charges, and incomplete '
        'financial evidence cannot establish a cost/token efficiency win. '
        'One attempt '
        'does not establish repeatability; paired statistics are exploratory. '
        'Do not infer project success, an accepted efficiency win, or leaderboard '
        'eligibility from this archive. The official task verifier determines reward.\n\n'
        'Method and changes: stage2/EXPERIMENT_PROTOCOL.md, '
        'stage2/COMPLETION_AMENDMENT_20260920.md and Git history in '
        'https://github.com/KarthikRamesh9149/UTS-ilab-Group-15-02 '
        '(private repository access required).\n\n'
        'No source code, credentials, prompts, agent text, hidden verifier content '
        'or raw logs are included. Archive creation does not publish or submit it.\n'
    )
    raw['README.md'] = readme.encode('utf-8')
    raw['CHECKSUMS.json'] = json.dumps({name: digest(value) for name, value in sorted(raw.items())},
                                     sort_keys=True, indent=2).encode('utf-8') + b'\n'
    return raw


def package(root, destination):
    supplied_root = Path(root).absolute()
    root = supplied_root.resolve()
    destination = Path(destination)
    # Preserve a legitimate root alias (for example macOS /var -> /private/var)
    # without resolving or following any output-directory symlink.
    if destination.is_absolute() and supplied_root != root:
        try:
            destination = root / destination.relative_to(supplied_root)
        except ValueError:
            pass
    destination = output_path(root, destination)
    with tempfile.TemporaryDirectory(prefix='uts-final-handoff-') as temporary:
        directory = export(root, Path(temporary) / 'audited-final')
        registration = root / '.runtime/stage2/final-matrix.json'
        if registration.is_symlink() or not registration.is_file():
            raise ValueError('Original final registration is missing or unsafe')
        members = payloads(directory, read_protocol(root / '.runtime/stage2'), registration.read_bytes())
    # No delivery output is created until the complete final reaudit has passed.
    output_path(root, destination)
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    destination.mkdir(mode=0o700, exist_ok=False)
    archive = destination / 'final-evidence.zip'
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        with zipfile.ZipFile(handle, 'w') as zipped:
            for name, raw in sorted(members.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zipped.writestr(info, raw)
        handle.flush()
        os.fsync(handle.fileno())
    durable_json(destination / 'archive_complete.json', {
        'kind': 'code_free_final_evidence_not_project_completion', 'rows': 267,
        'archive': archive.name, 'sha256': digest(archive.read_bytes()),
        'members': {name: digest(raw) for name, raw in sorted(members.items())},
        'published': False, 'includes_source_code': False})
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New directory under output/final-evidence; never published')
    args = parser.parse_args()
    print(package(Path(__file__).resolve().parents[1], args.output))
