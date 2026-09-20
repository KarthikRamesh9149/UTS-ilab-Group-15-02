# Spending audit artefacts

Client document: `OpenRouter_Spending_Audit_2026-09-20.pdf` (9 pages).

The CSV and sanitised JSON contain exactly the same 46 authoritative ledger
requests: 45 settled charges totalling USD 0.00774516 and one unresolved request.
Each settled charge is matched to a preserved or recovered provider receipt.
The JSON includes file names and SHA-256 evidence fingerprints, without account
identity, credentials, prompts, responses or private filesystem paths.

## Rebuild

Run from this folder with the bundled Python runtime:

```sh
/Users/karthikramesh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 build_spending_report.py
```

Requires ReportLab, pypdf and the Mac Arial fonts. This script makes no network
requests. It verifies the archived evidence hash, deserialises only the two
authoritative ledger databases into memory, enables read-only queries, and adds
supporting receipt metadata. It never extracts archive members to disk or edits
the runtime. Historical Mac ledger copies and synthetic ledgers are not counted.

The default independent readback and recovered receipt are existing private
evidence under the repository's `.runtime/netcup/` directory. They are read as
inputs; only allowlisted fields and file hashes enter the report outputs.

The build checks request uniqueness, receipt cost matching, exact totals,
expected page count, each identifier appearing exactly once in extracted PDF
text, and common credential/internal-path indicators. `artifact_manifest.json`
contains hashes of the three client artefacts. `report_text_for_qa.txt` and the
rendered PNGs are local review aids, not required client deliverables.

## Accounting boundaries

This is an audit of all recorded project generation requests, not an account-wide
invoice or a transaction log of every HTTP request. The unexplained USD
13.228888953 portion of the observed account balance decline is unassigned.
The USD 0.106496 unresolved reservation is not a confirmed charge. Infrastructure
and subscription costs have not been allocated without verified invoices.
