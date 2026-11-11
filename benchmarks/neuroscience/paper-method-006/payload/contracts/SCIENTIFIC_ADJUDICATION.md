# Printed expressions, constrained optimization and native behavior

This is source interpretation and analytic reasoning, not an empirical evaluation or implementation. Exact printed EQ01/EQ02 expressions, surrounding definitions and complete-page pins are retained unchanged in the bound parent `EQUATION_ADJUDICATION_V3.json`. Root independently inspected the complete relevant SI pages 4–6 and accepted their status as printed-source issues; that is not a native code or scientific-result validation.

## EQ01 and EQ02 remain unresolved

EQ01 is the free-energy display on SI PDF page 5 (printed page 4, line 288): the first line lacks the mixture-prior term included in its expansion, and the final expanded term is visibly `-(1/2)*pi*sigma_j^2`, without the logarithm present in a Gaussian log normalization. EQ02 is the common-scale simplification on PDF page 6 (printed page 5, lines 376–379): the displayed scalar factor differs from the previous weighted matrix, and the final scalar notation suppresses an identity matrix. These are statements about what is printed. The density and neighboring update formulas constrain interpretation but do not authorize editing the original or claiming a specific historical repair.

Common positive factors can cancel in the direction of a linear solve followed by normalization. That observation limits what may be concluded from EQ02; it does not authenticate finite rounding, whitening, singular/rank behavior, variance conventions, objective values or the actual source version.

## OPT01: normalization after regression is not generally the constrained M-step

The SI PDF page 5 states a linear solve for `w` and then renormalizes `w` to unit Euclidean norm. To assess that operation analytically, hold the responsibilities `r_kj`, component means `mu_j` and positive scales `sigma_j` fixed. Using the stated Gaussian quadratic part, define

`C = sum_k x_k x_k^T * sum_j r_kj/(2*sigma_j^2)`

`b = sum_k x_k * sum_j r_kj*mu_j/(2*sigma_j^2)`.

Terms independent of `w` can be omitted. Minimizing the negative expected Gaussian quadratic contribution is then minimizing

`q(w) = w^T C w - 2 b^T w`, subject to `w^T w = 1`.

For differentiable finite quantities, the Lagrange-stationarity condition is

`(C + lambda I) w = b`, with `w^T w = 1`.

This is a necessary stationary condition; by itself it is not a global-optimum or convergence certificate. In contrast, the printed operation first forms `u = C^-1 b` when that inverse exists, then chooses `w = u / ||u||`. Let `a = ||u||`. Its equation is `Cw = b/a`. To satisfy the constrained stationarity condition as well, it would require `lambda w = (1 - 1/a)b`. For general nonisotropic `C`, `b` is not parallel to `w`, so such a scalar `lambda` does not generally exist. The exception `a=1` is already unit norm; other special alignments may satisfy the condition.

Therefore, Euclidean normalization of the unconstrained solution cannot generally be described as the exact constrained quadratic M-step. This conclusion uses only the written mathematical form; no numerical test or algorithm execution was performed. It does not establish an observed decrease in any actual run. Neither exact EM monotonicity nor generalized-EM monotonicity follows without showing that the actual update increases the selected common objective and that all of its assumptions apply. Later updates of means/scales, alternative parameterizations or actual code may change the relevant argument; they must be examined explicitly rather than presumed.

If the common-scale features are **exactly** whitened so that `C = c I` with finite `c > 0`, then `w^T C w` is constant on the unit sphere. For nonzero `b`, the normalized direction `b/||b||` minimizes this quadratic, and normalized `C^-1 b` gives that direction. This explains a special case relevant to the Kilosort3 discussion; it is not proof that a finite native whitening routine produces the identity exactly or that every recursive subproblem has full rank. If `b=0`, directions are nonunique in that isotropic case and normalization of the zero vector is undefined; singular `C`, zero variance, vanishing component mass, zero norms and deficient rank need explicit policies.

## Required source distinction

Preserve literal original outputs and failure topology for a subsequently authenticated native source profile. If the benchmark later selects a reconstructed objective or constrained optimizer, it must be separately named, source-supported and reviewed before outcomes are available; it cannot replace the historical result silently. A claimed monotonic improvement property requires its own precise mathematical/algorithmic justification. Comparator competence and empirical sorting quality require actual separately authorized evidence, regardless of whether the method is called EM.

The old missing floor, ridge, rank, covariance normalization, total-iteration, stopping, initialization, tie and source-version policies remain unresolved. This amendment selects no solver, numerical floor, convergence rule, metric change or implementation.
