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

For normal paired declarations, the registry separately pins the current
definition, the two contracts and the outcome descriptor. The exact immediately previous definition is retained at
`historical/task.pre-outcomes.v1.json`. The complete pre-outcomes registry is
retained at `docs/provenance/registrations/paper-pre-outcomes-v1.json`. Existing
pre-improvement definitions and initial-registration snapshots remain immutable.
Original lineage checks use the authenticated predecessor row and definition;
current bytes are never substituted into old histories.

Run `python -I -S -B scripts/maintenance/bind_paper_outcomes.py` to inspect the
deterministic metadata plan. Required scientific sidecars must already exist and
pass validation; the explicit source-declaration-gap route below has no such
sidecars. `--check` requires the planned bytes to be current; `--write` applies
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

A reviewed source component can also belong to the original finding family while
covering too little of it to establish the complete primary result. New decisions
use `unavailable_complete_primary_pairing` with the explicit
`full_primary_pairing_unavailable` route for this neutral representation. Its
marker must use `reason_code: "full_primary_pairing_unavailable"`; the existing
scope-mismatch status keeps its original reason code. Neither route accepts a
normal paired bundle. The exact source relation and declared coverage remain in
the pinned decision, without treating a genuine component as an unrelated result.

The public scope artifact separately records `same_primary_corrections`. These
retain normal paired declarations and the unchanged same-paper and scientific
anchor checks. Their reviewed goal, source scope and outstanding limits appear
in the current definition and navigation; they are not scope-mismatch markers.
This reviewed adoption requires unresolved reproduction source eligibility and
an improvement contract that is not improvement-ready. Partial source components
cannot qualify the complete primary family. Removing these source and criterion
holds requires separately reviewed evidence and an explicit adoption revision.
An explicitly selected original primary family may retain the source disposition
`explicit_primary_selection` when its reviewed route is
`normal_same_primary_unqualified`. The source disposition remains visible; it
does not change the contract-anchor checks or grant eligibility.
Source-gap confirmations use the separate passive `source_gap_confirmations`
map with `projection_action: "none"`. They cannot also appear in an active
correction map, and do not change a task's accepted projection or eligibility.

Two tasks, `PAPER-paper-method-011` and
`PAPER-paper-method-replacement-009`, retain compatible original scope and an
independent improvement contract but lack an honest complete reproduction
declaration. Their distinct `source_declaration_unavailable` route pins
`docs/provenance/paper-outcome-source-declaration-gaps.v1.json` globally and in
each task's outcome binding. Initial adoption requires the exact independently
reviewed raw record; it cannot replace that authority by hashing a different
valid-shaped file. Later checks authenticate the explicit registered pins and
the exact original task, improvement contract, source paper and scientific
anchors. This route does not classify the task as a scope mismatch or infer
scientific ineligibility.

These two task definitions keep reproduction as an independent goal while their
reproduction and paired-protocol references are null. No reproduction or outcomes
sidecar is created. The binder refuses physical sidecars that conflict with this
absence, and the repository namespace gate rejects unowned extra metadata. The
unchanged improvement contract remains independently inspectable and keeps its
own comparison and eligibility rules. All four scientific cells remain unknown;
paired receipt admission is unavailable until honest source declarations and
matched access protocols are separately reviewed and adopted.

Once paper-outcomes coverage is adopted, the immutable original roster determines
which tasks require this gap route. Removing a current selector or catalog row
cannot hide that requirement. Source-only registries remain unbound. Every new
validation authenticates the record and predecessor bytes again; previously
loaded catalogs do not authorize changed files. External documentary assessment
locators are retained provenance and are never opened as runtime inputs.

`paper-outcomes TASK_ID` exposes both outcomes and their access conditions.
`paper-contract TASK_ID --outcome reproduction` exposes an adopted reproduction
contract or proposal. The default improvement contract route remains compatible
for normal bundles. `check-paper-outcome TASK_ID --receipt FILE` validates receipt
metadata through the selected versioned validator; it does not qualify scientific
truth or execute an evaluator. Unavailable primary bundles refuse this route and
the primary improvement comparison route. Source-declaration gaps instead retain
independent improvement inspection and comparison: `paper-outcomes` shows the
gap with a null descriptor, reproduction inspection refuses the absent contract,
and paired receipt checking refuses before reading the supplied receipt.
