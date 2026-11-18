# Condition-matched constant count baseline

This component supplies the constant-rate diagnostic already required by the
marmoset task. It takes the existing safe training-response adapter's complete
output, computes one mean spike count per selected cell, and returns the existing
protected scorer's prediction format on every declared eligible test update.
It adds no task, data source, access condition or scientific-readiness claim.

For each cell, the mean is the exact integer sum of every permitted **fit-domain**
training count divided by the total number of its training observations. All
declared trials, updates and seeds contribute; observations are weighted equally,
so unequal streams are not given equal weight. The count sums and denominators
remain integers. Predicted expected counts use binary64 rounding of their ratio.
There is no conversion to hertz, smoothing, cropping, quality selection, response
normalization, test-driven fit or likelihood floor in the predictor.

The six existing information conditions are unchanged:

| Condition | Counts used to estimate means | Additional counts excluded from means |
| --- | --- | --- |
| `wn_to_wn` | WN training | None |
| `wn_to_nm_source_only` | WN training | None |
| `nm_to_nm_source_only` | NM training, all declared seeds | None |
| `nm_to_wn_source_only` | NM training, all declared seeds | None |
| `nm_to_nm_wn_calibrated_author` | NM training, all declared seeds | WN calibration-only training |
| `nm_to_wn_wn_assisted` | NM training, all declared seeds | WN calibration-only training |

Providing calibration counts does not make them fitting observations. Their
metadata and integer domain are validated, but their numerical values are never
added to means. This baseline needs no RF/STA calibration. Consequently, equal
NM means in strict and assisted conditions are expected; they do not establish
equivalence of more complex models or qualify an NM-only RF method.

## Interface and source binding

Load `constant.py` with `importlib` from its installed component directory. The
existing sibling `training-response/train_only.py` and
`protected-scoring-v1/scorer.py` must match the SHA-256 identities in
[SOURCE.json](SOURCE.json). Python standard-library modules are sufficient.
The component hashes those code files once during import. It does not import the
original permissive author loader. The prediction function then performs no file
access and accepts no protected response body.

```python
result = constant.predict(
    qualified_training_policy,
    frozen_training_adapter_result,
    qualified_scoring_policy,
    training_policy_sha256=externally_frozen_training_policy_hash,
    training_result_sha256=externally_frozen_training_result_hash,
    score_policy_sha256=externally_frozen_scoring_policy_hash,
    training_count_byte_budget=complete_prepared_count_bytes,
    prediction_byte_budget=complete_prediction_buffer_bytes,
)
```

Training-policy hashes use the training adapter's canonical JSON convention.
The result and scoring-policy hashes use the protected scorer's `fingerprint`
function, which substitutes byte-length/SHA descriptors only for hashing while
retaining actual immutable buffers as operands. The policies must agree on task,
original release, condition, census evidence and every classified cell in its
original preparation and order. Every target-domain preparation/seed declared in
the training policy must occur in the scoring policy. The scoring policy retains
all externally frozen eligible update IDs; its counts cannot exceed the declared
native test extent. This component does not invent the temporal-crop rule or
authenticate eligible update identities.

The prepared result must contain all and only the permitted training streams,
with exact row/trial/frame identities, count dtype and units, original-source
hashes and timing evidence. It rejects omitted, duplicated or extra packets;
wrong calibration permissions; negative, fractional or nonfinite counts; changed
cohort/condition bindings; and insufficient whole-buffer allocations. It does not
return an earlier successful subset if any later operand fails. Both original
preparations and the full fixed170-cell class census remain mandatory. A falsely
declared native census is still possible without external source authentication.

The output contains `fit` with each cell's exact count sum, denominator and mean,
and `predictions` in the existing `marmoset-predictions-v1` schema. The model
commitment includes implementation identity, the frozen training-policy/result
identities and the complete fitted statistics. The separate scoring-policy hash
binds evaluation support without making test observations part of the fit.
All test updates receive their cell's same expected count. No targets or target
summaries are returned or inspected.

The byte budgets are complete buffer checks, not limits on Python peak memory or
operating-system isolation. Inputs already reside in memory, and metadata,
hashing and output temporaries coexist. Actual full-source preparation/prediction
must receive its own resource and execution admission. The pure function does
not establish file custody, freezing chronology or absence of prior exposure.

## How to interpret scores

A constant prediction has **undefined Pearson correlation**. Keep that value
undefined with the existing scorer's explicit reason and coverage count. Do not
replace it with zero, drop cells, or call its correlation a performance floor.
The registered individual-repeat Poisson NLL is well-defined using the scorer's
externally frozen positive likelihood floor; that floor affects scoring only.

This diagnostic is not the competent spatial-contrast reference required for a
paired improvement claim. It does not supply LN, SC or CNN fits, establish paper
reproduction, or demonstrate native understanding. Stimulus reconstruction,
source-qualified clocks/crops and cell/seed census, competent condition-matched
reference models, full protected execution and scientific qualification remain
outstanding. Current direct/viewer modes remain unsuitable: displaying protected
query spikes would disclose the encoding target.

The170-cell roster was historically selected using test reliability. Restricting
new fitting to permitted training counts does not erase that exposure. Two
retinal preparations are not established independent animals; this component
makes no population inference or SOTA claim.

## Generated verification

`test_constant.py` contains10 focused controls. They use the existing training
adapter on generated NPY byte bodies and the existing protected scorer on
generated counts. They cover all170 cells/both preparations/six conditions,
unequal-stream weighting, excluded calibration-only counts, exact sums above
binary64 integer precision, complete target streams and cell order, immutable
operand identities, insufficient allocations, malformed counts, and the expected
undefined-correlation/finite-Poisson result. A check forbids runtime file opens.
These checks contain no authentic observations and establish software behavior
only. The sole integration owner must enroll this new component and its10 tests
in maintained CI; source presence alone is not enrollment.

```sh
python3 -I -S -B benchmarks/neural/marmoset-retinal-contrast-generalization/implementations/constant-rate-v1/test_constant.py
```

The first local construction invocation ran all10 tests successfully. Unchanged
dependency suites were not replayed. Evidence and exact execution cost remain
in the private construction handoff; no local paths or private data are required
by the public component.
