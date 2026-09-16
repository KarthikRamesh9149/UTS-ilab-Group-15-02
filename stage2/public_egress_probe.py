"""Docker namespace firewall fixture. Never changes host firewall rules.

Tests public HTTPS alongside denial of a known-live private peer. Not a complete
runtime qualification: IPv6 and raw sockets are unavailable to task processes.
"""
import argparse
from datetime import datetime, timezone
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.request import urlopen
import uuid


def client(canary):
    checks = {}
    with urlopen('https://openrouter.ai/api/v1/models', timeout=20) as response:
        checks['public_https_works'] = response.status == 200
        response.read(1)
    ip = socket.gethostbyname(canary)
    checks['private_peer_dns_resolves'] = bool(ip)
    try:
        connection = socket.create_connection((ip, 8000), timeout=3)
        connection.close()
        checks['known_live_private_peer_blocked'] = False
    except OSError:
        checks['known_live_private_peer_blocked'] = True
    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        raw.close()
        checks['raw_socket_denied'] = False
    except PermissionError:
        checks['raw_socket_denied'] = True
    result = subprocess.run(['nft', 'list', 'ruleset'], capture_output=True)
    checks['task_cannot_control_firewall'] = result.returncode != 0
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_address[1]}', timeout=3) as response:
            checks['task_loopback_service_works'] = response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    checks['docker_socket_absent'] = not Path('/var/run/docker.sock').exists()
    checks['host_home_absent'] = not Path('/Users/karthikramesh').exists()
    checks['upstream_key_absent'] = 'OPENROUTER_API_KEY' not in os.environ
    print(json.dumps(checks))


def run_probe(root):
    output = root / 'stage2' / 'public_egress_probe_result.json'
    if output.exists():
        raise ValueError('Refusing to overwrite evidence')
    prefix = 'uts-egress-' + uuid.uuid4().hex[:10]
    network, canary, guard, task = [prefix + '-' + suffix for suffix in ['net', 'canary', 'guard', 'task']]
    created, network_created = [], False
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE, timeout=60).strip()
    image = docker('image', 'inspect', 'uts-stage2-egress-fixture:1', '--format', '{{.Id}}')
    evidence = {'kind': 'public_ipv4_egress_fixture_not_scored', 'time_utc': datetime.now(timezone.utc).isoformat(),
                'image_id': image, 'live_api_generations': 0, 'checks': {}}
    try:
        docker('network', 'create', '--label', 'uts.fixture=' + prefix, network)
        network_created = True
        docker('run', '-d', '--name', canary, '--network', network, '--cap-drop', 'ALL',
               '--cpus', '1', '--memory', '128m', '--entrypoint', 'python', image,
               '-m', 'http.server', '8000')
        created.append(canary)
        # Prove the peer is serving before interpreting any blocked connection.
        for attempt in range(30):
            result = subprocess.run(['docker', 'exec', canary, 'python', '-c',
                "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000',timeout=2).status==200"], capture_output=True, timeout=5)
            if result.returncode == 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Canary failed to start')
        evidence['checks']['canary_known_live'] = True
        docker('run', '-d', '--name', guard, '--network', network,
               '--cap-drop', 'ALL', '--cap-add', 'NET_ADMIN', '--security-opt', 'no-new-privileges:true',
               '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=4m',
               '--cpus', '1', '--memory', '128m', image)
        created.append(guard)
        for attempt in range(30):
            result = subprocess.run(['docker', 'exec', guard, 'test', '-e', '/tmp/ready'], capture_output=True, timeout=5)
            if result.returncode == 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Guard failed to install firewall; task not started')
        result = docker('run', '--name', task, '--network', 'container:' + guard,
            '--cap-drop', 'NET_RAW', '--security-opt', 'no-new-privileges:true',
            '--cpus', '1', '--memory', '256m', '--pids-limit', '64', '--entrypoint', 'python',
            '--mount', 'type=bind,src=' + str(root / 'stage2' / 'public_egress_probe.py') + ',dst=/probe.py,readonly',
            image, '/probe.py', '--client', canary)
        created.append(task)
        evidence['checks'].update(json.loads(result))
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    finally:
        # Include a task created by Docker even when its entrypoint exited nonzero.
        if task not in created and subprocess.run(['docker', 'inspect', task], capture_output=True).returncode == 0:
            created.append(task)
        for name in reversed(created):
            docker('rm', '-f', name)
        if network_created:
            docker('network', 'rm', network)
    evidence['cleanup_completed'] = True
    evidence['limitations'] = ['IPv4 public egress only; no IPv6 or raw task sockets.',
        'No host-wide or CETUS firewall was modified.',
        'This is not an adversarial audit or all89 task compatibility result.']
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2)
        handle.write('\n')
    print(json.dumps(evidence, indent=2))
    if evidence['status'] != 'passed':
        raise RuntimeError('Egress fixture failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--client')
    args = parser.parse_args()
    if args.client:
        client(args.client)
    else:
        run_probe(Path(__file__).resolve().parents[1])
