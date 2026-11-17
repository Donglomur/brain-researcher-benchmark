# Paired infant resampling extension

`uncertainty_v1.py` adds the grouped resampling operation missing from the
existing complete-support evaluator. It consumes the original reports from
`evaluate()` and calls the existing `compare()` validation before resampling.
The registered objective, support, three-expert soft-vote target, and all
predecessor files are unchanged. The authoritative [understanding
contract](../../understanding.v1.json) identifies infants as the independent
unit and requires paired infant resampling.

```python
from uncertainty_v1 import paired_infant_bootstrap

# left and right are assessor-private complete outputs of evaluate().
result = paired_infant_bootstrap(
    left, right, seed="prospectively-frozen-seed", resamples=10000, confidence=0.95,
)
```

Freeze the seed, replicate count and interval level before inspecting outcomes.
The function records those choices and hashes both complete input reports. It
cannot enforce prospective freezing or authenticate hand-edited reports.

Each replicate draws 79 infants uniformly with replacement and averages their
paired `right - left` soft-vote Brier losses. Both arms share the same sampled
infants; all windows and all experts remain within their infant-level score.
Long recordings receive no extra weight. Infants with flagged signals remain
included. A negative difference favors the right arm. No quality-stratum
selection or expert-level/window-level pseudoreplication is performed.

The result includes the original equal-infant point difference, a percentile
interval, the sample standard deviation of bootstrap means, and a digest of the
ordered bootstrap means. Quantiles linearly interpolate at `(B - 1) * p`, where
`B` is the requested replicate count. The seeded draw stream uses the documented
SHA-256 counter algorithm in `_indices`; rejection removes modulo bias and
avoids reliance on a particular Python PRNG version. Memory is proportional to
the requested number of replicates, not the EEG window count. Computational
cost is proportional to `79 * B`; operators still own execution budgets.

The interval is **conditional on the supplied frozen predictions and observed
cohort**. The five held folds have overlapping training sets, so their fitted
predictions can induce dependencies between infant losses. This helper performs
no refitting and does not include training-set or model-selection variation.
Population coverage and full learning-procedure uncertainty require a separate
prospective design; the percentile interval alone supplies neither a superiority
decision nor a clinical claim. It produces no p-value.

This is an assessor-side metric component, not a participant runtime. Input and
output reports must remain private because the original reports contain infant
identities and outcome-derived values. No direct/viewer/tool/programme access
mode is promoted, and no source or scientific readiness state changes.

All-79 native EDF normalization, corrected three-stream alignment, calibrated
quality flags, competent train-only comparators, protected case transport and
public-label contamination limitations remain unresolved by this component.
The original source pins remain Zenodo `4940267-v4` and author code revision
`1a59e4b414f28aba52e61c3360fdc324199071b4`; this extension obtains no new data.

`test_uncertainty_v1.py` uses only generated cohorts through the existing
reference/evaluation path. It checks a hand-derived two-replicate result,
pairing, unequal durations, constant differences, reversal of comparison
direction, reproducibility, malformed support and parameters, interpolation,
and rejection of biased integer draws. These are software controls, not
authentic neonatal evaluations. Run with the project's shared lightweight
test pool and ordinary unittest discovery for this directory.
