# Laser-evoked EEG: complete reported-intensity scoring

This is the task-local numerical consumer for the existing registered
`NEURAL-SCOPE-20261114-LASER-EEG-REPORT` contract. It implements its full primary
denominator and fixed penalty policy. It does not construct EEG epochs, extract
ratings, run models, qualify an authentic cohort, or add a benchmark ID.

The source paper describes 678 nominal participants across nine experiments,
with experiment counts `26,29,39,30,65,95,142,223,29`. The scorer requires all
678 participant-within-experiment records and those exact counts. These are
declared source counts, not a claim to have authenticated 678 independent people
or a complete actual trial census. Cross-experiment participant reuse remains
unresolved. The primary nine-experiment transfer estimand is explicit about that
limitation; it does not become independent-person generalization by assertion.

## Primary score and complete support

The target is the recorded **pain-intensity report on [0,10]**, including zero
and decimals. It is not pain unpleasantness, delivered laser energy, objective
pain, a diagnostic label, or a direct measure of nociceptive mechanism. Numeric
Boolean values and strings are not accepted as ratings, and no rounding or
clipping changes a report.

For every person the trusted ledger includes all source trials, strictly ordered
by a nonnegative integer chronological ordinal. Explicit predeclared exclusions
have a null target and a reason. All eligible trials have finite [0,10] ratings.
The first two *eligible* chronological trials are calibration only; every later
eligible trial is scored. Excluded trials before calibration do not consume a
calibration slot. A person with fewer than three eligible trials refuses the
complete assay; that person cannot be silently removed. Actual eligible-trial
counts come from the supplied trusted ledger, never a nominal count multiplied
by a planned number of trials. This validates the ledger's internal structure,
not the historical completeness or correctness of its eligibility decisions.

For each required query:

- A unique valid median prediction has loss `abs(median - recorded_intensity)`.
- An absent, duplicated, malformed, nonfinite or out-of-range required prediction
  has loss exactly **10**, the registered maximum error on the [0,10] scale.
- A duplicate ID invalidates that required prediction even if one copy was valid.
  No last-record overwrite can recover a preferred answer.
- An invalid optional quantile pair makes its record malformed. Valid quantiles
  obey `0 <= q10 <= median <= q90 <= 10`; providing just one endpoint is invalid.

Mean trial loss is taken within each person, then mean person loss within each
experiment, then the nine experiment losses are averaged equally. All required
queries remain in their denominators, including failed predictions. The report
also gives the separately labeled 678-person-weighted mean, all nine experiment
results, person-level results, and descriptive device strata weighted by people.
Device assignment follows the paper: BioSemi experiments 1/7, ANT 2/4/5, and
Brain Products 3/6/8/9. No new benchmark or independent cohort is created by a
stratum, fold, access condition or diagnostic.

The fixed energy/context-only comparator must have every required ID exactly once
and valid output. A defective trusted comparator refuses; it never receives the
candidate penalty and inflates apparent improvement. Paired reduction is
`reference_MAE - candidate_MAE`, for each person, experiment and overall. The
reference's declared information type and selection receipt do not prove its
competence, actual information access, or proper training. Those require separate
evaluation evidence. A negative or zero neural increment is a valid result.

## Output validity and descriptive diagnostics

The numerical penalty policy is separate from structural output validity.
Every required query is scored using the same declared rule even when the
submission fails the output contract. Unknown IDs and records without usable IDs
cannot earn credit or enter a denominator; they are counted and make
`output_contract_passed` false. Missing required IDs still receive loss10.
An unknown extra ID does not erase valid required predictions or introduce an
invented global scientific penalty. The result must not be reported as a valid
submission while that flag is false.

A malformed whole JSON envelope, duplicate JSON keys, incompatible protocol or
representation identity, or nonstandard NaN/Infinity literal gives no usable
prediction records, hence loss10 for every required ID. A valid JSON numeric
overflow such as `1e400` is classified at its record and penalized there.
Complete public parsing/classification precedes the trusted-loader callback,
including an explicit invalid disposition. Invalid candidate output is not a
reason to omit a difficult case from scoring. Malformed trusted targets are an
intake error and refuse the assay instead of being candidate abstentions.

Within-person rank correlation is Spearman correlation with average ranks for
ties. It is undefined for fewer than two trials, constant vectors, or *any*
invalid required prediction; a favorable successfully parsed subset is not used.
Undefined cases retain their person/trial counts and explicit reason.

Optional interval diagnostics report inclusive `[q10,q90]` coverage and mean
width only over valid supplied intervals, alongside both supplied and required
counts and a complete-support flag. This conditional coverage can be selected by
the submitter and is not full-assay uncertainty or a claim of calibrated 80%
coverage. No coverage pass floor, clipping tolerance, bootstrap or significance
test is introduced. The contract does not fix a complete training-normalization
denominator or bootstrap algorithm; those secondary components remain pending,
along with the required biological grouping and interpretation review.

## Concrete interface

The Python API is:

```python
grade(submission_bytes, trusted_loader,
      protocol_sha256=owner_protocol_sha256,
      representation_sha256=owner_representation_sha256)
```

Both expected identities are mandatory. Null/malformed identities refuse before
the callback is called. The callback returns `(targets_dict, comparator_dict)`
from the trusted owner's storage, after public submission classification. Its
custody and scientific authority remain the caller's responsibility; objects
already loaded by a caller cannot acquire retroactive isolation through this API.

The ordinary CLI uses independently supplied trusted body hashes as well:

```sh
python3 -B scorer.py \
  --submission SUBMITTED.json \
  --protocol-sha256 OWNER_PROTOCOL_SHA256 \
  --representation-sha256 OWNER_REPRESENTATION_SHA256 \
  --targets PRIVATE_TARGETS.json --targets-sha256 OWNER_TARGET_BODY_SHA256 \
  --comparator PRIVATE_REFERENCE.json --comparator-sha256 OWNER_REFERENCE_BODY_SHA256 \
  --output NEW_PRIVATE_REPORT.json
```

All four required expected identities are checked before any file open. They
must not come from the submitter. On Unix the input helper uses a nonblocking,
no-follow open and verifies a regular file on the same descriptor, reusing the
reviewed Hypothalamic admission pattern. All input documents are bounded to
32 MiB each; no truncated input is scored. Output creation is exclusive. This
is not a filesystem sandbox, arbitrary-filesystem deadline or process owner,
and no authentic full-assay resource qualification is claimed. The complete
report remains evaluator-private; it includes case/support identifiers and
losses whose feedback policy must be enforced by the surrounding operator.

Submission object has exactly `schema` (`lep-predictions-v1`), `task_id`,
`protocol_sha256`, `representation_sha256`, and `predictions`. Each prediction
has `query_id`, `median`, and optionally both `q10`/`q90`. Opaque IDs use 1–128
ASCII letters, digits, `_` or `-`; they are never interpreted as paths. A
prediction record cannot carry a target path, raw-data locator or answer-bearing
metadata field. The absence of such fields does not prove that the model never
saw answers elsewhere.

Trusted target object has exactly:

```text
schema = lep-targets-v1
task_id = NEURAL-SCOPE-20261114-LASER-EEG-REPORT
protocol_sha256, representation_sha256
inventory_receipt_sha256, producer_receipt_sha256
people = [{experiment, person_id, trials}]
trials = [{query_id, chronology, eligible, rating, exclusion_reason}]
```

There must be exactly 678 people with all nine registered experiment counts.
`experiment` is an exact integer 1–9; `(experiment,person_id)` must be unique.
Query IDs must be globally unique throughout the complete source ledger,
including excluded and calibration records. `chronology` is an exact integer,
strictly increasing within each person's list; the producer is responsible for
joining it to authentic chronology. `eligible` is Boolean. An eligible trial
has a numeric rating and null reason; an excluded trial has null rating and a
nonempty reason of at most 512 characters. The receipt strings identify external
evidence; this numerical consumer does not authenticate that evidence's contents.

Trusted comparator object has exactly `schema` (`lep-comparator-v1`),
`reference_id`, `information` (`energy_context_only`),
`selection_receipt_sha256`, and `prediction`. The last field has the same complete
prediction-envelope schema and exact owner protocol/representation identities.
It contains precisely the scored queries, with no calibration, excluded or
unknown IDs. All hashes are 64 lowercase hexadecimal characters.

## Provenance and remaining construction

`PROVENANCE.json` cites the public primary source and describes the benchmark-authored
policy. No private source binding or original evidence body is distributed. The [collection paper](https://www.nature.com/articles/s41597-025-05900-1)
defines the nine cohorts, the nominal counts, source devices, intensity scale,
and baseline/non-intervention restriction. The per-study metadata distinguish
decimal intensity from unpleasantness and calibrated “7/10” context from
physical laser energy. The historical technical-validation code selects epochs
by known ratings/energy and averages trials; it is not a protected prediction
reference and is not copied or executed here. Source preprocessing can use whole
sessions and manual ICA/QC; no causal or neural-specific exposure claim follows.

The two-calibration-trial protocol, macro MAE and failure penalty10 are the
registered benchmark design, not published prediction performance. Actual
trial-level condition extraction, source marker delays, delivered-energy
fields, full EEG/target chronology, all-channel representation, source identities,
reference fitting, cross-experiment participant linkage, protected delivery,
model contexts and cleanup remain unqualified. This implementation supplies
neither an event extractor nor a substitute set of biological targets.

This public package is an experimental numerical component. Its publication does
not change the scientific scope, create task IDs or enable protected execution.
There is no paired A/B authoring barrier, model runner or provenance adjudicator here.

Generated controls run with `python3 -B -m unittest -v test_scorer.py`. All IDs,
targets and trial ledgers in those checks are invented. No empirical benchmark,
model/API call, acquisition or neural-array read was performed by this phase.

## Portable source distribution

Use Python 3.11 on Unix; all production and test dependencies are standard library
and included source. The CLI above works from this directory with owner-provided
inputs. `SOURCE.json` lists the flat distribution; its expected hash must come from
the reviewed release. `test_delivery.py` checks an independently relocated actual
CLI with a complete invented population. The accepted 16-method source suite remains
available and enrolled in CI; the public packaging phase does not rerun it locally.
No original EEG, paper/code bodies, targets or competent reference is distributed.
