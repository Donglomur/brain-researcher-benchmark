# Processed activity and next-visit prediction evaluator

`initial-evaluator-v1` implements the task's next construction action: map longitudinal mouse/dendrite/spine identities to consecutive structural outcomes, compute pre-outcome activity/coactivity, and execute fixed competing predictors with mouse-held-out calibration. It is a complete evaluator for its explicitly defined processed-input interface. It is **not a whole-paper implementation or scientific qualification**, and does not reproduce the author's MATLAB mixed-effects results, spatial-label shuffles or postsynaptic timing analyses.

The authoritative `task.json` remains unchanged: 28,324 bytes, SHA-256 `8a452a1a2f4ad7be2f51af72392f9f5de03db9791b3f19d5e4cb92a9e68dc0f6`. Scientific qualification, native baseline competence and full-cohort equivalence remain unknown.

## Source and scientific boundary

The primary paper is Hedrick, Wright and Komiyama (2024), [doi:10.1126/sciadv.adk0540](https://doi.org/10.1126/sciadv.adk0540), [author-hosted published PDF](https://wjakewright.github.io/files/Hedrick_et_al_2024.pdf), Methods pages 11–14. [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10942101/) supplies the same article. `provenance.json` records acquired content hashes and distinguishes new primary-paper reads from historical source-reported archive metadata. The author archive is [Zenodo record 10108836](https://doi.org/10.5281/zenodo.10108836). Its 19,743,225,896-byte ZIP and recorded MD5 were **not acquired or independently verified**. No archive members were extracted or copied into this package.

The source's binary activity traces cover the complete imaging session, including movement, nonmovement and intertrial periods. Activity event frequency counts continuous active bouts. Pairwise normalized coactivity counts continuous bouts in the logical intersection, then divides by the geometric mean of individual event rates. Distance follows the dendritic path, and nearby means at most 10 μm. These definitions are implemented directly. Both spines must be active for a defined normalized value; inactivity yields an explicit missing feature, never a fabricated zero. The normalized value can exceed one.

The paper's retrospective sample includes baseline-existing spines and removes spines that disappear and reappear. Its stable rows correspond to consecutive session pairs in dendrites with an elimination event; a stable spine can contribute twice. This package reports that outcome-conditioned block flag and descriptive contrasts separately. Prediction retains eligible intervals from all supplied dendrites, including intervals with no elimination. All rows from a mouse, and therefore all its dendrites and repeated spines, remain together in one outer fold.

This is a retrospectively adjudicated cohort with a prospectively frozen prediction policy, not a simulated live deployment. Whole-trajectory reappearance exclusion is an identity-quality screen requiring future assessment. It removes ambiguous target rows, but **does not remove that spine's contemporaneous activity from other spines' neighbor features**. Newly formed spines are excluded from targets and neighbor features by the explicit v1 baseline-population policy. Exact archived-code handling of every partner population remains unverified. Source cohort selection and health judgments can induce selection bias; no claim about an unselected population is made.

## Input and units

Run from a repository checkout using an existing Python 3 + NumPy environment:

```sh
python3 benchmarks/paper/PAPER-FIND-REP-011/implementations/initial-evaluator-v1/evaluator.py INPUT.json OUTPUT.json
python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-REP-011/implementations/initial-evaluator-v1/tests -v
```

The output path must not already exist and cannot be the input path. The bundled `example_control.json` is a small **generated engineering control** accepted by this exact CLI. Its values are not recordings, empirical predictions or a reference answer.

Input schema `rep011-processed-v1` contains:

- `cohort`: exactly one of `iglusnfr2` or `iglusnfr3_rcamp2`. The cohorts are never pooled in one evaluation.
- `provenance`: `kind` (`generated_engineering_control` or `empirical`), fixed `source_record: zenodo.10108836`, and nonempty `input_scope`, `alignment_policy_id`, `activity_detection_policy_id`, `fate_assessment_id`. These declarations record provenance; they do not certify the transformations or independent label assessment.
- `sessions`: at least two globally scheduled sessions, each with unique `session_id` and strictly increasing numeric `day`. Different schedules require separate inputs; there is no unsignaled stitching of visits.
- `dendrites`: complete supplied roster, each with `mouse_id`, `dendrite_id`, `health_status` (`eligible`, `excluded`, `unresolved`), `health_assessment_id`, and `arc_start_um < arc_end_um` delimiting the imaged dendritic segment. Excluded/unresolved health is reported, not silently used.
- Each dendrite's `spines` has unique `spine_id` and an `observations` entry for **every** scheduled session in order. `state` is `present`, `absent`, or `unknown`. For `present`, require arc `position_um`, positive `sample_hz`, a complete binary `activity` list, and `continuous_complete_session: true`. Non-present observations cannot carry activity/position. Missing structural assessment must be represented as `unknown`, not an omitted visit.

All present traces on one dendrite/session must have identical length and sample rate. Activity values must be binary with no NaN or missing samples; this interface supports a single continuous session, not acquisition blocks, masks or concatenated traces across gaps. The continuity declaration must be established by a qualified native converter. Otherwise reject/hold the input. Optical image extraction, detection thresholds, alignment, dendritic identity and source cohort completeness are outside this processed-input evaluator. A source-faithful raw converter cannot be inferred from this schema.

## Frozen calculations and policies

Duration is `N / sample_hz` seconds; rate is `event_count * 60 / duration` events/minute. A trace beginning active contributes one event. That left-boundary convention is a prospective v1 choice because archived executable parity was unavailable. Equal-duration normalization cancels time: `joint_run_count / sqrt(count_a * count_b)`. `local_coactivity` is the unweighted mean over defined pairs between the focal spine and baseline-existing contemporaneously present same-dendrite neighbors within 10 μm. No neighbors, or no active eligible pair, gives `null`, with neighbor, eligible-pair and zero-activity-pair counts.

For a baseline-present eligible spine present at visit `k`:

| Next scheduled observation | Label | Interpretation |
| --- | --- | --- |
| present | 0 | Retained through that assessment |
| absent | 1 | Disappearance occurred in `(day_k, day_k+1]`; exact time unknown |
| unknown | null | Unobserved next-visit outcome; never treated as retained |
| no next scheduled visit | null | Terminal observation; no future horizon to score |

No interval spans an unknown visit. A later observed present spine may enter its own later adjacent interval. The package predicts observed next-visit elimination risk; it does not estimate survival curves, hazards, or censoring-adjusted incidence. Labels are complete-case outcomes, so informative censoring remains a scientific limitation. Scheduled intervals can have unequal duration; results describe the supplied mixture of horizons, and cross-cohort/horizon comparisons require a separately frozen protocol.

Three fixed models are fitted independently in every leave-one-mouse-out fold: intercept only, event rate, and event rate plus local coactivity. At least three mice must have known outcomes. Every training mouse receives equal total loss weight; its interval rows divide that weight equally. Feature means/scales and mean imputation use training mice only. Each feature also gets a missingness indicator. The logistic objective is weighted mean binary log loss plus `0.5 * sum(beta_feature**2)`; the intercept has penalty `0.5e-6 * beta_intercept**2`. Newton updates with descending line search stop at maximum gradient below `1e-10`, with a hard 100-step failure. Regularization is fixed, no tuning/calibration set is selected, and weak intercept regularization keeps one-class training folds finite. Model coefficients and training transforms are reported for audit. No outcome-conditioned environment feature is used.

Every scored mouse must have predictions for **all** its scheduled risk intervals, including censored rows; extra, missing, duplicate or nonfinite probabilities fail. Entirely censored mice are explicitly listed as unscorable and remain in population counts. Terminal rows remain in the result but have no prediction horizon.

The primary score is equal-mouse mean Brier loss. Secondary outputs are equal-mouse log loss (probabilities clipped only for this metric at `1e-15`), signed calibration bias (`predicted - observed`), per-mouse AUC with undefined one-class AUC left null, and fixed-decile reliability tables weighted equally by mouse. AUC's defined-mouse count is explicit; one-class mice still contribute all proper losses and calibration. Paired per-mouse Brier differences compare activity-plus-local to activity-only; negative favors the former. No uncertainty interval, significance, superiority or causal claim is produced. Spine rows are not treated as independent replicates for the reported primary comparison.

Descriptive source-aligned event-block contrasts report per-mouse means for eliminated and retained rows and an equal-mouse mean difference among mice with both groups. This aggregation is a declared prospective alternative; it is not `fitlme`, the published median, or a recreation of reported p-values. The paper's environment contrasts additionally condition neighbors on future elimination labels. Those retrospective groupings are deliberately not prediction features. Their caption/methods discrepancy requires archived-code verification before exact reconstruction.

## Requirement coverage and remaining holds

| Registered requirement | This package | Remaining gate |
| --- | --- | --- |
| Map longitudinal spine/dendrite/mouse IDs and elimination/censoring | Complete strict processed-input risk-set construction and exclusion ledger | Native array identity, independent fate assessment and full roster admission |
| Activity and local coactivity differences | Bout-based rates, ≤10 μm normalized coactivity, descriptive mouse summaries | Detection thresholds, source-native parity and original mixed effects |
| Held-out mouse/dendrite predictor comparison and calibration | Complete fixed-model leave-mouse-out fit/score path with training-only transforms | Authentic cohort execution, meaningful competent baselines, independent protected replay |
| Spatial clustering and postsynaptic timing | Arc-coordinate neighborhood used for local activity | Plasticity labels, nearest-neighbor global shuffles, RCaMP2 matching/timing and multiplicity remain unimplemented |
| Full populations and source identity | Supplied counts, exclusions, repeated rows, cohort separation and original archive identity retained | Full source cohort mapping and acquisition are not asserted |
| Rights/protected reference | No author code/data redistributed; original license metadata retained | Component/stimulus rights, empirical redistribution, protected labels/reference and candidate access boundary |

For comparison against a future qualified native conversion, the source reports iGluSnFR2 analysis counts of 24 mice with elimination, 72 dendrites with elimination, 2,014 unique spines, 2,686 retained transition rows and 252 elimination events. The coexpression analysis reports 7 mice, 11 dendrites with elimination, 325 unique spines, 517 retained transition rows and 46 events. These are **paper-reported audit targets**, not execution results, and they are not hard-coded as admission or scoring shortcuts. Prior healthy and imaged populations are larger and must be reconciled in a native roster audit.

Tests use analytic activity traces and constructed structural states only. They exercise real feature, cohort, fit, score and CLI paths, including coactivity above one, units, spatial boundaries, silent spines, censoring, reappearance, train/test isolation, complete coverage, unequal mouse counts, one-class folds and output preservation. They establish engineering behavior, not authentic reproduction, scientific difficulty or benchmark qualification. No model/API/native scientific campaign or dataset/archive acquisition was performed.
