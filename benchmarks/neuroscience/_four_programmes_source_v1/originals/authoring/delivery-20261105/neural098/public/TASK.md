# NEURAL098: sustained versus transient content information

Reconstruct a fixed, prospective temporal-content analysis of COGITATE experiment 1 MEG. Return the complete participant-level accuracy table and signed temporal contrasts defined below. This is an **analysis reconstruction task**: category and experimental-condition labels are observed analysis inputs. It differs from NEURAL097's unknown-category prediction interface. Do not present either task as an independent cohort, pool their scores, or expose this labeled packet before a supposedly hidden-label NEURAL097 evaluation.

The target is the declared sensor-space, single-trial operational analysis. It is not reproduction of the original source-space ROI, category-aware pseudotrial, inverse-solution or generalization-matrix procedure. It does not adjudicate entire theories of consciousness. Null, negative and reversed effects are valid outputs. Low decodability does not establish absence of content.

## Fixed sample and observations

Use every one of the 33 phase-3, V1, duration-task participants in `COHORT.json` whose source identifier begins SA. This is one declared source-prefix cohort, with no cross-site generalization claim. The complete roster is fixed before outcomes; it must not be silently narrowed by signal quality or results. The other phase-3 participants and phase 2 are outside this task.

Use only face/object trials, all three durations (500/1000/1500 ms), both `Irrelevant` and `Relevant non-target` conditions, and all Center/Left/Right orientations. Exclude any trial with `Response=True` or a raw button event from −0.5 s through its duration+0.3 s interval. Require its actual offset to agree with nominal duration within 1.01 raw samples, and no next stimulus before the final required interval ends. Incomplete next-onset coverage excludes that trial. Full support is mandatory for every participant × image half × category × duration × relevance × orientation cell, at least one trial each; otherwise the entire fixed panel is unavailable. Counts are descriptive and not extra biological replicates.

Six magnetometers, in order: MEG1931, MEG2121, MEG2331, MEG1921, MEG2111, MEG2341. These are the fixed posterior magnetometers in the pinned source config. All must exist with type `mag` and not be marked bad; no empirical sensor selection or interpolation replacement is authorized by this recipe. Actual source filtering, ICA, artifact rejection and detrending must be documented. Use provided author epochs with no additional filter, smoothing or resampling. They are retrospective signals; whole-record/whole-epoch operations do not establish causal online timing or perfectly remove motor leakage.

## Physical-time windows and duration controls

Subtract each trial/sensor's mean on [−0.5,−0.3). Compute a six-sensor mean vector for each required 200 ms window, with left-inclusive/right-exclusive native epoch samples:

| Name | Time from onset | Required durations |
|---|---|---|
| pre | [−0.3,−0.1) s | all |
| onset | [0.1,0.3) s | all |
| middle | [0.6,0.8) s | all |
| late | [1.1,1.3) s | 1000 and 1500 ms |
| post | [1.6,1.8) s | 1500 ms |

Short-trial late/post and medium-trial post entries are structural NaNs, never features, zero-imputed observations or classifier inputs. Required windows may not be missing. This prevents later trials from entering an earlier stimulus's comparison. The middle contrast compares short-offset against long-still-present content at the same clock time. The late contrast compares medium-offset against long-still-present content. Offset-sensitive responses remain a possible explanation, rather than evidence of conscious content by themselves.

## Frozen analysis

Image identity is `Stim_trigger` 1..20 for faces and 21..40 for objects. Split identity within category into `((Stim_trigger−1) mod 20) mod 2`; all repetitions/orientations of one identity stay together. For each of 33 held participants and two query image halves, fit only **1500 ms trials from the other 32 participants and the opposite image half**. Thus no fitted model observes its query participant or any query identity. Train the same model for all admissible query durations. All query trials are evaluated exactly once across the two image halves.

At each of five training windows, fit training-only feature means and population standard deviations; a zero standard deviation becomes 1. Fit `LogisticRegression(C=1, solver='liblinear', tol=1e-8, max_iter=2000, random_state=98098)`, binary class order [face=0, object=1]. Training weights give equal total mass to participant × category × relevance × orientation; weights average 1 over the training observations. No hyperparameter selection, target-batch fitting, model tools or learned embedding is part of this fixed reference. Reaching the iteration limit makes reference construction unavailable. Equal participant training weights do not turn trials or two identity halves into independent samples.

Use every diagonal training-window→same-window prediction and onset-trained→each other available query-window prediction. No true-label test averaging or test pseudotrials. Classify probability ≥0.5 as object. In each participant × duration × relevance × mapping cell, first average correctness within each category × orientation and then average the six values. This **orientation-balanced category accuracy** has chance 0.5; it is not an ordinary trial-count-weighted accuracy. There are 42 cells per participant (5 short, 7 medium, 9 long mappings per relevance condition).

For each relevance condition and each of diagonal/onset-transfer modes, report:

1. `(A1500,middle − A500,middle) − (A1500,onset − A500,onset)`.
2. `(A1500,late − A1000,late) − (A1500,onset − A1000,onset)`.
3. `A1500,late − A1500,onset`.
4. `A1500,post − A1500,late`.

Also report Relevant-non-target minus Irrelevant for each of these eight mode/contrast pairs: 24 signed contrasts per participant in total. In transfer mode, onset is the onset→onset cell shared with the diagonal. Exact key names and order-independent identity sets are in `protocol.py` and the schema. No contrast is omitted because of its sign. Prespecified pre-stimulus cells expose sensitivity/confounding; they are not automatically subtracted to manufacture evidence. Diagonal decodability and onset-transfer stability answer different operational questions. Decoder training on long presentations is a declared transfer condition, not an assumption that all duration distributions are equivalent.

## Submission and verification

Submit a UTF-8 `analysis.json` satisfying `submission.schema.json`: schema `neural098-analysis-v1`, all 33 participant keys, all 42 bounded accuracy cells and all 24 derived contrasts per participant. No extra fields, NaN, infinities, nulls or duplicate JSON keys. Maximum 4,000,000 bytes. Derived contrasts must agree with supplied cells within 1e-12.

The private verifier admits the complete candidate report before reading the independently generated, SHA256-bound reference. Primary score is equal-participant mean absolute cell reconstruction error (lower is better). Secondary score is equal-participant mean absolute signed-contrast reconstruction error. There is no invented scientific pass threshold or reward for a positive effect. The verifier also reports all equal-participant contrast means, participant SD and descriptive SD/√33. These are descriptive summaries of a fixed overlapping-training analysis, **not calibrated confidence intervals or p-values**. All 24 comparisons remain visible; no multiplicity-adjusted significance claim is made. Empirical calibration/inference is an explicit remaining gap.

Implement the specified analysis from these instructions and observed inputs. Access A receives the task, schemas, protocol helpers and observed packet. Access B additionally receives the original MIT-licensed author source evidence, which requires adaptation to this prospective contract. The benchmark-authored full-report reference is operator-private in both conditions. Never mount the full operator package or both A/B views into a candidate process. The copy-only stager constructs one declared view; it does not provide process isolation.

Artifact equality cannot authenticate method execution, preprocessing, leakage isolation or the absence of manual answer copying; provenance and program execution require a future trusted execution evaluation. This construction has not run the private reference, generated actual targets, fit a model or measured a scientific result. Exact numerical reconstruction still does not measure unconstrained independent discovery or an improvement of the underlying method.
