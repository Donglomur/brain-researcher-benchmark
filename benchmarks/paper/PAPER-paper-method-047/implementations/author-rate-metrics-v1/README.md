# Prepared-rate scorer for the author demo metrics

This component computes the primary per-neuron Pearson correlation and the
author demos' secondary normalized absolute error and bias. It accepts already
prepared spike-rate vectors; it does not train, infer spikes, generate targets,
select neurons, or aggregate the original Figure 1 endpoint.

The retained calibration scorer computes error and bias directly on prepared
rates. Both pinned author demos apply an additional Gaussian filter to prediction
and target before those diagnostics. This version implements that distinction
explicitly and leaves the preserved calibration code unchanged. Its qualification
is generated software controls for the demo formula, not original-paper
reproduction or empirical improvement.

## Metric definition

Let `y` and `p` be the aligned, prepared target and predicted rates on a fixed
evaluator-owned mask. Pearson correlation uses these vectors directly, with no
additional smoothing, clipping, affine fitting, or lag search. Define `G` as
SciPy's one-dimensional Gaussian filter with sigma
`sampling_rate_hz * smoothing_seconds`, `mode="reflect"`, and `truncate=4.0`.
The secondary diagnostics are `sum(abs(G(p)-G(y))) / sum(G(y))` and
`sum(G(p)-G(y)) / sum(G(y))`. Inputs must already use the same rate units.

The sampling rate and smoothing width are required arguments. The Figure 1
condition described by the source audit is 30 Hz, noise 8, with a 50 ms target
kernel. The checked-in pretrained configuration uses 25 ms; these conditions are
not interchangeable. This scorer does not certify which condition produced an
input vector. It records library versions and the supplied diagnostic condition.

As in the demo, filtering follows masking. Consequently, an internal gap is
compressed and the filter can mix adjacent retained samples across that gap.
The caller must preserve the exact prepared vector and support; it must not
silently concatenate recordings or substitute segment-local filtering while
claiming demo parity. Historical Figure 1 boundary and preprocessing provenance
remain unresolved.

Unlike the demo's prediction-derived NaN mask, the public function requires a
caller-supplied boolean mask shared by both methods. Nonfinite predictions on
that support are an error, so a candidate cannot discard difficult samples.
NaNs outside fixed support are permitted for padded boundaries. Formula parity
holds when the fixed mask equals the author's selected support. Mask provenance
and isolation require an evaluator; this library is not a security boundary.

Empty support, constant targets/predictions, one-sample correlations, and
zero-target normalization remain explicit undefined results. They are never
silently dropped or changed to zero. Negative predicted rates are retained;
clipping, if required by a source protocol, must occur upstream and be declared.

## Use

`score_rates` scores one neuron and condition. `compare_rates` scores two methods
against the same target and mask, returning descriptive candidate-minus-author
deltas. Lower absolute error is preferable; signed bias is not a monotone quality
score. Neither function supplies a significance test or paper-win decision.

The CLI accepts an evaluator-owned NPZ containing `prediction`, `target`, and
`valid_mask`, plus an optional `author` vector. It disables pickle loading and
refuses to overwrite an output. Keep authentic packets and scores outside Git.

```sh
python metrics.py --input /external/evaluator/one-neuron.npz \
  --output /external/evaluator/one-neuron-score.json \
  --sampling-rate-hz 30 --smoothing-seconds 0.05
```

NumPy and SciPy are the only nonstandard dependencies. Use the operator's pinned
environment; this component does not install them. The task-local test file uses
only generated vectors and must run through the shared test pool during the
parallel construction wave.

## Source and remaining scientific gaps

The [current author LOO demo](https://github.com/HelmchenLabSoftware/Cascade/blob/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Demo%20scripts/Demo_benchmark_model_within_dataset.py)
defines configuration-derived sigma, prepared-rate Pearson correlation, and
the additional filtering for error/bias. The
[publication-snapshot benchmarking demo](https://github.com/HelmchenLabSoftware/Cascade/blob/213fd1206653bbb9dbe68a5faa8c0dab91fc46ee/Demo%20scripts/Demo_benchmark_model.py)
uses the same diagnostic formulas. Immutable source descriptors are in
[SOURCES.json](SOURCES.json). The implementation is a new expression of these
mathematical definitions, not a copy of the author's training script.

The exact Figure 1 driver, model membership, historical preprocessing, original
aggregate and biological grouping remain unqualified. Prior identity-only
workbook audits found 117 entries per method/variant triplet and no canonical
filename crosswalk. A 105-finite-entry count occurred in Panel g, while the
paper's OASIS 105-neuron prose concerns Panel e; those counts do not establish
twelve exclusions. The initial release already contains 117 files. Do not
interpret the current contract's shorthand “historical105” as an authenticated
105-file cohort or silently select one.

No authentic data, prediction, checkpoint, or historical private target was read
to build or test this component. No paper superiority, current SOTA, or full
benchmark readiness is claimed.
