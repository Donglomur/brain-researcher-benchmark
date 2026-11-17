# Initial parameter-table evaluator

This additive package completes the **post-fit parameter-table statistics and grouped prediction-evaluation component** for `PAPER-ROOT-ADD-021`. It accepts the explicit generated CSV, validates its bytes and declared participant roster, applies source QC and temporal smoothing, computes hierarchy-dependent age statistics, and evaluates fully covered participant-held-out predictions. It does not provide the native ECoG spectral extractor, an empirical reference, a frozen benchmark score, or scientific qualification. The canonical task and historical records remain unchanged.

The primary source is [Miles et al., Journal of Neurophysiology](https://doi.org/10.1152/jn.00435.2025), with analysis repository `jtmiles/PAF_INT_neurodev` at `218f87e81d4aa8ac3658467f4a4c85ad1dc4128d`. `provenance.json` records exact source hashes, semantic mappings and unresolved discrepancies. No author source or data is redistributed here; the implementation is independently written from the documented operations.

## Run the component

Use Python 3.10+ and NumPy already present in the environment. No installation or native fitter is performed by these commands. From this implementation directory:

```sh
python3 -B evaluator.py analyze --parameters /approved/generated_parameters.csv --packet /approved/packet.json --output /operator/statistics.json
python3 -B evaluator.py score-heldout --reference /operator/statistics.json --submission /candidate/predictions.json --output /operator/errors.json
python3 -B -m unittest discover -s tests -v
```

The packet explicitly binds one file, avoiding the notebook's temporary filename coupling:

```json
{
  "table_sha256": "SHA256_OF_THE_EXACT_GENERATED_CSV",
  "official_code_commit": "218f87e81d4aa8ac3658467f4a4c85ad1dc4128d",
  "expected_participants": ["ALL_APPROVED_PARTICIPANT_IDS"],
  "assessment_kind": "unqualified_public_parameter_table"
}
```

`generated_engineering_control` is the other permitted assessment kind. The expected roster is operator-owned and must be exact: missing or extra participants fail. The canonical source describes 13 participants; output separately reports whether this count matches, without equating a matching count with authentic identity or full montage coverage. The approved authentic roster and coverage still require payload validation. A SHA-256 verifies byte identity against the supplied packet, not authenticity of that packet or table.

The CSV columns are `ID,age,region,time,fit0,PAF,PAA,INT,offset,knee,exp`. The native unit is a participant/region/time row following the author's regional bipolar preprocessing, **not an independent electrode or participant**. Duplicate `ID,region,time` keys, contradictory ages, unknown regions, infinite values, nonpositive INT, and finite PAF outside the source search range 2–14 Hz fail. Blank/NaN fit parameters are preserved as missing. Age must be positive and time nonnegative. Participant identities are strings. Any additional provenance columns are ignored rather than used to change endpoint eligibility.

Paths are explicit command arguments. The optional Python helper `portable_relative_path(root, relative)` normalizes Windows separators for a relative input name and rejects absolute or escaping paths. There is no automatic search for `params_table_TEST.csv`, no guessed Windows drive mapping and no automatic native notebook execution.

## Source semantics and prospective repairs

The notebook `PAF_INT_stats_figs.ipynb` masks PAF and INT where `abs(fit0) >= 0.2` or fit0 is missing, then computes a centered five-row Gaussian average with standard deviation one, excluding missing values from each local denominator. Groups are participant and region (age is checked consistent within participant). Smoothing can fill previously QC-rejected positions: this package preserves that source behavior and reports original rejection and later fill counts. It does not re-mask after smoothing.

Rows are explicitly sorted by time within participant/region before smoothing. This is a prospective portability/identity repair to the notebook's reliance on table row order and positional reassignment of time/keep. It is not evidence of a historical reference replay. The Gaussian standard deviation is explicitly one, matching the notebook variables; the notebook's positional `.mean(win,std)` call is pandas-version-sensitive and is not executed here. Gaussian width is five rows, not five seconds; interrupted or uneven time sequences are not resampled.

The fixed source mapping is:

| Context | Regions |
|---|---|
| Sensorimotor/unimodal (`S`) | Postcentral_gyrus, Precentral_gyrus, Superior_temporal_gyrus |
| Association (`A`) | Middle_frontal_gyrus, Middle_temporal_gyrus, Supramarginal_gyrus |

For PAF (Hz) and INT (ms), the source outputs include participant-region means, participant-context means, participant omnibus means, interquartile summaries, and OLS against `log2(age in years)`. Omnibus/context summaries pool regional time rows exactly as the source does; they are not equal-region means. Every regression contains one observation per included participant, with eligible and missing-endpoint participants listed. Six region-wise age p-values are adjusted by Benjamini–Hochberg separately for each metric only when all six region models are estimable. If any is unestimable, the six-region family is marked incomplete and adjusted p-values are not computed; the family is never silently reduced. Rank deficiency or insufficient residual degrees of freedom is reported as not estimable, never replaced by a score of zero.

The source interaction `INT ~ C(ctx)*PAF + log2(age)` uses participant-region means, treatment reference `A`, and source nonrobust covariance. It is reproduced as an algebraic statistics component, together with the source separate-context `INT ~ PAF + log2(age)` models and pooled regional Pearson correlation. The source correlation p-value treats region rows as independent; that limitation is labeled in output rather than promoted as participant-level inference. A separately named prospective sensitivity uses participant-clustered CR1 covariance with a `G-1` t reference. This small-cohort approximation is not an approved scientific improvement endpoint.

Two further prospective components are explicitly separated from source outputs:

- A paired within-participant association-minus-sensorimotor contrast, giving each **observed eligible region** equal weight before fitting against log2 age. Missing contexts are listed and excluded from the paired estimand. This handles participant nesting without claiming complete regional coverage or silently replacing the source pooled means.
- Participant-held-out PAF/INT prediction errors. Each fold must partition the exact roster into nonempty disjoint train/test sets; all participants appear in test exactly once. Predictions cover every finite participant-region-metric target in the operator reference, with no omissions, duplicate keys, candidate QC, or nonfinite values. Protected references must match the task/component, string roster, unique participant-region keys, and endpoint domains. Nonrepresentable derived errors or squared errors fail instead of becoming missing scores. Errors are first averaged across regions within participant, then equally across participants. Outputs are participant-macro MAE and square root of participant-macro MSE, alongside a same-region mean estimated only from each fold's training participants. This is a prospective comparison component, not a registered primary score or a numerical success threshold.

Prediction JSON has `folds`, each containing `fold`, `train_participants`, `test_participants`, and `predictions`. Each prediction has `ID`, `region`, `metric` (`PAF` or `INT`), and `prediction`. The reference is operator-owned and must not be passed to candidate fitting. The scorer validates declared partitions and target coverage; it cannot prove training history, prevent prior public-data exposure, or create a sealed assessment. No predictions or model fitting were run on authentic data.

## Native scientific gates retained

The native chain remains incomplete. No archive was acquired, no ECoG processed, no custom FOOOF installed or executed, and no empirical reproduction/result/runtime was established. Dataset `16954184` retains its CC-BY-NC-4.0 terms; the analysis-code license remains unknown. The clinical cross-sectional cohort and electrode coverage constrain developmental interpretation.

Source investigation resolved the current author FOOOF `lorentzian` branch to `858a5f703a05022d33d995dc31d4ba5c2b3cb01b` **prospectively**. The analysis repository does not establish that this was the historical paper dependency. Inspection found these material discrepancies, which must be adjudicated before native execution or numerical equivalence claims:

- The fork's Lorentzian model treats its knee parameter as `log10(f_k)`, while the notebook calls `10**compute_knee_frequency(knee, exponent)` and that helper computes `knee**(1/exponent)`. At knee=2 and exponent=2, the notebook expression gives 6.1320624519 ms; direct model-consistent `1000/(2π·10**2)` gives 1.5915494309 ms. This package consumes supplied INT unchanged; it chooses neither convention as the authentic reference.
- The paper reports alpha search 3–14 Hz whereas the source call uses 2–14 Hz. The helper's sample-width/relative-height behavior also differs from the paper's stated peak-width description. The package's range check follows the inspected table producer and is not paper equivalence.
- The fit notebook references `intfs` before its definition and applies a uniform filter across the whole spectral table, potentially across participant/region boundaries. These require explicit native fixes and review rather than silently executing altered source.

The inspected fit configuration is recorded in provenance, including frequency range 0.5–100 Hz, Lorentzian mode, six maximum peaks and the author bounds. The native spectral loader, fit QC interpretation, full population/montage validation, empirical figure references/tolerances, full-paper endpoint coverage, dependency/resource envelope, protected reference construction, and grouped scientific improvement qualification remain open.

## Validation scope

The package's generated controls test independent Gaussian and Student-t/OLS numerical references; strict QC boundaries and refill behavior; group/order isolation; source versus equal-region weighting; known interaction coefficients; participant-macro errors; train-only baseline behavior; roster/identity/split/target rejection; path containment; and a byte-bound CLI round trip. They establish bounded engineering behavior, not native fit correctness, baseline scientific competence, or authentic reproduction.
