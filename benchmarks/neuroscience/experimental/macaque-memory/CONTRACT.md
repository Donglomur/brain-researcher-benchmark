# Macaque memory: complete-session decoding reproduction and improvement

Status: **conditional source component, not registered or executable on authentic data**.
The two arms and two phases below are one proposed paper task, not extra benchmarks. No dataset MAT file has been opened and no fit has run here.

## Scientific question

For the complete released cohort of two macaques and 35 sessions, can an agent reproduce the memory-condition decoding analysis, then improve prediction of explicitly labeled old/new trials in held temporal blocks? An improvement supports predictive utility on this finite historical cohort; it does not establish memory consolidation, a causal mechanism, or generalization to a macaque population.

The source is Abbaspoor, Aljishi and Hoffman, [Experience reorganizes content-specific memory traces in macaques](https://www.nature.com/articles/s41593-026-02357-2), with [Figshare release 1](https://doi.org/10.6084/m9.figshare.31418819.v1) and [official code revision](https://github.com/hoffman-lab/Manuscripts/tree/09219676a8cc6b48ea4ed0b8c0d1156793e03456/AbbaspoorAljishiHoffman2025). The scientific protocol is based on the public schema documents and pinned official MATLAB source. This package does not redistribute the paper or official implementation.

## Newly resolved source facts

The complete processing sheet has 35 nonempty recording rows: 18 `animal_1`, 17 `animal_2`, with dates and `Set_day`. Three animal_2 rows have `Set_day=0`; two have `Set_day=4`. This field is **not a trial-level memory-condition label**. The neutral roster preserves all rows and never derives old/new classes from day numbers. The sheet also records channels and task end metadata; its author-local directory strings are not copied into this package.

The official schema describes single-unit spike timestamps in seconds, alongside numerous derived attributes. The SVM table is documented as fitted models, cross-validation loss/accuracy, permutation results and coefficients. It does not document a standalone aligned trial-by-feature matrix. The GLM function requires activation, memory age, sequence element, trial period, outcome and two velocity vectors; a direct join to those operands is still missing.

The schema also describes an `Assembly_Table` of learned templates and activation events, but that name is not a separate file in the eight-file release inventory. It may be an internal variable or retained model property; no claim of absence from MAT contents is justified. MATLAB fitted objects may retain predictor/response tables. Authentic format and property inspection, with no model execution, must resolve this before selecting a refit route.

The official SVM function takes an observation-by-feature matrix and two condition labels. It globally z-scores the matrix before cross-validation, chooses a box constraint using optimization, and uses 10 folds by default. It runs four accuracy-based permutation families plus a cofiring correlation comparison. The separate grid-search helper explicitly performs non-nested CV. Reproducing those operations is a historical-method exercise. They are not a clean protected test of a new predictor. The source file's declared function name also differs from its filename and requires an explicit, recorded adapter decision before native execution.

## Complete finite endpoint and two phases

**Reproduction:** preserve all 35 session accounts, original reference-epoch/feature-mask semantics and all five permutation families. The output vector comprises session-level cross-validation loss, accuracy, selected constraint, four permutation accuracy distributions and p-values, normalized coefficients and cofiring summaries. Record exact MATLAB releases/toolboxes, seeds, fold assignments and convergence warnings. Derive numerical acceptance tolerances only after an independently audited official reference exists. No arbitrary comparison threshold is supplied by this source component.

**Prospective improvement:** predict `p_new` for every evaluator-owned case in complete held temporal blocks within each session. Use the same cases for paper+data and paper+data+code conditions. Primary measure is a class-balanced log loss, averaged first over the two classes within a session, then equally over sessions within each animal, then equally over the two animals. Higher primary gain means the candidate's loss is lower than the competent nested linear-SVM comparator. Report each animal separately. Secondary balanced accuracy uses a fixed `p_new >= 0.5` decision. Probabilities are clipped only for scoring at `[10^-6,1-10^-6]` using natural logarithms.

This weighting defines a balanced-condition scientific target. It is not an estimate of the unbalanced empirical prevalence and must not be described as such. A fixed 0.5 predictor provides a useful class-balanced null. No improvement significance, independent animal replication or publication-level frontier result follows from a positive scalar alone.

Reference requirements: (1) training-only class prior, (2) behavior/position/velocity and mean-rate covariates without assembly structure, and (3) a linear SVM whose preprocessing, unit-stability decisions, assembly templates, hyperparameter selection and probability calibration use training blocks only. Freeze split IDs, complete case inventory, feature construction and resource budgets before candidate submissions. Retune every reference under the same protected split; an old published cross-validation number is not a fair comparator. The original optimized source remains available as the historical comparator, never silently renamed as this nested reference.

Temporal blocks must follow explicit trial/condition events and full session chronology. Blocks, time buffers, train-only template windows and any session ineligibility cannot be invented from array position or filenames. All 35 roster rows require a documented disposition. The present scorer intentionally refuses omitted sessions or missing old/new support; if authentic evidence makes a session ineligible, revise the finite contract explicitly and retain the old contract before introducing a different coverage rule.

## Information and contamination

Both arms receive the paper, the same admitted observation-level data, neutral data dictionary, frozen task specification, case IDs and training labels. The code arm additionally receives the exact official source only after its rights and delivery route are cleared. Neither arm receives historical fitted model objects, expected coefficients, permutation answers, full-release CV losses, evaluator labels or protected reference outputs. Necessary training predictors must be projected from source objects by a trusted reader; do not mount an entire result table because it also contains useful `X` or `Variables` properties.

An agent may improve feature extraction or estimation within the declared boundary. All predictions must be committed before evaluation; score feedback cannot choose a second submission. Public historical labels, code and manuscript results may already be in model training. New blocking within that public material cannot establish contamination-free evaluation. Findings must retain this limitation.

## Runnable component and remaining admission

`score.py` is a standard-library grader for a **trusted evaluator manifest**, candidate predictions and three complete baseline prediction files. It rejects missing/duplicate cases, nonfinite or out-of-range probabilities, unknown fields, wrong target labels, unknown or missing sessions, training/evaluation block overlap and incomplete baseline coverage. Candidate rows cannot supply targets. The manifest and roster must be immutable evaluator-owned inputs; this library does not implement authenticated intake, isolation, deadline enforcement or the candidate runner.

No authentic session roster is included in this public package. A future trusted evaluator must supply the complete independently authenticated roster using the stable export aliases `animal_1` (18 sessions) and `animal_2` (17 sessions); the mapping to original source animals stays evaluator-private. Its canonical JSON digest is the identity the manifest must reference. These aliases are an export interface, not evidence that the current private intake already emits it. `test_score.py` exercises arithmetic, group weighting, permutation of row order and 14 refusal cases using invented sessions and predictions.

A future complete intake must reconcile the eight-file release (998,727,104 advertised bytes), reusing the two already acquired metadata documents and acquiring the six scientific MAT files under a separately selected operation. Complete format/variable/property census and native-reader requirements remain. Before interpreting arrays, identify safe MAT versions and callable-object boundaries. Establish trial labels, block timing, assembly origin, stable unit IDs, all roster joins and data/code rights. If only fitted answers are recoverable, retain the release for result-table reanalysis and keep refit/improvement held. No new data acquisition or native run is selected by this document.

Data metadata declares CC BY 4.0; retain the authors, DOI and modification notice for derived packets. No repository-wide source-code grant has been established. This package contains newly authored implementation and facts, with links to official source; it does not redistribute that source or the manuscript. Registration and qualification remain unchanged.
