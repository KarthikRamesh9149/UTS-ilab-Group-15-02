"""Native-host launch sequence; never expands beyond the first baseline block.

Run under a single persistent service. Child runners retain their ownership
locks and immutable attempts. References are executed, never read into agent
policy. No model charge occurs until all twenty reference checks pass.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'stage2'))
from export_oracle_progress import summary
from scoring_admission import validate


def references(root, *, run=subprocess.run, inspect=summary):
    root = Path(root).resolve()
    python = root / '.venv/bin/python'
    # Start with previously architecture-sensitive tasks; then run all fixed
    # twenty. Completed oracle attempts are reused without replay or omission.
    for task in ('qemu-startup', 'install-windows-3.11', 'adaptive-rejection-sampler'):
        run([str(python), 'stage2/qualify_oracle.py', '--task', task], cwd=root, check=True)
        outcome = inspect(root, 'netcup')
        rows = [row for row in outcome['results'] if row['task'] == task]
        if len(rows) != 1 or rows[0].get('reward') != 1 or not rows[0].get('cleanup_verified'):
            raise RuntimeError('Reference qualification needs inspection: ' + task)
    run([str(python), 'stage2/qualify_oracle.py'], cwd=root, check=True)
    run([str(python), 'stage2/export_oracle_progress.py', '--run', 'netcup'], cwd=root, check=True)
    outcome = inspect(root, 'netcup')
    if outcome['status'] != 'all_references_passed':
        raise RuntimeError('Reference checks incomplete; no scored block launched')


def execute(root, admission_path, *, run=subprocess.run, inspect=summary, admit=validate):
    root = Path(root).resolve()
    admission_path = Path(admission_path)
    if admission_path.is_symlink() or admission_path.resolve().parent != root / 'stage2':
        raise ValueError('Registered local admission document required')
    admission_path = admission_path.resolve()
    admission = json.loads(admission_path.read_text())
    admit(root, admission)
    references(root, run=run, inspect=inspect)
    admit(root, admission)
    python = root / '.venv/bin/python'
    run([str(python), 'stage2/run_qualification.py', '--admission', str(admission_path)],
        cwd=root, check=True)
    print('First baseline block ended. Evidence review is required before any expansion.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--admission', type=Path)
    choice.add_argument('--references-only', action='store_true')
    args = parser.parse_args()
    if args.references_only:
        references(ROOT)
    else:
        execute(ROOT, args.admission)
