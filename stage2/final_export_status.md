# Audited final result exports

`export_final.py --output <new-directory>` takes the common matrix lock,
validates the frozen final registration and qualification, reaudits development
prerequisites and all 267 final receipts, and runs the paired analysis before
creating an output directory. Incomplete final matrices produce no export.

Outputs are `final_trials.csv`, `comparison.json`, `provenance.json` and a final
`export_complete.json` checksum marker. Existing directories are never
overwritten. A partial export without its completion marker is not complete.
The provenance links all 267 raw result hashes and the final registration hash.

Only allowlisted task/condition identities, rewards, protocol fingerprint,
costs, usage, budget stops and agent runtimes are exported. Raw model text,
credentials, prompts and hidden verifier content are excluded. This export is
the final matrix only, not total project expenditure; setup, development,
corrections and further deliverable evidence remain separately accountable.

Tests use synthetic result files and mocked admission/receipt audit. The actual
receipt audit implementation has its own test coverage. No genuine final CSV
or comparison has been generated: the compatible-host and live-evaluation
requirements remain outstanding. The exporter never dispatches trials or API
requests and never declares the overall project complete.
