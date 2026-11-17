# Original synthetic summary tables

This component implements the arithmetic and inclusion rules in the author's
`notebooks/synthetic/generate_summary_datasets.ipynb`, cells 4–24. It makes an
original reproduction intermediate executable: five pairs of complete and
clean tables, with explicit support records for every original unit. It does
not fit timescales, reproduce a figure or statistical model, score reproduction
against authenticated author results, or decide improvement.

Reproduction of original findings and improvement beyond them are separate,
first-class outcomes. This intermediate advances reproduction by recovering
original summary semantics. Improvement still needs a distinct protected
comparison with candidate-independent support and competent original references.
No new task ID, split, estimator restriction, or readiness promotion is added.

## Recovered source behavior

The author-designated paper release is commit
`7cdeaf0560b9bffa6c8fe4bda7a4594b312c10c5` (tag `v1.0.0`). The notebook's complete
Git blob is identical in that release and the previously retained current
revision `e78cfd2b2ea79b7a7e707db7b79e218212497e43`.
[The pinned notebook](https://github.com/iinnpp/isttc/blob/7cdeaf0560b9bffa6c8fe4bda7a4594b312c10c5/notebooks/synthetic/generate_summary_datasets.ipynb)
defines:

* `tau_ms = 50 * tau`, followed by `abs(tau_ms - tau_ms_true) / tau_ms_true * 100`.
  The source summary therefore uses **absolute** REE. The signed formula in the
  paper's displayed Eq. 21 does not describe this notebook's calculation.
* Clean support requires every column to be nonmissing and every paired method's
  R² to be at least zero. R² equal to zero is accepted. CI crossing zero and a
  nondeclining ACF do not exclude rows in these summary tables.
* `acf_decline` checks nonincreasing ACF ordinates at indices 1, 2, 3. An undefined
  ordinate yields `False`, which is a present boolean rather than a missing
  column. CI endpoints and their absolute difference remain in lag units; only
  `tau_ms` is multiplied by 50.
* Main continuous, trial, and four-method tables include the merged local
  variation (`lv`) covariate. A missing `lv` excludes their paired unit. The
  duration and trial-count tables do not merge this covariate.
* Duration support is paired independently at 60, 150, 300, 450, and 600 seconds.
  Trial-count support is paired independently at 40, 60, 80, and 100 trials.
  A failure at one coordinate does not remove other coordinates. Trial summaries
  use original sampling iteration zero, not a new random draw.

The input contains 19 distinct fits per original unit: two continuous methods
at five durations, two trial methods at four trial counts, and the extra
`sttc_trial_avg` method at 40 trials. The extra method is required by the original
three-method trial summary and does not silently replace the established
four-method finite programme. That programme alone cannot populate this complete
source intermediate.

| Output prefix | Original rows per unit | Shared clean support |
| --- | ---: | --- |
| `four_methods` | 4 | Four methods at 600 seconds / 40 trials, including `lv` |
| `continuous` | 2 | ACF and iSTTC at 600 seconds, including `lv` |
| `trials` | 3 | PearsonR, concatenated iSTTC, averaged iSTTC at 40 trials, including `lv` |
| `duration` | 10 | Two continuous methods within each duration, without `lv` |
| `trial_count` | 8 | Two trial methods within each trial count, without `lv` |

The producer requires all 100,000 units, ordered by original zero-based unit ID.
It preserves complete raw rows, including failures, before emitting the clean
companions. Its CSVs are unit-major, without pandas' exported index column;
they are semantic summary tables, not byte-identical notebook CSV exports.
The all-row continuous and three-method trial CSVs are additional audit outputs.
No condition-weighted aggregate or failure penalty is invented.

## Input and execution

`summary.py` uses Python 3.11 standard library only and processes one original
unit at a time. Input is operator-owned JSONL with exactly these unit fields:
`unit_id`, `tau_ms_true`, `fr`, `alpha`, `lv`, and `fits`.
`tau_ms_true` is the evaluator's effective Hawkes autocorrelation timescale in
milliseconds, not an unconverted kernel parameter. Identity and truth provenance
must be authenticated externally; cardinality is not identity authentication.

Each fit contains `method`, `duration_s` (continuous) or `n_trials` (epoched),
`tau`, `tau_lower`, `tau_upper`, `fit_r_squared`, and `acf_lags_1_3` (the original
three ordinates). Trial fits additionally require `trial_iteration: 0`.
Methods and coordinates are the literal entries described above. Failed numeric
fields use JSON `null`. The derived `acf_decline` boolean follows the source's
NaN comparison semantics. Numeric NaN/Infinity tokens, duplicated keys,
nonfinite values, unknown or omitted coordinates, repeated or reordered unit
IDs, and arithmetic overflow are rejected. Rejection is never recoded into a
successful fit. The source dataframe could retain infinity because it is not
NaN; this interface refuses nonfinite input rather than silently emulating an
undefined scientific result.

Invoke only after a separately frozen authentic-input/native resource protocol:

```sh
python3 -I -B benchmarks/paper/PAPER-paper-method-add-004/implementations/synthetic-summary-v1/summary.py \
  --input /operator/complete-original-fits.jsonl \
  --output /operator/new-summary-directory
```

No pickle loader is used. The numeric input and all outputs remain outside Git
and outside participant views. The candidate must never receive these ground
truths, author fits, or full-duration references through this operator path.
`support.jsonl` records each unit/method/coordinate's clean status, missing fields,
and negative-R² diagnostic. `COMPLETE.json` appears only after complete input
support; failed invocations may leave an incomplete output directory. There is
no transaction, sandbox, or full-run memory/runtime qualification claim.

## Qualification and remaining work

The twelve local tests use generated values and verify independent arithmetic,
zero-boundary R², paired exclusions, coordinate-local masks, CI units, the extra
trial method, the absent-Lv distinction, malformed input, and retained raw
failures. No authentic fit, private answer, signal body, model, or solver was run.

The recovered notebook resolves the summary-table absolute-error convention,
the listed condition grid, and these source clean masks. The downstream plotting
notebooks and R model scripts remain unauthenticated in this acquisition because
GitHub returned rate-limit responses. Their additional filters, transforms,
figure reductions, model coefficients, and numerical author results remain
unresolved. Cells 26–32 (bin-size/lag sweeps), empirical endpoints, the original
fit environment and publication numerical parity are outside this component.
No full reproduction, improvement, or current-SOTA result is established.

Canonical task/contract updates are integration proposals only: recognize this
source-backed partial resolution of summary semantics while retaining all
remaining original-panel, figure, baseline, and scientific qualification holds.
