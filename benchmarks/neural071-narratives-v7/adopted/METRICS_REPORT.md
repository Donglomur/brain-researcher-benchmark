# Numerical outcomes, biological hierarchy and interpretation

## Fixed complete metrics

Keep the original metrics.py definitions. Within each segment and parcel calculate signed Pearson r, MSE and Q²=1−MSE(pred,y)/MSE(real_training_mean,y). Pearson is bounded to [−1,1] only for floating-point roundoff; negative correlations are retained. A constant prediction on a variable target has r=0. A constant target has undefined correlation. Zero Q² denominator gives undefined Q². Do not clip negative Q², replace nulls by zero, or omit undefined parcels.

Aggregate all 400 parcels first, then segments within run, runs within held family, held families within listener, and listeners equally. Required nulls propagate at each level. Counts and affected support remain explicit. Primary outcome for each F/I REAL condition is CONTEXT listener-macro r over the fixed 171-listener estimand; report the other arms and ZERO conditions as prespecified secondary outcomes. Do not pool timepoints across people to increase n.

The same real-training mean denominator is used across candidates and every reference in a case, including ZERO candidates. That quantity is protected until scoring. All finite scores may be zero or negative without an execution failure. Numerical overflow/nonfinite arithmetic is a metric failure with retained inputs; it is not a scientific negative result. A mathematically undefined metric is a separate valid disposition, not a dropped case.

Family marginals separately average complete listener cases for each family. They are dependent and unbalanced. Report listener and family descriptive spreads separately; neither is a calibrated independent-trial SE, confidence interval or hypothesis test. No timepoint t-test or IID bootstrap is selected. No new ROI/language-network best-parcel mask, current-test-selected layer, threshold or success-based publication. The inherited response-selected layer-eight method prior is disclosed separately.

## Fixed comparison family

CONTRASTS.json enumerates 57 scientific differences, each for signed r, Q² and MSE with explicitly interpreted direction. Apply the same listener-first hierarchy and paired support; retain every definition even if null/negative. The contrasts are: candidate I−F for each arm/response (6); REAL−ZERO for each mode/arm (6); each candidate REAL minus each matching-arm R0/R2 and Rmean (18); each mode/response CONTEXT−NUISANCE and CONTEXT−LEXICAL (8); R2−R0 by arm (3); R2 CONTEXT−NUISANCE and CONTEXT−LEXICAL (2); R2 NUISANCE−Rtemp and −Racoustic (2); and each candidate REAL minus Rtemp/Racoustic (12). These are 57 scientific differences, each with three metrics, hence 171 numerical contrast rows.

Differences of fitted feature sets are conditional predictive comparisons. They are not unique linguistic information, neural-specific understanding, causal effects or variance partitions. Independently fitted low-level controls can fail too; report their actual fits/performance and their coverage limits. The old half-length circular prediction shift may be reported as a descriptive mismatch diagnostic only. It is not a refitted null, a temporal model, a p-value or an additional required score.

## Scientific investigation reporting

The pre-score declaration schema has hypotheses, direction/uncertainty, exact training analyses and support, intended failure tests, selection decisions, source/clock assumptions, uncertainty statement and prohibited-claim acknowledgement. The operator links each statement to original logs and later outcomes; it does not rewrite hypotheses after targets.

For optional adjudicated interpretation: two independent reviewers blinded to provider/mode labels receive the full fixed metric report and relevant sealed analysis evidence. For each of five dimensions—source/timing validity, current-fit training-only selection and historical method-prior provenance, control interpretation, biological hierarchy/uncertainty, and factual support for conclusions—they mark supported / contradicted / insufficient evidence, with exact evidence references and reasons. No aggregate scalar reasoning score or accuracy-based preference is selected. Disagreement requires a third adjudication record retaining both original ratings; unresolved disagreement remains unresolved. These human review outcomes are distinct from the prediction result.

Reviewer requests are owned before material access, record actual start/finish/provider-or-human identity, bytes/costs and all errors, and close after publication. A missing review cannot be fabricated by the benchmark author. Numerical reporting can say interpretation_review_pending; the programme cannot claim an adjudicated scientific-reasoning result until all required review records close.

## Orthogonal dispositions

Keep independent fields for source/design adoption, support completeness, process/API completion, cost qualification, numerical definedness, scientific outcome and interpretation review. Example: a correctly fitted model may have a negative defined Q² and fully qualified execution; an undefined target correlation may coexist with valid MSE; a valid-looking prediction with unknown write cost fails admission. Source-only design acceptance never sets executable/scientific readiness true.

Final report includes complete 345/873 census, 171/486/572 estimand, 174 ineligible persons, all 400 parcels, native-TR and alignment limitations, inner-family-count branch strata, every candidate/reference outcome, full 171 contrast rows, failures/unknowns, full costs and original provenance. No count of symbolic episodes is presented as count of independently validated benchmarks.

The layer-eight extractor is a historical Narratives-response-selected feature prior: Caucheteux et al. selected it using brain-prediction comparisons on 101 listeners, seven stories and 237 subject-story pairs from the same public corpus. The exact overlap with the current 171 listeners/486 cases is UNKNOWN. Current outer/inner transforms, coefficients and alpha/gamma selection use their fitting support only; this locality does not establish independence of the earlier global layer choice. Results are exploratory public-corpus evaluation with a disclosed shared-corpus prior, without an untouched-test or globally independent layer-selection claim. METHOD_PRIOR.json supplies the mandatory identity and disclosure.

The final report and every one of 57 contrast records must carry the exact prior/clock identities and exploratory evaluation label. CONTEXT scores, R2/CONTEXT and REAL/ZERO differences retain the historical prior; neither a positive nor null result establishes native LLM understanding. The pre-score declaration and blinded rubric must distinguish current-fit locality from historical response-selected global design. Unknown overlap stays null/UNKNOWN, not zero or an invented exact intersection. All metrics, directions, 171 rows and denominator rules remain unchanged.
