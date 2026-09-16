"""Trusted runtime wiring; task receives no gateway socket or host credentials.

The relay is a separate process/container in the task network namespace. This
allows non-root task users without making private socket permissions public.
Callers supply resolved image IDs and private host paths, never model inputs.
"""
from pathlib import Path
import re
import stat

from guarded_runtime import with_task_guard

SOCKET = '/socket/private/model.sock'


def bind(source, target, readonly=True):
    source = Path(source)
    if not source.is_absolute() or not source.exists() or source.is_symlink():
        raise ValueError('Existing absolute non-symlink mount source required')
    return {'type': 'bind', 'source': str(source), 'target': target, 'read_only': readonly,
            'bind': {'create_host_path': False}}


def compose_runtime(*, gateway_image, guard_image, state_dir, tokenizer_dir,
                    credential_file, token_file, trial_id, stage, uid, gid):
    for image in (gateway_image, guard_image):
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            raise ValueError('Immutable image ID required')
    if any(type(v) is not int or not 0 <= v <= 2**31-1 for v in (uid, gid)):
        raise ValueError('Numeric runtime identity required')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id) or stage not in {'development', 'final'}:
        raise ValueError('Invalid trial identity')
    for path in [state_dir, tokenizer_dir]:
        if not Path(path).is_dir():
            raise ValueError('Runtime and tokenizer mount sources must be directories')
    if Path(state_dir).stat().st_mode & 0o077:
        raise ValueError('Runtime state directory must be private')
    for path in [credential_file, token_file]:
        info = Path(path).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError('Credential and token mount sources must be private regular files')
    security = ['no-new-privileges:true']
    common = {'image': gateway_image, 'user': f'{uid}:{gid}', 'cap_drop': ['ALL'],
              'security_opt': security, 'read_only': True, 'pids_limit': 64,
              'tmpfs': ['/tmp:rw,nosuid,nodev,size=16m'], 'restart': 'no'}
    gateway = dict(common, cpus=1, mem_limit='512m', networks=['uts-gateway-egress'],
        command=['--root', '/study', '--trial', trial_id, '--stage', stage,
                 '--token-file', '/run/trial-token', '--credential-file', '/run/openrouter.env', '--socket', SOCKET],
        volumes=[{'type': 'volume', 'source': 'model-socket', 'target': '/socket'},
                 bind(state_dir, '/study/.runtime/stage2', False),
                 bind(tokenizer_dir, '/study/.cache/stage2-tokenizer'),
                 bind(credential_file, '/run/openrouter.env'), bind(token_file, '/run/trial-token')],
        depends_on={'socket-init': {'condition': 'service_completed_successfully'}},
        healthcheck={'test': ['CMD', 'test', '-S', SOCKET], 'interval': '1s', 'timeout': '2s', 'retries': 120})
    relay = dict(common, cpus=0.25, mem_limit='128m', network_mode='service:task-network-guard',
        entrypoint=['python', '/study/stage2/container_model_relay.py'],
        command=['--socket', SOCKET, '--port', '8765'],
        volumes=[{'type': 'volume', 'source': 'model-socket', 'target': '/socket', 'read_only': True}],
        depends_on={'model-gateway': {'condition': 'service_healthy'},
                    'task-network-guard': {'condition': 'service_healthy'}},
        healthcheck={'test': ['CMD', 'python', '-c',
            "import socket; socket.create_connection(('127.0.0.1',8765),timeout=2).close()"],
            'interval': '1s', 'timeout': '3s', 'retries': 20})
    result = {'services': {
        'main': {'network_mode': 'none', 'depends_on': {'model-relay': {'condition': 'service_healthy'}}},
        'model-gateway': gateway, 'model-relay': relay,
        'socket-init': {'image': gateway_image, 'user': '0:0', 'network_mode': 'none',
            'cap_drop': ['ALL'], 'cap_add': ['CHOWN'], 'security_opt': security,
            'read_only': True, 'cpus': 0.25, 'mem_limit': '64m', 'pids_limit': 16,
            'entrypoint': ['python', '-c'],
            'command': [f"import os; os.mkdir('/socket/private',0o700); os.chown('/socket/private',{uid},{gid})"],
            'volumes': [{'type': 'volume', 'source': 'model-socket', 'target': '/socket'}], 'restart': 'no'}},
        'volumes': {'model-socket': {}}, 'networks': {'uts-gateway-egress': {'driver': 'bridge'}}}
    return with_task_guard(result, guard_image)
