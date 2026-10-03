# PETVT: two explicit blood-reference assumptions

Status: source structure and numerical rules frozen before original kinetic
fitting. Machine-readable contracts fix exact axes, identities and tolerances.

This is a seven-person **methods-sensitivity application**, not a replication
of the human paper's regional two-tissue-compartment model. It cannot determine
the true decay reference of the released blood activity, establish tracer
validity, or support a biological/genotype conclusion. Neither branch is called
correct. There is no required direction, agreement, V_T range, or group result.

## Fixed sources and target

Use ds005619 snapshot 1.1.0, commit
`358a370c010a792484585b80d28adb699ec28927`, baseline subjects
`sub-sf02,sub-sf05,sub-sf06,sub-sf07,sub-sf08,sub-sf09,sub-sf10`.
Only the original `petprep_extract_tacs` gtmseg TAC TSV, matched manual blood
TSV, PET/blood JSON sidecars and explicit provenance are scientific inputs.
Authenticate the complete pinned source inventory before parsing; never use
the historical answer/reference bank. The runtime and verifier are offline.

The tissue estimand is the equal-weight mean of the frozen original `ctx-lh-`
and `ctx-rh-` columns in each frame, called
`equal_region_cortical_composite`. It is not a volume-weighted whole-cortex
value and not the mean of separately fitted regional V_T values. The exact
column set (68 regions), row counts (33 frames per person) and source identities
are pinned after structural inspection. All seven records remain present.

## Clocks, paired observations and assumptions

All input timestamps, frame edges and sidecar clocks are seconds relative to
the released PET TimeZero. Confirm matched sidecars have image reference,
injection start and scan start zero, Bq/mL activity, and half-life **6586.2 s**
for all seven. A mismatch stops source qualification; it is not silently
repaired. The half-life replaces the legacy rounded 6586.26 s constant.
TAC edges must match sidecar frame timings, with 1e-6 s absolute tolerance,
and be contiguous from injection with strictly positive duration.

Preserve each blood row and its original index. A retained paired knot needs
finite nonnegative plasma activity and parent fraction in [0,1] on the same
row. Only literal empty and `n/a` are missing tokens. Other invalid/nonfinite
observed values fail qualification, with row/column/reason preserved; they
are not missing observations. Retain missing rows in a complete eligibility
ledger. No interpolation across unmatched plasma/parent observations creates
new paired knots. Retained times are finite and nonnegative. Group paired
rows by exact numeric time and coalesce only when both plasma and parent
fraction are exactly identical throughout that group. Do not compare only
their product, average conflicting values, use an equality tolerance, or
infer that a row is padding. Conflicts fail source qualification. Sort the
resulting distinct knots by time. The representative key is the minimum
original source-row index; the complete contributing row indices and
multiplicity remain in the public ledger. At least two distinct paired knots
are required for input support. This representation amendment was made from
a structure-only equality diagnostic before any kinetic fitting.

For observed time t, image-reference time d, plasma P, parent fraction f, and
lambda=log(2)/6586.2 per second, the two and only two assumptions are:

- `already_image_reference`: parent input at the image reference is P*f.
- `sample_time_reference`: parent input is P*f*exp(lambda*(t-d)).

Transform at each observed paired knot **before** piecewise-linear
interpolation. Do not interpolate P/f separately, exponentiate an interpolant,
or apply both corrections. If the first knot is after injection, insert the
explicit operational pre-bolus anchor (injection time, zero) after transforming
observed knots. A valid zero-time knot is not replaced. This anchor is not a
measured concentration. Coalesced stored time-zero observations remain stored
observations, not a synthetic anchor. Whole blood is not fitted. No free-plasma, vascular,
delay, dispersion, metabolite-refitting or dose/SUV corrections are introduced.

Use minutes since injection for integration/regression, seconds for decay.
The quotient V_T has the concentration-ratio convention (mL/cm³ when image
activity is expressed per cm³ and plasma per mL). No dose/body-weight scaling.
No held-tail extrapolation: if final blood support does not reach the final
fitted frame midpoint, retain `input_time_support_unavailable` for both fits.
Do not shorten the fixed fit window to make an estimate available.

## Quadrature and estimators

Let each C_T be a released frame-average composite. At arithmetic midpoint m_i,
I_T(m_i)=sum over earlier frames(C_T*duration)+C_T[i]*duration[i]/2.
This includes the first half-frame. It deliberately replaces the prototype's
midpoint trapezoid that omitted early uptake. Input integration is the exact
integral of the transformed piecewise-linear knots, including partial final
segments and the stated zero anchor. No fixed 0.02-minute integration grid.

Both methods and assumptions use every frame midpoint >=30 minutes, with no
duration weighting or adaptive t-star. At least three fit rows are required.

- Logan: y=I_T/C_T, x=I_P/C_T; unweighted OLS y=VT*x+b including an intercept.
  A nonpositive fitted C_T makes the entire Logan record unavailable; do not
  delete individual rows.
- MA1: unweighted OLS C_T=a*I_P+b*I_T without an intercept; VT=-a/b.
  This is a rearranged-model diagnostic, not independent biological validation.

No nonlinear 2TCM, model selection, fit agreement requirement or physiological
coefficient box. Finite resolved negative/zero V_T values remain signed and
receive a nonpositive flag rather than being clipped or excluded.

## Numerical gauge, support and accepted-output authority

Use float64 C-contiguous arrays. Normalize each design column by its stable
L2 norm; solve with SciPy `linalg.lstsq(lapack_driver='gelsd',
cond=max(n,p)*eps64)`, and unscale coefficients. A zero design column or returned
rank below two is unavailable. The declared solver is the numerical gauge;
universal agreement of different SVD drivers near rank boundaries is not
claimed. Record rank, column scales and normalized singular values; no
condition-number exclusion is chosen from the participants.

Canonical source designs determine fit support/rank. Source-close submitted
NPZ coefficients are the sole downstream numerical authority. Rounded design,
integral and CSV coefficient receipts are never refitted. Derive V_T and all
cohort summaries from accepted coefficients once, without a second historical
or canonical V_T target. General coefficient tolerance is 1e-8 absolute plus
1e-6 relative. For source-supported MA1, denominator relative error must also
be <=1e-6 with no absolute floor, evaluated without an underflowing tolerance
product. Additionally the MA1 coefficient-vector L2 error must be <=1e-6 times
the source coefficient-vector L2 norm, without an absolute floor. Evaluate
this in scaled arithmetic. This protects a tiny numerator/denominator pair
without adding a second V_T target. The source-zero vector is unresolved.

MA1 denominator support is source-defined: abs(b) must exceed
64*eps64*max(abs(a),abs(b)). Otherwise retain finite coefficients but mark
`ma1_denominator_unresolved` and make V_T null. Serialization cannot reactivate
that mask. A nonzero quotient that overflows or underflows to zero is
`numerical_failure`. Exact zero numerator with resolved denominator has V_T=0.
Residual RSS is diagnostic, not an acceptance/quality threshold. If its
squaring is not representable, report null RSS and its numeric status without
inventing a physiological rejection. No naive OLS confidence interval is
required for correlated transformed TACs or uncertain arterial inputs.

## Complete reporting, no outcome target

Retain exactly 28 participant/assumption/estimator records. Processing status
`complete` does not imply every fit is defined. Null values are typed and carry
the declared reason, never NaN/Infinity or zero substitutions.

For each of four estimator/assumption combinations, report expected n=7,
defined n, complete-seven mean/sample SD/min/max. For each estimator report
each signed paired change (sample-time-reference minus already-image-reference)
and complete-seven mean/sample SD. An incomplete family has null group
statistics; no changing denominators or post-hoc complete-case estimate.
Exact constant complete values have SD=0. Numerically unrepresentable group
reductions are separately unavailable. No group p-value or percent-change
denominator is required. Findings explain both assumptions and actual support,
not an enforced scientific conclusion.

The human study is context, not an endpoint target:
[Yan et al. human SF51 study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11629344/).
The estimator equations are motivated by
[Logan et al. 1990](https://pubmed.ncbi.nlm.nih.gov/2384545/) and
[Ichise et al. 2002](https://pubmed.ncbi.nlm.nih.gov/12368666/).
Clock-field distinctions follow the
[BIDS PET specification](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/positron-emission-tomography.html).
Blood sample time by itself does not establish activity decay-reference time.
