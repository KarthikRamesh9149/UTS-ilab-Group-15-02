"""Admission checks for the dedicated Linux Docker host, not shared PBS nodes."""
from math import isfinite
import os
from pathlib import Path
import re
import shutil


def check_linux_host():
    # These paths are on the default Docker filesystem used by our bootstrap.
    docker_path = Path('/var/lib/docker')
    if not docker_path.is_dir():
        raise RuntimeError('Expected local Docker data directory is missing')
    paths = {'docker': docker_path, 'artifacts': Path(__file__).resolve().parents[1]}
    disks = {name: shutil.disk_usage(path).free for name, path in paths.items()}
    if min(disks.values()) < 20_000_000_000:
        raise RuntimeError('Host free space below 20 GB')
    info = Path('/proc/meminfo').read_text()
    values = {}
    for name in ('MemTotal', 'MemAvailable'):
        match = re.search(r'^' + name + r':\s+(\d+) kB$', info, re.M)
        if not match:
            raise RuntimeError('Linux memory availability signal missing')
        values[name] = int(match[1]) * 1024
    if not 0 <= values['MemAvailable'] <= values['MemTotal']:
        raise RuntimeError('Invalid Linux memory availability')
    # The largest frozen task requests 8 GiB; reserve 2 GiB for the host/agents.
    if values['MemAvailable'] < 10 * 1024**3:
        raise RuntimeError('Less than 10 GiB memory available for the next trial')
    cpu_count = len(os.sched_getaffinity(0))
    if cpu_count < 5:
        raise RuntimeError('Insufficient CPU headroom above the four-CPU task limit')
    pressure = Path('/proc/pressure/memory').read_text()
    match = re.search(r'^full avg10=(\S+)', pressure, re.M)
    if not match:
        raise RuntimeError('Linux memory pressure signal missing')
    full = float(match[1])
    if not isfinite(full) or not 0 <= full < 10:
        raise RuntimeError('Linux memory pressure critical or invalid')
    return {'free_disk_bytes': min(disks.values()), 'disk_free_by_role': disks,
            'memory_available_bytes': values['MemAvailable'],
            'memory_total_bytes': values['MemTotal'], 'available_cpus': cpu_count,
            'memory_full_stall_avg10_percent': full,
            'thermal': 'not_exposed_by_virtual_machine', 'host_os': 'Linux'}
