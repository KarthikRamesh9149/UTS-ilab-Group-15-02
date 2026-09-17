from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
import http.client
import json
import os
from pathlib import Path
import socketserver
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, AsyncMock
from urllib.parse import urlsplit

from local_study import LocalProtocol
from local_trace import PhaseRecorder, TraceSpool
from local_observation import DetailObserver
from local_model_client import LocalModelClient
from local_model_gateway import serve
from local_baselines import baseline_config, create_baseline
from local_langfuse import payload


def request():
    p = LocalProtocol()
    return dict(model=p.model, temperature=p.temperature, top_p=p.top_p, top_k=p.top_k,
                max_tokens=8, messages=[{'role': 'user', 'content': 'PRIVATE_FIXTURE_TEXT'}])


@contextmanager
def fixture_server(*, status=200, usage=True):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            result = dict(id='local-fixture', object='chat.completion', created=1, model=LocalProtocol().model,
                choices=[{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'PRIVATE_RESPONSE'}}])
            if usage: result['usage'] = dict(prompt_tokens=12, completion_tokens=3, total_tokens=15)
            encoded = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    with tempfile.TemporaryDirectory(prefix='uts-', dir='/tmp') as tmp:
        socket = Path(tmp).resolve() / 'model.sock'
        server = socketserver.UnixStreamServer(str(socket), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try: yield socket, calls
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


class LocalConnectionTests(unittest.TestCase):
    def test_real_unix_http_tokens_redaction_and_export_payload(self):
        with fixture_server() as (socket, calls), tempfile.TemporaryDirectory() as tmp:
            recorder = PhaseRecorder(TraceSpool(tmp), trial_id='fixture', task_id='fixture',
                                     harness='terminus-2', protocol_sha256='a'*64)
            detail = DetailObserver(recorder)
            start = time.time_ns()
            client = LocalModelClient(socket, observer=detail)
            result = client.complete(request())
            recorder(kind='trial', started_ns=start, ended_ns=time.time_ns(), seconds=0.01)
            self.assertEqual(result['choices'][0]['message']['content'], 'PRIVATE_RESPONSE')
            events = recorder.spool.events()
            generation = next(e for e in events if e['kind'] == 'generation')
            self.assertEqual(generation['metrics']['input_tokens'], 12)
            self.assertEqual(generation['metrics']['output_tokens'], 3)
            self.assertEqual(client.requests, 1)
            exported = json.dumps(payload(events))
            self.assertNotIn('PRIVATE_', exported)
            self.assertIn('gen_ai.usage.input_tokens', exported)
            self.assertEqual(len(calls), 1)

    def test_failed_requests_count_without_retries(self):
        with fixture_server(status=503) as (socket, calls):
            client = LocalModelClient(socket)
            with self.assertRaises(RuntimeError): client.complete(request())
            self.assertEqual(client.requests, 1)
            self.assertEqual(len(calls), 1)

    def test_budget_and_revocation_prevent_new_requests(self):
        with fixture_server() as (socket, calls):
            client = LocalModelClient(socket)
            client.requests = 99
            client.complete(request())
            with self.assertRaises(RuntimeError): client.complete(request())
            self.assertEqual(len(calls), 1)
            client.revoke()
            with self.assertRaises(RuntimeError): client.complete(request())

    def test_missing_usage_is_not_invented(self):
        with fixture_server(usage=False) as (socket, calls):
            self.assertNotIn('usage', LocalModelClient(socket).complete(request()))

    def test_protocol_and_external_routing_rejected_before_send(self):
        with fixture_server() as (socket, calls):
            client = LocalModelClient(socket)
            for change in ({'model': 'other'}, {'temperature': 0.0}, {'provider': {}},
                           {'stream': True}, {'extra_body': {'top_k': 1}}, {'max_tokens': 9000}):
                with self.assertRaises(ValueError): client.complete(dict(request(), **change))
            self.assertEqual(client.requests, 0)
            self.assertEqual(calls, [])
        for path in ('https://external.example/v1', '/tmp/not-a-socket'):
            with self.assertRaises((ValueError, FileNotFoundError)): LocalModelClient(path)

    def test_extra_body_top_k_is_normalized(self):
        with fixture_server() as (socket, calls):
            data = request()
            data['extra_body'] = {'top_k': data.pop('top_k')}
            LocalModelClient(socket).complete(data)
            self.assertEqual(calls[0]['top_k'], 40)
            self.assertNotIn('extra_body', calls[0])

    def test_detail_failure_does_not_change_response(self):
        def broken(**kwargs): raise OSError('private data must not leak')
        observer = DetailObserver(broken)
        with fixture_server() as (socket, calls):
            result = LocalModelClient(socket, observer=observer).complete(request())
            self.assertTrue(result['choices'])
        self.assertEqual(observer.errors, ['generation:OSError'])

    def test_loopback_gateway_auth_end_to_end_and_revoke(self):
        with fixture_server() as (socket, calls):
            client = LocalModelClient(socket)
            with serve(client) as (base, token):
                parsed = urlsplit(base)
                for credential, expected in [('wrong', 401), (token, 200)]:
                    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
                    connection.request('POST', '/v1/chat/completions', json.dumps(request()),
                                       {'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    response.read()
                    connection.close()
            self.assertTrue(client.revoked)
            self.assertEqual(len(calls), 1)


class LocalBaselineTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_terminus_client_through_local_gateway_and_unix_fixture(self):
        with fixture_server() as (socket, calls), tempfile.TemporaryDirectory() as tmp:
            client = LocalModelClient(socket)
            with serve(client) as (base, token):
                agent = create_baseline('terminus-2', logs_dir=Path(tmp), api_base=base, trial_token=token)
                response = await agent._llm.call('PRIVATE_INPUT', **agent._llm_call_kwargs)
                self.assertEqual(response.content, 'PRIVATE_RESPONSE')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]['top_k'], 40)
                self.assertEqual(calls[0]['top_p'], 0.95)
                self.assertEqual(calls[0]['max_tokens'], 8192)
                self.assertEqual(calls[0]['model'], LocalProtocol().model)

    async def test_openhands_installer_uses_existing_hash_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = create_baseline('openhands', logs_dir=Path(tmp), api_base='http://127.0.0.1:1234/v1', trial_token='fixture')
            environment = AsyncMock()
            environment.default_user = 'root'
            with patch.object(agent, 'ensure_system_dependencies', new_callable=AsyncMock), \
                 patch.object(agent, 'exec_as_root', new_callable=AsyncMock), \
                 patch.object(agent, 'exec_as_agent', new_callable=AsyncMock) as execute:
                await agent.install(environment)
            self.assertIn('--require-hashes', execute.call_args.kwargs['command'])
            self.assertEqual(environment.upload_file.call_args.args[0].name, 'openhands-requirements.lock')

    def test_same_native_model_limits_and_no_iteration_changes(self):
        for harness in ('terminus-2', 'openhands'):
            cfg = baseline_config(harness, api_base='http://127.0.0.1:1234/v1', trial_token='fixture')
            self.assertEqual(cfg['model_name'], 'openai/' + LocalProtocol().model)
            self.assertEqual(cfg['model_info']['max_output_tokens'], 8192)
            self.assertEqual(cfg['model_info']['max_input_tokens'], 24576)
            self.assertNotIn('max_iterations', cfg)
            self.assertNotIn('max_turns', cfg)
            self.assertNotIn('openrouter', json.dumps(cfg).lower())

    def test_external_baseline_endpoint_rejected(self):
        for url in ('https://openrouter.ai/api/v1', 'http://example.com:8000/v1',
                    'http://user:secret@127.0.0.1:1234/v1', 'http://127.0.0.1:1234/v1?x=y'):
            with self.assertRaises(ValueError): baseline_config('openhands', api_base=url, trial_token='fixture')

    async def test_real_native_constructors_and_openhands_forwarding(self):
        with tempfile.TemporaryDirectory() as tmp:
            for harness in ('terminus-2', 'openhands'):
                agent = create_baseline(harness, logs_dir=Path(tmp), api_base='http://127.0.0.1:1234/v1', trial_token='fixture')
                self.assertEqual(agent.model_name, 'openai/' + LocalProtocol().model)
                if harness == 'openhands':
                    with patch('harbor.agents.installed.openhands.OpenHands.exec_as_agent', new_callable=AsyncMock) as run:
                        await agent.exec_as_agent(None, 'fixture', env={'LLM_MODEL': agent.model_name, 'LLM_REASONING_EFFORT': 'high'})
                        forwarded = run.call_args.kwargs['env']
                        self.assertNotIn('LLM_REASONING_EFFORT', forwarded)
                        self.assertEqual(forwarded['LLM_TIMEOUT'], '120')
                        self.assertIn("'top_k': 40", forwarded['LLM_COMPLETION_KWARGS'])


if __name__ == '__main__':
    unittest.main()
