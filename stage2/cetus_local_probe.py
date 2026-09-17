"""Bounded trusted local-model qualification. Never executes model tool calls.

Python 3.6 compatible for CETUS. This is not a Harbor benchmark runner.
"""
import csv
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

REVISION = 'b82fb7382639d97b38fa7672e526c760c2fb358e'
LLAMA_REVISION = '4bc272fd729bd094c0422e4b8353da8d2fec91f8'
MODEL = 'Qwen3-Coder-Next-Q4_K_M'
SHARDS = [
    (15524827040, '6bcfc9f9c37901eeb92172e2ab871224dab36a453d263bcb2547f737409534da'),
    (14872168352, '817def0691ee9d08bf3dc4444be7aed29c9e52091e8fa9d97901ce7e7f6f01d3'),
    (14503294496, '23aa634d47dca9b4ca3ea249384e6f01951b24c83cdc076f37f6f43d6c99883f'),
    (3510702144, '249c768cc5f130dc731567d6edcbdacc48e14dec9e02c5dbe2b2185d2c5bdb2b'),
]


def run(args, **kwargs):
    return subprocess.check_output(args, universal_newlines=True, **kwargs)


def check_gpu_allocation(job, rows):
    if int(job['Resource_List'].get('ngpus', 0)) != 2:
        raise RuntimeError('Requires a scheduler allocation of two GPUs')
    # Fail closed rather than choosing arbitrary devices on a larger node.
    if len(rows) != 2:
        raise RuntimeError('Requires exactly two visible physical GPUs')
    for row in rows:
        if float(row[3]) < 44000 or float(row[4]) < 40000:
            raise RuntimeError('Insufficient GPU capacity/free VRAM for this candidate')


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path, timeout=180):
        super().__init__('localhost', timeout=timeout)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def request(path, endpoint, body=None):
    connection = UnixHTTP(path)
    try:
        connection.request('GET' if body is None else 'POST', endpoint,
                           None if body is None else json.dumps(body),
                           {'Content-Type': 'application/json'})
        response = connection.getresponse()
        data = response.read()
        if response.status != 200:
            raise RuntimeError('Model HTTP status {}'.format(response.status))
        return json.loads(data)
    finally:
        connection.close()


def tool_ok(response):
    calls = response['choices'][0]['message'].get('tool_calls', [])
    return (len(calls) == 1 and calls[0]['function']['name'] == 'add_numbers'
            and json.loads(calls[0]['function']['arguments']) == {'a': 2, 'b': 3})


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def main():
    os.umask(0o077)
    def interrupted(signum, frame):
        raise InterruptedError('Qualification interrupted by signal {}'.format(signum))
    signal.signal(signal.SIGTERM, interrupted)
    job_id = os.environ['PBS_JOBID']
    output = Path(os.environ['PBS_O_WORKDIR']) / ('local-probe-' + job_id)
    output.mkdir(mode=0o700, exist_ok=False)
    result = {'scope': 'synthetic_local_model_qualification', 'job': job_id,
              'model': MODEL, 'model_revision': REVISION,
              'runtime_revision': LLAMA_REVISION, 'benchmark_trials': 0,
              'harbor_integration': 'not_tested', 'checks': {}, 'complete': False}
    server = None
    try:
        jobs = json.loads(run(['qstat', '-f', '-F', 'json', job_id]))['Jobs']
        job = next(iter(jobs.values()))
        raw = run(['nvidia-smi', '--query-gpu=index,name,uuid,memory.total,memory.free,driver_version,compute_cap',
                   '--format=csv,noheader,nounits'])
        rows = [[field.strip() for field in row] for row in csv.reader(raw.splitlines())]
        result['gpu_inventory'] = rows
        result['scheduler_request'] = job['Resource_List']
        check_gpu_allocation(job, rows)
        result['checks']['gpu_capacity'] = True
        # Scheduler reserves both physical devices; selecting them does not
        # expand beyond this job's two-GPU allocation.
        os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(row[0] for row in rows)
        if shutil.disk_usage('/scratch').free < 110 * 1024**3:
            raise RuntimeError('Less than 110 GiB scratch available')
        work = Path(tempfile.mkdtemp(prefix='uts-local-model-', dir='/scratch'))
        result['scratch'] = str(work)
        print('scratch=' + str(work), flush=True)
        models = work / 'models'
        models.mkdir()
        for number, (size, digest) in enumerate(SHARDS, 1):
            name = '{}-{:05d}-of-00004.gguf'.format(MODEL, number)
            target = models / name
            url = 'https://huggingface.co/Qwen/Qwen3-Coder-Next-GGUF/resolve/{}/{}/{}'.format(REVISION, MODEL, name)
            print('downloading shard {}'.format(number), flush=True)
            subprocess.check_call(['curl', '--fail', '--location', '--silent', '--show-error',
                                   '--retry', '2', '--max-time', '900', '-o', str(target), url], timeout=1000)
            if target.stat().st_size != size:
                raise RuntimeError('Shard size mismatch')
            sha = hashlib.sha256()
            with target.open('rb') as stream:
                for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
                    sha.update(chunk)
            if sha.hexdigest() != digest:
                raise RuntimeError('Shard checksum mismatch')
        result['checks']['model_checksums'] = True
        source = work / 'llama.cpp'
        subprocess.check_call(['git', 'init', str(source)])
        subprocess.check_call(['git', '-C', str(source), 'fetch', '--depth', '1',
                               'https://github.com/ggml-org/llama.cpp.git', LLAMA_REVISION], timeout=180)
        subprocess.check_call(['git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD'])
        build = source / 'build'
        architectures = ';'.join(sorted(set(row[6].replace('.', '') for row in rows)))
        with (output / 'build.log').open('w') as log:
            subprocess.check_call(['cmake', '-S', str(source), '-B', str(build), '-DGGML_CUDA=ON',
                                   '-DCMAKE_CUDA_ARCHITECTURES=' + architectures,
                                   '-DLLAMA_CURL=OFF', '-DLLAMA_BUILD_TESTS=OFF'],
                                  stdout=log, stderr=subprocess.STDOUT, timeout=180)
            subprocess.check_call(['cmake', '--build', str(build), '-j', '8', '--target', 'llama-server'],
                                  stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        result['checks']['runtime_build'] = True
        endpoint = work / 'model.sock'
        with (output / 'server.log').open('w') as log:
            server = subprocess.Popen([str(build / 'bin/llama-server'), '-m', str(models / (MODEL + '-00001-of-00004.gguf')),
                                       '--host', str(endpoint), '-c', '32768', '-np', '1', '-ngl', '999',
                                       '--jinja', '--threads', '8', '--alias', MODEL],
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 600
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Model server exited during load; inspect server.log')
                try:
                    request(endpoint, '/health')
                    break
                except (OSError, RuntimeError, ValueError):
                    if time.monotonic() > deadline:
                        raise RuntimeError('Model load health timeout')
                    time.sleep(3)
            result['checks']['model_load'] = True
            cases = [
                ('generation', {'messages': [{'role': 'user', 'content': 'What is 2+3? Reply with only the integer.'}]}),
                ('tools', {'messages': [{'role': 'user', 'content': 'Call add_numbers with a=2 and b=3. Do not answer in text.'}],
                           'tools': [{'type': 'function', 'function': {'name': 'add_numbers',
                                      'description': 'Add two integers.', 'parameters': {'type': 'object',
                                      'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
                                      'required': ['a', 'b'], 'additionalProperties': False}}}],
                           'tool_choice': 'required'}),
                ('context', {'messages': [{'role': 'user', 'content': 'Remember marker ZEBRA_742.\n' +
                                         ('neutral filler words\n' * 3000) + '\nReturn only the marker.'}]}),
            ]
            for name, payload in cases:
                payload.update(model=MODEL, temperature=0, max_tokens=128)
                started = time.monotonic()
                response = request(endpoint, '/v1/chat/completions', payload)
                response['elapsed_seconds'] = time.monotonic() - started
                (output / (name + '.json')).write_text(json.dumps(response, indent=2))
                if name == 'tools':
                    result['checks'][name] = tool_ok(response)
                else:
                    expected = '5' if name == 'generation' else 'ZEBRA_742'
                    result['checks'][name] = response['choices'][0]['message']['content'].strip() == expected
            result['complete'] = all(result['checks'].values())
    except Exception as error:
        result['error'] = '{}: {}'.format(type(error).__name__, error)
        raise
    finally:
        if server is not None:
            stop(server)
        (output / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    sys.exit(main())
