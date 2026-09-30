"""Controller-only loopback proxy. API key never enters the task environment."""
import asyncio
import json
import secrets
import time
from aiohttp import ClientSession, ClientTimeout, web
from gemini_laptop_policy import (MODEL, SNAPSHOT, PROVIDER, CONTEXT, MAX_OUTPUT,
    INPUT_PRICE, OUTPUT_PRICE, Ledger, BudgetStop, money, wire, atomic_json)

ORIGIN = 'https://openrouter.ai/api/v1'


class Gateway:
    def __init__(self, key, private_dir):
        self.key, self.directory = key, private_dir
        self.token = secrets.token_hex(32)
        self.active = None
        self.pending = set()
        self.stop_reason = None
        self.recorder = None
        self.trace_errors = []

    async def get(self, path):
        async with self.session.get(ORIGIN + path,
                headers={'Authorization': 'Bearer ' + self.key}, allow_redirects=False) as response:
            if response.status != 200:
                raise RuntimeError('OpenRouter metadata HTTP ' + str(response.status))
            return (await response.json())['data']

    async def credit(self):
        key = await self.get('/key')
        credits = await self.get('/credits')
        remaining = min(money(key['limit_remaining']),
            max(money(credits['total_credits']) - money(credits['total_usage']), money(0)))
        return dict(available_usd=str(remaining), key_usage_usd=str(money(key['usage'])),
            key_limit_usd=str(money(key['limit'])))

    async def start(self):
        self.session = ClientSession(timeout=ClientTimeout(total=600))
        endpoints = (await self.get('/models/' + MODEL + '/endpoints'))['endpoints']
        endpoint = next(e for e in endpoints if e['tag'] == PROVIDER)
        if (endpoint['context_length'] != CONTEXT or endpoint['max_completion_tokens'] != MAX_OUTPUT
                or money(endpoint['pricing']['prompt']) > INPUT_PRICE
                or money(endpoint['pricing']['completion']) > OUTPUT_PRICE
                or SNAPSHOT not in endpoint['name']):
            raise RuntimeError('Model endpoint changed from frozen protocol')
        self.initial_credit = await self.credit()
        self.ledger = Ledger(self.directory / 'ledger.json', self.initial_credit['available_usd'])
        app = web.Application(client_max_size=16 * 1024**2)
        app.router.add_post('/v1/chat/completions', self.handle)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await self.site.start()
        self.url = 'http://127.0.0.1:' + str(self.site._server.sockets[0].getsockname()[1]) + '/v1'
        self.lock = asyncio.Lock()
        return self.initial_credit

    def activate(self, trial_id, deadline):
        if self.active is not None or self.pending or self.stop_reason:
            raise RuntimeError('Gateway not ready for another trial')
        self.active = (trial_id, deadline)

    async def revoke(self):
        self.active = None
        if self.pending:
            await asyncio.gather(*list(self.pending), return_exceptions=True)

    async def handle(self, request):
        if request.headers.get('Authorization') != 'Bearer ' + self.token or not self.active:
            return web.json_response({'error': {'message': 'Trial authorization revoked'}}, status=403)
        try:
            payload = wire(await request.json())
        except Exception:
            return web.json_response({'error': {'message': 'Unsupported request protocol'}}, status=400)
        trial = self.active
        operation = asyncio.create_task(self.dispatch(payload, trial))
        self.pending.add(operation)
        operation.add_done_callback(self.pending.discard)
        return await asyncio.shield(operation)

    async def dispatch(self, payload, trial):
        async with self.lock:
            if self.active != trial or self.stop_reason or time.monotonic() >= trial[1]:
                return web.json_response({'error': {'message': 'Trial deadline or study stop'}}, status=403)
            try:
                credit = await self.credit()
                row = self.ledger.reserve(trial[0], credit['available_usd'])
            except BudgetStop:
                self.stop_reason = 'budget_stop'
                return web.json_response({'error': {'message': 'US dollar budget stop'}}, status=402)
            except Exception:
                self.stop_reason = 'credit_check_failed'
                return web.json_response({'error': {'message': 'Credit check unavailable'}}, status=503)
            row['started_ns'] = time.time_ns()
            self.ledger.save()
            exchange = self.directory / 'exchanges' / ('%06d' % row['sequence'])
            atomic_json(exchange.with_suffix('.request.json'), payload)
            try:
                timeout = ClientTimeout(total=max(0.1, min(600, trial[1] - time.monotonic())))
                async with self.session.post(ORIGIN + '/chat/completions', json=payload,
                        headers={'Authorization': 'Bearer ' + self.key}, timeout=timeout,
                        allow_redirects=False) as response:
                    body = await response.json()
                    atomic_json(exchange.with_suffix('.response.json'), body)
                    row['http_status'] = response.status
                    row['generation_id'] = body.get('id')
                    usage = body.get('usage') or {}
                    for key in ('prompt_tokens', 'completion_tokens'):
                        if type(usage.get(key)) is int:
                            row[key] = usage[key]
                    if row.get('generation_id'):
                        try:
                            receipt = await self.get('/generation?id=' + row['generation_id'])
                            atomic_json(exchange.with_suffix('.receipt.json'), receipt)
                            row.update(provider=receipt.get('provider_name'),
                                resolved_model=receipt.get('model'))
                            if receipt.get('total_cost') is not None:
                                self.ledger.settle(row, receipt['total_cost'])
                        except Exception:
                            pass
                    if row.get('cost_usd') is None and usage.get('cost') is not None:
                        self.ledger.settle(row, usage['cost'])
                    if response.status != 200:
                        # Failed or timed out requests are never blindly retried.
                        self.stop_reason = 'provider_http_' + str(response.status)
                        return web.json_response({'error': {'message': self.stop_reason}}, status=502)
                    if body.get('model') not in {MODEL, SNAPSHOT} or body.get('provider') not in {'Google AI Studio'}:
                        self.stop_reason = 'routing_mismatch'
                        return web.json_response({'error': {'message': 'Provider routing mismatch'}}, status=502)
                    row.setdefault('resolved_model', body['model'])
                    row.setdefault('provider', body['provider'])
                    return web.json_response(body)
            except Exception as error:
                row['error_type'] = type(error).__name__
                self.stop_reason = 'provider_transport_failure'
                return web.json_response({'error': {'message': 'Provider transport failure; charge unresolved'}}, status=502)
            finally:
                row['ended_ns'] = time.time_ns()
                self.ledger.save()
                if self.recorder:
                    metrics = {'requests':1}
                    if row.get('prompt_tokens') is not None: metrics['input_tokens'] = row['prompt_tokens']
                    if row.get('completion_tokens') is not None: metrics['output_tokens'] = row['completion_tokens']
                    if row.get('cost_usd') is not None: metrics['charged_nanodollars'] = int(money(row['cost_usd'])*10**9)
                    try:
                        self.recorder(kind='generation',started_ns=row['started_ns'],ended_ns=row['ended_ns'],
                            seconds=(row['ended_ns']-row['started_ns'])/10**9,
                            status='error' if self.stop_reason else 'ok',metrics=metrics)
                    except Exception as error:
                        self.trace_errors.append(type(error).__name__)

    async def reconcile(self):
        for row in self.ledger.data['requests']:
            if row.get('cost_usd') is None and row.get('generation_id'):
                try:
                    data = await self.get('/generation?id=' + row['generation_id'])
                    self.ledger.settle(row, data['total_cost'])
                except Exception:
                    pass

    async def close(self):
        await self.revoke()
        await self.reconcile()
        await self.runner.cleanup()
        await self.session.close()
