# Stable paired-loss reduction

This successor scorer repairs finite cancellation in NEURAL-094's reported
whole-population primary. The previous score adapter computes a trial contrast
with NumPy's ordinary mean and session/mouse contrasts with ordinary summation.
For admitted three-class probabilities producing paired loss differences
`[2, 2**-53, -2, 0, …]`, the old trial mean is zero while the independently
implemented arithmetic preserves a positive effect. Negative effects can also
be erased. The successor also declares stable session-within-mouse and
equal-mouse reductions explicitly, so that they do not depend on the Python
version's built-in summation algorithm. The existing exact sign/zero check exposes
the problem; its tolerance is unchanged.

`score_adapter.py` preserves the preceding complete scorer API and changes only
the paired-difference mean and the nested extended-number means to use
`math.fsum`. Required infinities and undefined values keep their original
semantics: zero true-class probability yields infinite loss, paired infinity
minus infinity is undefined, and mixed signed infinities are undefined. Every
required trial, all 39 sessions, and all 10 mice remain in the same denominator.
There is no clipping, threshold, dropped case, or probability averaging across
seeds. The prior source component remains byte-for-byte unchanged.

The preceding scorer is pinned at
`1794e1a74b598524593b6ff0a9820ff645c360ce880b7fcb706f04c8d6600ec3`.
The existing `regional_grading` uses the score adapter's `paired_effect` and
`aggregate_reports`, so this successor retains those exact call signatures.
Before native use, the integration owner must select this successor in a new
authenticated numerical/runtime inventory and retain the old inventory as
history. Editing a pinned source body in place or recomputing an untrusted
manifest is not an admission path. This component is directly executable for
generated software checks; the old closed component continues to identify the
old scorer until that explicit integration.

Run `test_stable_loss.py` through the project's shared lightweight test pool
with an existing NumPy environment. Its controls use actual three-class
probabilities, independent arithmetic, trial permutation, the complete
39-session/10-mouse scalar interface, unequal session counts, malformed support,
and nonfinite losses. They create no authentic observations, estimator fits,
candidate predictions, or empirical benchmark results. The local Python and
NumPy versions are printed; matching NumPy 2.2.6 alone does not qualify a native
image or its other dependencies.

The scientific endpoint remains final right/NoGo/left choice from the first
100 ms beyond the competent stimulus/history/wheel reference. All 73 literal
regions, 2,628 pairs, and five fixed seeds remain the declared scope. Direct
observation and typed viewer access remain undelivered; tool-assisted and
frozen-program sources remain separately described and unqualified. This
arithmetic repair does not establish native execution, direct neural
understanding, causality, data readiness, or a scientific gain.
