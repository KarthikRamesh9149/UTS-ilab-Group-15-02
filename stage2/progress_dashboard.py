"""Loopback-only progress panel. Reads result metadata over SSH; never runs trials.

Run locally: python stage2/progress_dashboard.py [--port 8769]
GET / serves the bundled page; GET /status.json serves allowlisted metadata.
The browser polls every five seconds; one background reader polls SSH at most
once per sixty seconds. Failure retains the last snapshot and marks it stale.
No API, ledger, prompt, response, task source or credential contents are read.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import subprocess
import threading
import time

STAGE2 = Path(__file__).resolve().parent
REPO = STAGE2.parent
POLL_SECONDS = 60
STALE_SECONDS = 120
HOST = '127.0.0.1'
REMOTE_HOST = 'root@62.83.32.126'
SERVICE = 'uts-stage2-qualification-netcupv8.service'
MAX_METADATA_BYTES = 2 * 1024 * 1024
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z')

# Fixed program, passed on stdin to python3 over SSH. Only these two metadata
# filenames and one service state are read. Nothing is written on the server.
REMOTE_READER = r'''
import datetime,json,math,pathlib,subprocess
root=pathlib.Path('/opt/uts-capstone/.runtime/stage2/scored-trials')
records=[]; errors=[]
if not root.is_dir() or root.is_symlink():
    raise RuntimeError('metadata root unavailable')
directories=sorted(root.iterdir())
if len(directories)>4000:
    raise RuntimeError('metadata directory bound exceeded')
for trial in directories:
    if trial.is_symlink() or not trial.is_dir():
        continue
    paths={name:trial/name for name in ('started.json','result.json')}
    present={name:path.is_file() and not path.is_symlink() for name,path in paths.items()}
    if not any(present.values()):
        continue
    name='result.json' if present['result.json'] else 'started.json'
    path=paths[name]
    try:
        if path.stat().st_size>1048576:
            raise ValueError('metadata size')
        raw=json.loads(path.read_text())
        if not isinstance(raw,dict):
            raise ValueError('metadata shape')
        billing=raw.get('billing') if isinstance(raw.get('billing'),dict) else {}
        verifier=raw.get('verifier_result') if isinstance(raw.get('verifier_result'),dict) else {}
        rewards=verifier.get('rewards') if isinstance(verifier.get('rewards'),dict) else {}
        row={key:raw.get(key) for key in ('trial_id','task_id','stage','harness','status')}
        row['reward']=rewards.get('reward')
        row.update(directory=trial.name,has_started=present['started.json'],has_result=present['result.json'],
                   billing_verified=billing.get('billing_verified'),budget_stop_count=billing.get('budget_stop_count'))
        records.append(row)
    except (OSError,ValueError,TypeError):
        errors.append({'trial_id':trial.name,'kind':'metadata_unreadable'})
service=subprocess.run(['systemctl','show','uts-stage2-qualification-netcupv8.service',
                        '--property=ActiveState','--property=SubState'],capture_output=True,text=True,timeout=5,check=True)
state={}
for line in service.stdout.splitlines():
    if '=' in line:
        key,value=line.split('=',1)
        if key in ('ActiveState','SubState'):
            state[key]=value
print(json.dumps({'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'service':state,'records':records,'read_errors':errors},allow_nan=False))
'''


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError('UTC timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def load_json(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError('Local metadata exceeds bound')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('Object required')
    return result


def load_curated(path):
    value = load_json(path)
    required = {'engineering': ('updated_at_utc','status','detail','source'),
                'financial_snapshot': ('observed_at_utc','available_account_credit_usd',
                                       'known_project_charges_usd','unresolved_holds_usd','note')}
    for section, keys in required.items():
        if not isinstance(value.get(section),dict) or any(not isinstance(value[section].get(k),str) for k in keys):
            raise ValueError('Incomplete curated section')
    if not isinstance(value.get('pipeline'),list) or any(
        not isinstance(item,dict) or any(not isinstance(item.get(k),str) for k in ('name','state','detail'))
        for item in value['pipeline']):
        raise ValueError('Incomplete curated pipeline')
    conditions = value.get('custom_conditions', {})
    if not isinstance(conditions,dict) or any(conditions.get(k) not in (None,'C0','C1','C2')
        for k in ('development_harness','frozen_final_harness')):
        raise ValueError('Invalid explicit custom condition')
    return value


def expected_cells(manifest):
    dev = manifest.get('development_ids'); final = manifest.get('all_task_ids')
    if not isinstance(dev, list) or not isinstance(final, list) or len(dev) != 20 or len(final) != 89:
        raise ValueError('Frozen 20 and 89 task lists required')
    if (any(not isinstance(t, str) or not SAFE_ID.fullmatch(t) for t in dev+final)
        or len(set(dev)) != 20 or len(set(final)) != 89 or not set(dev) <= set(final)):
        raise ValueError('Invalid frozen task identities')
    expected = {}
    for harness in ('terminus-2', 'openhands', 'C0', 'C1', 'C2'):
        track = {'terminus-2':'initial_terminus', 'openhands':'openhands_development'}.get(harness, 'custom_development')
        for index, task in enumerate(dev):
            expected[f'dev-{harness}-{index:02d}-{task}'] = dict(task_id=task, stage='development',
                harnesses=(harness,), track=track)
    for role, track in [('terminus-2','final_terminus'),('openhands','final_openhands'),('custom','final_custom')]:
        for index, task in enumerate(sorted(final)):
            expected[f'final-{role}-{index:02d}-{task}'] = dict(task_id=task, stage='final',
                harnesses=('C0','C1','C2') if role == 'custom' else (role,), track=track)
    return expected


def empty_track(target):
    return dict(target=target, attempted=0, billing_verified=0, verified=0, passes=0, unknown=0, budget_stops=0)


def summarise(records, manifest, development_harness=None, frozen_final_harness=None):
    """Count exact registered cells; duplicate attempts never manufacture progress."""
    if not isinstance(records, list) or len(records) > 4000:
        raise ValueError('Invalid remote record collection')
    expected = expected_cells(manifest)
    if development_harness not in (None,'C0','C1','C2') or frozen_final_harness not in (None,'C0','C1','C2'):
        raise ValueError('Invalid explicit custom condition')
    tracks = {name:empty_track(target) for name,target in (
        ('final_terminus',89),('final_openhands',89),('custom_development',20),('final_custom',89),
        ('initial_terminus',20),('openhands_development',20))}
    accepted = {}; duplicates = set(); ignored = 0; rejected = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('Invalid remote record')
        trial = record.get('trial_id')
        if trial not in expected:
            ignored += 1
            continue
        spec = expected[trial]
        if (record.get('directory') != trial or record.get('task_id') != spec['task_id']
            or record.get('stage') != spec['stage'] or record.get('harness') not in spec['harnesses']):
            rejected.append(trial)
            continue
        if type(record.get('has_result')) is not bool or type(record.get('has_started')) is not bool:
            raise ValueError('Invalid record presence flags')
        if not record['has_result'] and not record['has_started']:
            continue
        if trial in accepted:
            duplicates.add(trial)
            continue
        billing_verified = record['has_result'] and record.get('billing_verified') is True
        reward = record.get('reward')
        reward = reward if type(reward) in (int,float) and math.isfinite(reward) and reward in (0,1) else None
        verified = billing_verified and record.get('status') == 'verified' and reward is not None
        if spec['track'] == 'final_custom' and record['harness'] != frozen_final_harness:
            verified = False
        stops = record.get('budget_stop_count')
        stops = stops if type(stops) is int and stops >= 0 else None
        accepted[trial] = dict(trial_id=trial, task_id=spec['task_id'], harness=record['harness'],
            stage=spec['stage'], track=spec['track'], billing_verified=billing_verified, verified=verified,
            passed=verified and reward == 1,
            reward=reward if verified else None, budget_stop_count=stops,
            budget_stopped=billing_verified and stops is not None and stops > 0,
            has_result=record['has_result'], duplicate=False)
    # Ambiguous repeated cells count as one attempted, unverified cell. Never
    # select a favourable result or silently declare a repeated cell complete.
    for trial in duplicates:
        accepted[trial].update(billing_verified=False, verified=False, passed=False, reward=None,
                               budget_stop_count=None, budget_stopped=False, duplicate=True)
    for name, track in tracks.items():
        selected = [r for r in accepted.values() if r['track'] == name]
        if name == 'custom_development':
            selected = [r for r in selected if r['harness'] == development_harness]
        attempted = {r['task_id'] for r in selected}
        verified = {r['task_id'] for r in selected if r['verified']}
        track.update(attempted=len(attempted), verified=len(verified),
                     billing_verified=len({r['task_id'] for r in selected if r['billing_verified']}),
                     passes=len({r['task_id'] for r in selected if r['passed']}),
                     unknown=len(attempted-verified),
                     budget_stops=len({r['task_id'] for r in selected if r['budget_stopped']}))
    custom_variants = {}
    for harness in ('C0','C1','C2'):
        selected = [r for r in accepted.values() if r['track'] == 'custom_development' and r['harness'] == harness]
        custom_variants[harness] = dict(target=20, attempted=len(selected), verified=sum(r['verified'] for r in selected),
                                       billing_verified=sum(r['billing_verified'] for r in selected),
                                       passes=sum(r['passed'] for r in selected), unknown=sum(not r['verified'] for r in selected))
    initial_rows = [r for r in accepted.values() if r['track'] == 'initial_terminus']
    initial_rows.sort(key=lambda r:manifest['development_ids'].index(r['task_id']))
    return dict(tracks=tracks, custom_variants=custom_variants, initial_trials=initial_rows,
                custom_conditions=dict(development_harness=development_harness, frozen_final_harness=frozen_final_harness),
                duplicate_cells=sorted(duplicates), rejected_records=sorted(set(rejected)), ignored_records=ignored)


def ssh_command(repo=REPO):
    return ['ssh','-F','/dev/null','-i',str(Path(repo)/'.runtime/netcup/id_ed25519'),
            '-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','BatchMode=yes',
            '-o','UserKnownHostsFile='+str(Path(repo)/'.runtime/netcup/known_hosts'),
            '-o','ConnectTimeout=10','-o','ConnectionAttempts=1','-o','ClearAllForwardings=yes',
            '-o','RequestTTY=no','-o','LogLevel=ERROR',REMOTE_HOST,'python3','-']


def fetch_remote():
    result = subprocess.run(ssh_command(), input=REMOTE_READER, text=True, capture_output=True,
                            timeout=20, check=True)
    if len(result.stdout.encode()) > MAX_METADATA_BYTES:
        raise ValueError('Remote metadata exceeds bound')
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or data.get('read_errors'):
        raise ValueError('Remote metadata snapshot incomplete')
    return data


class ProgressMonitor:
    def __init__(self, manifest, curated_path=STAGE2/'progress_status.json', *, fetcher=fetch_remote,
                 clock=time.monotonic, utc_clock=now_utc):
        expected_cells(manifest)
        self.manifest = manifest; self.curated_path = Path(curated_path)
        self.fetcher = fetcher; self.clock = clock; self.utc_clock = utc_clock
        self.lock = threading.Lock(); self.last_attempt = None; self.checking = False
        self.curated = load_curated(self.curated_path)
        self.snapshot = copy.deepcopy(self.curated['last_remote_snapshot'])
        self.source = 'recorded_checkpoint'; self.reachable = None; self.last_check = None
        self.error = None

    def refresh(self):
        with self.lock:
            current = self.clock()
            if self.checking or self.last_attempt is not None and current-self.last_attempt < POLL_SECONDS:
                return False
            self.checking = True; self.last_attempt = current
        try:
            raw = self.fetcher()
            observed = parse_utc(raw.get('observed_at_utc')).isoformat().replace('+00:00','Z')
            service = raw.get('service')
            if (not isinstance(service, dict) or set(service) != {'ActiveState','SubState'}
                or any(not isinstance(v,str) or not SAFE_ID.fullmatch(v) for v in service.values())):
                raise ValueError('Invalid service state')
            conditions = self.curated.get('custom_conditions', {})
            aggregate = summarise(raw.get('records'), self.manifest, conditions.get('development_harness'),
                                  conditions.get('frozen_final_harness'))
            if aggregate['rejected_records']:
                raise ValueError('Registered trial metadata mismatch')
            updated = dict(aggregate, observed_at_utc=observed, service=service)
            with self.lock:
                self.snapshot = updated; self.source = 'live_read_only_metadata'; self.reachable = True; self.error = None
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
            with self.lock:
                self.reachable = False
                self.error = 'Read-only server check failed ('+type(exc).__name__+'). Last snapshot retained.'
        finally:
            with self.lock:
                self.last_check = self.utc_clock(); self.checking = False
        return True

    def status(self):
        # The operator can update this single curated local file independently
        # of remote polling. A malformed edit does not erase the last metadata.
        try:
            curated = load_curated(self.curated_path)
            with self.lock:
                self.curated = curated
        except (OSError,ValueError):
            pass
        with self.lock:
            snapshot = copy.deepcopy(self.snapshot); curated = copy.deepcopy(self.curated)
            age = max(0,(parse_utc(self.utc_clock())-parse_utc(snapshot['observed_at_utc'])).total_seconds())
            stale = self.reachable is not True or age > STALE_SECONDS
            return {'schema_version':1, 'model':'DeepSeek V4 Flash 0731', 'endpoint':'deepinfra/fp8',
                    'browser_poll_seconds':5, 'remote_poll_seconds':POLL_SECONDS,
                    'remote':dict(snapshot, stale=stale, reachable=self.reachable, source=self.source,
                                  last_check_utc=self.last_check, age_seconds=round(age), error=self.error),
                    'engineering':curated['engineering'], 'pipeline':curated['pipeline'],
                    'financial_snapshot':curated['financial_snapshot']}


def make_handler(monitor, html):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            expected_hosts = {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in expected_hosts:
                self.send_error(403, 'Loopback host required'); return
            if self.path == '/':
                body = html; content_type = 'text/html; charset=utf-8'
            elif self.path == '/status.json':
                body = json.dumps(monitor.status(), allow_nan=False).encode(); content_type = 'application/json; charset=utf-8'
            else:
                self.send_error(404, 'Route not available'); return
            self.send_response(200)
            self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            self.send_error(405, 'Read-only server')
    return Handler


def create_server(monitor, port=8769):
    html = (STAGE2/'progress_dashboard.html').read_bytes()
    server = ThreadingHTTPServer((HOST,port), make_handler(monitor,html))
    server.daemon_threads = True
    return server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8769)
    args=parser.parse_args()
    monitor=ProgressMonitor(load_json(STAGE2/'input_manifest.json'))
    stop=threading.Event()
    def poll():
        while not stop.is_set():
            monitor.refresh(); stop.wait(POLL_SECONDS)
    server=create_server(monitor,args.port)
    worker=threading.Thread(target=poll,daemon=True); worker.start()
    print(f'Read-only progress: http://127.0.0.1:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set(); server.server_close()


if __name__ == '__main__':
    main()
