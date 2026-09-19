"""Prepare, but never start, a private self-hosted Langfuse dashboard.

Based on the hash-pinned official Compose distribution. Preparation neither
pulls images nor starts containers nor calls an inference API. Deploy after
benchmark execution so observability services cannot compete with timed tasks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from urllib.request import urlopen
import uuid

import yaml

REVISION = 'ef0add7b2598200bd44573178d9d1cc5f7cc770b'
SOURCE = f'https://raw.githubusercontent.com/langfuse/langfuse/{REVISION}/docker-compose.yml'
DIGEST = 'd373385b2ad54d11c4d26a66c70ee7eaab87c7088adeb6a017c6612143efc697'
BASE = 'http://127.0.0.1:3300'
EXPECTED = {'langfuse-web', 'langfuse-worker', 'postgres', 'redis', 'clickhouse', 'minio'}


def configuration(raw):
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError('Official Compose source digest changed')
    document = yaml.safe_load(raw)
    if set(document['services']) != EXPECTED:
        raise ValueError('Unexpected upstream services')
    values = {name: secrets.token_hex(32) for name in
              ('POSTGRES_PASSWORD', 'CLICKHOUSE_PASSWORD', 'REDIS_AUTH',
               'MINIO_ROOT_PASSWORD', 'SALT', 'ENCRYPTION_KEY', 'NEXTAUTH_SECRET')}
    public, secret = 'pk-lf-' + str(uuid.uuid4()), 'sk-lf-' + secrets.token_hex(32)
    owner_password = secrets.token_hex(24)
    values.update(NEXTAUTH_URL=BASE, TELEMETRY_ENABLED='false',
        LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES='false', LANGFUSE_IN_APP_AGENT_ENABLED='false',
        DATABASE_URL='postgresql://postgres:' + values['POSTGRES_PASSWORD'] + '@postgres:5432/postgres',
        MINIO_ROOT_USER='uts-observability', LANGFUSE_INIT_ORG_ID='uts-capstone',
        LANGFUSE_INIT_ORG_NAME='UTS Capstone', LANGFUSE_INIT_PROJECT_ID='netcup-harbor-study',
        LANGFUSE_INIT_PROJECT_NAME='Harbor same-model harness comparison',
        LANGFUSE_INIT_PROJECT_PUBLIC_KEY=public, LANGFUSE_INIT_PROJECT_SECRET_KEY=secret,
        LANGFUSE_INIT_USER_EMAIL='admin@localhost.local', LANGFUSE_INIT_USER_NAME='Local study owner',
        LANGFUSE_INIT_USER_PASSWORD=owner_password,
        LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT='http://127.0.0.1:3390')
    for kind in ('EVENT', 'MEDIA', 'BATCH_EXPORT'):
        prefix = f'LANGFUSE_S3_{kind}_UPLOAD' if kind != 'BATCH_EXPORT' else 'LANGFUSE_S3_BATCH_EXPORT'
        values[prefix + '_ACCESS_KEY_ID'] = values['MINIO_ROOT_USER']
        values[prefix + '_SECRET_ACCESS_KEY'] = values['MINIO_ROOT_PASSWORD']
    # No inherited host environment, provider keys, AWS keys or AI features.
    pattern = re.compile(r'\$\{([A-Z0-9_]+):-([^}]*)\}')
    def substitute(item):
        if isinstance(item, dict): return {k: substitute(v) for k, v in item.items()}
        if isinstance(item, list): return [substitute(v) for v in item]
        if not isinstance(item, str): return item
        return pattern.sub(lambda m: values.get(m[1], m[2]), item)
    document = substitute(document)
    document['name'] = 'uts-observability'
    for name, service in document['services'].items():
        service['ports'] = []
        service['restart'] = 'no'
        if service.get('privileged') or service.get('network_mode') or service.get('build'):
            raise ValueError('Unexpected host privilege or build')
        for mount in service.get('volumes', []):
            if not isinstance(mount, str) or mount.split(':')[0] not in document['volumes']:
                raise ValueError('Only dedicated named data volumes are allowed')
    document['services']['langfuse-web']['ports'] = ['127.0.0.1:3300:3000']
    document['services']['minio']['ports'] = ['127.0.0.1:3390:9000']
    for name in ('langfuse-web', 'langfuse-worker'):
        document['services'][name]['environment']['LANGFUSE_S3_MEDIA_UPLOAD_INTERNAL_ENDPOINT'] = 'http://minio:9000'
    document['services']['langfuse-worker']['environment']['LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT'] = 'http://minio:9000'
    credential = {'base_url': BASE, 'public_key': public, 'secret_key': secret,
                  'local_owner_email': values['LANGFUSE_INIT_USER_EMAIL'], 'local_owner_password': owner_password}
    return document, credential


def prepare(destination, raw):
    destination = Path(destination)
    document, credential = configuration(raw)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, value in (('compose.json', document), ('credentials.json', credential),
                        ('source.json', {'url': SOURCE, 'sha256': DIGEST,
                         'status': 'prepared_not_running_not_export_verified'})):
        fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-file', type=Path)
    args = parser.parse_args()
    if args.source_file:
        raw = args.source_file.read_bytes()
    else:
        with urlopen(SOURCE, timeout=30) as response:
            raw = response.read(256_000)
    print('Prepared private configuration; no services started: ' + str(prepare(args.output, raw)))
