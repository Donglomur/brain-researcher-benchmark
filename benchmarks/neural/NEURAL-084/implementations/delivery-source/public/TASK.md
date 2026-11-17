# NEURAL-084: overt-gaze flicker-target decoding

Identify which of four targets a person was instructed to gaze at from their EEG during stimulation. This uses OpenBMI's designated54 healthy participants, both sessions, and both offline/training and online/test acquisition phases. It is an overt-gaze BCI task: frequency, target position and visual cue are coupled in the experiment. It does **not** isolate covert attention, intention independent of gaze, or clinical effectiveness.

## Target and allowed information

Return four **raw real-valued scores**, larger meaning more support, in this exact order:

| Source label | Target position | Reference frequency | Harmonics in supplied reference |
|---|---|---|---|
|1|up|60/5 =12Hz|first and second|
|2|left|60/7Hz|first and second|
|3|right|60/9Hz|first and second|
|4|down|60/11Hz|first and second|

The exact ratios follow the pinned author analysis at a60Hz display refresh. Rounded paper values8.57,6.67 and5.45Hz are explanatory, not substituted reference frequencies. Absolute stimulus phase is not supplied. The unfitted CCA reference uses both sine and cosine at each harmonic and is phase-invariant within each sinusoidal subspace. These are reference frequencies, not verified trial-specific photodiode measurements. A method may use other publicly declared signal processing/harmonics if its policy is frozen before evaluation; it must use only the provided epoch.

Each query is a `float32[10,400]` array. Ordered source channels23–32 (MATLAB1-based) are `P7,P3,Pz,P4,P8,PO9,PO10,O1,Oz,O2`. Source labels and order must match exactly during preparation. The representation contains `[0,4)` seconds from the1-based source stimulus-onset sample: exactly4000 original samples at verified1000Hz, converted by nonoverlapping10-sample arithmetic means to100Hz. Block centers are0.0045+0.01×k seconds. Original numeric amplitude units and nasion reference are retained; no unverified conversion to volts is made. Preparation uses no filter, fitted transformation, padding, rereferencing, or samples outside this interval. Block averaging is a declared representation change, not ideal antialias filtering.

This is a prospective benchmark representation. The author analysis resamples and filters continuous data, then uses an inclusive0–4000ms helper; at100Hz the code's endpoint convention produces401 samples although the paper describes400. We explicitly use400 half-open blocks to exclude the4s boundary and feedback beyond it. The supplied Python reference has not been qualified as numerically identical to the original MATLAB pipeline. Published accuracies are not qualification targets for this new representation/split.

## Held-person contexts

There are54 mandatory contexts. Each holds out one entire person, including both sessions and both acquisition phases. The other53 people supply labeled training trials from both sessions/phases. The held person supplies400 queries:100 trials per session/phase, with25 of each target in every cell. No person, session, phase or class may be dropped based on signal quality, baseline performance, or a perceived BCI-literacy threshold. Incomplete actual source support blocks preparation.

One context contains `fold.json`, `training.npy`, `training.json`, and `queries.npy`. Array pins and ordered query IDs are in `fold.json`; training metadata exposes only training identities, labels, person, session and acquisition phase. Query order is sorted by secret-derived opaque IDs, independently of source trial order. Trial cues, triggers, target labels, source timestamps/order, subject metadata, EMG and all unselected channels stay private. Query session/phase labels are withheld. Read the supplied query rows as-is.

Learn dataset-level normalization, feature selection, hyperparameters, or calibration only on training people with grouped inner selection. No target-person labeled calibration, query-batch fitting, policy adaptation, or feedback from the scorer is allowed. A frozen deterministic per-epoch calculation is allowed: this includes CCA's epoch centering and canonical-weight/subspace calculation, but never learning a new policy from other queries. Train/freeze one policy before access to any query context. Reset the candidate process and writable state between all54 contexts; do not retain earlier training/query examples or model state. A person is training data in other contexts, so shared context/state would expose future answers. Mount only the current packet and candidate program. The private pool, original MAT files, other task packages and sibling packets must remain inaccessible. NEURAL083 shares people/source collection and belongs to the same contamination group.

The primary score is equal-person, equal-session, equal-acquisition-phase, equal-class mean recall. Keep the216 phase-level confusion matrices/supports,54 person scores, and aggregate score. Both sessions are held-person evaluation data, not training from the target person's first session: this is not longitudinal adaptation or a session2-only transfer claim. Repeated trials are nested within people; they are not21,600 independent participants. Scores alone do not support population uncertainty or a clinical claim.

## Candidate interface

Run a candidate in a fresh context:

```text
python /program/program.py --input /input --out /output/predictions.json
```

Write strict UTF-8 JSON with schema `neural084_scores_v1`, the exact `generation` and `fold` from `fold.json`, and400 ordered predictions. Each prediction has exactly `id` and `scores`, a four-element list of finite nonboolean numbers. Negative scores are valid; probabilities and normalization are not required. No softmax/calibration is silently applied. Ties choose the earliest class above. Duplicate JSON keys, additional fields, missing/reordered IDs, NaN/infinity, oversized integers or a file over262,144 bytes are invalid. The scorer validates **all54 submissions** before opening private labels and cannot give a partial-cohort score.

```json
{"schema":"neural084_scores_v1","generation":"<exact supplied generation>","fold":"fold001","predictions":[{"id":"<exact supplied ID>","scores":[0.1,0.9,0.2,0.0]}]}
```

The example shows one row for notation; an actual submission requires all400. The supplied `reference_cca.py` follows this interface, uses no training labels, and returns the largest canonical correlation with each two-harmonic reference. Constant/rank-zero EEG yields four zero scores and the declared tie outcome. This source implementation and generated-signal checks are not empirical reference results.

The operator must retain a cue/timing-only constant-score baseline (no per-trial cue/timing variables are public), per-frequency confusion, and a prespecified frequency-column permutation diagnostic. The supplied reference's `--mode constant` emits four zeros; `--mode frequency-permuted` rotates the CCA score columns left by one without changing inputs or labels. Neither has been run on actual EEG. A poor decoder baseline cannot establish mechanistic specificity. Neither this source construction nor the available data rules out eye-position, cue-driven visual responses, ocular artifacts, frequency-response differences, or source preprocessing effects.

## Current availability

The exact108-recording roster is known; its listed total is59,597,469,294 bytes. These EEG recordings are **not bundled or acquired**. Only one128-byte official MAT header was checked; that establishes a MATLAB5 little-endian file container, not actual field layouts or numerical compatibility. The operator has deterministic preparation/scoring source, but no prepared real training/query packets, private gold, empirical baseline scores, or qualified execution environment. Do not interpret a successful source-package check as a ready benchmark run.
