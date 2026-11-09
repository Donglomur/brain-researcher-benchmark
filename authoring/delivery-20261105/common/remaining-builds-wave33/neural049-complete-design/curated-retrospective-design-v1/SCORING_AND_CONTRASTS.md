# Complete outcome and comparison contract

This document is normative with DESIGN.md and the reference mathematics. It defines a prospective statistical procedure, not an executed score or a qualified numerical implementation. All source and scientific admission gates remain open.

## Units, folds and denominators

For person s, day d and released curated row i, let y_sdi,k be the exact admitted target for endpoint k, and let p_sdi,k be the single final out-of-fold prediction from the model whose outer held day is d. The three endpoints are folded vertical angle (degrees), magnitude (pixels), and onset speed (pixels/second). Targets and predictions are never pooled across these units. The primary endpoint is angle.

E_sd denotes the complete authenticated row count, E_s=sum_d E_sd, and E=sum_s E_s. These remain unknown symbols in this design. Every required row has one keyed prediction and one disposition. A known all-masked neural row remains a prediction obligation, not an exclusion. Unresolved target identity, malformed required output, missing model/row/person or nonfinite required prediction leaves the corresponding complete endpoint result undefined. An incomplete endpoint is not repaired by using its valid subset. All three endpoints are required for a complete panel; the report may separately state that angle is complete while a secondary endpoint is incomplete, without calling the entire panel complete.

For every person and endpoint:

    mean_s,k = (1/E_s) sum_(d,i) y_sdi,k
    SSE_s,k  = sum_(d,i) (y_sdi,k - p_sdi,k)^2
    SST_s,k  = sum_(d,i) (y_sdi,k - mean_s,k)^2
    R2_s,k   = 1 - SSE_s,k / SST_s,k
    macro_R2_k = (1/12) sum_(s=1..12) R2_s,k

The sums use all held-day predictions together within each person. They do not average daily R², average daily means, weight people by their event counts, or calculate a single pooled-cohort R². Negative R² remains negative. Each person has equal weight in the final macro while each event has equal weight within that person's SSE and SST. Report E_sd, E_s, SSE, SST, target mean, R², units and status at all levels. A zero SST, zero E_s or nonfinite accumulation gives an explicitly undefined person result and therefore an undefined 12-person macro. No epsilon denominator or surviving-person mean is used. Day-level error summaries remain diagnostics with their denominators and may be undefined without inventing day-level R².

Before any target body is opened, every raw prediction must be finite. Apply the same fixed target-domain projection to every candidate, reference and lower-baseline prediction: angle to[-90,+90], magnitude and speed to[0,+infinity). Retain both raw and projected outputs, including how many values changed. All inner selection uses the identical projected prediction rule. This is a prospective, target-blind prediction constraint shared by all methods; authentic labels are never clipped, imputed or transformed by it. Unexpected label range/units still fail source admission. A later alternate unprojected metric must be separately named and cannot replace the selected primary after results.

Both reference implementations must compute numerators/denominators independently using the same keyed complete support. Bounded, compensated or pairwise float64 accumulation is required, with an independently qualified finite-error policy established before protected evaluation. An overflow is a numerical failure, not a biological null. No reported unrounded score may depend on row arrival order without an explicit fixed source-key order.

## Model selection and fixed lower baseline

For each endpoint/view/family/outer fold, choose a configuration solely by minimum total inner held-day SSE across the complete 202-fold graph's applicable inner cases. The denominator is the number of scored inner events only for descriptive MSE; since support is fixed across configurations, SSE and MSE select the same configuration. Equal configuration scores use the written candidate order. Every candidate must cover the same rows and provide the same required finite outputs; a failed candidate configuration is recorded, never silently compared on fewer rows. A required family with no fully admitted configuration leaves its strong-reference contract incomplete.

After inner selection, refit each selected family on all outer training days. Choose the independently selected strongest family using the same inner SSE and fixed family tie order, without looking at the outer targets. The selected family may differ across outer folds, endpoints and views; retain that mapping. Constant training targets use the documented unit target scale/intercept convention and are not necessarily an unsupported fit. The held-person SST rule remains independent.

The lower baseline predicts the exact outer-training target mean for every held row, separately for each endpoint. No held-day mean is exposed. It must cover the entire support and is reported beside the three competent reference families; it cannot substitute for them. There is no arbitrary zero-angle claim of competence and no model selected by the outer score.

## Two independent reference implementations

Name the independently authored reference contracts R1 and R2 before implementation. R1 is the prespecified numerical anchor for the comparison tables. R2 must independently construct all configurations, folds, selected states, final outputs and scoring quantities from the same written contract and admitted inputs. Neither imports the other implementation or candidate code/results. A shared exact basic library/environment is permitted only when disclosed; implementation independence is not hardware, library or conceptual independence.

Both outputs and every discrepancy are retained. No average, best-of-two choice, or post-test tolerance adjustment is allowed. Exact discrete identities, support and selections must agree except where an expressly predeclared numerical tie rule applies. Numerical tolerances, including any trained-network determinism limits, must be qualified independently before authentic target access; they are not selected from the actual study differences. If the implementation agreement or competence gate fails, the reference comparison stays unqualified even if candidate predictions exist. R2's complete result is separately reported and never discarded because it is weaker. Deterministic seed declarations do not prove GPU/library determinism.

## Prespecified point contrasts

Each contrast is computed within person on identical complete support, then averaged across all 12 people. Positive values mean the first named method has higher R². It is algebraically also the corresponding reduction in SSE divided by that person's fixed SST. Preserve the person-level paired values and the two method scores. No conditional subset gain is reported when one side is undefined.

For the core angle panel, the 11 primary paired contrasts are:

1. F-NC minus F-C.
2. I-NC minus I-C.
3. I-C minus F-C.
4. I-N minus F-N.
5. I-NC minus F-NC.
6–8. NC minus C within each of the three reference families, using that family's independently selected hyperparameters in each view.
9. Independently selected strongest NC reference minus strongest C reference.
10. F-NC minus the selected strongest NC reference.
11. I-NC minus the selected strongest NC reference.

N-only, all family scores, the mean baseline and all secondary endpoint scores remain complete outputs, even where no extra primary contrast is selected. Within-family contrasts hold the method family fixed, but permit train-only tuning per view. The strongest-family contrast may additionally change family; it is an optimized access comparison, not a pure marginal coefficient or causal effect.

For the separately complete supplied-tool angle panel, four paired contrasts are F-NC/T1 minus F-NC/T0, I-NC/T1 minus I-NC/T0, F-NC/T1 minus tool-alone, and I-NC/T1 minus tool-alone. They measure contribution conditional on access to that exact trained decoder. They do not establish total neural contribution or unaided signal understanding. The T0 comparator is the exact frozen core policy/output; module selection and reuse are declared before any outputs, not chosen after observing a favourable core score.

For the separately complete assignment diagnostic, six paired angle contrasts are original NC minus NC_D for F, I, each of the three reference families, and the independently selected strongest reference. Every disrupted arm is separately fitted and investigated from its first exposure, using the exact same frozen source-only NC F program/I policy, provider configuration and paired declared seed contract as its original arm. No independent global D authoring realization is introduced. All D case-local state is fresh. The donor permutation changes masks and signal assignment together. It supplies no exchangeability p-value, no causal ablation, and no total-information estimate conditional on a fixed original mask. No original-query-derived prompt, embedding, model output, cache, feature, tool trace, learned state or prediction can enter the disrupted actor or fit context. The actor receives no explicit arm cue; inference from data and unqualified provider nondeterminism remain limits, so the R=1 difference is not claimed free of stochastic variation.

The same point-contrast tables are generated for the two secondary endpoints, with their own R² and denominator status. They are explicitly secondary; no automatic multiplicity-adjusted primary claim is made across all endpoints and modules.

## Uncertainty and limits

When all 12 person-level angle effects in a selected contrast family are defined, use a fixed 10,000-replicate person-cluster bootstrap. A replicate draws 12 person indices with replacement and retains each selected person's complete collection of days, event rows, model fits, donor edges, contexts and paired outputs as one block. It reweights the already computed person effects; it does not refit models, resample events independently, recompute donor maps, change fits or regenerate provider outputs. This preserves dependence from overlapping same-day windows and within-day permutation donors. Use the same source-only draw table across selected contrast families. For replicate b=0..9999, position k=0..11 and rejection counter t=0,1,..., compute SHA-256 of canonical JSON array["NEURAL049.curated-retrospective.v1.person-bootstrap.angle",b,k,t], UTF-8, ensure_ascii=True, no whitespace. Interpret the first eight digest bytes as unsigned big-endian u. Accept the first u <12*floor(2^64/12), returning person index u modulo12 in the fixed01..12 roster. This fixes the pseudorandom draw order and avoids modulo imbalance without a framework RNG/default; retain the draw-table pin. Actual implementation and qualified numerical accumulation remain future gates.

For one prespecified family J (11 core, four supplied-tool, or six assignment effects), let Delta_hat_j be the 12-person mean. For bootstrap replicate b compute Delta_star_b,j, then M_b=max_(j in J) abs(Delta_star_b,j-Delta_hat_j). Use the order-statistic quantile with index ceil(0.95*10000)-1 in the ascending M list; report Delta_hat_j ± q for that family. This is an approximate bootstrap family-wise band in common R² units, not a finite-sample simultaneous guarantee. Families are separate: three 95% families do not imply 95% joint coverage across all modules or endpoints. Undefined required effects suppress that entire selected family's bands; do not shrink J after seeing support or results. Point/disposition reporting remains complete.

Twelve clinical participants is small and not an established random sample of a wider population. These bands describe conditional variability across the included participant clusters under the stated bootstrap assumptions. They do not remove selection bias from curated events, upstream whole-day preprocessing, shared pose-model training, public-source development or policy selection. R=1 author realizations make F/I and tool comparisons conditional on the realized policies and provider behavior. Neither event nor person bootstrap estimates author/provider variance. No significance or mechanistic conclusion follows merely from an interval excluding zero.

No scalar score is manufactured for missing support. The report always leads with completion, exact support and qualification status before the numerical table.
