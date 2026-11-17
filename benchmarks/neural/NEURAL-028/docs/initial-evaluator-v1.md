# Initial NEURAL-028 evaluator scope

The new [package](../implementations/initial-evaluator-v1/README.md) computes neural statistics from complete explicitly mapped array packets: source selectivity and reward-location d′ fractions, a prospective movement/position standardized selectivity endpoint, paired animal changes with animal bootstrap uncertainty, gray-baseline activity, whole-trial null diagnostics, and a before-only leave-animal-out explanatory reference with full test residuals. It preserves the canonical task and historical source identities.

| Contract requirement | Implementation and boundary |
| --- | --- |
| Calcium-derived neural inputs and frame alignment | Validates neurons × frames, exact behavior alignment, source category mapping, trial completeness, cortical IDs, finite values, and 60-bin trial tensors. Native NPY extraction and interpolation are not executed. |
| Before/after regime contrasts | Requires a complete supplied session manifest and paired phases for every declared mouse; session means precede animal differences. Actual native mappings and complete question-specific population remain an intake gate. |
| Animal grouping and uncertainty | All date/block observations share `mname`; bootstrap resamples animals. No cross-day cell tracking is assumed. Singletons remain descriptive. |
| Movement/position matching | Reports all-session common-support standardized selectivity and coverage; this is an explicit prospective estimand on behavioral covariates. Reward coding and unobserved physical behavior remain unmatched. |
| Observable neural endpoints | Implements source-grounded arithmetic-SD d′, source reward-location split/window/gate, area denominators, baseline activity and finite/undefined reporting. No invented reproduction score. |
| Held-out explanation and model residuals | Fits only other animals' before-phase sessions; behavior-only and stimulus-augmented ridge models return every held-out frame residual and phase/mouse losses. Regional amplitude calibration is unresolved. |
| Null controls and malformed inputs | Whole trials shuffle within identical observed movement/position profiles; invalid identities, missing sessions, phase leakage, array mismatch and nonfinite values fail. Constant/undefined statistics withhold the endpoint without dropping neurons or animals. |
| Protocol/resource/reference/replication holds | Policies and source revision are explicit. Authentic reference execution, benchmark admission, protected packets and native resource estimates remain unresolved. Generated engineering controls establish numerical behavior only. |

Primary provenance is pinned in [source-provenance.json](../implementations/initial-evaluator-v1/source-provenance.json). Source code was independently reimplemented from mathematical definitions and has not been vendored. The package README documents prospective changes, interfaces, commands and remaining source/rights gates. Scientific qualification and submission readiness remain unknown; the global registry, task counts and canonical task files are unchanged.

## Detailed interface and scientific policy

## Run

Requires an existing Python 3 and NumPy environment. No installation, dataset access, model service, or network call occurs in the evaluator.

From this package directory:

```sh
python3 -m unittest discover -s tests -v
python3 evaluator.py /absolute/path/packet.json --output /absolute/path/result.json
```

To exercise the entire CLI using the generated engineering fixture:

```sh
PYTHONPATH=tests python3 -c 'import json; from test_evaluator import packet; print(json.dumps(packet()))' > /tmp/neural028-generated-packet.json
python3 evaluator.py /tmp/neural028-generated-packet.json --output /tmp/neural028-generated-result.json
```

The fixture is fabricated engineering input, never authentic neural evidence. The package tests are not scientific replication.

## Input and source mapping

JSON has `task_id: "NEURAL-028"`, `schema_version: 1`, `protocol`, `session_manifest`, and `sessions`. Every declared session must appear once; every animal must have both declared phases. A native operator must freeze the full question-specific cohort and exclusions before evaluating outcomes. This validator checks completeness **relative to the supplied manifest**; it cannot independently prove that the native cohort is complete. Source asset SHA-256 strings are provenance declarations, not recomputed native payload verification.

The protocol requires:

- `source_revision: "ba64ac697f5d9914926baac79399e80707a5f3a6"`, `data_scope: "public_development_only"`, `activity_kind: "calcium_derived_activity"`, and `selection_frozen_before_outcomes: true`.
- `phase_mapping_evidence` and `calibration_evidence`: nonempty descriptions or evidence identifiers. These are attestations requiring later audit, not proof of mapping or cross-session calibration.
- `fit_phases: ["before"]`. All after-phase observations and every session of the held-out mouse are excluded from that mouse's fit.
- Increasing finite `position_edges` and `movement_edges`. Edges use exactly the packet's source units, with half-open bins `[left, right)`. No implicit conversion into milliseconds, centimetres, or physical running speed occurs. Source `ft_move` is a frame-to-frame VR position difference, not physical treadmill speed.
- Optional frozen policies: `selectivity_threshold` (default 0.3), `reward_threshold` (must be 0.3), `ridge_lambda` (default 0.001), `bootstrap_replicates` (100–10000, default 1000), `shuffle_replicates` (10–1000, default 100), and integer `seed` (default 0). Binning, ridge strength and resampling counts are prospective benchmark choices, not author defaults.

Each manifest record has `session_id`, `mname`, `datexp`, `blk`, `regime`, `phase`, `source_asset_sha256`, and `mapping_evidence`. `regime` is `unsup`, `sup`, `naive`, or `grating`; `phase` is `before` or `after`. A mouse cannot span regimes; at least three mice and both `sup` and `unsup` are required. The evaluator pairs **animal-level session summaries** using verified `mname`; it never asserts cross-day cell identity. Test-only naive recordings cannot be relabeled as before/after to satisfy this interface. They require a different, explicitly frozen question-specific profile. No omitted native population is silently treated as included.

Each session contains:

| Field | Shape / interpretation |
| --- | --- |
| `session_id` | Exact manifest key |
| `activity` | Neurons × frames; calcium-derived source activity, not electrode spikes |
| `area_ids` | One source cortical area ID per neuron |
| `trial_id` | One integer per frame; complete contiguous trial IDs starting at zero |
| `stimulus_id` | One source-mapped category 0–6 per frame |
| `position`, `movement` | One finite source-coordinate value per frame |
| `corridor`, `gray` | Boolean frame masks; nonoverlapping |
| `trial_stimulus_id` | One category 0–6 per trial, equal to each frame's label |
| `sound_del_pos` | Source delayed-cue position per trial |
| `position_activity` | Same neuron order × same trial order × exactly 60 position bins |
| `interpolation_evidence` | Nonempty evidence identifier describing source interpolation provenance |

The native mapping is from `spks` to `activity`, `ft_trInd` to `trial_id`, source wall names resolved through `UniqWalls`/`stim_id` to stimulus categories, `ft_Pos` to `position`, `ft_move` to `movement`, `ft_CorrSpc`/`ft_GraySpc` to masks, `WallName` through the same source mapping to trial categories, and `SoundDelPos` to `sound_del_pos`. The operator must establish these mappings from native arrays. **This package does not unpickle NPY objects, truncate mismatched vectors, interpolate raw activity, or claim native loader equivalence.** It checks array shapes, finite data, identities, labels, bins and declared completeness. Boundary frames with missing trial IDs require a declared source-level exclusion audit, not fabricated labels. A later native adapter must verify original filenames, source hashes, neuron order, 60-bin interpolation, trial coordinates and treatment of unsupported frames.

## Numerical estimands

Source-grounded statistics use the pinned mathematical definitions, independently implemented here. Stimulus d′ uses category 2 minus category 0 on original moving corridor frames, with denominator equal to the arithmetic mean of population standard deviations. Reward-location d′ contrasts late versus early category-2 trials from mean interpolated bins 5:40; the cue threshold uses all trials. Reward fractions require nonnegative stimulus d′ and reward d′ ≥ 0.3. Area denominators retain all cells in V1, mHV, lHV or aHV. Category 2 identifies a homologous corridor; it does not imply delivered water in an unsupervised mouse. See `source-provenance.json` for the exact source revision and locations.

The implementation rejects all nonfinite inputs, unlike the source's NaN-aware reductions. It requires two observations per d′ arm. A zero total dispersion is undefined, including equal or unequal constant arms; it is not converted into zero or infinite selectivity. The affected regional fraction and cohort contrast are withheld, with undefined cell/animal counts. Absent regions are explicit and do not shrink denominators. These are prospective strict missingness policies, not claims of bitwise equivalence to author NumPy behavior.

The **matched selectivity** estimand equalizes the joint distribution of frozen movement and position bins. It finds strata with at least two frames in each of the two categories in **every declared session**, then gives each common stratum equal mass within every session/category. Weighted moments produce d′. All sessions and animals remain present; per-session coverage exposes frames outside common support. No overlap means rejection. This changes the estimand to common covariate support. It is transductive matching on evaluator-side behavioral covariates, never held-out neural activity or an agent adaptation permission. Matching does not account for physical running speed, licking, arousal, or other unmeasured behavior. The source reward-location endpoint remains behavior-unmatched and is explicitly held against the full scientific question.

Within each phase, session fractions receive equal weight; animal changes are after minus before. Regime means give animals equal weight. The between-regime contrast is supervised change minus unsupervised change. Confidence intervals resample animals, separately within each regime for the difference. A singleton gets descriptive output and no population interval. All observations of an undefined animal remain reported and hold the complete regime estimate. These percentile bootstrap intervals are prospective; they do not reproduce the article's statistical tests or establish causality.

Baseline activity is the mean of each region's cells and moving gray frames, with its own animal-level change. It is not removed from the separate d′ metric. Whole-trial stimulus nulls permute complete category assignments only among trials with identical moving-corridor movement/position count profiles within the same session. This preserves observed profiles, category counts and temporal samples. Nonexchangeable trials remain fixed and are counted; a session without exchangeable trials is held. Null mean fractions are diagnostics, not calibrated p-values or causal evidence. Cue labels are not shuffled; this is not a reward-coding null.

The explanatory reference is a prospective weighted ridge regression. Its target is the per-frame regional mean activity. Predictors are position and movement, with a second model adding the category-2 indicator. Every held-out animal's complete sessions are excluded from fitting; only before-phase sessions of other animals fit feature normalization and coefficients. Training loss weights animals equally, then sessions equally, then frames equally. The intercept is unpenalized. No hyperparameter selection uses evaluation data. Every scored held-out moving-corridor category-0/2 frame has an output prediction and residual. MSE is in squared input activity units; scaled MSE divides by training target variance and is null when that variance is zero. Test losses average sessions within phase, phases within mouse, then mice. Phase-specific losses and after-minus-before losses remain visible. Cross-session amplitude calibration remains a gate because regional means can change with sampled cells and recording gain. The model does not claim to explain the full reward process.

## Interpretation and remaining gates

There is no favored biological conclusion and no composite leaderboard score. Null, negative and inconclusive contrasts are valid outcomes. Outputs include packet/protocol hashes, complete declared populations, session metrics, animal effects/intervals, null diagnostics, fitted coefficients, training identities, test frame indices and residuals.

Native cohort/session mapping, authentic array alignment and hashes, v1/v2 loader agreement, amplitude calibration, behavior-matched reward analysis, source-reference execution, an independent authentic comparator, protected evaluation, resource measurement and scientific admission remain open. User-supplied evidence strings cannot clear those holds. The paper's figure-specific mouse/session populations must be mapped independently; repeated recordings do not create new mice. This package does not reproduce source coding-direction or cross-validated population-trace figures. Public development remains public development, and scientific qualification is unknown.

Author code is GPL-3.0; it was read as mathematical/interface reference and is not vendored or imported. The primary paper is CC BY 4.0. Source dataset rights and any future source-code redistribution require their own verified records. No neural payload is included.
