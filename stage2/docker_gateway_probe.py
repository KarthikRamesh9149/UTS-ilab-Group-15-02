"""Two-container socket/HTTP integration fixture; no paid provider traffic.

No host ports, network access, upstream credential, or Docker socket is exposed
to either fixture. Cleanup targets only unique resources created by this run.
"""
import argparse
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

IMAGE = 'sha256:b6007a73910218ab068c7a9a7fb91e68f97017ab486af0ecd00403561a64e573'
SOCKET = '/socket/private/model.sock'
TOKEN = 'synthetic-fixture-token-not-a-real-credential'


def gateway_fixture():
    from budget_ledger import Ledger
    from gateway_core import Gateway, Trial, token_digest
    from gateway_http import make_unix_server
    from gateway_policy import MODEL
    Path('/socket/private').mkdir(mode=0o700)
    def factory():
        ledger = Ledger('/tmp/fixture.sqlite', '.1', '.055')
        def upstream(request):
            return {'id': 'synthetic-only', 'model': MODEL, 'usage': {'cost': '.001'},
                    'choices': [{'message': {'role': 'assistant', 'content': 'UTS_SOCKET_OK'}}]}
        return Gateway(ledger, Trial('fixture', 'development', token_digest(TOKEN)),
                       lambda: '25', lambda request: '.01', upstream,
                       lambda identifier: {'id': identifier, 'model': MODEL,
                           'provider_name': 'DeepInfra', 'total_cost': '.001'})
    with make_unix_server(factory, SOCKET) as server:
        server.serve_forever()


def client_fixture():
    from container_model_relay import make_relay
    from gateway_policy import MODEL
    relay = make_relay(SOCKET)
    thread = threading.Thread(target=relay.serve_forever, daemon=True)
    thread.start()
    def call(token, path='/v1/chat/completions'):
        conn = http.client.HTTPConnection(*relay.server_address, timeout=10)
        try:
            conn.request('POST', path, json.dumps({'model': MODEL,
                'messages': [{'role': 'user', 'content': 'Synthetic fixture'}], 'max_tokens': 32}),
                {'Authorization': 'Bearer ' + token})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()
    try:
        status, response = call(TOKEN)
        checks = {'completion_roundtrip': status == 200 and response['choices'][0]['message']['content'] == 'UTS_SOCKET_OK',
            'wrong_trial_denied': call('wrong')[0] == 403,
            'account_route_denied': call(TOKEN, '/credits')[0] == 404,
            'upstream_key_absent': 'OPENROUTER_API_KEY' not in os.environ,
            'host_home_absent': not Path('/Users/karthikramesh').exists(),
            'docker_socket_absent': not Path('/var/run/docker.sock').exists(),
            'no_network_interfaces': sorted(os.listdir('/sys/class/net')) == ['lo'],
            'ledger_absent': not Path('/tmp/fixture.sqlite').exists()}
        try:
            Path('/socket/private/unauthorised').touch()
            checks['socket_mount_readonly'] = False
        except OSError:
            checks['socket_mount_readonly'] = True
        print(json.dumps(checks))
    finally:
        relay.shutdown()
        relay.server_close()
        thread.join(timeout=3)


def run_probe(output):
    root = Path(__file__).resolve().parents[1]
    output = Path(output)
    if output.exists():
        raise ValueError('Refusing to overwrite previous evidence')
    prefix = 'uts-gateway-fixture-' + uuid.uuid4().hex[:10]
    volume, gateway, task = prefix + '-socket', prefix + '-gateway', prefix + '-task'
    containers = []
    created_volume = False
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE, timeout=120).strip()
    evidence = {'kind': 'real_docker_gateway_relay_with_scripted_upstream_not_scored',
                'time_utc': datetime.now(timezone.utc).isoformat(), 'image_id': IMAGE,
                'live_api_calls': 0, 'checks': {}}
    try:
        docker('image', 'inspect', IMAGE)
        docker('volume', 'create', '--label', 'uts.fixture=' + prefix, volume)
        created_volume = True
        common = ['--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                  '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
                  '--cpus', '1', '--memory', '256m', '--pids-limit', '64',
                  '--mount', 'type=bind,src=' + str(root / 'stage2') + ',dst=/code,readonly',
                  '--workdir', '/code', '--entrypoint', 'python']
        containers.append(gateway)
        docker('run', '-d', '--name', gateway, *common,
               '--mount', 'type=volume,src=' + volume + ',dst=/socket', IMAGE,
               'docker_gateway_probe.py', '--mode', 'gateway')
        for attempt in range(50):
            ready = subprocess.run(['docker', 'exec', gateway, 'test', '-S', SOCKET], capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Fixture gateway did not become ready')
        containers.append(task)
        result = docker('run', '--name', task, *common,
                        '--mount', 'type=volume,src=' + volume + ',dst=/socket,readonly', IMAGE,
                        'docker_gateway_probe.py', '--mode', 'client')
        evidence['checks'] = json.loads(result)
        rows = docker('exec', gateway, 'python', '-c',
                      "import sqlite3,json; print(json.dumps(sqlite3.connect('/tmp/fixture.sqlite').execute('SELECT state,charged FROM requests').fetchall()))")
        evidence['checks']['one_settled_scripted_request'] = json.loads(rows) == [['settled', 1000000]]
        for name in containers:
            ports = json.loads(docker('inspect', '--format', '{{json .HostConfig.PortBindings}}', name))
            evidence['checks'][name.rsplit('-', 1)[-1] + '_no_published_ports'] = not ports
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    finally:
        for name in reversed(containers):
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30, check=True)
        if created_volume:
            docker('volume', 'rm', volume)
    evidence['cleanup_completed'] = True
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2)
        handle.write('\n')
    print(json.dumps(evidence, indent=2))
    if evidence['status'] != 'passed':
        raise RuntimeError('Fixture checks failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['gateway', 'client', 'probe'], default='probe')
    parser.add_argument('--output', default='stage2/docker_gateway_probe_result.json')
    args = parser.parse_args()
    if args.mode == 'gateway':
        gateway_fixture()
    elif args.mode == 'client':
        client_fixture()
    else:
        run_probe(args.output)
