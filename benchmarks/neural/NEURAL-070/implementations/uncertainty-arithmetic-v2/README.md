# Finite crossed-bootstrap arithmetic

This callable successor repairs uncertainty arithmetic for NEURAL-070. It leaves
the registered objective, primary R² scorer, predecessor implementation and
historical source descriptors unchanged. It is an implementation component,
not an activated or scientifically qualified benchmark.

The predecessor `n070.statistics.crossed_bootstrap` averages coordinate scores
with NumPy `mean`, then participant scores with `sum(...)/10`. Both can overflow
on finite, valid negative R² values. For example, two generated target rows
`[-0.5, 0.5]` and predictions `5e153` give finite R² near `-1e308` in each
coordinate; averaging two identical coordinate scores overflows in the
predecessor. The repaired primary scorer already handles this case, so the
uncertainty path could fail after a valid complete primary report.

`statistics_v2.py` computes coordinate means, paired coordinate-difference
means and participant means through exact rational sums of the finite
binary64 scores, rounding each required mean once. Linear quantiles use exact
convex interpolation, avoiding overflow when comparison draws span opposite
large values. The two probabilities are exactly `1/1840` and `1839/1840`, the
declared two-sided 0.05/46 Bonferroni tails. This preserves the mathematical
estimator; it does not promise low-bit parity with NumPy interpolation.
Unrepresentable nonzero means or interval endpoints remain unavailable, rather
than silently rounding to zero. Any undefined draw blocks all intervals, and
every requested draw is attempted without replacement of failed draws.

The procedure remains conditional on fixed fitted predictions and released
joint GLMsingle VersionB measurements: ten participant selections with
replacement, source-equivalence-group resampling, shared indices across all
46 ROIs and all three metric families, both protected fixed references, at
least 20,000 draws, and separate 46-ROI multiplicity families. There is no
refitting, candidate-self-contrast reward, simultaneous coverage claim across
families, or new evidence of direct interpretation. Ten-person uncertainty
calibration remains outstanding.

## Use and integration boundary

Make the sibling `registered-runtime/programme` directory and this directory
importable, then call `statistics_v2.crossed_bootstrap` with the same positional
arguments as `n070.statistics.crossed_bootstrap`. It accepts evaluator-owned
arrays; it opens no data files and performs no fitting or model execution.
The internal `_score_draw` helper exists for generated controls and does not
relax the public 20,000-draw floor.

The original `n070.scorer.run` still imports the preserved predecessor.
Integration must explicitly select this successor at that existing target-last
call site and update the applicable source closure. This component does not
silently modify that caller, canonical task, registration or protected runtime.
Dependency and predecessor hashes appear in `SOURCE.json`.

## Generated controls

Run `test_statistics_v2.py` using the shared test pool and an existing Python
environment with NumPy. No extra dependency is required. The tests cover the
actual 460-cell generated draw, the preserved overflow counterexample, paired
rounding, underflow refusal, constant-support and bad-reference failures,
signed-extreme quantiles, ordinary quantile parity, and full 20,000-dispatch
control flow. The dispatcher controls stub per-draw scoring and, in the
successful dispatcher control, quantile calculation; these controls do not
constitute a scientific bootstrap run. Arithmetic helpers and complete draw
scoring are separately exercised with generated arrays.

No authentic data, private historical answers, source downloads, model trials
or native scientific preparation are used. Actual execution results and costs
are recorded in the external handoff. Source identity and generated controls
do not resolve authentic roster/rights/mask/coordinate joins, environment and
checkpoint qualification, reference competence, full native execution, or
uncertainty calibration.
