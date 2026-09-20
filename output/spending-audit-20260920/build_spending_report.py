#!/usr/bin/env python3
"""Build a sanitised spending report from existing evidence; makes no network calls.

Run with the bundled Python. Only output files beside this script are written.
The two authoritative SQLite databases are deserialised into memory and queried
read-only. Archive members are never extracted onto the filesystem. Supporting
Mac receipts enrich those ledger rows; they never create additional charge rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from pypdf import PdfReader

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
ARCHIVE = REPO / '.runtime/netcup/endpoint-recheck-20260920-eahIfK/stage2-runtime.tar.gz'
ARCHIVE_SHA = '2eaeaa01452bb8b10a0d786b5d6a4d38eeca935d916b5692303694619dba50e5'
LEDGER_HASHES = {
    'setup': '8a9a009ea5d6db3d1d03a7d4e9d7b3b165fa0ac811f1246e94e0eda5fe08535e',
    'scored': '4504d4289a06643ee93d1690502d7d8b978ff9e20c0cb75fa56440d95fb34359',
}
UNIT = Decimal(1_000_000_000)
CATEGORIES = ['Connectivity', 'Tool checking', 'Setup / token calibration', 'Harness fixtures', 'Real benchmark attempt']
INITIAL_BALANCE = Decimal('25.265176805')
LATEST_BALANCE = Decimal('12.028542692')
LATEST_UTC = '2026-09-20T00:21:07+00:00'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact(value) -> str:
    return format(Decimal(value), 'f')


def dollars(n: int | None) -> str | None:
    return None if n is None else exact(Decimal(n) / UNIT)


def safe_source(name: str, data: bytes, origin: str) -> dict:
    return {'filename': Path(name).name, 'sha256': sha(data), 'origin': origin}


def purpose(trial: str, position: int, count: int) -> tuple[str, str, str, str]:
    suffix = f'Call {position} of {count}.'
    if trial == 'compatibility-plain-v1':
        return 'Connectivity', 'First model connection', 'Confirm the gateway can obtain a simple model reply.', 'project documentation'
    if trial == 'compatibility-tools-v1':
        return 'Tool checking', 'Structured tool-call check', 'Check structured tool output; no tool side effects were executed.', 'project documentation'
    if trial == 'harbor-http-live-v1':
        return 'Connectivity', 'Harbor client connection', 'Check the Harbor client reaches the real model through the gateway.', 'project documentation'
    if 'receiptlatency' in trial:
        return 'Connectivity', 'Receipt timing diagnostic', 'Investigate delayed availability of billing receipts.', 'inferred from trial identity and diagnostic records'
    if 'endpoint-recheck' in trial:
        return 'Connectivity', 'Endpoint recheck', 'Verify the key and endpoint respond after the benchmark interruption.', 'diagnostic-purpose and endpoint result records'
    if 'token-calibration' in trial:
        short = 'Unicode history' if 'unicode' in trial else ('Tool history: chat' if 'chat-v1' in trial else 'Tool history: default')
        return 'Setup / token calibration', short, 'Compare local token counting with actual billed input for this request shape.', 'project documentation'
    if trial.startswith('dev-'):
        return 'Real benchmark attempt', 'Terminus-2: video processing', f'Work on the first selected development benchmark task. {suffix}', 'trial result and billing interruption records'
    harness = 'OpenHands' if 'openhands' in trial else ('Custom agent' if 'custom' in trial else 'Terminus-2')
    if trial.startswith('uts-terminus'):
        why = 'Check the real agent can use its terminal and complete a controlled fixture.'
    elif 'pinnedv2' in trial:
        why = 'Recheck agent and tool integration with the pinned runtime images.'
    elif 'netcupv5' in trial:
        why = 'Requalify model and tool integration after the Debian package-source repair.'
    elif 'netcupv4' in trial:
        why = 'Qualify model and tool integration with the revised receipt policy.'
    else:
        why = 'Check real model and tool integration before scored benchmark execution.'
    return 'Harness fixtures', f'{harness} integration fixture', f'{why} {suffix}', 'project documentation and named fixture result'


def gather(supplement: Path | None) -> dict:
    archive_bytes = ARCHIVE.read_bytes()
    assert sha(archive_bytes) == ARCHIVE_SHA, 'Archive fingerprint changed'
    rows, receipts = [], {}
    evidence_sources = []
    with tarfile.open(ARCHIVE, 'r:gz') as tf:
        for kind in ['setup', 'scored']:
            name = f'.runtime/stage2/{kind}_budget.sqlite'
            raw = tf.extractfile(name).read()
            assert sha(raw) == LEDGER_HASHES[kind]
            evidence_sources.append(safe_source(name, raw, 'authoritative archived ledger'))
            db = sqlite3.connect(':memory:')
            db.deserialize(raw)
            db.execute('PRAGMA query_only=ON')
            db.row_factory = sqlite3.Row
            sql = '''SELECT r.rowid sequence, r.*, g.generation_id, c.state receipt_check_state
                     FROM requests r LEFT JOIN generations g ON r.id=g.request_id
                     LEFT JOIN receipt_checks c ON r.id=c.request_id ORDER BY r.rowid'''
            for row in db.execute(sql):
                rows.append(dict(row, ledger=kind))
            db.close()
        # Restrict receipts to authoritative native setup and scored attempt roots.
        for member in tf.getmembers():
            if (member.isfile() and member.name.endswith('.receipt.json') and
                member.name.startswith(('.runtime/stage2/native-setup-attempts/', '.runtime/stage2/scored-attempts/'))):
                raw = tf.extractfile(member).read()
                rec = json.loads(raw)
                if isinstance(rec, dict) and str(rec.get('id', '')).startswith('gen-'):
                    receipts[rec['id']] = (rec, safe_source(member.name, raw, 'archived provider receipt'))
        raw = tf.extractfile('.runtime/stage2/scored-attempts/dev-terminus-2-00-video-processing/000003.timing.json').read()
        unknown_started = json.loads(raw)['started_ns']
        unknown_time = datetime.fromtimestamp(unknown_started / 1e9, timezone.utc).isoformat(timespec='milliseconds')
        unknown_source = safe_source('000003.timing.json', raw, 'archived failed-request timing')
    local_root = REPO / '.runtime/stage2'
    paths = list(local_root.glob('*.receipt.json'))
    paths += list((local_root / 'native-setup-attempts').glob('*/*.receipt.json'))
    paths += list((local_root / 'terminus-agent-lcdrxe3b').glob('receipt-*.json'))
    for path in paths:
        raw = path.read_bytes()
        rec = json.loads(raw)
        if isinstance(rec, dict) and str(rec.get('id', '')).startswith('gen-'):
            receipts.setdefault(rec['id'], (rec, safe_source(path.name, raw, 'preserved Mac provider receipt')))
    account_source = None
    recovered_path = REPO / '.runtime/netcup/compatibility-tools-v1.audit-receipt-20260920.json'
    if recovered_path.exists():
        raw = recovered_path.read_bytes()
        assert sha(raw) == 'c30ac47b23f9a84734c0dbda3ec3d12962ae5d4e93a07441fc0d0ad55628d7bb'
        rec = json.loads(raw)
        receipts[rec['id']] = (rec, safe_source(recovered_path.name, raw, 'read-only recovered provider receipt'))
    if supplement:
        raw = supplement.read_bytes()
        if supplement.name == 'spending-account-snapshot-20260920.json':
            assert sha(raw) == 'c713104ea70ad131c553f63fc4af621dda71b4afa107bf63a2177d4339a58065'
        sup = json.loads(raw)
        account_source = safe_source(supplement.name, raw, 'independent read-only verification')
        for rec in sup.get('recovered_receipts', []):
            assert str(rec.get('id', '')).startswith('gen-')
            receipts[rec['id']] = (rec, account_source)
        if 'latest_account' in sup or 'available_account_credit_usd' in sup:
            acc = sup.get('latest_account', sup)
            assert Decimal(str(acc['available_account_credit_usd'])) == LATEST_BALANCE
            assert Decimal(str(acc['key_usage_usd'])) == Decimal('0.00774516')
    trial_count = Counter(r['trial'] for r in rows)
    trial_pos = Counter()
    clean = []
    for r in rows:
        trial = r['trial']
        trial_pos[trial] += 1
        category, title, why, why_basis = purpose(trial, trial_pos[trial], trial_count[trial])
        item = {
            'audit_no': len(clean) + 1, 'ledger': r['ledger'], 'ledger_request_id': r['id'],
            'generation_id': r['generation_id'], 'trial_id': trial,
            'trial_call_index': trial_pos[trial], 'trial_call_count': trial_count[trial],
            'category': category, 'title': title, 'purpose': why, 'purpose_basis': why_basis,
            'source_host': 'Netcup native Linux' if 'netcup' in trial or r['ledger'] == 'scored' or 'endpoint-recheck' in trial else 'Mac',
            'host_basis': 'NETCUP.md migration and native runtime records' if 'netcup' in trial or r['ledger'] == 'scored' else 'README.md historical Mac execution journal',
            'charged_usd': dollars(r['charged']), 'ledger_state': r['state'],
            'unresolved_reservation_usd': dollars(r['reserved']) if r['state'] == 'pending' else None,
            'utc_timestamp': None, 'timestamp_basis': None, 'input_tokens': None,
            'output_tokens': None, 'token_basis': None, 'receipt_status': None,
            'provider_request_id': None, 'sources': [],
        }
        if r['generation_id'] in receipts:
            rec, source = receipts[r['generation_id']]
            assert Decimal(str(rec['total_cost'])) == Decimal(item['charged_usd']), f'Receipt mismatch: {trial}'
            item.update({
                'utc_timestamp': rec.get('created_at'), 'timestamp_basis': 'provider receipt creation time',
                'input_tokens': rec.get('native_tokens_prompt'), 'output_tokens': rec.get('native_tokens_completion'),
                'token_basis': 'provider-native tokens, including reasoning in output',
                'receipt_status': 'Receipt matched to generation ID and exact ledger charge',
                'provider_request_id': rec.get('request_id'),
            })
            item['sources'].append(source)
        elif r['generation_id'] == 'gen-1789527978-dcXQ48AiF4WStPVKSpWK':
            path = REPO / 'stage2/setup_tools_probe_reconciled.json'
            raw = path.read_bytes(); rec = json.loads(raw)
            assert Decimal(rec['actual_cost_usd']) == Decimal(item['charged_usd'])
            item.update({'utc_timestamp': rec['time_utc'], 'timestamp_basis': 'historical reconciliation time, not dispatch time',
                         'input_tokens': rec['usage']['prompt_tokens'], 'output_tokens': rec['usage']['completion_tokens'],
                         'token_basis': 'recorded completion usage',
                         'receipt_status': 'Historical reconciliation recorded; raw receipt not available for recheck'})
            item['sources'].append(safe_source(path.name, raw, 'historical reconciliation record'))
        elif r['state'] == 'pending':
            item.update({'utc_timestamp': unknown_time, 'timestamp_basis': 'local request timing start',
                         'receipt_status': 'Unresolved: no generation ID or receipt'})
            item['sources'].append(unknown_source)
        else:
            raise AssertionError(f'Unexpected missing receipt: {r["id"]}')
        if r['state'] == 'pending':
            item['outcome'] = 'Transport/API error; no usable response; charge unknown; original request not replayed'
        elif trial in ['setup-native-terminus-2-netcupv1', 'setup-native-terminus-2-netcupv2']:
            item['outcome'] = 'Charged; fixture stopped on delayed receipt; billing recovered'
        elif 'receiptlatency' in trial:
            item['outcome'] = 'Charged; delayed receipt recovered without another generation'
        elif r['ledger'] == 'scored':
            item['outcome'] = 'Charged request; overall trial later stopped with unresolved billing'
        else:
            item['outcome'] = 'Charged and settled; diagnostic or fixture only'
        clean.append(item)
    assert len(clean) == 46 and Counter(r['ledger'] for r in clean) == {'setup': 43, 'scored': 3}
    settled = [r for r in clean if r['charged_usd'] is not None]
    total = sum((Decimal(r['charged_usd']) for r in settled), Decimal(0))
    assert len(settled) == 45 and total == Decimal('0.00774516')
    assert len({r['ledger_request_id'] for r in clean}) == 46
    assert len({r['generation_id'] for r in settled}) == 45
    category_totals = []
    for category in CATEGORIES:
        group = [r for r in clean if r['category'] == category]
        category_totals.append({'category': category, 'recorded_requests': len(group),
            'known_charged_usd': exact(sum((Decimal(r['charged_usd']) for r in group if r['charged_usd'] is not None), Decimal(0))),
            'unknown_requests': sum(r['charged_usd'] is None for r in group)})
    sources = [REPO / 'stage2' / p for p in ['README.md', 'NETCUP.md', 'setup_probe_reconciled.json',
        'setup_tools_probe_reconciled.json', 'tool_call_evidence.json', 'netcup/billing_interruption_20260919.json',
        'netcup/endpoint_recheck_20260920a.json']]
    evidence_sources += [safe_source(p.name, p.read_bytes(), 'project evidence') for p in sources]
    if account_source:
        evidence_sources.append(account_source)
    return {
        'report_title': 'OpenRouter spending reconciliation', 'scope': 'All recorded generation requests in the authoritative setup and scored project ledgers',
        'as_of_utc': LATEST_UTC, 'currency': 'USD', 'archive_sha256': ARCHIVE_SHA,
        'model': 'deepseek/deepseek-v4-flash-0731', 'provider': 'DeepInfra', 'endpoint': 'deepinfra/fp8',
        'summary': {'recorded_requests': 46, 'settled_requests': 45, 'unknown_requests': 1,
            'setup_charged_usd': '0.0073707', 'scored_known_charged_usd': '0.00037446',
            'known_total_charged_usd': exact(total), 'unknown_request_hold_usd': '0.106496',
            'initial_account_balance_usd': exact(INITIAL_BALANCE), 'latest_account_balance_usd': exact(LATEST_BALANCE),
            'account_balance_decline_usd': exact(INITIAL_BALANCE - LATEST_BALANCE),
            'account_decline_not_attributed_usd': exact(INITIAL_BALANCE - LATEST_BALANCE - total),
            'key_usage_usd': '0.00774516', 'key_limit_usd': '30', 'key_limit_remaining_usd': '29.99225484', 'key_limit_reset': None},
        'category_totals': category_totals, 'sources': evidence_sources, 'requests': clean,
        'limitations': [
            'This is all recorded generation requests, not every HTTP transaction or every request in the entire account.',
            'Read-only balance, metadata and receipt lookups are not individually logged as generation requests.',
            'The unexplained account decline is not attributed to this project, another user or any other cause.',
            'The unresolved reservation is a conservative local hold, not a confirmed charge.',
            'Purpose summaries interpret recorded trial identities and project evidence; the receipt timing diagnostic purpose is explicitly inferred.',
            'Mac local-Qwen and CETUS local-inference work has no OpenRouter generation charge in this register.',
            'Server rental, Codex subscriptions, electricity and other infrastructure costs are excluded; no invoice allocation is available.',
            'Fixture success is not benchmark performance. The sole real benchmark attempt stopped with reward zero and unresolved billing.',
        ],
    }


# Deliberately restrained report design; every page uses the same readable grid.
NAVY = colors.HexColor('#123047')
TEAL = colors.HexColor('#086E69')
INK = colors.HexColor('#172D3B')
MUTED = colors.HexColor('#566773')
LINE = colors.HexColor('#D8E2E7')
PALE = colors.HexColor('#F0F6F7')
AMBER = colors.HexColor('#87580C')
W, H = A4
M = 36
WIDTH = W - 2 * M


def init_fonts():
    root = Path('/System/Library/Fonts/Supplemental')
    for label, file in [('Body', 'Arial.ttf'), ('Bold', 'Arial Bold.ttf'), ('Italic', 'Arial Italic.ttf')]:
        pdfmetrics.registerFont(TTFont(label, str(root / file)))


def para(c, text, x, y, width=WIDTH, size=10, leading=None, color=INK, bold=False):
    style = ParagraphStyle('p', fontName='Bold' if bold else 'Body', fontSize=size,
                           leading=leading or size * 1.35, textColor=color, alignment=TA_LEFT,
                           spaceAfter=0, allowWidows=0, allowOrphans=0)
    p = Paragraph(text, style)
    _, height = p.wrap(width, H)
    p.drawOn(c, x, y-height)
    return y-height


def textline(c, text, x, y, size=10, color=INK, bold=False):
    c.setFillColor(color); c.setFont('Bold' if bold else 'Body', size); c.drawString(x, y, text)


def right(c, text, y, size=10, color=INK, bold=False, x=W-M):
    c.setFillColor(color); c.setFont('Bold' if bold else 'Body', size); c.drawRightString(x, y, text)


def base(c, page, title, subtitle, total_pages):
    c.setFillColor(TEAL); c.rect(M, H-35, 28, 3, fill=1, stroke=0)
    textline(c, 'UTS CAPSTONE  /  SPENDING AUDIT', M+38, H-36, 8, MUTED, True)
    textline(c, title, M, H-75, 22, NAVY, True)
    para(c, subtitle, M, H-89, size=9.5, color=MUTED)
    c.setStrokeColor(LINE); c.line(M, 39, W-M, 39)
    textline(c, '20 September 2026  |  USD  |  Recorded generation requests', M, 25, 7.5, MUTED)
    right(c, f'{page} / {total_pages}', 25, 7.5, MUTED)


def money_row(c, label, amount, y, strong=False, color=INK):
    textline(c, label, M+12, y, 10, color, strong)
    right(c, '$'+amount, y, 10.5, color, strong, W-M-12)
    return y-27


def build_pdf(data):
    init_fonts()
    rows = data['requests']; s = data['summary']
    checks = sorted([r for r in rows if r['category'] not in ['Harness fixtures', 'Real benchmark attempt']],
                    key=lambda r: (CATEGORIES.index(r['category']), r['audit_no']))
    fixtures = [r for r in rows if r['category'] == 'Harness fixtures']
    scored = [r for r in rows if r['category'] == 'Real benchmark attempt']
    assert len(checks) == 8 and len(fixtures) == 35 and len(scored) == 3
    sections = [('Connection, tools and setup', checks)]
    sections += [(f'Harness fixtures  |  {i//7+1} of 5', fixtures[i:i+7]) for i in range(0, len(fixtures), 7)]
    sections += [('Real benchmark attempt', scored)]
    total_pages = 2 + len(sections)
    pdf = OUT / 'OpenRouter_Spending_Audit_2026-09-20.pdf'
    c = canvas.Canvas(str(pdf), pagesize=A4, invariant=1)
    c.setTitle('UTS Capstone - OpenRouter Spending Audit - 20 September 2026')
    c.setAuthor('UTS Capstone project')
    c.setSubject('All recorded generation requests, exact USD charges and account reconciliation')
    base(c, 1, 'OpenRouter spending reconciliation',
         'Evidence through 20 September 2026, 00:21:07 UTC. All figures are exact US dollars.', total_pages)
    c.setFillColor(PALE); c.roundRect(M, 592, WIDTH, 112, 7, fill=1, stroke=0)
    textline(c, 'KNOWN PROJECT CHARGES', M+16, 682, 8.5, TEAL, True)
    textline(c, '$0.00774516', M+16, 645, 29, NAVY, True)
    textline(c, '45 settled requests  |  less than one US cent', M+16, 619, 10, MUTED)
    textline(c, '1 request unresolved', M+315, 675, 12, AMBER, True)
    para(c, '$0.106496 remains reserved locally.<br/>This hold is not a confirmed charge.', M+315, 655,
         width=WIDTH-331, size=9, color=AMBER)
    textline(c, 'Account balance movement', M, 568, 14, NAVY, True)
    y = 541
    for label, amount, strong in [
        ('Initial balance observed on 16 September', s['initial_account_balance_usd'], False),
        ('Balance observed on 20 September, 00:21 UTC', s['latest_account_balance_usd'], False),
        ('Observed account balance decline', s['account_balance_decline_usd'], True),
        ('Matched to this key and the project ledgers', s['known_total_charged_usd'], False),
        ('Not attributed by the available evidence', s['account_decline_not_attributed_usd'], True),
    ]:
        y = money_row(c, label, amount, y, strong)
    y = para(c, 'The account declined by $13.236634113, but only $0.00774516 matches this project\'s '
        'recorded charges. The remaining $13.228888953 is unexplained by the available evidence; '
        'it is not assigned to this project or to anyone else.', M, y+2, size=10)
    textline(c, 'What the recorded charges paid for', M, y-27, 14, NAVY, True)
    y -= 53
    textline(c, 'Purpose group', M+10, y, 8.5, MUTED, True)
    right(c, 'Requests', y, 8.5, MUTED, True, W-M-128)
    right(c, 'Known charge (USD)', y, 8.5, MUTED, True, W-M-10)
    y -= 10; c.setStrokeColor(LINE); c.line(M, y, W-M, y)
    for group in data['category_totals']:
        y -= 24
        textline(c, group['category'], M+10, y, 9.5)
        right(c, str(group['recorded_requests']), y, 9.5, x=W-M-145)
        right(c, '$'+group['known_charged_usd'], y, 9.5, x=W-M-10)
    y -= 25
    textline(c, 'Total: 46 recorded requests, including 1 unknown', M+10, y, 9.5, NAVY, True)
    right(c, '$0.00774516', y, 10, NAVY, True, W-M-10)
    para(c, 'Setup ledger: $0.0073707 across 43 calls. Scored ledger: $0.00037446 across 2 settled '
         'calls plus 1 unresolved call. Fixtures are preparation work, not benchmark scores.', M, y-19, size=8.5, color=MUTED)
    c.showPage()
    base(c, 2, 'Scope, interpretation and evidence',
         'How to read the request register and what this report can establish.', total_pages)
    y = 703
    for title, body in [
        ('The register is complete for the two project ledgers',
         'Every request in the authoritative setup and scored ledgers appears once on the following pages. '
         'Earlier snapshots, migrated copies and synthetic test ledgers are not additional spending. '
         'This is all recorded generation requests, not every HTTP transaction or every call in the entire account. '
         'The model was DeepSeek V4 Flash 0731, routed through OpenRouter to DeepInfra FP8.'),
        ('Why these calls were made',
         'Connectivity calls checked the model route and delayed receipts. Tool checking tested structured tool output. '
         'Token calibration compared local counts with provider usage. Harness fixtures checked the agents in controlled tasks. '
         'Only three requests belong to the first real benchmark attempt. Purpose descriptions summarise project records; '
         'the receipt timing diagnostic purpose is explicitly marked as inferred.'),
        ('Charges, receipts and timestamps',
         'Charges come from integer-nanodollar ledger values and are added using exact decimal arithmetic. '
         'A matched receipt must have the same generation ID and exact charge. These are provider-reported charges, '
         'not estimates from multiplying token counts by a price. Times are UTC receipt creation times, '
         'except the unresolved call, which uses its local dispatch timing. Tokens are provider-native input and output counts; '
         'output may include reasoning. A null or unknown charge is never treated as zero.'),
        ('The key allowance is separate from account credit',
         'The latest key readback reports $0.00774516 usage, a $30 limit, $29.99225484 allowance remaining '
         'and no limit reset (null). The shared account balance is $12.028542692. A remaining key allowance '
         'does not mean that amount exists as spendable account credit.'),
        ('What is excluded, and what remains unresolved',
         'Read-only balance, metadata and receipt queries are not individually logged in these generation ledgers. '
         'Earlier local Qwen and CETUS inference work is not OpenRouter spending. Server rental, Codex subscriptions, '
         'electricity and other infrastructure costs are excluded because no verified invoice allocation is provided. '
         'The missing benchmark response still lacks a generation identity and a confirmed charge; aggregate key usage '
         'does not individually reconcile it. To investigate the account difference, the account owner can supply an '
         'Activity export for 16-20 September filtered by API key and model. No password or API key is needed.'),
    ]:
        y = para(c, title, M, y, size=11, color=NAVY, bold=True)-6
        y = para(c, body, M, y, size=9.4, leading=13)-18
    y = para(c, 'Evidence fingerprints', M, y, size=11, color=NAVY, bold=True)-6
    for name, fingerprint in [('stage2-runtime.tar.gz', ARCHIVE_SHA),
                              ('setup_budget.sqlite', LEDGER_HASHES['setup']), ('scored_budget.sqlite', LEDGER_HASHES['scored'])]:
        textline(c, name, M, y-9, 8.2, MUTED)
        y = para(c, fingerprint, M+114, y, width=WIDTH-114, size=7.3, leading=9)-8
    para(c, 'Supporting source files: README.md, NETCUP.md, setup_probe_reconciled.json, '
         'setup_tools_probe_reconciled.json, tool_call_evidence.json, billing_interruption_20260919.json and '
         'endpoint_recheck_20260920a.json. The accompanying sanitised JSON includes per-record source hashes.', M, y-3,
         size=8, leading=11, color=MUTED)
    c.showPage()
    for page, (title, group) in enumerate(sections, 3):
        page_total = sum((Decimal(r['charged_usd']) for r in group if r['charged_usd'] is not None), Decimal(0))
        subtitle = f'{len(group)} recorded requests on this page  |  Known charges: ${exact(page_total)}'
        if group[0]['category'] == 'Harness fixtures':
            subtitle += '  |  Controlled setup tasks; not benchmark scores.'
        base(c, page, title, subtitle, total_pages)
        y = 713
        height = 79 if len(group) == 8 else 87
        for row in group:
            c.setFillColor(PALE if row['audit_no'] % 2 else colors.white)
            c.roundRect(M, y-height+3, WIDTH, height-6, 4, fill=1, stroke=0)
            x = M+10
            label = f'{row["audit_no"]:02d}  {row["title"]}'
            textline(c, label, x, y-12, 9.4, NAVY, True)
            right(c, '$'+row['charged_usd'] if row['charged_usd'] is not None else 'CHARGE UNKNOWN', y-12,
                  10, TEAL if row['charged_usd'] is not None else AMBER, True, W-M-10)
            why = row['purpose'].replace('Call ', 'Call ')
            if 'inferred' in row['purpose_basis']:
                why += ' (Purpose inferred.)'
            py = para(c, escape(why), x, y-19, width=WIDTH-20, size=8.1, leading=9.3)
            # The fixture purpose occupies up to two lines; the compact checks occupy one.
            shift = max(0, y-28.3-py)
            textline(c, f'Trial: {row["trial_id"]}  |  Host: {row["source_host"]}', x, y-38-shift, 7.6, MUTED)
            timestamp = row['utc_timestamp'].replace('T', ' ').replace('+00:00', 'Z')
            token = 'unknown' if row['input_tokens'] is None else f'{row["input_tokens"]:,} in / {row["output_tokens"]:,} out'
            basis = 'dispatch' if row['charged_usd'] is None else 'receipt'
            textline(c, f'UTC ({basis}): {timestamp}  |  Tokens: {token}', x, y-49-shift, 7.8)
            generation = row['generation_id'] or 'unmapped / unavailable'
            textline(c, f'Gen: {generation}  |  Ledger request: {row["ledger_request_id"]}', x, y-60-shift, 6.8, MUTED)
            receipt = 'receipt matched' if row['receipt_status'].startswith('Receipt matched') else 'receipt unavailable'
            if row['charged_usd'] is None:
                status = 'Unresolved API error; no usable response or receipt. Local hold: $0.106496 (not a charge).'
            elif 'stopped on delayed' in row['outcome']:
                status = f'Settled; fixture stopped on delayed receipt; {receipt} during recovery.'
            elif row['ledger'] == 'scored':
                status = f'Settled; {receipt}. Overall trial later stopped with unresolved billing.'
            else:
                status = f'Settled; {receipt}. Diagnostic / fixture only.'
            textline(c, status, x, y-71-shift, 7.6, AMBER if row['charged_usd'] is None else MUTED)
            assert y-71-shift >= y-height+6, (row['audit_no'], 'card overflow')
            y -= height
        if group is scored:
            y -= 19
            y = para(c, 'Status of the benchmark attempt', M, y, size=14, color=NAVY, bold=True)-10
            y = para(c, 'The first Terminus-2 development trial retained reward zero and an API error. '
                 'Its first two model calls cost $0.00037446 in total. The third call returned no usable response '
                 'or generation identity, so its charge remains unknown and the $0.106496 reservation remains held. '
                 'The original failed request was not replayed.', M, y, size=10, leading=14)-17
            y = para(c, 'The later endpoint recheck (request 43, on the connection page) cost $0.00000918. '
                 'It confirmed that the key and endpoint worked at that time. It did not explain the earlier error, '
                 'resolve the missing request or complete a benchmark comparison.', M, y, size=10, leading=14)-17
            para(c, 'No completed harness comparison or demonstrated custom-agent win is established by this spending record.',
                 M, y, size=10, color=AMBER, bold=True)
        c.showPage()
    c.save()
    reader = PdfReader(pdf)
    assert len(reader.pages) == total_pages
    content = '\n'.join(p.extract_text() or '' for p in reader.pages)
    for row in rows:
        assert content.count(row['ledger_request_id']) == 1, row['ledger_request_id']
        if row['generation_id']:
            assert content.count(row['generation_id']) == 1, row['generation_id']
    assert '$13.228888953' in content and '$0.00774516' in content
    for forbidden in ['sk-or-', 'Bearer ', 'BEGIN OPENSSH', '/Users/', '/opt/', 'workspace_id', '@']:
        assert forbidden not in content, f'Unexpected sensitive/internal text: {forbidden}'
    (OUT / 'report_text_for_qa.txt').write_text(content)
    return pdf, total_pages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--supplement', type=Path,
                        default=REPO / '.runtime/netcup/spending-account-snapshot-20260920.json',
                        help='Sanitised independent verification JSON')
    args = parser.parse_args()
    data = gather(args.supplement)
    json_path = OUT / 'spending_audit_sanitised.json'
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')
    csv_path = OUT / 'recorded_generation_requests.csv'
    fields = [k for k in data['requests'][0] if k != 'sources'] + ['source_filenames', 'source_sha256']
    with csv_path.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        for row in data['requests']:
            flat = {k:v for k,v in row.items() if k != 'sources'}
            flat['source_filenames'] = '; '.join(s['filename'] for s in row['sources'])
            flat['source_sha256'] = '; '.join(s['sha256'] for s in row['sources'])
            writer.writerow(flat)
    pdf, pages = build_pdf(data)
    manifest = {'pdf': pdf.name, 'pages': pages, 'requests': len(data['requests']),
                'known_total_charged_usd': data['summary']['known_total_charged_usd'],
                'receipt_matched_requests': sum(r['receipt_status'].startswith('Receipt matched') for r in data['requests']),
                'artifacts': {p.name: sha(p.read_bytes()) for p in [pdf, csv_path, json_path]}}
    (OUT / 'artifact_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
