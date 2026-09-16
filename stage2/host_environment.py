"""Stable execution-host identity, excluding secrets and transient load."""
import json
import subprocess


def snapshot():
    def read(command):
        return subprocess.check_output(command, text=True, timeout=20).strip()
    info = json.loads(read(['docker', 'info', '--format', '{{json .}}']))
    fields = ('Architecture', 'OSType', 'KernelVersion', 'ServerVersion', 'NCPU', 'MemTotal')
    if any(info.get(field) in (None, '', 0) for field in fields):
        raise ValueError('Incomplete Docker host identity')
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
