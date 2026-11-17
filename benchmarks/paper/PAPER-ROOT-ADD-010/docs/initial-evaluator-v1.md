# PAPER-ROOT-ADD-010: initial sensor-RSA evaluator

This additive component computes the complete **processed-reference sensor-RSA numerical path**: epoch arrays to run-crossvalidated dissimilarities, then separate symbolic and CORnet-S IT model correlations for all 20 sensor participants. It includes a native clean-epoch export adapter, an explicitly labeled model-CSV importer, both source smoothing branches, and the source temporal cluster-test call. It does not implement raw-BIDS preprocessing or historical shape/oddball decoding. It is therefore a useful construction component, **not a complete or scientifically qualified benchmark**. No authentic data, models, or paper reference results were run or bundled.

The canonical task remains immutable (`task.json` SHA-256 `40e9ad5a0593399399e449e0b005caa1f9e31f84bca32f91c96f8eb1c7da0edd`). The official source snapshot is `133669b577b5ae341cd0842dfb0e7f0af85c0020`; the empirical route remains OpenNeuro **ds006012 v1.0.1**. Sensor analysis uses 20 participants; the paper's 19-person anatomy subset applies to source reconstruction and is not used to shrink this population.

## Source correspondence

| Contract or primary source | Implemented behavior | Limit |
|---|---|---|
| [Pinned sensor RDM calculation](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/MEG/02_rsa/sensor/01_compute_rdms.py) | Reference epochs; MNE virtual-magnetometer conversion; exact 11-shape order; per-run cross-validation; optional Savitzky–Golay 25-sample/order-2 filter | Conversion adapter is not raw preprocessing; native conversion has not been empirically qualified |
| [Pinned sensor model comparison](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/MEG/02_rsa/sensor/02_model_rdms.py) | Separate covariance-weighted correlations, source population-SD SEM; positive temporal clusters with 8192 requested permutations over 0–0.8 s inclusive | No fitted joint coefficients or variance partition is claimed; exact native-version p-value parity remains open |
| [Pinned preprocessing configuration](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/MEG/POGS_MEG_config.py) | Required 301-sample time axis, −0.1 through 1.1 s at 250 Hz | 0.1–40 Hz filtering, Maxwell/SSP processing, event construction and no-baseline provenance must be established upstream |
| Immutable task raw-POGS inventory | Exact subject roster `sub-01`…`sub-20`, 158 runs; only `sub-10` and `sub-11` omit run 08 | File identity does not prove successful preprocessing or complete retained trials |
| [rsatoolbox crossnobis source](https://rsatoolbox.readthedocs.io/en/stable/_modules/rsatoolbox/rdm/calc.html) | Leave-one-run-out pooled-trial means, identity precision, no pattern demeaning, division by channel count; signed distances | Algorithm reference is not the authors' historical dependency/environment pin |
| [rsatoolbox whitened correlation source](https://rsatoolbox.readthedocs.io/en/stable/_modules/rsatoolbox/rdm/compare.html) | Centered upper triangles, covariance `(C C.T)**2` for pairwise shape contrast matrix `C` | Constant/nonfinite vectors fail explicitly; native parity remains to be tested |

`crossnobis` pools **trials**, not run averages, in each training fold. This matters after unequal trial rejection. All observed runs must contain each required shape; missing cells raise an error rather than deleting a shape, pair, subject or run. The cohort entry point enforces the exact run roster, common time axis and sensor mask/order. There is no subset mode. Low-level numerical functions accept smaller shape sets solely for reusable mathematical checks and separately labeled controls.

The fixed shape order is `square, rectangle, isoTrapezoid, parallelogram, losange, kite, rightKite, rustedHinge, hinge, trapezoid, random`. Pair vectors use the strict upper triangle in row-major order (55 entries). Negative crossnobis values remain negative. Model correlations are averaged equally across subjects, not trials. Source z-scoring is algebraically immaterial to centered whitened correlation; the implementation rescales before centering for numerical safety. Source SEM uses population standard deviation (`ddof=0`) divided by √20.

## Inputs and use

Use an existing Python environment with NumPy and SciPy; pytest is needed only for tests and MNE only for native adapters. No dependencies were installed. In the construction environment `/opt/homebrew/bin/python3` has these packages; the bare `python3` in this worktree resolves to another environment without SciPy/pytest.

From this implementation directory, the CLI is:

```text
/opt/homebrew/bin/python3 sensor_rsa.py export-epochs CLEAN+META_EPOCHS.fif sub-01 sub-01.npz
/opt/homebrew/bin/python3 sensor_rsa.py import-models SYMBOLIC.csv CORNET_IT.csv models.json
/opt/homebrew/bin/python3 sensor_rsa.py evaluate packet.json result.json
```

The export adapter requires already-cleaned metadata-bearing epochs, selects `reference` through MNE, requests `as_type("mag")`, and selects magnetometers. Run identity comes from metadata, never trial position. It writes a new NPZ and prints a receipt containing the source FIF hash, output hash, subject and MNE version. Keep that receipt with upstream provenance. The adapter does not certify filtering, event timing or trial retention. Outputs are created exclusively and never overwrite existing files.

Each NPZ has exactly these arrays:

| Field | Shape/type |
|---|---|
| `data` | Finite trial × channel × 301 numeric array |
| `shapes` | Trial-length string array, all 11 labels in every run |
| `runs` | Trial-length string array, zero-padded `01`…`08` matching that subject's inventory |
| `times` | 301 seconds values, −0.1…1.1 inclusive in 0.004 s steps |
| `channel_names` | Unique channel-length string array, common order/mask across subjects |
| `subject` | Scalar string, matching manifest subject |
| `representation` | Scalar string `reference_mne_virtual_magnetometers` |

The representation tag is a declaration, not proof. Only the native adapter performs conversion; manually supplied arrays require independent provenance review. Object/pickled arrays are never loaded.

`packet.json` requires the exact `source_revision` above, `models: {"path": "models.json", "sha256": "..."}`, and `subjects`, an array of 20 distinct entries of the form `{"subject": "sub-01", "path": "sub-01.npz", "sha256": "..."}`. Relative paths resolve against the manifest directory. Every file is hashed before reading. Model JSON contains `shape_order` equal to the fixed order and exactly two entries under `models`, named `symbolic` and `visual_cnn`; each has a symmetric zero-diagonal 11×11 `matrix` and nonempty `source` declaration. The CSV importer reorders both labeled axes and records input hashes. Supplied model source declarations are preserved as **unverified** in reports; a correct hash proves packet integrity, not official model identity.

The pinned model routes are:

- [Symbolic RDM](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/derive_theoretical_RDMs/symbolic/symbolic_sym_diss_mat.csv)
- [CORnet-S IT RDM](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/derive_theoretical_RDMs/CNN/output/diss_mat_model-cornet_s_layer-IT.csv)

Both pinned files were inspected as 11×11 labeled matrices. Model payloads are not bundled. The importer does not generate features or run CORnet-S.

Reports retain per-subject time × pair RDMs, model correlations, group means/SEM, time and pair labels, per-run shape trial counts, file hashes and unresolved gates, for both unsmoothed and smoothed branches. They always state `scientifically_qualified: false`, `full_contract_complete: false` and no established authentic reference agreement. No numeric target or success tolerance is invented.

`cluster_inference(correlations, seed=None)` is a separate optional native MNE adapter for a 20×301×2 correlation array. It retains the source's 8192 requested permutations, one-sided test and inclusive samples 25:226. Other MNE defaults remain native; the source left the seed unspecified. A supplied seed is explicitly recorded as a **prospective reproducibility choice**, not a historical seed. Correlations outside [−1,1], zero subject variance in the tested window and nonfinite native statistics fail explicitly. The function returns actual cluster membership, p-values, statistics and null maxima. `evaluate` does not silently launch permutation inference. The negative generated control exercised this native adapter without any positive cluster or permutation campaign; authentic cluster agreement remains untested.

## Verification and retained gates

Run bounded generated controls from the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 -m pytest -q -p no:cacheprovider benchmarks/paper/PAPER-ROOT-ADD-010/implementations/initial-evaluator-v1/tests
```

Independent hand-derived controls distinguish pooled-trial crossvalidation from equal-run averaging, preserve negative distances, verify channel normalization, compare whitened correlation against a fixed numeric oracle distinct from Pearson, check quadratic smoothing including boundaries, and enforce 20 subjects/158 runs/301 times. Additional controls run the complete cohort numerical path on generated arrays, verify model axis alignment and hashes, reject missing populations/cells/timing, guard extreme-value overflow, and compare native negative-control t statistics with the direct formula. Generated controls are not scientific observations, baseline competence or reproduction evidence.

The [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12795501/) was consulted, but exact historical v2-to-Version-of-Record `.3` figures, latency claims and all model definitions still need reconciliation. Raw BIDS processing, archived decoding, native dependency parity, authentic full-population checks, independent reference agreement, noise-ceiling specification, assessment exposure/protection, tolerances, difficulty and measured native resources remain open. The inspected central sensor comparison has no noise-ceiling computation; this package does not invent one. fMRI and source-space reconstruction remain separate projects.

The previously unknown repository license was inspected at the exact source pin and is [CC0 1.0 Universal](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/LICENSE). That finding does not clear third-party pipeline, dependency, stimulus or pretrained-model rights. This package is an independent implementation of the documented mathematical operations, with no vendored author source or payload. Historical task/rights records are unchanged.
