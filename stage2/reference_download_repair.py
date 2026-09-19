"""A transport-only amendment to a private reference copy, never model policy.

The original reference's HTTPS download gets Cloudflare HTTP 403. POV-Ray's
official download page also publishes anonymous FTP, which is reachable.
Replace only three exact URLs in one hash-pinned reference script. All task,
verifier and model-environment bytes stay canonical. Never display the script.
"""
import hashlib
import json
from pathlib import Path
import shutil

from scored_gateway import durable_json, private_directory

TASK = 'build-pov-ray'
ORIGINAL_NAMESPACE = 'oracle-dev20-snapshot-v4'
REPAIRED_NAMESPACE = 'oracle-povray-ftp-v1'
SOURCE_SHA256 = '3da9dbf589656512cd7a7004dc3752d3552a6af939cfe59eff79f91695fa42c7'
DOCUMENTATION = 'https://www.povray.org/download/'
FILES = ('POVDOC.TAR.Z', 'POVSCN.TAR.Z', 'POVSRC.TAR.Z')
HTTPS = 'https://www.povray.org/ftp/pub/povray/Old-Versions/Official-2.2/'
FTP = 'ftp://ftp.povray.org/pub/povray/Old-Versions/Official-2.2/'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def amend(raw):
    if digest(raw) != SOURCE_SHA256:
        raise ValueError('Reference source is not the pinned original')
    updated = raw
    for name in FILES:
        source, target = (HTTPS + name).encode(), (FTP + name).encode()
        if raw.count(source) != 1:
            raise ValueError('Expected exactly one occurrence of each download URL')
        updated = updated.replace(source, target)
    if updated == raw:
        raise ValueError('No reference transport amendment made')
    return updated


def canonical_task(root):
    provenance = json.loads((root / 'stage2/dataset_provenance.json').read_text())
    return root / provenance['dataset_path'] / TASK


def inventory(folder):
    files = {}
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlinked reference copy refused')
        if path.is_file():
            files[str(path.relative_to(folder))] = digest(path.read_bytes())
    return files


def expected(root):
    root = Path(root).resolve()
    original = root / '.runtime/stage2' / ORIGINAL_NAMESPACE / TASK
    original_raw = (original / 'result.json').read_bytes()
    result = json.loads(original_raw)
    if (result.get('task') != TASK or result.get('live_api_calls') != 0
            or result.get('status') != 'verified'
            or result.get('cleanup_verified') is not True
            or result.get('verifier', {}).get('rewards', {}).get('reward') != 0
            or (original / 'agent/exit-code.txt').read_text().strip() != '8'):
        raise ValueError('Recorded failed reference download required')
    log = (original / 'agent/oracle.txt').read_text()
    if HTTPS + FILES[0] not in log or log.count('ERROR 403: Forbidden.') != 1:
        raise ValueError('Exact original HTTP 403 evidence required')
    source = canonical_task(root)
    before = (source / 'solution/solve.sh').read_bytes()
    after = amend(before)
    files = inventory(source)
    files['solution/solve.sh'] = digest(after)
    manifest = {'kind': 'reference_only_official_download_transport_amendment',
        'task': TASK, 'original_namespace': ORIGINAL_NAMESPACE,
        'original_result_sha256': digest(original_raw),
        'original_solution_sha256': digest(before), 'repaired_solution_sha256': digest(after),
        'changed_paths': ['solution/solve.sh'], 'official_documentation': DOCUMENTATION,
        'replacements': [{'from': HTTPS + name, 'to': FTP + name} for name in FILES],
        'task_instruction_and_verifier_bytes_changed': False,
        'canonical_dataset_changed': False, 'model_environment_changed': False,
        'copy_file_hashes': files}
    return source, after, manifest


def prepare(root):
    root = Path(root).resolve()
    source, after, manifest = expected(root)
    destination = private_directory(root / '.runtime/stage2' / REPAIRED_NAMESPACE)
    copy = destination / 'reference-copy'
    if copy.exists() or (destination / 'amendment.json').exists():
        validate_copy(root)
        return copy, manifest
    shutil.copytree(source, copy)
    (copy / 'solution/solve.sh').write_bytes(after)
    if inventory(copy) != manifest['copy_file_hashes']:
        raise ValueError('Reference copy changed beyond the approved URLs')
    durable_json(destination / 'amendment.json', manifest)
    validate_copy(root)
    return copy, manifest


def validate_copy(root):
    root = Path(root).resolve()
    _, _, manifest = expected(root)
    destination = root / '.runtime/stage2' / REPAIRED_NAMESPACE
    copy, record = destination / 'reference-copy', destination / 'amendment.json'
    if copy.is_symlink() or record.is_symlink() or json.loads(record.read_text()) != manifest:
        raise ValueError('Reference amendment identity changed')
    if inventory(copy) != manifest['copy_file_hashes']:
        raise ValueError('Reference copy changed beyond the approved URLs')
    return manifest


def qualified_override(root):
    """Return the explicitly amended attempt, not whichever reward is higher."""
    root = Path(root).resolve()
    path = root / '.runtime/stage2' / REPAIRED_NAMESPACE / TASK / 'result.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('Unsafe reference result')
    value = json.loads(path.read_text())
    if value.get('reference_amendment') != validate_copy(root):
        raise ValueError('Result is not bound to the exact reference amendment')
    return value
