"""Fixed-origin OpenRouter transport. CLI performs read-only checks only.

No retries, no redirects carrying credentials, no raw HTTP exception bodies.
Generation must be enabled explicitly by a qualified gateway, never by a client.
"""
from decimal import Decimal
import json
from pathlib import Path
import re
import stat
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlencode

BASE = 'https://openrouter.ai/api/v1'
ENDPOINTS = '/models/deepseek/deepseek-v4-flash-20260731/endpoints'
MAX_RESPONSE = 16 * 1024 * 1024


class TransportError(RuntimeError):
    def __init__(self, message='', *, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic


ERROR_TYPES = frozenset(('context_length_exceeded', 'max_tokens_exceeded',
    'token_limit_exceeded', 'string_too_long', 'authentication', 'permission_denied',
    'payment_required', 'rate_limit_exceeded', 'provider_overloaded',
    'provider_unavailable', 'invalid_request', 'invalid_prompt', 'not_found',
    'precondition_failed', 'payload_too_large', 'unprocessable',
    'content_policy_violation', 'refusal', 'invalid_image', 'image_too_large',
    'image_too_small', 'unsupported_image_format', 'image_not_found',
    'image_download_failed', 'server', 'timeout', 'unmapped'))


def error_diagnostic(document=None, *, status=None, headers=None):
    """Retain reconciliation identifiers, never error prose or provider payloads.

    No status code or identifier here establishes a charge or releases funds.
    https://openrouter.ai/docs/api/reference/errors-and-debugging
    """
    document = document if isinstance(document, dict) else {}
    error = document.get('error')
    error = error if isinstance(error, dict) else {}
    metadata = error.get('metadata')
    metadata = metadata if isinstance(metadata, dict) else {}
    headers = headers or {}
    kind = metadata.get('error_type')
    def identifier(value, prefix):
        return value if isinstance(value, str) and re.fullmatch(prefix + r'-[A-Za-z0-9_-]{1,250}', value) else None
    return {'http_status': status if type(status) is int and 100 <= status <= 599 else None,
        'error_code': error.get('code') if type(error.get('code')) is int and 100 <= error['code'] <= 599 else None,
        'error_type': kind if isinstance(kind, str) and kind in ERROR_TYPES else None,
        'generation_id': identifier(document.get('id'), 'gen') or identifier(headers.get('X-Generation-Id'), 'gen'),
        'request_id': identifier(headers.get('X-Request-Id'), 'req'),
        'billing_outcome': 'unknown_reservation_retained'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TransportError('Redirect refused')


def load_key(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise TransportError('Credential file must be a private regular file')
    values = []
    for line in path.read_text().splitlines():
        if line.startswith('OPENROUTER_API_KEY='):
            values.append(line.split('=', 1)[1].strip().strip('\"\''))
    if len(values) != 1 or not values[0] or any(c.isspace() for c in values[0]):
        raise TransportError('Missing or invalid credential')
    return values[0]


class OpenRouter:
    def __init__(self, key, generation_enabled=False, opener=None):
        self._key = key
        self.generation_enabled = generation_enabled
        self.opener = opener or build_opener(NoRedirect())

    def _request(self, path, payload=None):
        if path not in {'/credits', '/key', ENDPOINTS, '/chat/completions'} and not path.startswith('/generation?id='):
            raise TransportError('Unapproved API path')
        if path == '/chat/completions' and (not self.generation_enabled or payload is None):
            raise TransportError('Generation is disabled')
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        req = Request(BASE + path, data=body, headers={
            'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json',
        })
        try:
            with self.opener.open(req, timeout=45) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise TransportError('Response too large; outcome may be ambiguous')
                result = json.loads(raw, parse_float=Decimal)
                if not isinstance(result, dict) or 'error' in result:
                    raise TransportError('Provider returned an error', diagnostic=error_diagnostic(
                        result, status=getattr(response, 'status', None), headers=getattr(response, 'headers', None)))
                return result
        except HTTPError as exc:
            # HTTP error bodies can contain task text or upstream secrets. Read
            # only a bounded envelope and retain strictly allowlisted metadata.
            document = None
            try:
                raw = exc.read(65537)
                if len(raw) <= 65536:
                    document = json.loads(raw)
            except (OSError, ValueError, TypeError):
                pass
            finally:
                exc.close()
            raise TransportError('OpenRouter HTTP status ' + str(exc.code),
                diagnostic=error_diagnostic(document, status=exc.code, headers=exc.headers)) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise TransportError('OpenRouter response unavailable or invalid') from None

    def balance(self):
        data = self._request('/credits')['data']
        credit, usage = Decimal(str(data['total_credits'])), Decimal(str(data['total_usage']))
        if not credit.is_finite() or not usage.is_finite() or min(credit, usage) < 0:
            raise TransportError('Invalid account balance')
        return credit - usage

    def metadata(self):
        return self._request(ENDPOINTS)

    def key_status(self):
        data = self._request('/key')['data']
        return {k: data.get(k) for k in ('limit', 'limit_remaining', 'usage', 'limit_reset')}

    def complete(self, payload):
        return self._request('/chat/completions', payload)

    def generation(self, identifier):
        if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
            raise TransportError('Invalid generation identifier')
        return self._request('/generation?' + urlencode({'id': identifier}))['data']


if __name__ == '__main__':
    client = OpenRouter(load_key(Path(__file__).resolve().parents[1] / '.env'))
    metadata = client.metadata()['data']
    endpoints = [e for e in metadata.get('endpoints', []) if e.get('tag') == 'deepinfra/fp8'
                 or e.get('provider_name') == 'DeepInfra']
    print(json.dumps({'read_only': True, 'generation_enabled': False,
        'available_account_credit': str(client.balance()), 'key': client.key_status(),
        'model_id': metadata.get('id'),
        'endpoint_candidates': [{k:e.get(k) for k in ('name','tag','provider_name','quantization','pricing','context_length','max_completion_tokens','supported_parameters')} for e in endpoints]},
        default=str, indent=2))
