# Empirical spectra and dynamics in critical-init

Task ID: **PAPER-FIND-050**. This is one source-anchored reconstruction task, not 29 benchmarks. It reconstructs selected empirical estimands from Figures 2 and 3 of Pachitariu, Zhong, Gracias, Minisi, Lopez and Stringer (2026), [A critical initialization for biological neural networks](https://doi.org/10.1038/s41586-026-10528-1). It does not ask for a generic network initialization experiment.

**Current delivery is partial source construction.** All 29 source sessions are mapped to versioned official files, but the neural files, actual shape binding and independently established trusted result are absent. The operator must complete those ingredients before an empirical submission can be scored. No fitting, neural analysis or empirical scoring was performed while building this package.

## Candidate interface

The supplied-code condition receives this task, `CONTRACT.json`, `COHORT.json`, `ASSETS.json`, `SUBMISSION_SCHEMA.json`, `protocol.py`, the pinned `author_code/` sources and, when provisioned, the complete 29 original NPZ files plus an operator-prepared `design.json`. The article is linked, not bundled. This is not a completed paper-only versus supplied-code study. The reference solution is code-derived and must never be labeled an independent paper-only solution.

A candidate may implement its own method and writes exactly `result.json`, at most 64 MiB, conforming to the schema and validator. Preserve the source session IDs and Fig2 roster order. The geometry and SHA256 of every actual input are supplied by `design.json`; copy the SHA256 of that exact design file into `design_sha256`. Do not supply a candidate-generated geometry. Each session requires:

| Field | Output |
|---|---|
| `covariance` | First 500 descending ordinary covariance eigenvalues |
| `svca2` | First 500 descending, unnormalized cross-neuron singular values |
| `svca` | First 500 signed cross-neuron/cross-time held-out estimates, in source basis order |
| `svca_variance` | Corresponding first 500 projection-variance estimates |
| `pc_acg` | Raw cross-neuron PC correlations at lags 0–99: first 400 PCs for V1/sensorimotor/PPC, first 100 for CA1/ephys |
| `dmd` | Every source DMD eigenvalue, up to 1,000, as `[real, imaginary]`; no stability filtering |

All source neurons and all recording frames are used subject only to the source preprocessing below. Outputting first 500 ranks or the plotted PC ranges does not authorize cropping the input population, time interval or cohort. Missing cases, changed support, duplicate IDs, nonfinite values, unknown keys and undefined zero-mass SVCA2 normalization are invalid. Actual data that cannot support the declared ranks must block provisioning; do not silently change the task. No successful empirical geometry has yet been observed here.

## Exact estimands

The authoritative code revision is `2c15edf4e770165fc3962dcc3920c8bcaf555bed`. `private/SOURCE_MAP.md` maps entry points; `private/reference.py` is an unexecuted, source-derived core driver.

**Spectra (Fig2):** calcium `sp` is cropped by `tstart` when present; every neuron is centered and divided by its population standard deviation without epsilon. Ephys is binned at 22 Hz by rounded timestamps after subtracting the first time; the source uses uint8 CSR counts, then float32 dense activity and a >0.01 Hz filter. The literal uint8 accumulation may wrap at extreme per-bin counts; it is retained here, not silently repaired. Coordinates use `iprobe*0` as x for ephys. Neuron order is permuted with NumPy seed0. Ordinary covariance is `X Xᵀ / T`. SVCA2 uses the source checkerboard neuron split (25 µm calcium, 40 µm ephys) and **does not divide its cross-product by T**. SVCA additionally learns on source-defined temporal chunks and evaluates signed covariance on other chunks. Do not substitute nonnegative ordinary PCA values or claim this within-recording split is an animal holdout.

**Dynamics (Fig3):** use the full calcium `sp`, without the Fig2 `tstart` crop, and the source epsilon-0.001 zscore. Ephys preprocessing is otherwise the same. DMD uses lag5 frames (5/22 s), top1,000 basis dimensions when needed, ridge0.01 for calcium and0.1 for ephys, and the literal source chunk/weighting behavior. PC correlations use source alternating blocks, a 25 µm checkerboard for both modalities and circular FFT correlations. Ephys uses the source 41-tap Gaussian (sigma2) for basis estimation and raw-data basis reordering. Preserve raw lag0 values; plotting normalizations are not these outputs. Do not replace the circular correlation with an unannounced linear estimator or repair DMD tail handling under the reproduction label.

The retained empirical outputs omit the simulated matrices, 500-step shuffle controls, neuron/time subsampling and behavioral-state sweeps, Fig4 connectivity inference, Fig5 working memory, supplementary external datasets and figure rendering. Thus this is a **bounded empirical-core reconstruction**, not a full-paper or full-figure reproduction.

## Scoring and scientific units

The primary continuous error is the mean over the 29 session-specific MAEs between the first500 SVCA2 values normalized by their own sum. It measures spectral shape; lower is better. Raw per-field MAE/max error retain scale information, so rescaling an entire spectrum can leave the primary shape score unchanged while producing a nonzero raw error. Raw PC-correlation errors and one-to-one minimum-total-distance matching of complex DMD eigenvalues are separate metrics. DMD matching preserves multiplicity and does not compare arbitrary eigenvector gauges. There is no invented composite of incompatible units and no binary scientific tolerance.

The grader also derives weighted log-absolute-spectrum slopes on ranks11–500, following the code, and rotations per tenfold attenuation for modes with magnitude>0.25 and nonnegative imaginary part. Negative signed SVCA values are retained. Zero values in a slope fit produce an explicit undefined diagnostic. Unit-magnitude DMD modes produce an explicit undefined rotation count; unstable modes are retained and counted. Neither condition is silently filtered or replaced with epsilon. These descriptive diagnostics are not a mechanism test.

The 26 calcium sessions map to 25 distinct mouse-name strings; the source repeats `FX43` across V1 and PPC. The primary reporting summary says 29 sessions from29 mice. This identity discrepancy remains unresolved. The package therefore does not claim that the 29 sessions are 29 confirmed independent biological units. Ephys has three named mice and reuses the Stringer2019 eight-probe recordings with Kilosort4 processing; the 2024–25 calcium recordings are a newer cohort. Region-specific errors are reported separately. Session averaging here is a reconstruction convention, not an inferential sample-size declaration.

The grader compares artifacts only. It does not prove that a submitted program ran, establish unseen generalization, validate a causal criticality mechanism or authorize runtime/benchmark admission. Protected reference files and operator sources must never be supplied to a candidate. A later program-execution wrapper may use existing isolation; none is added by this package.

## Rights and provenance

Cite the Nature paper and the [versioned Figshare data](https://doi.org/10.25378/janelia.27854448.v1). The data metadata declares [CC BY-NC4.0](https://creativecommons.org/licenses/by-nc/4.0/). Ephys also requires the original Stringer et al. [Science article](https://doi.org/10.1126/science.aav7893) and [eight-probe dataset](https://doi.org/10.25378/janelia.7739750). Supplied author code retains its GPLv3 LICENSE. No raw data are bundled; public redistribution and a built numerical environment have not been established.
