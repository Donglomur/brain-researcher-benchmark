# Paired integration-window quantities

This component computes the source-defined per-electrode window quantities in
the primary Figure 3 family declared by [reproduction.v2.json](../../reproduction.v2.json).
It consumes already fitted source-shaped values; it does not fit neural responses
or establish source authenticity, native parity, reproduction or improvement.

The pinned author [intwin_maps.m](https://github.com/snormanhaignere/time-vs-structure/blob/08f2319a99a047ab2d1f631e0bffcfcea8a5bc08/matlab-code/intwin_maps.m)
concatenates the slow and fast tied integration widths in participant/electrode
order, computes `(log2(slow_width) - log2(fast_width)) / log2(3)`, and selects map
entries using the strict condition `slow_logP / 2 + fast_logP / 2 > 3`.
The overall window is independently supplied by `M{3,i}.best_intper_sec`; it is
not the mean of the two tied widths. This component emits that width and its
base-two logarithm, preserving both original rate-specific quality values.

Every supplied electrode is returned, including those below or exactly at the
quality boundary. Input participant order and within-participant electrode order
are retained. No yoking value is clipped to a zero-to-one or display range, and
no population average, success threshold, p-value conversion or biological
independence claim is introduced. Anatomy is outside this component; the returned
participant/electrode keys support a later independently authenticated join.

## Input and output

The API is `paired_quantities(panel)` in `quantities.py`. Its JSON-compatible
input is:

```json
{
  "schema": "find024-paired-window-input/v1",
  "participants": [{
    "participant_id": "generated-person",
    "electrode_ids": ["generated-electrode"],
    "slow_tied_width_sec": [0.375],
    "fast_tied_width_sec": [0.125],
    "overall_width_sec": [0.25],
    "slow_logP_gaussfit": [2.0],
    "fast_logP_gaussfit": [5.0]
  }]
}
```

This example is generated, not an empirical source record. For each participant,
all five vectors must cover the same ordered electrode list. IDs must be unique
within their stated scope; electrode names may repeat in different participants.
All values must be finite real numbers, and widths must be positive seconds.
An invalid or incomplete row rejects the whole panel rather than being omitted.
This is an explicit finite-domain restriction; the component does not reproduce
native undefined-fit handling or claim to cover a cohort containing such fits.

The output retains all raw supplied numbers, paired structure-yoking values,
mean-rate fit quality and the source eligibility flag, plus participant and
electrode counts. Floating calculations use the source log difference rather than
forming a width ratio, so extreme positive finite widths remain representable.
Counts describe the supplied input, not a verified original cohort.

The offline CLI takes an operator-frozen SHA-256 and captures input bytes once.
Its hash and arithmetic refer to the same captured input even if the pathname
changes. Byte identity alone does not establish empirical provenance.

```sh
python3 benchmarks/paper/PAPER-FIND-024/implementations/paired-window-quantities-v1/quantities.py \
  /absolute/path/panel.json /absolute/path/quantities.json \
  --expected-sha256 OPERATOR_FROZEN_SHA256
python3 -I -S -B -m unittest discover \
  -s benchmarks/paper/PAPER-FIND-024/implementations/paired-window-quantities-v1/tests -v
```

Python 3.10+ standard library is sufficient. Generated checks cover analytic
yoking values, strict eligibility, independent overall widths, input ordering,
invalid-row refusal and snapshot binding. They are software controls.

## Remaining scientific work

Original neural fitting and native TCI dependency closure, source input and cohort
identity, anatomical matching, undefined-fit policy, model-free CCC corroboration,
hierarchy-aware uncertainty and justified original-result comparison remain
unresolved. This transformation is one part of the declared primary array family;
it does not complete it. The secondary opposite-split reliability correlations
remain separate and are not computed here. Existing task contracts and historical
components are unchanged.
