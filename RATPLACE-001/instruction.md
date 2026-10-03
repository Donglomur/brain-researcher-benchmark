# Mouse CA1 normalized-position spatial information

Using the original NWB recording baked into /app/data/ratplace, implement the fixed normalized-position methods case described in /app/methods.md and /app/method_contract.json. RATPLACE-001 is a legacy task identifier: this recording is mouse M02, not a rat or spaceflight experiment.

The source has independent camera tracking, but physical-unit metadata conflict with author raw-coordinate usage. Preserve this limitation. Use the supplied camera observation window, a scale-invariant 4 x 5 grid, the disclosed CA1 operational unit selection, and 300 deterministic elapsed-window shifts. Do not infer centimeters, speed, maze epochs, biological cell class, or a required outcome.

Authenticate the source using /app/source_manifest.json. No network access is needed or allowed at runtime. Do not use a hidden reference bank or substitute derived example data.

Write these five artifacts to OUTPUT_DIR (default /app/output):

- spatial_information.csv — all eligible units, exact counts and own-replay scalar receipts.
- spatial_evidence.npz — bounded source-bound occupancy, counts, offsets, masks and explicit axes.
- results.json — equal-unit summaries derived from accepted CSV receipts.
- run_metadata.json — all-source unit ledger, provenance, tracking/clock support and fixed contract pins.
- findings.md — a concise interpretation limited to this methods case and source limitations.

Exact typed fields, null rules, storage bounds and permitted coherent permutations are in /app/output_schema.json. Undefined null draws, no eligible units, and negative adjusted information are valid when correctly represented. A resource pilot is not a completed submission. Any failure_report.json means failure, not partial success.
