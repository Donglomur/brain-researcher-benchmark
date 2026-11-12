# Optional probability-diagnostics join

`probability_diagnostics_join.py` adds an optional consistency join to the existing full-night sleep comparison. It accepts JSON-decoded objects and returns a detached report; it opens no files and receives no probability arrays, neural signals or stage records. The base comparison and its seven published files remain unchanged.

```python
from paired_sleep_contribution import assess
from probability_diagnostics_join import join_probability_diagnostics

# All operands below must come from the already admitted scoring/reporting path.
# envelope is the explicit v2 scorer output; it is not an installed v1 drop-in.
grade = envelope["grade"]
base_report = assess(grade, expected_support, frozen_profile)
report = join_probability_diagnostics(
    grade, base_report, envelope["probability_diagnostics"]
)
```

For a v1 grade without diagnostics, call `join_probability_diagnostics(grade, base_report)`. It returns an equal, detached report with the original unavailable calibration state. A report that already contains joined diagnostics refuses, preventing accidental double attachment. No qualification, reasoning credit or additional benchmark is granted.

The admitted grade has schema `neural007_full153_grade_v1`; its already admitted report has schema `sleep_scientific_comparison_v1`. The companion must have exactly `schema`, `predictions`, `people`, `nights`, `classes`, and `panels`, with schema `neural007_full153_probability_diagnostics_v1`. The prediction descriptor is exactly a positive integer byte count and a lowercase SHA-256 string. All three objects must bind the same descriptor. This equality is a consistency check, not proof of data or producer authenticity.

All 27 existing candidate/reference/control panels remain required: 78 people, 153 nights, six folds, five classes in order W/N1/N2/N3/R, and the existing 936 candidate plus 1,170 reference inferences upstream. Both frozen profiles are supported as separate treatments. The join preserves the base descriptive contrasts, person/fold sensitivities, undefined REM results and admission flags. It verifies common scored truth support from the original confusion rows and exact person keys across every panel. Night counts agree with the independently supplied base support; clock/mask/eligible sums and night identifiers must agree across all diagnostic panels. The grade does not supply original per-night identities or masks, so this cannot independently authenticate those identities or their provenance.

Per-person summaries require `sleep_probability_diagnostics_person_v1`, the exact five-class taxonomy, complete typed counts, full night accounting, positive eligible support and `defined: true`. The integrated original scorer refuses if a required person has no eligible epochs; a standalone accumulator's null-support result is therefore not accepted by this integrated join. Panel summaries require `sleep_probability_diagnostics_panel_v1`, all 78 people, an empty undefined-person list, equal-person aggregation and null interval/p-value fields. Closed field sets, finite nonboolean numbers, fixed floor 1e-15, valid count bounds and probability-loss ranges are checked.

The join recomputes observed class frequencies from confusion-row counts, each marginal prediction-minus-observation bias from declared mean probabilities, and all equal-person macros. It checks clipping-count consistency with the declared log loss. Multiclass Brier is the sum across five classes, without division by five. Within-person losses pool eligible epochs across nights; panel macros weight people equally. Accepted mean probability sums retain the upstream 1e-6 simplex tolerance, without normalization. Brier uses the conservative range [0, 2 + 1e-6]; log loss is bounded by -ln(1e-15). These bounds and arithmetic joins do not authenticate the individual probability rows.

Raw Brier/log-loss means and mean predicted probabilities are attributed to the trusted, already admitted protected scorer. They cannot be recovered from confusion counts, and this helper deliberately does not attempt that reconstruction. A malicious or mistaken producer can supply internally consistent false summaries. The output says `raw_probability_metrics_authenticated_by_this_join: false`. Marginal biases are descriptive calibration diagnostics; they establish neither full conditional calibration nor internal LLM understanding, causal effects, valid population confidence intervals or clinical performance. Existing scientific and native-execution holds remain.

Shared captured fitted-model and source identities also do not establish stochastic-state equivalence between original and shifted inference. The existing sleep shifted path does not generally restore random-number-generator state. Its mismatch contrasts remain descriptive comparisons under that execution protocol; neither the base report nor this summary join converts them into isolated causal signal effects. This join adds probability diagnostics without modifying the captured fit, execution protocol or interpretation of those controls.

Run the standalone invented summary controls from any directory with:

```sh
python3 -I -S -B /path/to/test_probability_diagnostics_join.py -v
```

The test imports only the adjacent join module. Its complete-support synthetic summaries are analytic fixed-confidence examples, not authentic sleep records or probability-array computations. Separate private source validation composed this helper with both accepted base reporting profiles. Source review and engineering controls are not scientific results.
