# AJILE12 prospective reconstruction evaluator

This package implements a complete **prospective reconstruction evaluation component** for the selected human processed AJILE12 data. It prepares a fixed 12-participant, 180-mask panel; exports isolated single-mask observed inputs and separates private target arrays; runs training-mean and conditional ridge baselines; and scores submitted missing-channel reconstructions. It does not train diffusion models, reproduce the paper's random-forest endpoint, or establish scientific qualification. Canonical task and historical evidence remain unchanged.

The authoritative contract is `task.json`, SHA-256 `98c1df78da7b6063962681eeedfcb553d7126498354fa899399e8dcdb94cd253`. The implementation is `implementations/initial-evaluator-v1/evaluator.py`. Only NumPy is needed for prepared-array scoring. Native NetCDF conversion additionally needs an **already installed** xarray and compatible backend; none was installed or available during this construction. That adapter has source/interface review but no authentic NetCDF execution evidence.

## Source-derived decisions and prospective policies

The paper is [Vetter, Macke and Gao, Patterns 2024](https://doi.org/10.1016/j.patter.2024.101047), with [primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11573898/). The pinned author source revision is `7e9c3314dc242c36a206d18f13158c049e84cd1d`. Specific sources and requirement mappings are saved in `provenance.json` in the package; their raw bytes were not downloaded, so no invented content digest is asserted.

| Decision | Origin and implementation |
|---|---|
| Population | Author `scripts/ajile_script.sh`: all EC01–EC12, channel counts 94, 86, 80, 84, 106, 80, 64, 92, 126, 126, 106, 116. Authentic inputs must match. Generated controls explicitly use smaller channels. EC07 in YAML is a default, not a replacement cohort. |
| Event window | `load_ajile_data`: inclusive −2 to +2 seconds, 1001 samples at 250 Hz. ECoG excludes the terminal label channel; native adapter checks label codes 1/2. |
| Split | Loader's last sorted unique `events` day is test; every earlier day is training. Every input row is retained in exactly one partition. This follows code even when fewer than seven days are available; paper prose describes first six days/seventh day. Actual train/test days and counts are emitted. |
| Normalization | Channel range fences from all training event ranges: Q25 − 5×IQR and Q75 + 5×IQR. Zero range and values strictly outside fences are invalid. Training mean/population standard deviation pool eligible event×time values per channel. Same statistics transform test. Undefined channels fail the panel. |
| Missingness | Author convention: observed count `round((1−dropout)×channels)` using NumPy ties-to-even; `default_rng(seed).choice` without replacement. Dropouts .5/.7/.9, seeds 0–4, same mask for every test event/time of that participant. No zero-observation or zero-target case accepted. |
| Candidate quality handling | Prospective: unavailable observed event/channels are zero-filled and explicitly masked; hidden-channel quality never enters the public packet. The author imputation routine itself does not consult the quality mask. |
| Scoring | Prospective MSE, scalar spectral error, correlation convention, artifact eligibility and participant-macro aggregation below. They are not the paper's numeric targets. |
| Baselines | Source-grounded training mean; prospective instantaneous ridge. Ridge is not the paper's trained deterministic neural network. |

The paper reports missing-channel correlations, spectral plots and downstream rest/movement random-forest decoding. The author plotting function uses `scipy.signal.csd` and quantile summaries. This package's FFT periodogram diagnostic is an explicit prospective alternative, not a reproduction of those spectral plots. Published random-forest accuracy, three training folds, learned deterministic baseline and diffusion model execution remain separate held work.

## Inputs and commands

Commands below are run from this package directory with absolute paths substituted for the operator's inputs and outputs. No command downloads data, installs a dependency, trains a diffusion model or invokes a model API. Native source is the processed [Figshare 16599782 version 2](https://figshare.com/articles/dataset/16599782) ECoG family. Raw DANDI NWB, rat LFP and macaque anesthesia files are not interchangeable inputs.

```sh
python3 evaluator.py convert /approved/EC01_ecog_data.nc /approved/extracted/EC01.npz
python3 evaluator.py prepare /approved/extracted/panel.json /operator/ajile-conditions /operator/ajile-private
python3 evaluator.py export-case /operator/ajile-conditions/manifest.json EC01-drop50-seed0 /isolated-run/case-input
python3 evaluator.py baseline /operator/ajile-conditions/manifest.json /operator/mean-predictions --method mean
python3 evaluator.py baseline /operator/ajile-conditions/manifest.json /operator/ridge-predictions --method ridge
python3 evaluator.py evaluate /operator/ajile-conditions/manifest.json /operator/ajile-private/manifest.json /operator/ridge-predictions/predictions.json /operator/ridge-score.json
```

Run conversion once for each participant. Fresh output locations are required; conditions/reference directories must be disjoint, with neither nested inside the other. Both operator directories use mode 0700 and files 0600. The complete conditions collection is **operator-only**: different masks reveal each other’s targets, so it must never enter a candidate environment. `export-case` creates exactly one case input, its participant training data, and `case.json` in a fresh directory outside that collection. Only this exported directory may enter one candidate run. Reset the candidate process/container and writable state between masks, deny other-case outputs, and keep both operator directories inaccessible. These files and export checks do not prove process/container isolation; independent operator enforcement remains held. The built-in baseline commands are trusted operator computations, not candidate executors.

The panel JSON has `schema: "ajile-reconstruction-v1"`, `kind: "authentic_input"` (or `"generated_control"` for clearly labeled controls), and ordered `participants` entries for every ID EC01–EC12. Each entry contains `id`, `path` (extracted NPZ relative to panel JSON), and the NPZ's SHA-256. A minimal entry is:

```json
{"id":"EC01","path":"EC01.npz","sha256":"<64 lowercase hexadecimal characters>"}
```

Each NPZ must have finite `signal` of shape events×ECoG-channels×1001, integer `days` of length events, uniformly sampled `times`, unique text `row_ids`, `source_filename` such as `EC01_ecog_data.nc`, and `source_sha256` of the original native file. The adapter derives sequential native-row identifiers and hashes the native file. It expects one NetCDF variable with dimensions events/channels/time, matching the inspected loader. Extraction provenance supplied without native conversion is an operator assertion; a checksum does not prove complete or authentic data. Arbitrary source units are retained; this package does not assert volts or microvolts.

The operator conditions manifest (internally named `public_manifest` to distinguish it from the target-reference manifest) binds all case files, training data, source identity, exact masks, days, row counts and expected shape. Exportable training files contain standardized training signals, training quality and row IDs. Each case file contains only `condition` (test events×2C×1001) and test row IDs. The first C channels are availability masks, the second C are zero-filled standardized observations. This admits the entire retrospective observed window; there is no online or future-blind forecasting claim. No test targets, test labels, target quality, or test-derived normalization are released.

Each prediction NPZ contains finite `prediction` shaped test events×C×1001 in standardized units, matching `row_ids`, and the scalar text `case_digest` from the exported `case.json`. Observed-channel predictions are ignored by scoring; only hidden channels contribute. After separately isolated candidate runs, the operator creates a submissions JSON with `predictions` entries containing each case `id`, relative NPZ `path`, and its file `sha256`. `python3 evaluator.py collect /operator/ajile-conditions/manifest.json /operator/submissions.json /operator/collected-predictions` validates all 180 bindings and gathers the files. The resulting `predictions.json` contains the schema, `public_manifest_sha256` (the operator conditions manifest), and the exact case records. Candidates do not need the multi-mask collection or its manifest to emit a bound prediction. Candidate rows must match the declared order exactly. Missing cells, changed references/inputs, duplicate cases, nonfinite predictions and incorrect row bindings fail evaluation.

## Computation

The conditional ridge baseline fits each hidden channel only on eligible training target events. Observed training channels marked invalid are zero-filled, identically to test conditioning. It regresses instantaneous target samples on the observed channels using an unpenalized intercept and objective `mean((y − b − Xw)^2) + 0.001 * ||w||²`. This fixed prospective penalty is not tuned on test data. Mean baseline predicts zero in standardized hidden channels, corresponding to each training channel mean. Both use the identical observed channels and time context as the submitted candidate.

Metrics are target-only. `mse_standardized_all` includes every hidden event/channel/time value, including artifact outliers. This full-population number prevents artifact eligibility from silently improving the reported primary error. `mse_standardized_eligible` additionally reports the fixed training-fence-quality subset; `mse_source_units_squared_eligible` multiplies each channel error by that channel's training variance before averaging. The raw-unit score therefore has input-unit squared units and can give larger-variance channels greater weight.

`pearson_eligible` calculates correlation per target event/channel across time and averages those values. Constant prediction against variable target is assigned zero, matching the stated mean-imputation convention; its count is reported. A constant true target has undefined correlation and is counted/excluded; normal quality filtering already excludes it. An entire case with no eligible targets fails instead of disappearing from the panel.

`psd_db_mae_eligible` uses each standardized trace after removing its own time mean; computes a one-sided rectangular periodogram `|rfft|² / (fs*N)` with doubled interior bins (excluding the even-length Nyquist bin); omits DC; floors both powers at **1e−12 standardized-unit²/Hz**; and takes mean absolute difference of `10*log10(power)` across frequency bins, then eligible target event/channels. This metric is in dB. It detects amplitude discrepancies but cannot distinguish phase inversion; MSE/correlation supply that complementary information. There is no fitted epsilon or spectrum normalization based on held-out targets.

Each case reports complete and eligible/excluded target event/channel counts, total target sample count and correlation conventions. Scores average cases equally within each participant, then participants equally. Dropout-specific summaries average five masks within participant, then the 12 participants. Participants with more events/channels do not dominate cohort summaries. No binary reward, pass threshold, significance claim or uncertainty calibration is supplied.

## Validation and remaining holds

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Generated controls exercise independently derived normalization/fence values, ties-to-even mask counts and seed indices, train-only ridge closed form, source-unit scaling, phase inversion with identical PSD, amplitude scaling, even/odd Parseval identity, target isolation, quality counts, complete-panel preparation/scoring, a cross-mask channel-union attack, safe single-case export/collection, manifest/row failures, participant weighting and rejection of small generated arrays relabeled as authentic inputs. They run both baseline paths over 180 generated cells. They establish engineering behavior only.

No empirical file was acquired or opened. No model was trained and no paid/native scientific campaign was run. Authentic schema compatibility, event completeness, native reference numerical agreement, diffusion competence, empirical metric behavior and CPU/GPU feasibility remain unmeasured. The generated panel is not an authentic reproduction or benchmark difficulty measurement.

Day-held-out splitting cannot establish absolute-time guard bands or certify nonoverlap of event windows from relative time vectors alone. Absolute event support metadata, cross-day clock reconciliation and a declared guard policy remain necessary before claiming blocked-time qualification. Participant-specific models do not demonstrate held-out-participant generalization. Artifact filtering, scalar PSD, ridge, MSE and macro aggregation are prospective policies with explicit rationale, not newly discovered historical requirements.

Figshare metadata records CC BY 4.0; pinned author code records MIT. No empirical data or author implementation was copied into this package. Full-text/component/stimulus redistribution rights and actual pretraining exposure still require task-specific qualification. Public source availability does not establish blind evaluation or causal code-access benefit. Research/submission qualification remains **unknown**, and task counts are unchanged.
