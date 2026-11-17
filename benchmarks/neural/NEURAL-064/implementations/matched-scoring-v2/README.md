# Matched response scoring component

This independently written, standard-library component supplies the missing
numerical prediction/contrast calculations for NEURAL-064. It consumes the
existing assembled response-row schema. It does not acquire data, restore the
omitted NWB reader, authorize a native run, fit references, or establish source
membership. The preceding `neural-064` implementation and canonical contracts
are preserved unchanged.

`scoring.py` exposes `weights`, `training_scale`, `macro_error`, `contrasts`, and
`score_policy`. The first four operations can supply the numerical API already
used by the preserved reference and evidence consumers. They do not supply the
separate native `spans`, `response`, or `percentile_bins` preparation API. The
generated test exercises the preserved `_evaluate_policy` with this numerical
core while verifying that the original public native entrypoint still refuses.

The full policy consumer checks the original declared **55 FIT, 11 validation,
and 14 query mice** from the operator-owned support roster. These counts remain
unverified source declarations; matching these counts cannot authenticate a
membership list. Cases must retain their query role, biological parents,
complete FIRST/REPEAT pairs, image and subset identities. Both candidate arms
and both fixed reference families must cover every expected query case,
including familiar controls. NaN, infinity and boolean predictions are invalid.

The numerical conventions make the existing prose endpoint explicit:

- Each response row has weight `1 / mice / containers_in_mouse /
  pairs_in_container / 2`. Neural responses are already equal-cell source dF/F
  post-stimulus mean `[0.05, 0.55)` minus baseline mean `[-0.25, 0)` upstream;
  this scorer does not reinterpret a cell or imaging plane as a mouse.
- FIT scale is the population standard deviation of new-image responses with
  those weights. No sample-size correction, query scaling or epsilon is added.
  Exactly constant FIT targets produce unavailable scale.
- Within each query mouse, compute RMSE using equal container, pair and phase
  weights, divide by the frozen FIT scale, then average these mouse errors.
  The mean of mouse square roots differs from the square root of pooled MSE;
  the unequal-mouse-error arithmetic control distinguishes them.
- FIRST-minus-REPEAT contrasts average pair differences within containers, then
  containers within mice. Cell-type summaries average mice, and contrast error
  is the mean absolute per-mouse difference. No preferred sign is imposed.
- Primary gain is the frozen evaluator nuisance NRMSE minus candidate JOINT
  NRMSE. Candidate NUISANCE error is descriptive. Validation losses determine
  the selected grid member and family; first grid member wins grid ties and
  hierarchy wins family ties. Query errors cannot reverse that selection.

`score_policy(policy, candidate, targets, reference, query_binding)` accepts the
same structures passed into the preserved `_evaluate_policy` consumer, except
that it owns this numerical core internally. Valid but unavailable support,
unknown new-image status, absent reference or undefined scale leaves the primary
error and gain null with explicit reasons. Malformed identities, missing phase
partners, role changes, prediction omissions and inconsistent frozen selection
raise `ScoringError` (malformed missing structural keys can raise `KeyError`).
The two policies are evaluated separately. The caller must retain the complete
catalogue-support obligation and both policy outputs to form an investigation.

The consumer cannot prove that targets were protected, predictions were captured
before targets opened, the reference was actually frozen before query, the
declared FIT scale was computed from authentic FIT data, or the intended support
roster is genuine. It validates their supplied structure and numerical
consistency. Production owners remain absent. No confidence interval,
significance threshold, causal novelty claim or performance qualification is
introduced.

Source basis is the existing `understanding.v1.json`, preserved implementation
`public/PROTOCOL.md`, `public/TASK.md`, `programme/assembly.py`,
`programme/evidence.py`, and `programme/native_references.py`. The source data
remain Allen Visual Behavior manifest v1.1.0, with AllenSDK source revision
`a56bd8ea7613a812334602b64746cdd30c325a96`. No new source acquisition or authentic
data preparation was performed for this component.

`test_scoring.py` contains generated software controls only: hand-calculated
unequal hierarchy weights/SD/RMSE, contrast sign and replication invariance,
extreme finite arithmetic, missing roles/mice/pairs, invalid values, unavailable
support, familiar controls, frozen reference selection, candidate nuisance
manipulation, and preserved-consumer compatibility. Run it with `python3 -I -B`
through the coordinator's shared test pool. These controls do not demonstrate
neural prediction performance or qualify a direct/viewer/programme condition.
