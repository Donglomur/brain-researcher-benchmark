# Released-summary observations and complete response collection

This task-local component presents the existing NEURAL-086 first-fixation
(`FFD`) numerical feature ABI and collects one immutable condition probability
for every query in a separately frozen job census. It fills a presentation and
collection gap; it does not change `task.json`, activate an access condition, or
replace the existing programme engine, source admission or paired-support
scorer.

The component accepts the candidate `training.json` and `query.json` objects
produced by the current shared ZuCo engine. All 17 training-person groups must
be present with both source conditions. Every training row, its label, weight,
and opaque person/item grouping remains available. No calibration subset is
selected by this component. Query rows may contain only an opaque ID and the
permitted feature block. The exact ordered query census and training-ID digest
come from the trusted issuer's pre-exposure freeze, independently of a
participant's output or chosen subset.

For `COVARIATES`, all 46 common columns are shown: 19 numerical covariates,
their 19 missingness indicators and eight EEG-availability indicators. For
`PLUS_EEG` and `COVARIATES_SHUFFLED_E`, the same common columns and all eight
source scalp-band means are shown. Nulls are retained, not filled with zero.
The implementation checks that missingness agrees with available values. It
does not shuffle EEG, calculate new features, fit transformations, infer units
that the source has not qualified, or alter the existing source recipe.

`Session.training(index)` and `Session.query(index)` return fixed numerical
observations. Their row and grouping tokens are local aliases; source file
names, source person/item IDs, held-person tokens, row HMACs, source hashes and
query labels are not returned. `render_svg(observation)` optionally renders
every value as an unscaled numerical card. These are released summaries, not
raw/cleaned EEG waveforms or a scalp topography. SVG source is not proof of
raster presentation, readability or native neural understanding.
Card width follows the longest numeric line; explicit SVG text extents retain
long finite values inside the viewport. Output is bounded to 131,072 UTF-8 bytes.

An operator can construct a session from already bound bytes:

```python
session = Session(
    training_bytes,
    query_bytes,
    {
        "training": issuer_training_pin,  # bytes and sha256, without a path
        "query": issuer_query_pin,
        "identity_sha256": issuer_job_identity_sha256,
        "training_census_sha256": frozen_job_training_census_sha256,
        "query_ids": frozen_job_query_ids,
    },
    max_input_bytes=admitted_combined_view_byte_limit,
)
```

The operator keeps the session object, input bytes, source identity, and
`finish_operator()` return private. Only the results of `overview()`,
`training(index)`, `begin_inference()` and `query(index)` belong in a participant
presentation. Training observations remain available during inference, matching
the current programme's permitted training copy. Query responses use the
session token, local query token, and one finite probability in `[0,1]`.
Unseen queries, duplicate/revised responses, cross-session responses, extra
fields, mismatched pins, unsupported feature representations and incomplete
responses are rejected. `begin_inference()` is a collection-phase boundary;
it does not attest that a participant fitted or froze a model.

`finish_operator()` restores the original opaque query IDs for the trusted
operator and binds the full ordered probability list. It emits no scores and
reads no protected query targets. Its report explicitly says it is not a
campaign-admitted result or an established isolated runtime. It is not a
substitute for a genuine execution receipt, global submission admission,
target-last access, independent reference outputs, source/support qualification
or investigation-rubric adjudication. An authenticated whole-study operator
must still run all required 18-person/five-item-fold jobs and keep the other
contexts/representations/controls and unscorable dispositions; a complete
supplied job is not a complete benchmark. FFD is this component's explicit ABI,
not a replacement for the task's secondary-context obligations.
An empty frozen query census is retained with zero predictions and an explicit
operator-disposition requirement. It never becomes a full-panel score or an
invented nonempty assessment subset.

The current source identity's `frozen_program`/`case_adaptive` labels are
retained strictly as input provenance. This component does not reinterpret
either label as a delivered direct-observation or interactive tool condition.
There is no participant process, network restriction, filesystem sandbox,
model adapter or durable controller here. Those must be supplied and qualified
before a model is given these observations. The source-condition/chronology
confound also remains: accurate condition prediction does not identify a causal
effect of reading demand.

`test_response.py` uses generated data only. It checks the real shared source
feature exporter on generated original-shaped rows for all three arms, exact
field/missingness parity, source-identity suppression, ordered census binding,
complete immutable collection, malformed-output refusal and full SVG value
coverage. No recordings, original source join, scientific fit, model evaluation
or new scientific result is involved. Maintained test command after integration:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-086/implementations/released-summary-response-v1/test_response.py
```

This new component still needs explicit registry/component CI enrollment by the
shared integrator; its presence alone does not add an automatic workflow run.
