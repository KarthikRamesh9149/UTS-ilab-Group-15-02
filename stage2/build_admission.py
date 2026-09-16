"""Build a scoring admission from completed proofs, without launching trials."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from gateway_policy import MODEL, ENDPOINT
from model_protocol import ModelSettings
from scoring_admission import source_hashes, validate


def build(root, *, proofs, settings, setup_timeout_seconds=900):
    root = Path(root).resolve()
    if type(setup_timeout_seconds) is not int or setup_timeout_seconds <= 0:
        raise ValueError('Positive integer setup timeout required')
    document = {'model': MODEL, 'endpoint': ENDPOINT,
                'settings': asdict(settings), 'source_hashes': source_hashes(root),
                'setup_timeout_seconds': setup_timeout_seconds, 'proofs': {}}
    for role, relative in proofs.items():
        relative = Path(relative)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[:1] != ('stage2',):
            raise ValueError('Evidence must be inside stage2')
        path = root / relative
        if path.is_symlink() or path.suffix != '.json':
            raise ValueError('Regular JSON evidence required')
        raw = path.read_bytes()
        evidence = json.loads(raw)
        if role == 'runtime':
            for field in ('gateway_image', 'guard_image'):
                document[field] = evidence[field]
        document['proofs'][role] = {'path': relative.as_posix(),
                                  'sha256': hashlib.sha256(raw).hexdigest()}
    validate(root, document)
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('runtime', 'terminus-live', 'openhands-live', 'custom-live'):
        parser.add_argument('--' + role, required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-output-tokens', required=True, type=int)
    parser.add_argument('--temperature', required=True, type=float)
    parser.add_argument('--reasoning-effort', required=True, choices=['low', 'medium', 'high'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    document = build(root, proofs={role: getattr(args, role) for role in
        ('runtime', 'terminus_live', 'openhands_live', 'custom_live')},
        settings=ModelSettings(args.max_output_tokens, args.temperature, args.reasoning_effort))
    # Refuse replacement of an earlier frozen admission.
    with args.output.open('x') as handle:
        json.dump(document, handle, indent=2)
        handle.write('\n')
    print('Admission evidence validated and saved; no scored trial launched.')
