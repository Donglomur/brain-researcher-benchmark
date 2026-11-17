# Matched FCz error companion

This stdlib scorer measures error in the fixed NEURAL-078 matched FCz estimand. It accepts the existing complete eight-person `neural078_contrast_submission_v1` report and an operator-selected reference report. It leaves the historical 195-field tolerance-agreement grade and all predecessor source files unchanged.

The primary metric is the equal-person mean absolute error in `matched_FCz_contrast`, in `native_EEGLAB_amplitude` units. Those source units have not been independently identified as microvolts. Each of the eight people receives weight 1/8, regardless of matched-pair count. The metric does not average signed errors before taking an absolute value; opposing errors cannot cancel. Lower error is better. A fixed zero-contrast predictor's complete-cohort MAE is also reported, using the same people and target units.

The complete schema, fixed participant roster, protocol hash, finite/null policy and ten-pair threshold are derived from the existing [analysis core](../neural078-deferred-grade/scorer/analysis_core.py) and [public report contract](../neural078-deferred-grade/producer/program/report_contract.py). Before scoring, every eligible count, stratum count, matched-pair count, pair digest and support status must exactly match the reference. Different support is rejected, not dropped or assigned a favorable subset score. The report contains pair digests, not trial IDs; equality confirms the reports' pair-identity commitments. It does not independently authenticate the underlying trials or recompute their pairing.

If any reference participant has fewer than ten pairs, the complete-cohort primary and zero-contrast comparator are `null`. The result names every unsupported person and retains their null fields. Supported-subset errors are explicitly diagnostic and cannot substitute for the complete-cohort primary. Null, positive and negative reference effects are all legitimate. Three-way sign agreement (negative/zero/positive) is diagnostic only; there is no required negative ERN effect or sign gate.

All 58 original numeric fields receive separate absolute-error diagnostics: seven fields per person plus two aggregate fields. RT errors use milliseconds; amplitude errors retain native EEG units. Different physical units are never averaged into one score. The original report permits finite numeric RT and aggregate fields without enforcing their arithmetic or physical consistency; this companion preserves that admission policy and reports their error against the reference. It does not add new caliper or aggregate-arithmetic rejection rules. Values whose calculated error cannot be represented as a finite JSON float, or whose nonzero mean error would round to zero, are refused with an arithmetic-range error.

Run from the repository root, after freezing the complete submission and independently admitting the selected reference:

```sh
python3 benchmarks/neural/NEURAL-078/implementations/understanding-metrics-v1/score.py \
  --submission /operator/frozen-submission.json \
  --gold /operator/admitted-reference.json \
  --gold-sha256 "$OPERATOR_REFERENCE_SHA256" \
  --output /operator/new-matched-fcz-errors.json
```

The paths above are placeholders; set `OPERATOR_REFERENCE_SHA256` to the independently recorded selected reference hash. Both inputs are bounded to 64 KiB; duplicate JSON keys, nonfinite numbers, extra fields, omitted people and malformed support are rejected. The entire candidate is validated before the reference is opened. The explicit reference SHA256 binds selected bytes; it does not establish reference competence or admission. Output must be new. Refusal exits 2, success exits 0. Python users may call `compare(candidate, gold)` after independently managing source identity and custody; that dictionary API does not authenticate files.

Detailed errors and signs are **operator-only post-freeze diagnostics**. They disclose target-derived information and must not be returned as iterative candidate feedback. This standalone scorer is not a sandbox, participant transport or authorization path. Parent-directory filesystem isolation and protection against a hostile same-user process are not provided.

The [current source inspection](../../docs/current-source-inspection.md) identifies a repaired RT-validation core whose numerical-source identity differs from the originally admitted protected grading binding. This companion does not remove that hold or authorize use of the old protected reference. An independently recomputed and admitted reference matching the selected numerical source remains necessary. Authentic packet custody, raw trial pairing, timing/filtering provenance, complete producer execution and scientific qualification remain unestablished by this addition.

This is numerical evaluation of a descriptive observational analysis with grouping covariates exposed. It does not measure hidden EEG-label prediction, direct waveform interpretation, causal error processing, human performance or model reasoning. No recording, protected target or model was read or run during construction.

Generated source controls:

```sh
python3 -m unittest discover \
  -s benchmarks/neural/NEURAL-078/implementations/understanding-metrics-v1 \
  -p 'test_*.py' -v
```

Tests cover the independently specified cancellation/unequal-pair-count example, complete support and identity, unsupported outcomes, units, signs, numerical range and public-before-reference CLI ordering. They establish software behavior only.
