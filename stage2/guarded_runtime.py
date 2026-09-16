"""Add an isolated public-IPv4 task namespace to a gateway compose document.

This does not grant task access to the gateway network. The gateway remains
reachable only through its private Unix socket. Callers must still validate
the final merged Docker configuration and destroy the whole trial on exit.
"""
from copy import deepcopy
import re


def with_task_guard(compose, image):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Guard image must be resolved to an immutable local ID')
    result = deepcopy(compose)
    services = result['services']
    main = services['main']
    if 'task-network-guard' in services or 'uts-task-egress' in result.get('networks', {}):
        raise ValueError('Guard names already in use')
    if main.get('network_mode') != 'none' or main.get('networks'):
        raise ValueError('Expected an explicitly isolated initial task configuration')
    if main.get('privileged') or main.get('cap_add') or main.get('ports'):
        raise ValueError('Task privilege or published ports violate guarded runtime')
    main['network_mode'] = 'service:task-network-guard'
    # Docker default capabilities are retained except raw sockets; NET_ADMIN
    # is absent by default. Do not silently change task CPU/memory settings.
    main['cap_drop'] = sorted(set(main.get('cap_drop', [])) | {'NET_RAW', 'NET_ADMIN'})
    main['security_opt'] = sorted(set(main.get('security_opt', [])) | {'no-new-privileges:true'})
    main.setdefault('depends_on', {})['task-network-guard'] = {'condition': 'service_healthy'}
    services['task-network-guard'] = {
        'image': image, 'networks': ['uts-task-egress'],
        'cap_drop': ['ALL'], 'cap_add': ['NET_ADMIN'],
        'security_opt': ['no-new-privileges:true'], 'read_only': True,
        'tmpfs': ['/tmp:rw,nosuid,nodev,size=4m'],
        'cpus': 0.25, 'mem_limit': '128m', 'pids_limit': 32,
        'healthcheck': {'test': ['CMD', 'test', '-f', '/tmp/ready'],
                        'interval': '1s', 'timeout': '2s', 'retries': 20},
    }
    result.setdefault('networks', {})['uts-task-egress'] = {'driver': 'bridge'}
    return result
