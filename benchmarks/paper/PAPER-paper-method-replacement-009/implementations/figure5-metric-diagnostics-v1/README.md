# Figure 5 metric diagnostics

This additive numerical component exposes an unresolved metric disagreement in
the preserved runtime. It does not activate a Figure 5 benchmark or establish
paper performance. The original cohort, preprocessing, dynamic score reduction,
plotted aggregation and author calibration remain unresolved in
[`improvement.v1.json`](../../improvement.v1.json). Historical implementations and
source bodies are unchanged.

Reproduction of the original finding and improvement on the same task are
separate first-class outcomes. Resolving the metric disagreement supports both;
this component establishes neither outcome and does not merge their scores.

The [pinned author evaluator](https://github.com/yzhang511/neural_decoding/blob/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/utils/eval_utils.py#L77-L83)
computes regression R² after flattening trials and outputs and classification
accuracy after argmax. Figure 5A–D instead requires choice AUC, prior Pearson
correlation and dynamic-behavior R², as recorded by the existing source-reviewed
improvement contract. The preserved `programme/scoring.py` uses flattened dynamic
R², while `programme/full_score.py` uses uniform-output R². Source presence does
not decide which reduction generated the original dynamic panels.

`metrics.py` supplies:

- Continuous-score binary AUC with tie handling and explicit single-class
  undefined scores; static prior Pearson correlation with constant-input handling.
- Both flattened R² and uniform-output R² on exactly matched trial/output shapes,
  with every output-bin result retained. Uniform-output R² stays undefined if any
  bin has constant truth; it does not silently use scikit-learn's `force_finite`
  constant-bin replacement. This strict convention is a diagnostic, not an
  assertion about the paper's original undefined-value handling.
- Descriptive session and animal means for one target/region/method group, with
  a required nonempty earlier expected census. Missing and undefined sessions
  retain their denominator and prevent a complete mean. Distinct regions,
  targets and methods cannot be silently pooled.

For the generated arrays `truth=[[0,100],[2,102]]` and
`prediction=[[1,101],[1,101]]`, flattened R² is `1-4/10004` while uniform-output
R² is `0`. This arithmetic counterexample demonstrates a material difference,
not a measured biological effect. A constant second output bin also demonstrates
why undefined per-bin scores must remain visible during source reconciliation.

Use `score_case(target, truth, prediction)` on explicitly paired values, then
`summarize_group(expected_cases, scores, metric_name)` on an operator-selected
case census. Each expected case has `case_id`, `session`, `animal`, `target`,
`region` and `condition`. The caller must establish trial ordering, label
orientation, animal identities, source admission and the prediction/target
barrier independently. This module does not read files or issue qualification.
It accepts ordinary Python lists/tuples; no additional dependencies are required.
Pearson centers independently scaled inputs to avoid overflow from large finite
values. R² still uses binary64 arithmetic; extreme finite magnitudes can raise
an arithmetic overflow instead of producing a score.

All controls in `test_metrics.py` use tiny generated values and hand-derived
results. Run them through the wave's shared two-slot `test_pool.py`, with owner
`paper_01`, one thread, at most 1 GiB and 180 seconds. These checks neither load
authentic recordings nor fit/run a model. No numeric published baseline, authentic
input preparation, author inference, scientific improvement, or current SOTA is
claimed. Independent review and central integration/CI enrollment remain separate.
