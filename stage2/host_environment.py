"""Stable execution-host identity, excluding secrets and transient load."""
import json
import os
import platform
import subprocess


def snapshot():
    def read(command):
        return subprocess.check_output(command, text=True, timeout=20).strip()
    info = json.loads(read(['docker', 'info', '--format', '{{json .}}']))
    fields = ('Architecture', 'OSType', 'KernelVersion', 'ServerVersion', 'NCPU', 'MemTotal')
    if any(info.get(field) in (None, '', 0) for field in fields):
        raise ValueError('Incomplete Docker host identity')
    system = platform.system()
    if system == 'Linux':
        if platform.machine() not in ('x86_64', 'AMD64') or info['Architecture'] not in ('x86_64', 'amd64') or info['OSType'] != 'linux':
            raise ValueError('Native Linux qualification requires an x86-64 client and Docker server')
        context = read(['docker', 'context', 'show'])
        details = json.loads(read(['docker', 'context', 'inspect', context]))
        if len(details) != 1:
            raise ValueError('Ambiguous Docker context')
        endpoint = details[0].get('Endpoints', {}).get('docker', {}).get('Host', '')
        if not endpoint.startswith('unix:///'):
            raise ValueError('Native host identity requires a local Unix Docker endpoint')
        if os.environ.get('DOCKER_HOST') not in (None, '', endpoint):
            raise ValueError('Docker host override differs from inspected local context')
        return {'docker': {field: info[field] for field in fields},
                'docker_context': context, 'docker_endpoint': endpoint,
                'execution_mode': 'native_linux_x86_64',
                'client_kernel': platform.release(), 'client_architecture': platform.machine()}
    if system != 'Darwin':
        raise ValueError('Unqualified host operating system')
    registration = read(['colima', 'ssh', '--', 'sh', '-c',
        'for name in rosetta qemu-x86_64; do '
        'if test -f /proc/sys/fs/binfmt_misc/$name; then '
        'printf "%s\\n" "$name"; cat /proc/sys/fs/binfmt_misc/$name; fi; done'])
    if not registration or '\nenabled\n' not in registration:
        raise ValueError('No verified x86-64 translation registration')
    return {'docker': {field: info[field] for field in fields},
            'docker_context': read(['docker', 'context', 'show']),
            'macos_build': read(['sw_vers', '-buildVersion']),
            'x86_translation_registration': registration}
