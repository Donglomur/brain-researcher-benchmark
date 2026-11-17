# NEURAL-083 — Motor-imagery protocol classification with fixed calibration

Predict right-versus-left cued imagery protocol class from the designated OpenBMI MI panel: all54 people, both sessions, all100 online-phase trials per person/session. This is one assignment with calibration/control conditions, not multiple benchmarks or independent cohorts. NEURAL084 uses the related SSVEP paradigm and remains a separate scientific target.

**Partial construction:**108 MAT recordings totaling64,847,432,285 bytes are unacquired; actual array/channel/label schema, prepared inputs/targets, numerical environment and empirical baseline are unverified. A bounded128-byte request confirms only MATLABv5 format for one recording. No array values, models or empirical scores were inspected or executed. Do not infer readiness from source code or generated tests.

## Scientific scope and full panel

Primary question: how well can the source protocol's classes be decoded when software receives only the first20 chronological same-session offline calibration labels from the target person? The visible class arrow persists through imagery, and the recorded online phase contains visual feedback from the **original100-trial calibrated classifier**. Restricting the new decoder's supplied labels cannot change historical feedback or the participant's earlier100 training trials. This is retrospective decoding under a software-input allowance, not a20-trial closed-loop system, calibration-time reduction, cue-independent intention decoder or causal motor-specific physiology claim. Removing trigger/response/EMG channels does not remove cue-evoked EEG or historical feedback.

Keep all54 people, including poor-performing users, and both sessions. Every source phase must contain100 trials and50 labels per class. Any missing file, unsupported schema, missing channel, nonfinite sample or failed bound stops preparation; do not drop a person, trial or inconvenient class. The10800 unique online queries are shared across all conditions.

## Fixed information conditions

Each isolated invocation receives one target person/session and one setting/arm. All settings may receive offline100-trial records from the other53 people in both sessions (10600 donor trials); no donor online targets are supplied. All recordings from the held person are excluded except the explicit calibration allowance:

* `target20` (primary): first20 offline trials from the queried session, regardless of class balance.
* `transfer0`: no target-person labels or other-session recording; subject transfer from donors only.
* `target100`: all100 same-session offline trials; comparison at the native label budget, not a claim of native numerical parity.
* `other_session20`: first20 offline trials from the target person's opposite session; no queried-session calibration. This is bidirectional retrospective session transfer; session2→1 is not a future forecast.

The label budget counts all supplied target labels, including internal probability calibration/tuning. No replacement trials, class-balanced quota, query-batch adaptation, hidden-person covariance fit or additional source lookup is allowed. Inner tuning preserves whole donor people; within allowed target calibration, use only those supplied trials. No query labels, source filenames, class cue, response/trigger channel or original person/trial identifiers are mounted.

Three arms use identical query IDs and eligible trials: `EEG` has only20-channel signal windows; `CONTEXT` has only the declared five features `[session==1,session==2,trial_rank/99,seconds_since_previous_cue,first_trial_flag]`; `PERMUTED_EEG` has the same signal inputs and within-person/session shuffled training labels (query truth unchanged). The permutation is deterministic and predeclared, a label-dependence diagnostic, not an inferential p-value. Context is intentionally permitted in that arm only; a chance context score would still not establish cue independence of EEG. Query and training rows are sorted by opaque keyed IDs, not original trial sequence. Permutation is applied before this sorting.

Freeze the candidate artifact/settings before all cases. Every case/setting/arm needs a fresh network-free invocation and isolated filesystem/history, with only its own packet. No cross-case caches, model persistence or combined packet access: the held person's labels occur in other people's donor pools. This package stages files and grades captured outputs; it does not implement or attest to an isolated runner.

## Signal and source method

The paper reports62 EEG channels at1000Hz and source structs EEG_MI_train/EEG_MI_test. Use the fixed source channel indices `[8,9,10,11,13,14,15,18,19,20,21,33,34,35,36,37,38,39,40,41]` (MATLAB1-based), with an operator-observed exact62-channel name binding. No auxiliary streams enter query arrays. Preserve source amplitude units; no unit conversion is guessed.

The new Python preparation uses `resample_poly(1,10,window=('kaiser',5),padtype='constant')`, then5th-order Butterworth8–30Hz causal lfilter on each continuous phase, and the source's positive MATLAB rounding of `100:350 + native_onset/10`, minus1 for Python indexing. This produces251 samples inclusive1–3.5s. The paper says250; the exact segmentation helper is inclusive, and this contract explicitly follows251. No claim of bitwise MATLAB resample edge/filter parity is made. Resampling and whole-record context are not qualified as an online pipeline. True class cues/feedback remain scientific limitations of these windows.

The author native baseline is per-person/session100-offline→100-online CSP/logvariance/shrinkageLDA, reporting class accuracy. Exact source is retained privately. The supplied `reference_program.py` is a declared independent probability reference: regularized generalized-eigen CSP with two extreme filters per side, sample logvariances, sklearn shrinkageLDA and training-only out-of-fold Platt calibration. It uses target calibration alone when present, otherwise donors; candidates may use the complete permitted donor pool. `REFERENCE.md` specifies defaults, fallback and departures. It has not been fitted or qualified.

## Artifact and score

A case directory contains only `case.json`, `training.npy` and `query.npy`. Arrays are little-endian float32, NPYv1, C order, finite; EEG shape[N,251,20], CONTEXT[N,5], queryN=100. Training metadata contains only opaque trial/person IDs, binary label(right=1,left=0) donor/calibration role and training-only inner-fold assignment. `case.json` pins exact arrays, generation and case/setting/arm. Match `input.schema.json`.

Produce one file matching `prediction.schema.json`, with generation/case/setting/arm unchanged and100 ordered `{trial,p_right}` predictions. Probabilities must be finite in[0,1]; booleans are invalid. Alternatively return `status: abstain` and a bounded reason. The operator collects all1296 case outputs, then submits the collection schema. Missing/duplicate/extra cases are invalid; any abstention leaves the complete panel unscored without reading targets.

Primary score is EEG/target20 balanced accuracy: average left/right recall per session, average the two sessions per person, then average54 people equally. Tie p=.5 predicts right. Report binary log loss with floor1e-15 separately, all12 setting/arm metrics, per-person results and paired calibration/context/permutation differences. No binary success threshold, favorable-sign requirement or BCI-illiteracy trait classification is defined. Person SD/sqrt54 is descriptive, not a calibrated confidence interval under shared donor training. The scorer validates every artifact before accessing operator-pinned private labels and never trains or executes candidate code.

Sources: [dataset/paper](https://doi.org/10.1093/gigascience/giz002), [GigaDB100542](https://gigadb.org/dataset/100542), [exact toolbox revision](https://github.com/PatternRecognition/OpenBMI/tree/c0e56825366681ae576801af08eb5fe326a5afd8). Published accuracies are not this contract's qualification targets.
