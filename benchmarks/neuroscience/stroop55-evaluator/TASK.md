# Stroop condition inference from frontal fNIRS

Existing registered draft: **NEURAL-SCOPE-20261114-STROOP**. Infer neutral, congruent or incongruent Stroop condition from an anonymized onset-aligned frontal HbO/HbR block. The complete endpoint retains all55 source participants and every eligible session3 block, with all165 participant-sessions represented in the source census. This package supplies a numerical evaluator and split logic for that task; it does not assert an authentic packet, new benchmark ID or scientific qualification.

The controlling scientific contract is the exact23,017-byte `STROOP_CANDIDATE_V3.json` pinned in SOURCES.json. All its source, preprocessing, nuisance-control, paired-information and exposure requirements remain. This implementation does not replace that contract with a smaller cohort or author-truncated30-block analysis.

## Intended evaluation and permitted training

The trusted assembler maps the actual55 source identities to unique opaque64-character lowercase hexadecimal identifiers and freezes this mapping before partitioning. Choose and commit one32-byte hexadecimal seed prospectively; never search seeds using outcomes. Rank IDs by SHA256 of `stroop55-joint-holdout-v1` followed by a NUL byte, the32 raw seed bytes, another NUL and the ASCII ID. Break hash ties by ID. Consecutive groups of11 form folds0..4. `fold_assignment` implements this rule. No authentic roster, mapping or seed has been selected in this source phase.

In each outer fold, training is the other44 participants' sessions1 and2 (88 participant-session pairs). The11 held participants contribute **no** training session. Their session3 blocks are intended evaluation. Session3 from every participant is absent from all training and tuning. This is joint held-person/held-session evaluation, not within-person session transfer. `training_roles` enumerates allowed records and `check_training_roles` refuses missing, extra, duplicate, held-person or session3 training declarations. These checks validate declarations; only an independently audited harness can enforce actual process access and per-fold state reset.

Any data-dependent scaling, feature choice, CAR choice, decoder fitting and calibration must be fitted only on permitted training participants, using nested participant-grouped validation. No transform may pool statistics from session3 or from held participants. Fixed signal-processing rules, marker offsets, units and potential continuous-filter carryover still require acquisition-level validation. The source contract's paired A/B/C six-example conditions and separate full-training conditions retain their distinct data budgets. Do not attribute differences between them solely to tool use.

## Candidate input and output

The future candidate input is the source contract's verified[-5,20) onset-relative HbO/HbR block and fixed time/channel metadata. Its proposed40×70 serialization needs independent units, anti-aliasing, filter, marker-window and information-loss checks. No signal packet has been assembled here. Event codes, block number, source filenames, session labels, absolute time, word/ink/response and behavioral reaction time must be withheld. Shuffle evaluation cases independently of chronology. Original schedule is identical across people within a session, making timing leakage a material risk.

Candidate output is a JSON object with schema `stroop55-predictions-v1`, task `NEURAL-SCOPE-20261114-STROOP`, and `predictions`. Each row has exactly an opaque `case_id`, three `probabilities` in neutral/congruent/incongruent order, and `label` using one of these class strings. Values must be finite, in[0,1], and sum to1 within1e-9; the scorer never renormalizes. Label must be the maximum-probability class; ties choose the first class in the fixed order. One and only one row is required for every precommitted case. Unknown, duplicate, missing or added cases fail the entire score.

The evaluator-owned manifest uses schema `stroop55-private-labels-v1`, task, `partition_seed`, `cohort`, and `cases`. Cohort has exactly55 unique opaque participants, each with sessions[1,2,3]. Each case has `case_id`, opaque `participant`, `session`3, source `block` index, deterministic `fold`, and integer `target`0/1/2. These private fields never enter candidate packets. Every participant must have all three classes; a missing class, person or session fails construction rather than changing a denominator. Duplicate source blocks are rejected even with different case IDs. Eligibility, every actual block and exclusions must be frozen from authenticated acquisition metadata before predictions; the scorer cannot establish physical completeness from a declaration alone.

The external owner supplies the manifest SHA256 selected before candidate execution. Run:

`python3 -I -S -B stroop.py --manifest PRIVATE.json --manifest-sha256 FROZEN_SHA256 --submission OUTPUT.json`

The module reads at most16MiB per operand and prints the score to stdout. Input paths must be ordinary single-link files without symlink ancestors. This I/O check and digest do not replace an evaluator sandbox, trusted source custody or exposure audit. The manifest and labels must be inaccessible and immutable to the candidate.

## Scoring and interpretation

For each participant, calculate recall separately for all three classes, then average the three recalls. The primary score is the equal mean of those55 participant balanced accuracies. Unequal block counts cannot give one participant more weight. The output includes each person's class supports, true-by-predicted confusion matrix, recalls and all five fold means.

Secondary metrics first average blocks within each person and then average persons: multiclass Brier is the **sum** of three squared probability errors (range0–2, no division by3); log loss is `-log(max(1e-15, probability_of_true_class))`. Only this log argument is clipped. No probability vector is renormalized or changed for Brier or classification. Uniform probabilities yield balanced accuracy1/3 under the stated tie rule, Brier2/3 and log loss log3; these are generated mathematical controls, not empirical results.

No bootstrap interval is implemented in this source phase. A future fixed-prediction participant bootstrap would be descriptive conditional on this cohort, observed session3 schedule, fixed folds and fitted policy. It cannot capture training, prompt-selection, refitting or new-schedule uncertainty; overlapping training folds are dependent. Blocks/channels/folds are not additional independent people.

The two study-wide comparisons require continuous numerical scores and same-case paired participant comparisons against competent train-only baselines. No success threshold, SOTA claim or published64% comparison is invented: that author result concerns a different within-person binary task. Passing generated controls says nothing about model ability.

All source labels are public. Session3 is **intended** evaluation until exposure, independence and the enforced input boundary are audited. No short-separation channels were recorded, so accurate classification cannot establish cortical specificity over systemic hemodynamics. Schedule-only, common-mode-only, pre-onset-only and spatial-pattern controls remain mandatory authentic scientific work, not simulated outcomes in this package.
