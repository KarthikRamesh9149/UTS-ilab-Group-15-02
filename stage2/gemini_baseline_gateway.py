"""Shared-budget native gateway; authenticated task interface exists per trial."""
import json
from pathlib import Path
import time
from aiohttp import web
from gemini_baseline_budget import SharedBaselineLedger, ExtendedBaselineLedger
from gemini_laptop_gateway import Gateway
from gemini_laptop_policy import atomic_json, wire


class BaselineGateway(Gateway):
    def __init__(self, key, directory, *, prior_path, prior_sha256, cells, authorization=None):
        super().__init__(key, directory)
        self.prior_path, self.prior_sha256, self.cells = prior_path, prior_sha256, cells
        self.authorization = authorization
        self.task_site = None
        self.client_sequence = 0

    def create_ledger(self, available):
        if self.authorization is not None:
            return ExtendedBaselineLedger(self.directory / 'ledger.json', available,
                prior_path=self.prior_path, prior_sha256=self.prior_sha256,
                cells=self.cells, authorization=self.authorization)
        return SharedBaselineLedger(self.directory / 'ledger.json', available,
            prior_path=self.prior_path, prior_sha256=self.prior_sha256, cells=self.cells)

    async def attach_interface(self, address):
        if self.task_site is not None or self.active or self.pending:
            raise RuntimeError('Trial interface already attached')
        port = self.site._server.sockets[0].getsockname()[1]
        self.task_site = web.TCPSite(self.runner, address, port)
        await self.task_site.start()
        return f'http://{address}:{port}/v1'

    async def revoke(self):
        await super().revoke()
        if self.task_site is not None:
            await self.task_site.stop()
            self.task_site = None

    async def reconcile(self):
        # Inherited unresolved charges remain immutable; only reconcile this
        # comparison's requests with an authoritative generation identifier.
        count = len(self.ledger.prior['requests'])
        for row in self.ledger.data['requests'][count:]:
            if row.get('cost_usd') is None and row.get('generation_id'):
                try:
                    receipt = await self.get('/generation?id=' + row['generation_id'])
                    self.ledger.settle(row, receipt['total_cost'])
                except Exception:
                    pass

    async def handle(self, request):
        if request.headers.get('Authorization') != 'Bearer ' + self.token or not self.active:
            return web.json_response({'error': {'message': 'Trial authorization revoked'}}, status=403)
        self.client_sequence += 1
        try:
            raw = await request.json()
            atomic_json(self.directory / 'client-requests' / f'{self.client_sequence:06d}.json', raw)
            wire(raw)
        except Exception:
            self.stop_reason = 'invalid_client_protocol'
            return web.json_response({'error': {'message': 'Unsupported request protocol'}}, status=400)
        return await super().handle(request)

    async def dispatch(self, payload, trial):
        answer = await super().dispatch(payload, trial)
        rows = self.ledger.data['requests'][len(self.ledger.prior['requests']):]
        if rows and rows[-1].get('cost_usd') is None and not self.stop_reason:
            self.stop_reason = 'unresolved_charge'
        return answer
