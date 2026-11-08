# Exact scientific mathematics and reference procedure

This is an additive prospective specification, not fitted code or a performance result. Symbols identify complete admitted source support. Numerical conventions must be implemented and independently checked before authentic fitting; no engineering fixtures or scientific calculation are selected in this phase.

## HMP gain and retained state

For fixed event count k, event e, component j and retained sample t, the pinned source uses

`g_e(t) = exp(sum_j C(t,j)*m(e,j) - 0.5*sum_j m(e,j)^2)`.

C is the actual cross-correlation under the declared 25 ms half-sine and source transform; m is the frozen training channel parameter. For finite C and exactly zero finite m, g=1. Original trial length, grouping, fitted duration parameters and event count remain. Let W(z,T) be the exact source duration/path weight for complete path z and length T, and S=sum_e log g_e(t_e). Define Zm=sum_z W exp(S), Z0=sum_z W. On the positive finite domain,

`delta = log(Zm) - log(Z0) = log E_{W/Z0}[exp(S)]`.

Retain the signed delta and the ordinary/zero posterior differences for every trial and count. It is not nonnegative by definition and not mutual information, causal neural effect or a cognitive-stage answer. The latent durations were fit using training EEG, so this frozen ablation is not an RT-only trained reference. Conditioning/selection already retains legal RT and the original artifact eligibility.

The exact held transform calls `_distribute_groups(..., location=False)`; EM fits use default location=True. The latter replaces early interior-stage density samples with 1e-15 and is not a hard zero-support constraint. The duration PDF is sampled on `0..M-1` and normalized over that range, with M the maximum duration of the evaluated group. Every valid path under location=False contains one duration factor for each of k+1 stages. Its common product of stage normalizers cancels in matched Zm/Z0 and in each normalized event posterior. Raw absolute scores retain M dependence. Preserve identical group population, M, support, parameters and method in each pair. Do not claim numerical cancellation under underflow/clipping/NaNs, change M by arbitrary batching, or compare raw scores across a different sample space.

An exact log-domain implementation must preserve source support, convolution orientation, source indexing, PMF and boundary conventions; it cannot introduce a toy likelihood, hidden density calibration or different model. Source-finite agreement tests and numerical stress controls belong to a later authorized implementation phase. Nonfinite C/parameters, zero forward mass, undefined posterior normalizers or unsupported environment behavior are explicit failures. No epsilon floor repairs a failed scientific calculation into a valid score. Preserve finite decreases and signed differences. EM's initial-plus-updates trace and signed stopping rule do not prove convergence or reference competence; retain all traces and stop reasons.

Total RT cannot generally label latent stage order: convolution of complete duration factors is permutation-invariant when boundary/support conventions match. Biological interpretation requires additional evidence. Max-marginal event modes can cross; retain negative differences instead of relabeling events. Keep the original six intervals and its two declared sums. All ordinary/zero timing summaries are within-model statements conditional on fitted parameters, not independent latent truth.

## Reference support, transformations and weights

For each outer person h, let S be the other 25 people and n_p the number of admitted trials of p. A training row has weight w_pt=1/(|S| n_p), summing to one. For each of the 25 inner held people v, repeat the complete reference feature fit/selection calculations on S\{v} (24 people), evaluate every trial of v, and use its arithmetic trial MSE. Do not fit a feature mean/scale on inner-validation or outer-held rows. The final reference uses all 25 outer-training people after inner selection. No source sample, subject or inconvenient target is omitted to fit a model.

The target y is the exact logged stimulus/100. Covariates are the original RT r, instruction a (speed0, accuracy1), and deterministic crop length. The RT basis uses u=log(r) and the fixed anchors

`q_j = log(0.1) + j*(log(3)-log(0.1))/31, j=0..31`,
`b_j(u)=exp(-0.5*((u-q_j)/s)^2), s=2*(log(3)-log(0.1))/31`.

The 70-column behavior vector is `(1, a, u, a*u, u^2, a*u^2, b_0..b_31, a*b_0..a*b_31)` in that order. Bounds/anchors are predeclared source-window design constants; no held target selects them. Actual RT acceptance and source rounding remain the original reader's responsibility. Candidate views disclose the exact crop length because all neural tools necessarily observe it; it remains a deterministic representation of the legal RT.

For ridge features, keep the leading intercept outside penalization. Compute each remaining column's weighted population mean and variance from the fitting people only. Remove exactly constant columns using a retained mask; standardize each other column. No hidden variance floor or held-data standardization is used in the reference. A nonfinite/invalid variance is a failed reference calculation. With centered standardized design X and weighted target mean mu, fit

`beta_lambda = argmin_beta sum_i w_i*(y_i-mu-X_i beta)^2 + lambda*||beta||_2^2`.

All lambda values are strictly positive: `{0.0001,0.01,1,100}`. The solution is the complete weighted ridge system `(X'WX+lambda I) beta=X'W(y-mu)`. No training-row subsampling or low-rank approximation is implicit. An implementation may choose an algebraically equivalent full primal/dual factorization but must retain exact support and prove its equivalence in the selected environment. Require finite coefficients and a normwise residual at most `1e-10*max(1, ||A||_inf*||beta||_inf+||b||_inf)`; a failed residual does not authorize jitter, row omission or an undeclared solver change. Reference numerical conditioning, tolerances and exact environment are recorded; this design does not certify them empirically.

A ridge forecast is `clip(mu+Xnew beta,0,1)`. Clipping to the declared target's containing interval is fixed before labels and cannot worsen squared error for valid y; it is recorded, never fitted on held outcomes. Actor forecasts also lie in [0,1], must be finite, and must have an exact one-to-one match to every held trial. Squared error is a proper point-prediction criterion for the conditional mean; no probability or latent-stage interpretation is attached.

## Non-neural candidates

B-mean predicts the weighted training mean within instruction; if that instruction has no fitting rows, it predicts the global weighted mean. This support-based fallback is declared and logged. B-ridge has four lambda settings using only the 70 behavior features above.

B-kernel has six bandwidth settings `{0.05,0.1,0.2,0.4,0.8,1.6}`. Standardize u with fitting-set weighted mean and population SD; if SD is exactly zero, z=0 for fitting and new values under a constant-column flag. For query instruction a and standardized log-RT z, use every fitting row of that instruction with weights proportional to

`w_i * exp(-0.5*((z-z_i)/h)^2)`.

Normalize those weights and predict their weighted target mean. Use stable log-sum-exp normalization; overflow/nonfinite distance or normalizer is a recorded calculation failure, not an arbitrary nearest-neighbor substitution. If the instruction has no fitting rows, use B-mean's global fallback. The state includes every fitting (person,RT,instruction,target,weight) row; an implementation must account for the full query work and cannot silently bin/subsample this kernel reference. B-kernel's bounded mean already lies in [0,1]. It is trained solely on behavior and targets, with no EEG-informed durations, eligibility changes or fitted spatial states.

Thus B selection has 11 candidates: one instruction mean, four flexible RT-ridge settings and six kernel settings. These references address nonlinear RT/contrast relationships; a neural advantage against a constant-mean straw baseline is insufficient.

## Independent neural candidates

All waveform features use the complete 32-channel, native-sample retained trial before PCA/HMP. They use no stimulus, response, expected-side, original epoch ID, fitted HMP state or target-derived selection. Historical source cleaning remains retrospective. The reference does not refit or reinterpret that cleaning.

Let X_c(t) be channel c, t=0..n-1. Partition all n samples into exactly eight deterministic relative-time bins using `floor(8*t/n)`; every sample appears once. The admitted RT window implies n>=8, but actual admission must verify that condition rather than drop short trials. Relative-time binning is a representation of the complete retrospective waveform; it is not resampling or reducing the actor's source data.

G comprises per-channel mean and population SD within each bin: 32×8×2=512 features. C comprises the upper triangle including diagonal of the 32×32 population covariance over all retained samples, after subtracting each channel's whole-trial mean: 528 features. The channel and pair order follows the exact existing 32-channel list. Values keep their declared voltage/voltage-squared units until training-only feature standardization.

Three neural families concatenate behavior features with `(G,a*G)`, `(C,a*C)`, or `(G,C,a*G,a*C)`. Dimensions before constant removal are 1,094, 1,126 and 2,150. Fit each with the same four ridge lambda values, weighting, final clipping and numerical policy. Every inner reference fit recomputes feature centering/scaling on its 24 fitting people. All held data remain pure feature transformations. There is no inner-validation EEG in a fitted reference covariance/PCA; these are single-trial descriptive covariances followed by training-only supervised regression.

The reference grid contains 12 neural candidates in addition to the 11 B candidates. N-ref selects among all 23, so choosing a behavior-only state is allowed and visible. B-ref selects among its own 11. Reuse an identical B inner fit within this comparison only with exact source/support/state identity; never count it as both newly executed and free. Neural reference features are deliberately transparent, reproducible baselines, not a claim of state-of-the-art EEG decoding. Competence must be established from actual held-person execution and the prescribed diagnostics before strong claims; additional future competitors require separate prospective selection.

## Selection, failures and competence

For each candidate, the selection value is the arithmetic mean of its 25 inner-person MSEs, not a pooled-trial score. Complete all declared candidate/fold attempts and preserve failures and costs. A candidate with any failed inner fold is ineligible for selection, with the full failure vector retained; it is not assigned a fabricated large score. B-mean supplies a transparent complete fallback only if actual target/support admission is valid. If no flexible B candidate completes, the B reference is labeled deficient. If any of G/C/G+C has no complete setting, the planned neural comparison is deficient, not silently relabeled as the remaining family. The inner grid and all unselected outcomes remain inspectable.

Select the finite minimum inner score. Ties are broken by a fixed ordered list: B-mean, B-ridge in ascending lambda, B-kernel in ascending bandwidth, then G, C and G+C in that order with ascending lambda. Selection uses exact admitted numerical values without an outer-outcome tie rule. Refit each selected B/N method on all 25 outer-training people; if both select the identical method, a shared immutable fitted state is legal only with exact lineage. Reserve both final slots until actual reuse is proved. Never rescue a failed outer fit by choosing another method after viewing outer targets.

Reference execution qualification requires: authentic complete source/answer admission; exact training/validation/outer support joins; valid numerical solver behavior and fit records; all candidate/failure accounting; no target leakage; complete sealed forecasts before target access; and independent verification of observed reference losses against B-mean and each family. A negative or null EEG improvement can be a scientifically valid outcome. Reference competence is not defined by forcing a positive EEG gain, but gross numerical instability, missing flexible B competitors or unvalidated implementation forbids a demonstrated-neural-superiority claim. Candidate losses and failed programme components remain separately reported.

## Spatial and response descriptions

Homologous pairs are Fp1/Fp2, AF3/AF4, F7/F8, F3/F4, FC1/FC2, FC5/FC6, T7/T8, C3/C4, CP1/CP2, CP5/CP6, P7/P8, P3/P4, PO3/PO4 and O1/O2. Fz, Cz, Pz and Oz are midline. Never infer missing channels from labels or invent a between-hand manipulation. The same 14-pair convention applies to all people.

For the reconstruction/interpretation branch, retain the five-event max-marginal sample indices and the original source-order electrode values at them; for each person/event compute trial means of left-minus-right paired voltages. Keep all trials and both response choices; publish separate descriptive instruction/response-choice strata only when support is present, with counts and undefined small/empty support explicit. These event-conditioned topographies are generated by the same model/observations and are not independent validation.

For an independent-alignment *description*, predeclare stimulus windows [0,0.1), [0.1,0.2), [0.2,0.4) seconds and response-relative windows [-0.3,-0.2), [-0.2,-0.1), [-0.1,0) seconds. Use only their intersection with each original retained interval, with the original time-axis/rounding and actual sample support recorded. An empty intersection is undefined, not zero. These six descriptive windows add no EEG fit; they do not constitute independent biological measurements or causal identification. Report their contrasts/response-choice relationships descriptively using the source-defined regression basis and full person support; do not tune windows based on held effects or use event-derived selection to manufacture an independent test. Keep truncated-window support effects visible, because RT conditioning can itself change which samples enter a window.

The within-model event probabilities and descriptive spatial patterns can constrain competing interpretations, but no preferred contrast sign, hemisphere, latency or paper agreement is a success condition.
