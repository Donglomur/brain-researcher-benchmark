# Sleep and EOG scientific comparisons

This component reports paired workflow and signal contrasts from an **already admitted** complete Sleep Cassette score. It is a pure Python standard-library assessment: it does not run candidates, authenticate empirical inputs, open labels, fit models or establish a neuroscience result.

The full programme remains 78 people, 153 nights, six outer folds, both frozen-program and case-adaptive modes, and four views: C (clock), EC (two EEG channels plus clock), OC (EOG plus clock), EOC (all three channels plus clock). All nights of a person belong together. The existing private scorer must already have admitted all 936 candidate and 1,170 independent-reference inference outputs. This report preserves all 27 resulting panels, including references and diagnostic controls. Their source and empirical qualification are not supplied by this bundle.

## What the report computes

The primary absolute score for each mode remains EOC equal-person fixed-five-class macro-F1, higher is better. Each person's confusion matrices are combined across nights **before** computing F1; then all 78 people receive equal weight. The fixed class order is W, N1, N2, N3, R. An absent and never-predicted class has F1 zero. The report checks these reductions against the supplied confusion matrices, supports and original metrics.

Its primary mode comparison is adaptive minus frozen EOC macro-F1. It also retains the corresponding comparison in C, EC and OC. Signal contrasts remain EC−C, EOC−OC and EOC−EC within each mode. Mode-by-signal comparisons subtract the frozen signal gain from the adaptive signal gain, person by person. They are predictive performance contrasts, not causal difference-in-differences estimators.

The report also returns original-minus-shifted EEG differences for EC/EOC under each mode and applicable reference; R2's separately refitted label-association diagnostics; same-view candidate/reference comparisons; and independent-reference signal increments. All 52 predefined comparison vectors are descriptive; they are not 52 independent experiments or a post-hoc menu for selecting a favorable result. The original six scorer contrasts and all absolute panels remain present.

For the EOG investigation, EOC−EC asks how performance changes when the provided EOG becomes available alongside EEG and clock. REM-recall increments and mode-by-EOG increments accompany macro-F1. REM recall is undefined for a person with no true REM. If any required person's REM contrast is undefined, the all-person mean is null. Per-person denominators remain explicit; there is no silent replacement by a defined-person mean or zero. Primary fixed-five-class F1 still uses all 78 people.

These are contributions of provided signals for the selected procedures. Weakening EC can inflate EOC−EC without improving absolute EOC performance. Matched methods, competent references, exposure and resource accounting require independent review. A gain does not establish that an LLM internally understands neural signals, that an ocular mechanism caused the stages, or that the model is clinically valid. The [primary dataset documentation](https://physionet.org/content/sleep-edfx/1.0.0/) describes the expert R&K labels and recording modalities. This whole-clock protocol is different from the annotated-sleep crop in the [MNE demonstration](https://mne.tools/stable/auto_tutorials/clinical/60_sleep.html).

## Profiles and uncertainty

The explicit `generic_current_person` profile compares a prewritten policy with new case-visible code authorship under matched permitted input/tool opportunities. It requires 312 frozen and 312 adaptive final fits. It does not equate actual spending or prove identical fitting semantics.

The alternative `training_only_reuse` profile seals 24 frozen fold/view models before query exposure, while adaptive mode still uses 312 final fits. It is a different query-selection and fit-reuse treatment, not an equal adaptive-access experiment. The report refuses a profile whose panel keys disagree with the grade. Work counts are declared requirements, not measured costs; the existing execution receipts remain necessary for cost reporting.

Every comparison includes its complete person vector, six fixed-fold summaries and six leave-one-fold-out sensitivity means. The primary remains the full 78-person mean. These summaries neither refit models nor choose a scoring subset. No bootstrap, population interval or p-value is computed. Scores share fitted training/validation data across the six folds, and a single campaign does not estimate model-generation variability. Neither 78 score differences nor six fold summaries are automatically independent replications. See [Bengio and Grandvalet on correlated cross-validation errors](https://www.jmlr.org/papers/v5/grandvalet04a.html).

Calibration cannot be recovered from confusion matrices. This component returns an explicit unavailable calibration state. Any future probability-diagnostics companion must be separately constructed and bound to the same protected score; no calibration statistic is invented here.

## API and admission boundary

Call `paired_sleep_contribution.assess(grade, expected_support, profile)` with the existing **JSON-decoded** `neural007_full153_grade_v1` object. The full expected support is an independent trusted-operator input:

```json
{"schema":"sleep_full153_support_v1","people":[{"person":"100000","fold":1,"nights":2}]}
```

The single row illustrates syntax only and is deliberately invented. Actual input requires exactly 78 unique canonical nonnegative decimal-string person identities, 13 in each of six folds, and 153 total nights (one or two per person). The caller must authenticate the exact original roster, folds and all nights before supplying it; passing a dictionary with those dimensions is not empirical admission. Real participant identities are not embedded in this source.

The grade must have all 27 exact panel identities and its original nested metric schema. Every person's scored class support must agree across panels. Boolean/nonfinite metrics, inconsistent arithmetic, missing people, altered profiles, omitted references/controls, fabricated contrasts or qualification promotion raise `ValueError`. Counts must be nonnegative signed-64-bit representable integers. Numeric equality uses absolute and relative tolerance 1e−12. The module never forwards arbitrary added input fields.

Trusted preparation, source/model lineage, target custody, original/shifted same-state enforcement, complete producer closure, stage masks and matched-method review belong to the existing operator and scorer. The pure report cannot establish those facts from its inputs. It accepts coherent invented fixtures in engineering tests because its responsibility is arithmetic and interpretation, not authentication. No model, private-target path, original dataset or runtime container is included.

The NEURAL-008 full raw-cohort EOG readout is a disclosed proposed successor sharing NEURAL-007's cohort and costs. It does not adopt a registry entry or qualify the historical six-training/two-development-person engineered-feature component. No new assignment is counted.

## Numeric EOG claims

Call `neural008_numeric_claims.check_claims(claims, report["neural008_numeric_claim_targets"])` after producing the report. It compares only six predefined aggregate/per-person EOG macro-F1 and REM targets: frozen gain, adaptive gain and their mode interaction. Claims can assert a number or undefinedness, abstain explicitly, or be absent. Unknown claim IDs are unsupported, not credited. An optional per-person assertion must include the exact full person set.

The checker reports consistent, inconsistent, abstain, not-submitted and unsupported states, together with the numerator and denominator of numeric consistency. Checkable null-definedness assertions count as evaluable; separate null and finite assertion counts make that denominator transparent. Negative expected results remain valid. Numeric agreement is not scientific reasoning credit, method adequacy, causal evidence or empirical-provenance authentication. No positive-effect reward is supplied.

## Invented verification

From this directory run:

```sh
python3 -I -S -B test_paired_sleep_contribution.py -v
python3 -I -S -B test_neural008_numeric_claims.py -v
python3 -I -S -B test_sleep_claims_integration.py -v
```

Fixtures use invented full-size metadata and confusion counts. They check correct person/night weighting, paired signs and interactions, all panels, profile distinction, undefined REM, sensitivity, adverse/zero outcomes, refusal paths and no input mutation. They do not read authentic data, execute a candidate, or run a scientific study. Scientific qualification and submission readiness remain false.
