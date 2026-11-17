# Temporal-adaptation prediction interface

This component connects the existing complete source plans to participant
observations, durable candidate predictions and the original Figure 3 numerical
reduction. It performs no fitting and executes no participant code.

Each separately selected branch retains **79 electrodes, 72 conditions, 819
samples and 2,054 coordinates**: 1,896 cross-validation coordinates and 158
full-data coordinates. Both original DN-none and category-scaled DN-S comparison
slots remain present. Those slot names identify the author comparison; they do
not attest the candidate's architecture. Reusing one frozen method identity in
multiple slots does not create multiple independent attempts.

`source_positional_cv` preserves the source's 819-column selection:
`temp_cond` followed by response samples 0–817. `named_response_columns` uses
response samples 0–818. These branches have different targets and never share a
score. Full-data coordinates use all 72 **named** responses in both branches.
The physical sample-time variable is retained without pretending that the
positional branch's first column is a neural time sample.

## Observation and prediction flow

`protocol.Source` authenticates the unchanged producer, replay implementation and
cohort. `protocol.Protocol` binds an externally frozen source plan, the candidate
method digest and exactly one assistance condition (`paper_data` or
`paper_data_author_code`). It snapshots the plan, rejects incomplete panels and
the separately available three-scaling diagnostic plan, and refuses later public
attribute reassignment. The method digest is an operator attestation, not proof
of which code or model was executed. The paper and author-code material packages
are separate external obligations; a condition label does not deliver them.

`Protocol.project_job` is a trusted preparation primitive. Cross-validation
observations contain 66 training responses, six response-free query identities,
the original time/pulse variables and exact source provenance. Full-data
observations expose all 72 responses and are explicitly labeled as observed
data, not held-out prediction. No source path, protected input bank or Protocol
object belongs in the participant interface.

`delivery.DeliverySession` creates a fresh operator-owned directory. Its
`observe(input_root)` / `submit(predictions=...)` sequence visits all 1,896 CV
coordinates first. `submit(failure={"type": "candidate_declined", "message":
"..."})` retains an explicit failure instead of dropping a coordinate. Every
CV output is authenticated and bound in `CV_FREEZE.json` before the first
full-data observation can be returned. The remaining 158 outputs are then
collected. `seal()` checks the earlier CV commitments again and joins the full
prediction manifest to a separate delivery receipt.

**Interactive held-out use remains unqualified.** Training conditions in one
fold include another fold's query responses. A runner must start a fresh
participant context for every coordinate and prohibit response, fitted state,
messages and scratch-file carryover across folds, comparison slots and branches.
Freeze the candidate programme or scientific procedure before observations are
delivered. Sequential delivery and content hashes alone do not enforce those
requirements. This component supplies no process sandbox, provider adapter,
resource enforcement or execution attestation. The session has no resume mode.

## Durable submission and scoring API

The modules can be imported from this component directory. Typical trusted
operator calls are:

```python
source = Source()  # existing sibling source-model-producer-v1
protocol = Protocol(plan, externally_frozen_plan_hash, manifest,
                    frozen_method_hash, "paper_data", source)
session = DeliverySession(protocol, fresh_run_directory)

# A separately implemented runner must enforce fresh participant state here.
observation = session.observe(private_input_root)
# Send only observation and the declared public materials to that participant.
session.submit(predictions=returned_finite_traces)
# Repeat for every coordinate; alternatively record a typed failure.

commitment = session.seal()
scores = evaluate(session.predictions_directory, protocol,
                  commitment["submission"]["sha256"], private_input_root,
                  bootstrap_seed=19)
```

Each candidate record is prediction-only: source/method/row/column bindings,
either complete finite traces or a typed failure, and no submitted truth or
claimed score. The convenience `write_record` handles one record; `Writer`
validates a complete protocol once and accounts all of its exclusive writes.
`seal` requires all 2,054 canonical files, including failures. The separate
`evaluate` path authenticates **every record body** before opening any protected
target, then checks every body again against its frozen digest during scoring.
Only `Protocol.targets` supplies original target values. Missing, extra,
duplicate, malformed, aliased, relabeled or changed records are refused.

Records are bounded at 16 MiB, the manifest at 2 MiB, and the complete prediction
store at 1 GiB. These are logical operator file limits, not total native I/O or
OS memory limits. Repeated verification and protected source reads need their
own admitted run budget. Files and directories remain in operator custody;
filesystem and candidate-process isolation require a separate runner.

CV evaluation reuses the unchanged source `native_r2`: each condition score is
rounded to three decimals, six-condition fold means to four, and twelve-fold
electrode means to four. The source's 1,000-resample regional bootstrap and RNG
order are preserved, including its median of bootstrap medians. Undefined R²
remains undefined; it is not silently replaced or dropped. A failed coordinate,
including a full-data coordinate, gates all regional summaries. A submitted
coordinate with undefined R² gates its affected electrode/region without
inventing a global execution failure. Electrode bootstrap intervals are
descriptive and are not independent-participant uncertainty.

Full-data candidate traces are retained, but arbitrary models are not made to
invent DN internal components or a `converged` optimizer status. Figure 4–9
biological companion recipes, category-selected identities, historical state and
publication-to-current-release correspondence remain separate unresolved work.
This component alone establishes neither whole-paper reproduction nor improvement,
and it does not define a binary success threshold or current-SOTA comparison.

## Construction evidence

Generated controls exercise both complete plans, real 819-sample projections,
complete 2,054-record stores, failure retention, target-access ordering, source
metric parity and later-payload tampering. The complete durable transport control
uses explicit generated failures and a metadata projection seam; it is not an
authentic participant run. Numeric source-reduction parity uses shared in-memory
generated traces, avoiding a large synthetic data bank.

Run the three test files with Python 3.11 or later and the existing NumPy
environment. Their default dependency paths match this repository; an operator
may set `TEMPORAL_PRODUCER_DIR` for an authenticated alternate checkout. No data,
model, install or network request is required. `CONSTRUCTION_EVIDENCE.json`
records the composite passing controls and preserved fixture failures. Source
tests, the earlier authentic input join and this new interface do not change
the registered task's scientific-readiness status.
