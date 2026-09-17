"""PBS-only benign Apptainer capability probe (Python 3.6 compatible).

No model, benchmark, privileged command, network workaround or stress test.
Only network-none is attempted; a prior bridge denial is not retried.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

FLAGS = ['--cleanenv', '--containall', '--writable-tmpfs',
         '--no-mount', 'home,tmp,bind-paths,hostfs,cwd,sys', '--net', '--network', 'none']
LIMITS = ['--cpus', '1', '--memory', '512M', '--pids-limit', '64']


def command(args, timeout=30):
    try:
        done = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=timeout)
        return {'exit_code': done.returncode, 'stdout': done.stdout[-24000:], 'stderr': done.stderr[-12000:]}
    except subprocess.TimeoutExpired:
        return {'exit_code': 124, 'stdout': '', 'stderr': 'bounded command timeout'}


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def cgroup_snapshot(pid):
    """Read only the identified instance's cgroup; never writes controllers."""
    text = read_text('/proc/{}/cgroup'.format(pid))
    result = {'membership': text, 'files': {}}
    if text is None:
        return result
    for line in text.splitlines():
        hierarchy, controllers, relative = line.split(':', 2)
        if '..' in Path(relative).parts:
            raise ValueError('Unexpected cgroup path')
        if hierarchy == '0' and not controllers:
            base = Path('/sys/fs/cgroup') / relative.lstrip('/')
            names = ['memory.max', 'cpu.max', 'pids.max', 'cpuset.cpus.effective']
            for name in names:
                result['files'][name] = read_text(base / name)
        else:
            for controller, name in [('memory', 'memory.limit_in_bytes'),
                                      ('cpu', 'cpu.cfs_quota_us'), ('cpu', 'cpu.cfs_period_us'),
                                      ('pids', 'pids.max')]:
                if controller in controllers.split(','):
                    for directory in (controllers, controller):
                        value = read_text(Path('/sys/fs/cgroup') / directory / relative.lstrip('/') / name)
                        if value is not None:
                            result['files'][name] = value
                            break
    return result


def limits_verified(snapshot):
    files = snapshot.get('files', {})
    try:
        memory = int(files.get('memory.max', files.get('memory.limit_in_bytes')))
        pids = int(files['pids.max'])
        if 'cpu.max' in files:
            quota, period = map(int, files['cpu.max'].split())
        else:
            quota, period = int(files['cpu.cfs_quota_us']), int(files['cpu.cfs_period_us'])
        return 0 < memory <= 512 * 1024 ** 2 and 0 < pids <= 64 and 0 < quota <= period
    except (ValueError, TypeError, KeyError):
        return False


FIXTURE = r'''
import json, os, pathlib, socket, subprocess
checks = {}
checks['fake_controller_secret_absent'] = 'UTS_FAKE_CONTROLLER_SECRET' not in os.environ
checks['shared_home_absent'] = not pathlib.Path('/shared/homes').exists()
checks['controller_dir_absent'] = not pathlib.Path(os.environ.get('UTS_PROBE_HOST_PATH', '/shared/homes/u26025369')).exists()
checks['docker_socket_absent'] = not pathlib.Path('/var/run/docker.sock').exists()
checks['namespace_isolated'] = all(os.readlink('/proc/self/ns/'+name) != target for name,target in HOST_NAMESPACES.items())
routes = pathlib.Path('/proc/net/route').read_text().splitlines()
checks['no_ipv4_routes'] = len(routes) <= 1
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    checks['loopback_bind'] = True
pathlib.Path('/tmp/uts-state').write_text('synthetic persistence marker')
print(json.dumps({'checks': checks, 'uid': os.getuid(), 'affinity': sorted(os.sched_getaffinity(0)),
                  'cgroup': pathlib.Path('/proc/self/cgroup').read_text()}))
'''


def instance_pid(name):
    found = command(['apptainer', 'instance', 'list', '--json', name])
    try:
        rows = json.loads(found['stdout'])['instances']
        matches = [r for r in rows if r.get('instance') == name]
        if len(matches) == 1 and int(matches[0]['pid']) > 1:
            pid = int(matches[0]['pid'])
            if Path('/proc/{}'.format(pid)).stat().st_uid == os.getuid():
                return pid
    except (ValueError, KeyError, TypeError, OSError):
        pass
    return None


def trial(image, name, *, fakeroot, enforce):
    result = {'fakeroot': fakeroot, 'limits_requested': enforce, 'checks': {}, 'complete': False}
    flags = FLAGS + (['--fakeroot'] if fakeroot else []) + (LIMITS if enforce else [])
    try:
        result['start'] = command(['apptainer', 'instance', 'start'] + flags + [str(image), name], timeout=40)
        if result['start']['exit_code'] != 0:
            return result
        pid = instance_pid(name)
        result['instance_pid'] = pid
        result['cgroup'] = cgroup_snapshot(pid) if pid else {}
        result['checks']['hard_limits_verified'] = limits_verified(result['cgroup'])
        namespaces = {n: os.readlink('/proc/self/ns/' + n) for n in ('mnt', 'pid', 'net', 'ipc')}
        source = 'HOST_NAMESPACES = ' + repr(namespaces) + '\n' + FIXTURE
        observed = command(['apptainer', 'exec', '--cleanenv', 'instance://' + name, 'python', '-c', source])
        result['fixture'] = observed
        if observed['exit_code'] == 0:
            result['checks'].update(json.loads(observed['stdout'])['checks'])
        persistence = command(['apptainer', 'exec', '--cleanenv', 'instance://' + name, 'python', '-c',
            "from pathlib import Path; assert Path('/tmp/uts-state').read_text() == 'synthetic persistence marker'"])
        result['checks']['persistence'] = persistence['exit_code'] == 0
        timeout = command(['apptainer', 'exec', '--cleanenv', 'instance://' + name, 'timeout', '1', 'sleep', '5'])
        result['checks']['command_timeout'] = timeout['exit_code'] == 124
        result['complete'] = True
        return result
    finally:
        result['stop'] = command(['apptainer', 'instance', 'stop', name], timeout=20)
        result['checks']['instance_stopped'] = instance_pid(name) is None
        stopped = command(['apptainer', 'exec', 'instance://' + name, 'true'], timeout=10)
        result['checks']['stopped_rejects_exec'] = stopped['exit_code'] not in (0, 124)


def main():
    job = os.environ.get('PBS_JOBID', '')
    if not re.fullmatch(r'[0-9]+\.[A-Za-z0-9.-]+', job):
        raise RuntimeError('Run only inside the approved PBS job')
    os.umask(0o077)
    def interrupted(signum, frame):
        raise InterruptedError('Probe interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    output = Path(os.environ['PBS_O_WORKDIR']) / ('apptainer-capabilities-' + job)
    output.mkdir(mode=0o700, exist_ok=False)
    report = {'scope': 'synthetic_apptainer_capabilities_not_benchmark', 'job': job,
        'scored_trials': 0, 'model_requests': 0, 'external_inference_requests': 0,
        'full_study_admitted': False, 'network_mode': 'none', 'variants': []}
    try:
        report['host_cgroup'] = cgroup_snapshot(os.getpid())
        scratch = Path(tempfile.mkdtemp(prefix='uts-apptainer-caps-', dir='/scratch'))
        report['scratch_retained'] = str(scratch)
        os.environ['APPTAINER_CACHEDIR'] = str(scratch / 'cache')
        os.environ['APPTAINER_TMPDIR'] = str(scratch / 'tmp')
        for directory in ('cache', 'tmp'):
            (scratch / directory).mkdir(mode=0o700)
        os.environ['UTS_FAKE_CONTROLLER_SECRET'] = 'synthetic_not_a_real_credential'
        image = scratch / 'python.sif'
        report['pull'] = command(['apptainer', 'pull', str(image), 'docker://python:3.12-slim-bookworm'], timeout=180)
        if report['pull']['exit_code'] != 0:
            return
        # The image is used only for trusted synthetic commands, not task parity.
        import hashlib
        digest = hashlib.sha256()
        with image.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        report['synthetic_image_sha256'] = digest.hexdigest()
        for suffix, fakeroot, enforce in [('limited-user', False, True), ('limited-fakeroot', True, True),
                                          ('offline-fixture', True, False)]:
            name = 'uts-caps-' + job.split('.')[0] + '-' + suffix
            report['variants'].append(trial(image, name, fakeroot=fakeroot, enforce=enforce))
    except Exception as exc:
        report['error_type'] = type(exc).__name__
    finally:
        report['completed_at_unix'] = time.time()
        with (output / 'result.json').open('w') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps({'output': str(output), 'full_study_admitted': False}))


if __name__ == '__main__':
    main()
