# NEURAL-050 initial evaluator

This package implements a complete **prospective development analysis** from bounded, locally exported ECoG/pose arrays to held-out movement predictions, matched gamma contrasts and patient-level summaries. It does not establish a scientifically qualified benchmark. The canonical task and historical source records remain unchanged.

The question is whether motor gamma adds movement information beyond behavior state and time of day. `evaluator.py` computes the actual signal features, fits both comparators using training data, produces held-out predictions, and recomputes the contrasts. It does not score agreement with a positive biological narrative. A null or negative increment remains a valid result.

## Source and prospective decisions

The source is [AJILE12](https://doi.org/10.1038/s41597-022-01280-y), [DANDI 000055 version 0.220127.0436](https://api.dandiarchive.org/api/dandisets/000055/versions/0.220127.0436/), and the [official notebook at f44ca6f6](https://github.com/BruntonUWBio/ajile12-nwb-data/blob/f44ca6f6c51251b62b6f47492bba400472d4a7ba/Example_AJILE12_exploratory_analysis.ipynb). The release advertises 12 patients and 55 recording-day files. No NWB payload was downloaded or analyzed for this implementation. Exact source response/content pins are in `implementations/initial-evaluator-v1/provenance.json`.

The notebook illustrates 80–100 Hz processing and wrist/neural association. Its neural expression differentiates `10 * natural_log(Hilbert_amplitude)`; its plotting labels do not make this conventional gamma power or decibels. Its pooled reverse-direction regression is not a validated movement predictor. This implementation therefore does not claim notebook reproduction.

The following are explicit new protocol choices requiring scientific approval before authentic outcomes:

- Nonoverlapping 2-second windows; per-channel demeaning, Hann taper, one-sided FFT periodogram integration over **80 ≤ f < 100 Hz**, then the mean natural logarithm of power across anatomically selected motor channels. No temporal derivative and no decibel claim. The half-open band excludes the 100 Hz edge. This does not replace line/muscle-artifact qualification.
- Same-window wrist path length divided by elapsed time, in source pixels/second. This is contemporaneous association/prediction, not future movement forecasting. Pixel geometry and camera differences remain a transfer limitation; no metric calibration is invented.
- Pose confidence ≥0.4, all source-valid masks true across a window, finite selected signals, the expected neural sample count and at most one pose-frame interval of endpoint discretization, and no behavioral-state transition inside a window. This confidence threshold is a prospective whole-window policy, not a claim that all source pose frames meet it.
- State-only one-hot terms plus daily sine/cosine as the baseline, versus the identical design plus gamma. Ridge uses fixed alpha 1 on standardized non-intercept coefficients. The weighted objective is weighted mean squared error plus alpha times squared coefficient norm; the intercept is unpenalized. No tuning uses held-out rows.
- Training weights give equal patients, equal days within patient, and equal windows within day. Feature means/scales use those training weights. Held-out unseen behavior states fail explicitly.
- Matched high/low movement windows use the training fold's median speed as the threshold. This unweighted training-window median is a prospective event definition, not source reach annotation or a diagnostic movement threshold. Match within patient, day, exact state-label set and hour bin; greedily pair each high window in time/ID order with the nearest unused low window within 300 seconds. Report all unmatched windows. Matching uses held-out target values solely to define the prespecified analysis groups, not to fit predictors.

## Local input and execution

Requires Python 3.10+ and NumPy. Pytest is only needed for tests. No package installation, network access, NWB loading, model call or dataset download occurs in this package. The caller must supply already bounded exports and qualified provenance. NumPy loads each export into memory; size the intake before running. Direct NWB extraction and payload qualification remain outstanding.

Run from this package directory:

```sh
python3 evaluator.py prepare raw-manifest.json feature-packet.json
python3 evaluator.py evaluate feature-packet.json population-report.json
python3 evaluator.py evaluate feature-packet.json within-patient-report.json --mode within_patient_days
python3 -m pytest -q tests
```

`prepare` consumes a JSON document with `schema: "neural050-raw-v1"`, `data_scope: "public_development_only"`, an exact copy of `evaluator.PROTOCOL`, the exact `source_dataset: {"dandiset": "000055", "version": "0.220127.0436"}`, an explicit `input_kind` of `ajile12_export` or `generated_engineering_control`, and a nonempty `recordings` list. The dataset field names the target source interface even for generated controls; the input-kind field prevents treating controls as authentic observations. Each recording has:

| Field | Meaning |
| --- | --- |
| `patient`, `session` | Stable biological and recording identifiers; patient/session pairs must be unique. |
| `day` | `YYYY-MM-DD`, matching the local calendar date of the session origin. Split cross-midnight exports at intake. |
| `source_asset_path`, `source_asset_id` | Source archive asset identity; generated controls use explicitly synthetic identifiers. |
| `path`, `sha256` | Local `.npz` export and its SHA-256; paths resolve relative to the manifest. No pickled arrays. |
| `session_start_utc` | Explicit timezone-aware UTC ISO timestamp. |
| `local_utc_offset_seconds` | Qualified offset for the recording date, used for local time matching. DST transitions require separately qualified exports. |
| `motor_channels` | Nonempty unique zero-based ECoG column indices, chosen before outcomes. |
| `anatomy_evidence`, `wrist_selection_evidence` | Nonempty references to the prespecified motor ROI and contralateral wrist choice. These strings record evidence; they do not validate it. |
| `clock_evidence`, `artifact_mask_evidence` | References to independently qualified clock/alignment and source QC procedures. |
| `pose_units` | Exactly `pixels`; no silent combination of calibrated and uncalibrated values. |
| `behavior_epochs` | List of `{start_s, stop_s, state}` intervals on the shared recording clock. Overlapping labels form a sorted exact label-set state. |

Each `.npz` contains **exactly** `ecog` (samples × channels), `ecog_time_s`, `ecog_valid` (boolean sample mask), `pose_xy` (frames × 2 for the selected wrist), `pose_time_s`, `pose_confidence` (one value in [0,1] per frame), and `pose_valid` (boolean frame mask). Times are actual shared recording-relative sample timestamps, including source stream offsets. Both clocks must be strictly increasing and regular. ECoG rate must exceed 200 Hz. Explicit validity masks must cover source discontinuities, including zero-filled neighborhoods, bad channels, muscle/line artifacts, camera motion and occlusion as applicable. Finite zero-filled signal is not evidence of validity. No missingness imputation occurs.

Pose speed uses the first and last acquired frame inside the window and divides by their actual elapsed time; it does not assume that offset pose and neural clocks have identical sample boundaries. Windows with greater than one frame interval of missing pose support fail.

The preparation command starts windows on a 2-second grid within the shared supported interval. It records excluded windows and reasons. Its FFT has exactly the independent window's support; there is no hidden zero-phase filter context extending into another split. Adjacent windows can share a pose endpoint, which is why windows are nested observations, never independent biological replicates.

Preparation binds the canonical complete raw manifest with SHA-256 and retains every recording extraction field, including asset identity, source path, session origin, UTC offset and state epochs. Reports also bind the canonical entire feature packet with SHA-256. These hashes are content bindings, not authenticity attestations.

The resulting feature packet has `schema: "neural050-features-v1"`, the same scope/protocol, dataset and input kind, `raw_manifest_sha256`, `source_pins`, `rows`, and `excluded_windows`. Each row carries unique `id`, `patient`, `day`, `session`, `start_utc_s`, `stop_utc_s`, `local_seconds`, `state`, `gamma`, and `movement`. The evaluator validates identities, complete 2-second support, no within-patient interval overlap across any session/day, finite values and source-pin linkage. It can also consume independently prepared packets with this exact declared interface. Source-pin declarations alone do not establish payload authenticity; packet qualification is a preserved gate.

## Endpoints, splits and interpretation

`population_transfer` performs leave-one-patient-out fitting: all available days of the held-out patient remain outside training. At least three patients are required to fit a comparator using at least two training patients. `within_patient_days` independently leaves each day out using only the same patient's other days and requires at least two days per patient. Its report is separate and has a distinct estimand. Actual support intervals plus a 2-second guard are checked across same-patient train/test splits, so relabeling nearby windows as separate days cannot bypass the guard.

For every held-out patient/day, the scorer recomputes baseline and augmented MSE. **Signed improvement is MSE_baseline − MSE_gamma**; positive values favor added gamma. The secondary delta-R² divides that difference by the held-out day's target variance. Constant target days retain MSE and explicitly have undefined delta-R²; summaries expose total and defined day counts. Constant challenger predictions are diagnosed, not automatically rejected, because constant predictions and null results can be scientifically legitimate.

The report averages days within patients, then patients equally. It retains all predictions, fold train/test IDs, training transformations and coefficients, daily errors, matched pair IDs, paired gamma differences and unmatched counts. Raw MSE units are pixels²/second² and are not invariant to camera scale; report the patient values and the secondary within-day normalized increment alongside the macro value. A patient bootstrap resamples patient effects with 2,000 fixed-seed draws for a descriptive percentile interval. It does not make overlapping cross-validation fits statistically independent or establish population uncertainty validity. Single-patient summaries have no population interval.

A fixed half-sequence circular shift of gamma **within each patient/day** is passed through the same fitting/scoring path. This preserves the day's gamma values and most order structure but has a wrap seam and can cross gaps or state changes. It is an alignment/autocorrelation diagnostic, not an exchangeable randomization test or a p-value. No biological significance decision is generated. Matched effects average available matched days within patient; days/patients with no pairs have no matched estimand, and `matched_coverage` explicitly counts every evaluated versus matched patient and day, retaining zero-pair days.

`score_predictions(rows, baseline, augmented)` independently checks exact prediction IDs and finite numeric outputs, then recomputes daily errors. `evaluate` fits its own prospective comparators; it is not an agent submission runner or protected evaluation service. The feature packet contains movement targets and must stay in the trusted analysis/scoring boundary if a future agent interface is built.

## Evidence and remaining gates

Tests use generated sinusoids, linear pose, analytic metric examples and adversarial identities/splits only. They test power units, QC exclusion, clock/hash failure, exact label sets, train-only fitting, biological weighting, constant targets, malformed predictions, temporal leakage, matching, null grouping and the CLI. They demonstrate implementation behavior, not a measured AJILE12 effect or reference competence.

Still unresolved: full selected population and payload equality; source-native bounded NWB export; anatomy/laterality and camera-scale validity; source-qualified artifacts and pose QC; stream-start alignment; prospective protocol and resource freeze; protected input/target separation; authentic reference and matched comparator runs; independent scientific replication; native parity; rights/access qualification; scientific admission and submission readiness. The implementation never marks these gates satisfied. Source data are CC-BY-4.0 according to the release metadata, and the converter has an MIT license; neither declaration is a current patient-access/privacy clearance. No third-party payload or notebook body is redistributed.
