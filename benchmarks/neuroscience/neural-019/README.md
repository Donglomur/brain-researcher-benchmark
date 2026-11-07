# NEURAL-019: movement information in neural representations

Predict two-dimensional hand velocity from preprocessed motor-cortex spike counts on held-out maze groups within one macaque/session. The fixed reference study compares a 10-component PCA representation with a fixed 10-component random orthonormal projection under the same ridge-readout budget. A 137-unit readout and a movement-phase-only prediction provide additional controls. Arbitrary submitted velocity arrays are accepted; submissions need not reproduce any reference model.

This directory contains an operator scoring adapter. Source preparation does not establish adapter runtime qualification or external benchmark acceptance; consult the separately frozen qualification receipts.

## Task and data

The pinned source is MC_Maze DANDI `000128/0.220113.0400`, Jenkins session `20090925`, asset `26e85f09-39b7-480f-b337-278a8f034007`. The local source and packet identities are recorded in `assets.json` and the authoring protocol under `authoring/nlb-movement-v1/`.

The fixed split contains 1,340 official-training trials from 28 maze groups and 126 official-validation trials from eight different maze groups. All three maze versions remain within their maze group. Four whole-group folds are supplied for training-only selection. Assessment targets remain separate from candidate inputs.

| Public packet field | Shape or meaning |
|---|---|
| `train_counts` | `uint16[1340,140,137]`, spikes per 5 ms bin |
| `assessment_counts` | `uint16[126,140,137]`, identical unit order |
| `train_velocity` | `float64[1340,140,2]`, physical m/s |
| `train_trial_ids`, `assessment_trial_ids` | Anonymous unique identities in packet order |
| `neural_unit_ids` | 137 anonymous unit identities |
| `train_group_ids`, `train_cv_fold_ids` | Anonymous training groups and frozen fold membership |
| `neural_left_edges_ms` | 140 entries: −250, −245, …, 445 relative to movement onset |
| `velocity_left_edges_ms` | 140 entries: −150, −145, …, 545; fixed 100 ms behavioral lag |
| `velocity_axes`, `velocity_units` | `['x','y']` and scalar `'m/s'` |
| `panel_fingerprint` | Scalar Unicode digest binding the fixed packet |

These are processed spike counts and filtered velocity targets, not raw neural waveforms. Velocity conversion uses the stored physical timestamp clock, a complete 1,200 ms source support per trial, the source conversion factor `0.001`, and a 501-tap Hamming FIR decimator. Every output was checked against an independent valid convolution during conversion. The task is retrospective: the target FIR and reference Gaussian smoothing are symmetric and do not define a causal online decoder.

## Submission

Write a single regular, unlinked NPZ file, at most 1,048,576 bytes including archive overhead, containing exactly these six fields:

| Field | Required value |
|---|---|
| `velocity` | Finite signed float32 or float64, shape `(126,140,2)`, in m/s |
| `trial_ids` | All 126 unique assessment identities; reordering is allowed when predictions are reordered with them |
| `velocity_left_edges_ms` | Exact 140-bin public velocity clock |
| `velocity_axes` | Unicode `['x','y']`, in that order |
| `velocity_units` | Scalar Unicode `'m/s'` |
| `panel_fingerprint` | Exact scalar public fingerprint |

No labels, models, executable code, object arrays, extra fields, missing cases or duplicated identities are accepted. The scorer does not interpolate, clip or fill submitted outputs. Both C- and Fortran-order numerical arrays are supported. ZIP/NPY inventory, headers, payload sizes and CRC are checked before numerical payload allocation; public identities, units, clocks and finite values are checked before any private target loader runs.

The operator CLI is:

```sh
python benchmarks/neuroscience/neural-019/score.py validate --submission /absolute/submission.npz --output /absolute/validation.json
python benchmarks/neuroscience/neural-019/score.py score --submission /absolute/submission.npz --output /absolute/score.json
```

Use fresh output paths. The launcher binds the submitted SHA256, copies the submission into isolated worker scratch, and runs trusted scoring code in the fixed offline container. It never executes candidate code. `validate` reads no private target or reference asset. Invalid submissions exit with code 2 and `status: invalid_submission`; successful public validation reports `valid_prediction_contract`.

## Score and frozen comparators

The primary metric is the equal-maze-group mean of uniform-average x/y R². Each group's axis R² uses all of that group's trial/time observations and its own target mean. Groups receive equal weight regardless of trial count. The report retains every group's axis R², SSE, SST, MAE and MSE; pooled uniform-axis R² is secondary. Exact constant target axes have `SST=0` and undefined R². Any such assessment group makes the primary macro score `null`; groups are never omitted and undefined contrasts remain `null`.

The scorer reports signed candidate-minus-reference differences for both macro and pooled R² against `phase_only`, `raw137`, `pca10` and `random10`. Negative scores and negative differences remain valid results. There is no scientific pass floor or reference-family acceptance rule.

The four frozen references used identical spike inputs and a training-only phase template. Neural arms used within-trial Gaussian smoothing (SD 50 ms, truncation four SD), training-only unit scaling, and residual ridge readouts with an unpenalized intercept. PCA and projected scaling were fitted inside each training fold. The random projection used PCG64 seed `19019` and QR sign normalization. Each neural arm selected among `0.01, 0.1, 1, 10` on the same four group-held-out training folds; maximum-relative ties within `1e-12` favored the larger penalty. The study used 48 cross-validation and three final ridge solves.

PCA10 minus random10 is the matched representation contrast. The raw137 comparator has different input capacity. Stored reference scores are pinned to the stopped-producer prediction commit and source freeze `4d004f6bc17b0b26713759ed9b6bb20a53ddfef7e25f90ca56586ac2e8698555`; their prior arithmetic audit recorded 704 checks. This adapter compares against those frozen scores without rerunning models. The scalar audit was separately implemented by the same AI author as the fit core and is not independent human validation.

## Input boundary and exposure

Candidate input is the public packet above and its public manifest. It excludes assessment velocity, source trial/maze identities, original NWB data, the operator identity map and unrelated earlier task packets. Anonymous training groups remain available for grouped selection.

The scoring worker's public mounts are the package, public packet and submitted NPZ. Score mode additionally receives exactly the private target NPZ, pinned reference grade and pinned reference commit. The target NPZ contains assessment velocity, matching identities/clocks/units/fingerprint and the eight assessment maze labels. All candidate validation completes before any private asset is opened. After reference-lineage validation, targets are loaded once and joined to canonical public identities. Validate mode receives none of these private mounts.

All data are historical public development data from one macaque/session. The same source was used in NEURAL-017 and NEURAL-018, and these movement references have already been scored on the 126-case assessment panel. This is exposed development evaluation, not an untouched final test, new biological cohort, population estimate or independently replicated animal-level result. Trial and maze counts are not animal counts. Scores do not establish true biological latent states, causal mechanisms, native LLM understanding or published state-of-the-art performance.
