# Paper outcome bindings

Each registered paper task retains one task ID and can declare two independent
outcomes: recreate the original findings and exceed them on the same original
task. Each outcome has separate paper+data and paper+data+author-code conditions.
Contract eligibility, a consistent metadata receipt and a scientific result are
different claims. The catalog reports scientific results as unknown.

`reproduction.v1.json` contains a v1 source-grounded reproduction contract;
`reproduction.v2.json` contains an explicitly selected structured v2 contract.
The filename and declared `schema_version` must agree. The registry pins exactly
one current reproduction contract, and its version selects the reviewed validator.
`improvement.v1.json` keeps its existing criteria unchanged.
`outcomes.v1.json` binds both contract digests and the raw current `task.json`
digest. The current task refers to filenames, so the bindings have no digest
cycle. A change to the selected reproduction version requires a separately
reviewed task projection and descriptor binding. Initial adoption refuses two
unbound v1/v2 variants; after adoption the exact registry pin selects the current
contract. The full repository ownership gate rejects unowned alternate metadata,
which never selects a validator or changes an inspected contract. Neither an
author baseline nor a historical reconstruction is promoted to
a newly qualified AI reproduction.

The registry separately pins the current definition, the two contracts and the
outcome descriptor. The exact immediately previous definition is retained at
`historical/task.pre-outcomes.v1.json`. The complete pre-outcomes registry is
retained at `docs/provenance/registrations/paper-pre-outcomes-v1.json`. Existing
pre-improvement definitions and initial-registration snapshots remain immutable.
Original lineage checks use the authenticated predecessor row and definition;
current bytes are never substituted into old histories.

Run `python -I -S -B scripts/maintenance/bind_paper_outcomes.py` to inspect the
deterministic metadata plan. Scientific sidecars must already exist and pass
validation. `--check` requires the planned bytes to be current; `--write` applies
the complete validated plan. The binder preserves scientific contracts, refuses
stale pins and conflicting archives, and verifies inputs again before writing.
It does not run task implementations, acquire data or generate scientific
contracts. Repository ownership, current source closures and generated navigation
must then be reviewed and refreshed with their existing maintenance commands.

Some tasks have source-adjudicated primary findings that differ from their
retained secondary improvement endpoints. Their public decisions are pinned at
`docs/provenance/paper-outcome-scope-decisions.v1.json`. Their `outcomes.v1.json`
uses `paper-outcomes-unavailable/v1`, explicitly retaining the secondary contract
and optionally binding an honest primary reproduction proposal. This marker is
not a normal paired bundle, a scientific failure or evidence of ineligibility.
All four primary scientific cells remain unknown, and primary receipt admission
is refused. Secondary source work retains its own scope.

`paper-outcomes TASK_ID` exposes both outcomes and their access conditions.
`paper-contract TASK_ID --outcome reproduction` exposes an adopted reproduction
contract or proposal. The default improvement contract route remains compatible
for normal bundles. `check-paper-outcome TASK_ID --receipt FILE` validates receipt
metadata through the selected versioned validator; it does not qualify scientific
truth or execute an evaluator. Unavailable primary bundles refuse this route and
the primary improvement comparison route.
