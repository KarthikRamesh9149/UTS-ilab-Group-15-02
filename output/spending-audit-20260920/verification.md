# Report verification

Verified on 20 September 2026 against the preserved runtime archive and existing
read-only account evidence. No model generation or paid API call was made by the
report builder.

- 9 PDF pages; all pages rendered successfully with Poppler.
- All nine pages inspected as a contact sheet, with full-size inspection of the
  summary, methods, dense eight-request page, final fixture page and benchmark
  page. Changed pages 2 and 8 were re-rendered and re-inspected after the final
  wording updates. No clipping, overlapping text or missing request rows found.
- All 46 ledger request identifiers appear exactly once in PDF text.
- All 45 settled generation identifiers appear exactly once in PDF text.
- 45 provider receipt costs match their authoritative ledger charges exactly.
- Setup: 43 requests, USD 0.0073707. Scored: 2 settled requests, USD 0.00037446,
  plus 1 unresolved request. Known total: USD 0.00774516.
- The unresolved USD 0.106496 reservation is labelled as a hold, not a charge.
- Account decline USD 13.236634113 less known project charges USD 0.00774516
  leaves USD 13.228888953 unassigned by the available evidence.
- Text extraction checked for common key prefixes, bearer material, SSH key
  markers, private absolute paths, account workspace identifiers and email
  addresses; none appeared in the PDF.
- The companion CSV and JSON are built from the same 46 sanitised records.
- No runtime, benchmark or synced source files were changed.

Final PDF SHA-256:
`ca889808c9e0583d05f78659c0eb2bfbca0f4cb086f6632a5cbb855667b65405`

Evidence gaps remain: the failed third benchmark call has no usable generation
identity, tokens or charge; full account activity is outside the available
project evidence; HTTP metadata/receipt calls lack a complete transaction log;
infrastructure and subscription invoice allocations are not provided.
