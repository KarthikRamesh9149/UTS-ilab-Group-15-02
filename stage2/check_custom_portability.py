"""Offline fixed-dev20 image compatibility check, not a scored trial.

Run only on the native server in a separate working directory. Uses the
completed dev-only baseline metadata for image identity, never task answers.
No model service, API credential, network or benchmark verifier is involved.
This is not the complete source-bound native Harbor qualification.
"""
import asyncio
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace
import uuid

from custom_backend import HarborSandbox
from custom_portable_backend import PortableHarborSandbox
from custom_python_runtime import PythonBundle, prepare_python
from qualify_oracle import check_host
from run_corrected_custom import lock_all
from scored_gateway import durable_json

BASELINE = Path('/opt/uts-capstone-corrected-20260923')
ORIGINAL = Path('/opt/uts-capstone-custom-development-20260926')
WORK = Path('/opt/uts-capstone-custom-compatibility-20260926-r2')
PYTHON_SOURCE = Path('/root/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu')


class OfflineDocker:
    """Small test IO adapter; production continues to use Harbor."""
    def __init__(self, name):
        self.name = name

    async def exec(self, command, timeout_sec, **kwargs):
        process = await asyncio.create_subprocess_exec('docker', 'exec', self.name, 'bash', '-c', command,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(process.communicate(), timeout_sec)
            return SimpleNamespace(return_code=process.returncode, stdout=out.decode(errors='replace'),
                stderr=err.decode(errors='replace'))
        except TimeoutError:
            process.kill()
            await process.wait()
            return SimpleNamespace(return_code=124, stdout='', stderr='test transport timeout')

    async def upload_file(self, source, target):
        process = await asyncio.create_subprocess_exec('docker', 'cp', str(source), self.name + ':' + target,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, error = await process.communicate()
        if process.returncode:
            raise RuntimeError('Offline Docker copy failed')


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE, timeout=45).strip()


def bundle():
    path = WORK / 'python-runtime.tar.gz'
    if not path.exists():
        def header(member):
            member.uid = member.gid = 0
            member.uname = member.gname = ''
            return member
        with tarfile.open(path, 'w:gz', dereference=False) as archive:
            archive.add(PYTHON_SOURCE, arcname='python', filter=header)
        path.chmod(0o644)  # Vendor files only; task user must read Docker copy.
    with path.open('rb') as stream:
        result = PythonBundle(path, hashlib.file_digest(stream, 'sha256').hexdigest())
    result.validate()
    return result


def images():
    manifest = json.loads((ORIGINAL / 'stage2/input_manifest.json').read_text())
    matched = ORIGINAL / 'stage2/results/baseline-corrected-20260923/development-baselines.csv'
    from corrected_custom_scope import MATCHED_CSV_SHA256
    if hashlib.sha256(matched.read_bytes()).hexdigest() != MATCHED_CSV_SHA256:
        raise ValueError('Matched development metadata changed')
    selected = {r['task_id']: r for r in csv.DictReader(matched.open()) if r['harness'] == 'terminus-2'}
    if set(selected) != set(manifest['development_ids']) or len(selected) != 20:
        raise ValueError('Exact fixed development split required')
    from harbor.models.task.task import Task
    provenance = json.loads((ORIGINAL / 'stage2/dataset_provenance.json').read_text())
    for task_id in manifest['development_ids']:
        row = selected[task_id]
        result_path = BASELINE / '.runtime/stage2/scored-trials' / row['trial_id'] / 'result.json'
        data = result_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row['result_sha256']:
            raise ValueError('Original development result changed')
        result = json.loads(data)
        task = Task(ORIGINAL / provenance['dataset_path'] / task_id)
        image_id = result['task_image_id']
        if not re.fullmatch('sha256:[0-9a-f]{64}', image_id):
            raise ValueError('Immutable task image required')
        yield task_id, image_id, task.config.agent.user, task.config.environment


async def check(task_id, image_id, user, config, runtime):
    check_host()
    name = 'uts-compat-' + uuid.uuid4().hex[:12]
    options = ['run', '-d', '--name', name, '--network=none', '--cpus', str(config.cpus),
        '--memory', str(config.memory_mb) + 'm', '--cap-drop=NET_ADMIN', '--cap-drop=NET_RAW',
        '--security-opt=no-new-privileges', '--entrypoint', 'bash']
    if user is not None:
        options += ['--user', str(user)]
    docker(*options, image_id, '-c', 'sleep 300')
    result = dict(task_id=task_id, image_id=image_id, live_api_calls=0, task_user=user,
        cpus=config.cpus, memory_mb=config.memory_mb, network='none')
    start = time.monotonic()
    try:
        inspected = json.loads(docker('inspect', name))[0]
        host = inspected['HostConfig']
        if inspected['Mounts'] or host['PortBindings'] or host['Privileged'] or host['NetworkMode'] != 'none':
            raise RuntimeError('Unexpected offline probe access')
        env = OfflineDocker(name)
        before = await env.exec('command -v python3 || true', timeout_sec=5)
        result['python3_present_before'] = bool(before.stdout.strip())
        wrapped, proof = await prepare_python(env, runtime)
        result['bootstrap'] = proof
        backend = PortableHarborSandbox(wrapped, identifier=name)
        outcome = await backend.aexecute('printf portable-ready', timeout=1)
        result['command_ok'] = outcome.output == 'portable-ready' and outcome.exit_code == 0
        uploaded = await backend.aupload_files([('/tmp/uts-synthetic.txt', b'alpha\nbeta\n')])
        read = await backend.aread('/tmp/uts-synthetic.txt')
        edited = await backend.aedit('/tmp/uts-synthetic.txt', 'beta', 'gamma')
        downloaded = await backend.adownload_files(['/tmp/uts-synthetic.txt'])
        result['filesystem_ok'] = (uploaded[0].error is None and read.error is None
            and edited.error is None and downloaded[0].content == b'alpha\ngamma\n')
        await backend.aupload_files([('/tmp/uts-synthetic-large.txt', b'long line\n' * 16000)])
        large = await backend.aread('/tmp/uts-synthetic-large.txt', limit=16000)
        result['large_read_ok'] = large.error is None and large.file_data is not None and large.end_line == 16000
        timed = await backend.aexecute('sleep 10', timeout=.1)
        result['timeout_observation_ok'] = timed.exit_code == 124
        started = time.monotonic()
        background = await backend.aexecute('sleep 30 & printf background-ready', timeout=1)
        result['background_pipe_ok'] = (background.exit_code == 0 and background.output == 'background-ready'
            and time.monotonic() - started < 3)
        # Demonstrate the old helper's generic descriptor problem once. This
        # does not replay the original model command or establish its cause.
        if task_id == 'mailman':
            try:
                old = HarborSandbox(env, identifier='legacy-synthetic')
                await old.aexecute('sleep 30 & printf background-ready', timeout=.1)
                result['legacy_background_probe'] = 'returned'
            except RuntimeError:
                result['legacy_background_probe'] = 'helper_runtime_error_reproduced'
        result['passed'] = all(result[k] for k in ('command_ok', 'filesystem_ok', 'large_read_ok',
            'timeout_observation_ok', 'background_pipe_ok'))
    except Exception as exc:
        result.update(passed=False, error_type=type(exc).__name__)
    finally:
        docker('rm', '-f', name)
        result['cleanup_complete'] = not docker('ps', '-aq', '--filter', 'name=^/' + name + '$')
        result['seconds'] = round(time.monotonic() - start, 3)
    return result


def main():
    if Path(__file__).resolve().parent != WORK / 'stage2' or sys.platform != 'linux':
        raise SystemExit('Use only the separate native compatibility work directory')
    path = WORK / 'compatibility.json'
    if path.exists():
        raise SystemExit('Preserve existing check evidence; do not overwrite')
    with ExitStack() as stack:
        lock_all(stack, ORIGINAL)
        if docker('ps', '-q', '--filter', 'name=uts-scored-'):
            raise RuntimeError('Scored work is active')
        runtime = bundle()
        rows = []
        for task_id, image_id, user, config in images():
            row = asyncio.run(check(task_id, image_id, user, config, runtime))
            rows.append(row)
            print(json.dumps({k:v for k,v in row.items() if k != 'bootstrap'}), flush=True)
            if not row['cleanup_complete']:
                break
        report = dict(kind='offline_image_compatibility_not_full_qualification',
            checked_utc=datetime.now(timezone.utc).isoformat(), live_api_calls=0,
            bundle=runtime.validate(), rows=rows, passed=len(rows) == 20 and all(r['passed'] for r in rows))
        report['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (WORK / 'stage2').glob('*.py') if not p.name.startswith('._')}
        durable_json(path, report)
        print(json.dumps(dict(status='passed' if report['passed'] else 'failed',
            checked=len(rows), live_api_calls=0)), flush=True)


if __name__ == '__main__':
    main()
