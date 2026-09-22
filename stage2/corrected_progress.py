"""Read-only live progress for the corrected run; never reads keys or calls APIs."""
import copy
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading

from progress_dashboard import HOST, make_handler, ssh_command, parse_utc

SERVICE = 'uts-stage2-corrected-20260923.service'
REMOTE = r'''
from pathlib import Path
from datetime import datetime,timezone
import json,subprocess
r=Path('/opt/uts-capstone-corrected-20260923/.runtime/stage2')
registration=json.loads((r/'corrected-matrix.json').read_text())
cells=registration['cells']; rows=[]
assert len(cells)==178 and len({v['trial_id'] for v in cells})==178
for c in cells:
    folder=r/'scored-trials'/c['trial_id']
    if not folder.exists(): continue
    assert folder.is_dir() and not folder.is_symlink()
    done=(folder/'result.json').exists()
    path=folder/('result.json' if done else 'started.json')
    assert path.is_file() and not path.is_symlink() and path.stat().st_size<1048576
    value=json.loads(path.read_text())
    assert all(value.get(k)==c[k] for k in ('trial_id','task_id','harness'))
    reward=((value.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    rows.append(dict(trial_id=c['trial_id'],task_id=c['task_id'],harness=c['harness'],
        completed=done,reward=reward if type(reward) in (int,float) and reward in (0,1) else None,
        cleanup_complete=done and all(value.get(k) is True for k in ('containers_removed','networks_removed','volumes_removed'))))
state=subprocess.check_output(['systemctl','show','uts-stage2-corrected-20260923.service',
    '--property=ActiveState','--property=SubState'],text=True,timeout=5)
service=dict(line.split('=',1) for line in state.splitlines() if '=' in line)
print(json.dumps(dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),rows=rows,service=service)))
'''


def summarise(raw):
    rows = raw['rows']
    if not isinstance(rows, list) or len(rows) > 178: raise ValueError('Invalid record count')
    seen = set()
    manifest = json.loads(Path(__file__).with_name('input_manifest.json').read_text())
    expected = {(f'corrected1-final-{h}-{i:02d}-{t}', t, h)
        for h in ('terminus-2', 'openhands') for i, t in enumerate(sorted(manifest['all_task_ids']))}
    summary = {h: dict(completed=0, passed=0, failed=0, no_score=0, cleanup_issues=0, target=89)
               for h in ('terminus-2', 'openhands')}
    active = []
    for row in rows:
        key = (row['trial_id'], row['task_id'], row['harness'])
        if key not in expected or key in seen or type(row['completed']) is not bool:
            raise ValueError('Unregistered or duplicate cell')
        seen.add(key)
        if not row['completed']:
            active.append(row['harness'] + ': ' + row['task_id'])
            continue
        item = summary[row['harness']]
        item['completed'] += 1
        reward = row.get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1): item['no_score'] += 1
        elif reward == 1: item['passed'] += 1
        else: item['failed'] += 1
        item['cleanup_issues'] += row.get('cleanup_complete') is not True
    if len(active) > 1: raise ValueError('Unexpected concurrent or interrupted tasks')
    return dict(observed_at_utc=parse_utc(raw['observed_at_utc']).isoformat(),
        service=raw['service'], conditions=summary, active=active,
        completed=sum(v['completed'] for v in summary.values()), intended=178)


def fetch():
    result = subprocess.run(ssh_command(), input=REMOTE, text=True, capture_output=True, timeout=25, check=True)
    if len(result.stdout.encode()) > 1048576: raise ValueError('Unexpected metadata size')
    return summarise(json.loads(result.stdout))


class Monitor:
    def __init__(self, fetcher=fetch):
        self.fetcher, self.lock, self.value, self.error = fetcher, threading.Lock(), None, None
    def refresh(self):
        try:
            value = self.fetcher()
            with self.lock: self.value, self.error = value, None
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            with self.lock: self.error = type(exc).__name__
    def status(self):
        with self.lock:
            value = copy.deepcopy(self.value)
            error = self.error
        age = None if value is None else max(0., (datetime.now(timezone.utc) - parse_utc(value['observed_at_utc'])).total_seconds())
        return dict(snapshot=value, stale=value is None or error is not None or age > 120,
            error=error, age_seconds=None if age is None else round(age), read_only=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    monitor, stop = Monitor(), threading.Event()
    def poll():
        while not stop.is_set(): monitor.refresh(); stop.wait(60)
    server = ThreadingHTTPServer((HOST, args.port), make_handler(monitor,
        Path(__file__).with_name('corrected_progress.html').read_bytes()))
    server.daemon_threads = True
    threading.Thread(target=poll, daemon=True).start()
    print(f'Corrected run progress: http://127.0.0.1:{args.port}', flush=True)
    try: server.serve_forever()
    finally: stop.set(); server.server_close()
