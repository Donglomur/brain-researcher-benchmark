# NEURAL-080 source recovery v2: scope and precedence

This is an inactive complete-scoped source construction checkpoint. It is not a registered runtime, an empirical result, a qualified decoder, a hardware-clock calibration or an active F/I controller. The canonical assignment is unchanged. `docs/RECOVERY_CONTRACT.md` names the current source entries and the explicit clip-time profile; the preserved legacy documents below describe the older source packet and are retained as historical method context. Their claims about metadata previously acquired do not mean that those bodies were read or copied in this recovery.

# NEURAL080 operator recipe and unresolved inputs

The source package is partial. It supplies an actual authenticated EEG/eye trial-metadata join, deterministic data projection code, five-arm candidate boundaries and numerical grading. It does not supply recordings, videos/audio, a qualified decoder/clock mapping, features, normalized targets, fitted references or an executed model environment. A valid external manifest is not scientific evidence that missing inputs have been acquired or aligned correctly.

## What is actually held

The shared NEURAL079 owner acquired the12 small EEG/eye object-NPY metadata files once and converted a restricted allowlist of fields into primitive JSON. Full original metadata remain outside this delivery. Six selected JSON files and their exact receipt are included operator-private:stimulus ID, run, trial, channel labels and native clocks only. Test-derived noise ceilings/SNR and unrelated saved arguments are excluded. A separate compact record preserves only `sfreq`, `tmin`, `tmax` and baseline-correction declarations. All12 saved records declare500Hz and−0.1..3.5second epochs; EEG baseline flag is integer1, eye baseline mode is `baseline`. These are authenticated saved declarations, not independent validation of the numerical preprocessing.

`join_metadata.py` was actually run as data-only metadata preparation (tool2d3b9a). `JOINED_METADATA.json` is3,245,600 bytes, SHA256`fa3b05a001c897327990d60f13ba0969cced17a4f1aa1e6a5b64cb284148cd24`. It retains exact source EEG and eye row indices, full unmatched-trial dispositions, all eight sessions and all1,102 video counts per person. Intersections by person are8,065/7,868/7,052/7,361/7,881/6,917. Minimum query repeat counts are21/18/16/17/19/15. No signal value, target average, model, prediction or scientific score was computed for this metadata join.

To recreate only that metadata artifact from the bundled primitive inputs:

```sh
python3 private/join_metadata.py --source private/source --out FRESH_JOINED_METADATA.json
```

The code authenticates the frozen selected-field receipt before parsing, verifies keys and clocks, joins by source identities, checks stimulus agreement and requires complete coverage. It does not load original object NPYs. The supplied join is an operator asset, never a candidate input.

## Source recordings and media gap

`source/REQUIRED_RECORDINGS.json` lists all96 exact recording objects:48 EEG and48 eye files,44,559,729,408 bytes total. It retains publisher URLs, observed exact lengths/MD5 ETags and release1.1.0/Git`b4f81bb8d2fb163afc5adb345e2218150b5d53b7`. The release's live object keys are mutable; content replacement must fail the selected identity and require a reviewed successor, not silently update this task. No recording has been downloaded or opened here. Full intake requires a separate root-selected capacity/resource plan; it is outside this100MB construction allocation.

The pinned author code is`a7408c8be3e015770dd986628dbc3f0ed499def3`. The eye writer defines the internal H5 dataset `eyetracking`; the EEG source uses `eeg`. Actual96-file schema compatibility remains unverified. Source raw EEG preprocessing contains a known undefined local in noise-SNR computation. This package uses the already published derivatives and does not execute or repair that raw pipeline; published derivatives are not invalidated merely by the source defect.

Videos/audio are accessed separately under the BOLD Moments stimulus terms. NeuralCC0 and author-code MIT do not grant stimulus redistribution. No stimulus terms/password file or archive was fetched. `DECODER_GAP.md` identifies the missing authoritative media-ID mapping, byte identities, trusted decoder and actual frame/audio presentation-clock receipts. Those gaps are not closed by the existence of the projection functions.

## Future fixed audiovisual feature preparation

Once the missing source mapping and decoder have been independently established, supply one immutable `neural080_decoded_media_v1` manifest in exact video-ID order1–1102. Each record needs the original media file/size/SHA256, actual decoded frame-cell arrays, frame start/end arrays, native audio samples/channel geometry/rate and first-audio-sample time relative to presentation. Frame-cell arrays must come from `stimulus_core.spatial_cells` applied to the decoded native RGB frames. The manifest also names the video-ID mapping receipt, decoder-source SHA and presentation-clock receipt. No placeholder receipts are provided.

`prepare_stimuli.py` has a strict input/output cap and verifies original local media SHA256 plus every captured primitive array. It then implements the frozen feature formulas. Its receipt does **not** independently establish that the external decoder or media-ID mapping was correct:

```sh
python3 private/prepare_stimuli.py --source-root FROZEN_DECODED_SOURCE_ROOT --decoded-manifest FROZEN_DECODED_MANIFEST.json --decoded-manifest-sha256 EXACT_ROOT_SELECTED_SHA --out FRESH_FEATURE_ROOT --max-input-bytes EXPLICIT_CAP --max-output-bytes EXPLICIT_CAP
```

This source is presently not an end-to-end video decoder. The future output contains static `(1102,384)`, motion `(1102,30,64)`, acoustic `(1102,30,10)` and dynamic `(1102,30,192)` primitive arrays plus `FEATURES.json`. Model counts and scientific-score counts remain zero. Duration weighting uses actual source intervals and stable anchored means; exact constant colors cannot become artificial dynamic variance. The acoustic recipe is a deliberately limited control, not proof that every auditory explanation is removed.

## Future full-cohort EEG/eye projection

Arrange raw files according to the frozen relative paths, with separate `eeg/` and `eye/` subtrees. The complete96-file existence check occurs before any recording or feature-array read. No one-person/session substitute is accepted. After a separately reviewed full intake:

```sh
python3 private/prepare_pool.py --raw-root FROZEN_RECORDING_ROOT --feature-root FROZEN_FEATURE_ROOT --out FRESH_OPERATOR_POOL --max-output-bytes EXPLICIT_CAP
```

The adapter validates regular-file identity on a stable open descriptor, computes each source SHA256 in addition to the recorded MD5, and checks internal nonvirtual/nonexternal H5 geometry. It preserves all exact source joined rows. The source metadata require127 EEG channels, three ocular signals and1,800 native samples. It never infers a128th channel, averages unjoined trials into the target, reads a noise ceiling or selects a favorable subset of people/videos/channels/times.

Per-session EEG normalization uses only joined900-fit-ID trials. Anchored batch statistics and exact constancy detection prevent false positive scales from a constant decimal value. Binned EEG and ocular means use stable anchoring, including averaging repeated video observations; there is no query-based fit, missing-target imputation or model training. Every128-apparatus/127-released-channel distinction remains visible. Source preprocessing itself remains offline and may use more than the designated fit trials; this additional normalization does not certify a wholly inductive preprocessing history.

All outputs are private:raw fixed nuisance/dynamic/ocular features, fit/validation targets, test targets, complete pool/provenance, query metadata and source row mappings. Expected prepared storage is much larger than this source build; no actual full-pool size/RAM/runtime benchmark is claimed. Explicit selected caps include final receipts. Incomplete output is retained on failure. Recording schema, scale support, all feature provenance and full runtime bounds still require actual qualification.

## Future isolated candidate views

For each of six participants and five arms:

```sh
python3 private/stage.py --pool FROZEN_OPERATOR_POOL --pool-sha256 EXACT_POOL_JSON_SHA --subject sub-XX --arm ARM --out FRESH_VIEW --max-output-bytes EXPLICIT_CAP
```

The stager reads only descriptor-bound private pool data. It constructs the selected feature matrix, fits feature scaling on the900 fit rows and copies the permitted fit/validation targets. The output view contains `x_fit.npy`, `x_validation.npy`, `x_query.npy`, `y_fit.npy`, `y_validation.npy` and `SCOPE.json`. There is no query target, source metadata, other-person data or alternate arm. Feature widths are2,630 nuisance;3,830 nuisance+eye;8,390 nuisance+dynamic;9,590 full or shifted-full. The full/shifted-full fit and validation matrices are exactly identical. Query dynamic shifting precedes the unchanged fit-coordinate transformation; no model is refitted to a shifted training dataset.

Mount only that view and promised public task/reference/dependency files into a fresh candidate environment, read-only. Do not expose the entire delivery, operator pool, raw files, private grader, original publicly reconstructible labels or another arm's state. Actual network/cache restrictions and same-method/model replay must be observed later; no execution controller or successful run is created by this package.

The prospective reference command fits models and has **not** been run:

```sh
python3 public/reference_model.py --view FRESH_VIEW --out FRESH_ARM_RESULT
```

It uses the same five ridge strengths and validation rule across arms. It is a deliberately fixed baseline recipe, not a proven competitive/optimal nuisance predictor. Full versus shifted-full must reproduce the same trained model/selection; a declaration or identical input recipe does not independently prove that a candidate complied.

## Future collection and grading

Each candidate result has `prediction.npy` and `RESULT.json`. The trusted operator supplies the exact list of30 result directories:

```sh
python3 private/collect.py --query FROZEN_OPERATOR_POOL/query.json --result-paths RESULTS_LIST.json --out FRESH_COMBINED_CANDIDATE --max-output-bytes EXPLICIT_CAP
python3 private/score.py --candidate FRESH_COMBINED_CANDIDATE --query FROZEN_OPERATOR_POOL/query.json --binding FROZEN_OPERATOR_POOL/gold/binding.json --out FRESH_SCORE.json
```

The scorer captures all30 finite primitive arrays before opening private binding/targets. Candidate arrays have exact shape102×127×150, float32 or float64, with no object pickles, extra payload, missing people/arms or ambiguous video order. Total candidate channel is capped at512MiB, each array20MB. Private targets are separately pinned. The operator must provide fresh output paths and adequate selected compute/storage; these commands are not empirical authorizations embedded in task data.

The primary is full-arm error, not a candidate-controlled gain. All signed contrasts and participant03 sensitivity remain descriptive. Bootstrap intervals are pointwise and conditional on these102 exposed videos, not an independent-video or simultaneous significance claim. Calibrated eye measurements, comprehensive acoustic controls, same-method restricted replay and competent comparators remain unproved. `qualified_dynamic_information` stays null even if a hypothetical supplied prediction file obtains a small error.

## Recorded construction evidence

Actual work:shared authenticated source metadata and args, the exact data-only trial join, code/contracts, seventeen distinct invented-data checks and source inspection. No EEG/eye signal, decoded movie/audio, model, fit, candidate trial, empirical score, dynamic/ocular scientific contrast or native scientific environment was executed. All future source acquisition and preparation gaps remain visible in `STATUS.json` and the delivery manifest.
