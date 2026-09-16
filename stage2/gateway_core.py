"""Gateway dispatch core with separate hard and estimated trial reservations.

Only the host supplies the estimator, balance reader and upstream transport.
Agent payloads cannot choose them. There is deliberately no live default or
retry loop. Missing/ambiguous billing retains the reservation and blocks work.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import hmac
import threading
import uuid

from budget_ledger import dollars
from gateway_policy import MODEL, CANONICAL_MODEL, prepare_request


class GatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class Trial:
    identifier: str
    stage: str
    token_digest: str


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def reconcile_receipt(response, receipt):
    if response.get('model') != MODEL or receipt.get('id') != response.get('id'):
        raise ValueError('Receipt identity mismatch')
    if receipt.get('model') not in {MODEL, CANONICAL_MODEL} or receipt.get('provider_name') != 'DeepInfra':
        raise ValueError('Receipt provider/model mismatch')
    cost = response['usage']['cost']
    actual = receipt.get('total_cost')
    for value in (cost, actual):
        if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
            raise ValueError('Missing exact receipt cost')
    if dollars(actual) != dollars(cost):
        raise ValueError('Costs disagree')
    return actual


class Gateway:
    def __init__(self, ledger, trial, balance_reader, maximum_charge, upstream, generation_reader=None, *, trial_estimate=None, request_policy=None):
        self.ledger = ledger
        self.trial = trial
        self.balance_reader = balance_reader
        self.maximum_charge = maximum_charge
        self.upstream = upstream
        self.generation_reader = generation_reader
        self.trial_estimate = trial_estimate
        self.request_policy = request_policy
        self.lock = threading.Lock()
        self.revoked = False

    def revoke(self):
        with self.lock:
            self.revoked = True

    def complete(self, token, payload):
        # One runner owns the ledger connection. Cross-process admission is
        # also protected by the ledger's BEGIN IMMEDIATE / pending barrier.
        with self.lock:
            if self.revoked or not isinstance(token, str) or not hmac.compare_digest(token_digest(token), self.trial.token_digest):
                raise GatewayError('Unauthorised trial')
            request = prepare_request(payload)
            if self.request_policy is not None:
                request = self.request_policy(request)
            if self.maximum_charge is None:
                raise GatewayError('No qualified request charge bound')
            if self.generation_reader is None:
                raise GatewayError('No billing reconciliation reader')
            maximum = self.maximum_charge(request)
            if dollars(maximum) <= 0:
                raise GatewayError('Invalid request charge bound')
            estimate = self.trial_estimate(request) if self.trial_estimate is not None else None
            balance = self.balance_reader()
            identifier = str(uuid.uuid4())
            self.ledger.reserve(identifier, self.trial.identifier, maximum, balance, self.trial.stage,
                                trial_estimate=estimate)
            try:
                response = self.upstream(request)
            except Exception:
                # Never release funds or replay on network errors. Exception
                # bodies may contain credentials, so do not relay them.
                raise GatewayError('Upstream outcome unknown; reservation retained') from None
            if not isinstance(response, dict) or response.get('model') != MODEL:
                raise GatewayError('Unverified response identity; reservation retained')
            self.ledger.attach_generation(identifier, response.get('id'))
            usage = response.get('usage')
            if not isinstance(usage, dict) or usage.get('cost') is None or not response.get('id'):
                raise GatewayError('Missing billing evidence; reservation retained')
            cost = usage['cost']
            if isinstance(cost, bool):
                raise GatewayError('Invalid billing evidence; reservation retained')
            try:
                dollars(cost)
            except (ValueError, TypeError, ArithmeticError):
                raise GatewayError('Invalid billing evidence; reservation retained') from None
            # Exact upstream decimal parsing is required of the transport.
            if not isinstance(cost, (str, int, Decimal)):
                raise GatewayError('Inexact billing evidence; reservation retained')
            try:
                receipt = self.generation_reader(response['id'])
                reconcile_receipt(response, receipt)
            except Exception:
                raise GatewayError('Billing reconciliation incomplete; reservation retained') from None
            self.ledger.settle(identifier, cost)
            return response
