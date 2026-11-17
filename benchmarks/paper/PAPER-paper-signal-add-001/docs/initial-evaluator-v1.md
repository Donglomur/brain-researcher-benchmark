# Initial PAC evaluator

This package implements the numerical path from locally supplied, exactly pinned 2024 NWB example recordings to load-dependent LFP phase–amplitude coupling (PAC), the author-style single-unit count table and Poisson model comparisons. It also implements a separately labeled prospective patient-level load contrast. No authentic recording, MATLAB execution, published numerical target or scientific qualification has been established. This is a construction deliverable, not a completed reproduction or a qualified task.

The immutable contract is `task.json`, SHA256 `af6f2bf29ed18bc720632f05388a77aab696879bcf83c01ef20872a1e5022aca`. The primary paper is [Daume et al., Nature 2024](https://www.nature.com/articles/s41586-024-07309-z). Source settings derive from [SBCAT-release-NWB commit a25e8cc3](https://github.com/rutishauserlab/SBCAT-release-NWB/tree/a25e8cc3f61630a428f190381745257d4506f148), especially `NWB_samplePAC_LFP.m`, `cfc_tort_comodulogram.m`, `NWB_samplePAC_SU.m`, `plot_PAC_neuron.m`, and the bundled FIR helpers. Exact retrieval URLs, bytes, SHA256s, settings and original public trial-mask values are in [source_contract.json](../implementations/initial-evaluator-v1/source_contract.json). Source reads used the pinned jsDelivr mirror where direct GitHub access failed; the canonical URLs are retained.

## Implemented calculation and evidence boundary

| Contract output | Implemented behavior | Remaining qualification |
|---|---|---|
| Fig2d load1/load3 curves and Tort comodulograms | Raw selected channel → original selected trial IDs → trial-local FIR/Hilbert → phase-bin mean amplitudes → normalized probabilities and MI on the full 7×25 grid; curve averages LF4/6 and HF70:5:140 | Authentic arrays, MATLAB numerical comparison, grading target/tolerance, source timing issues |
| Single-unit PAC model comparisons | Original load3/correct/artifact masks; original binary spike occupancy; theta filtering; seven-cycle Morlet gamma; 20 count rows; full/no-interaction/no-gamma Poisson fits and likelihood ratios | Explicit prospective alignment repair, native fitglme agreement, complete neuron/channel population and selection procedure |
| Patient-level extension | Complete explicit eligible/excluded roster; per-channel paired load3−load1 MI; channel→session→patient averaging; patient bootstrap interval | Eligibility and prospective endpoint approval, full-population extraction, authentic validation and scientific interpretation |

The implementation is executable numerical code, not a schema-only adapter. Python/SciPy expressions implement the inspected source equations without vendoring author implementation files. Generated controls verify entropy, filter coefficients, trial boundaries, wavelet convolution, Poisson likelihoods, patient weighting and local NWB parsing. They provide engineering evidence only.

## Exact examples and source settings

The conservative snapshot is DANDI `000673/0.240118.2135`. Both local file bytes and SHA256 must match source-reported pins before the NWB loader reads arrays. Receipt fields are `dandiset`, `version`, `path`, `asset_id`, `bytes`, `sha256`. The receipt is compared against package pins; a receipt alone is not proof of acquisition authority or scientific provenance.

- LFP: `sub-4/sub-4_ses-1_ecephys+image.nwb`, asset `9a0b7309-0322-4fee-bd81-1f24da41960b`, 1,089,980,788 bytes, SHA256 `3156dc7fc6dd19f402f88743c7d266627ee2ca7ec70cb80511a78e2d6fb015fa`; MATLAB channel row49, Python storage column48. The original `P60cs_RH1_stratTrials.mat` supplies 53 correct artifact-excluded trials for each load; these IDs are preserved and checked against load/accuracy arrays, not reselected.
- Single unit: `sub-26/sub-26_ses-1_ecephys+image.nwb`, asset `199e0072-2fe4-427b-941f-4fb358421b15`, 419,993,012 bytes, SHA256 `30994d69c4cf9dcdeea4d330b1b2a4d164512d5ed75762a55f5a7afd4b646143`; MATLAB channel row33 and unit row20. The original 17 artifact trial IDs are preserved.

The NWB bridge reads sample×channel `acquisition/LFPs/data`, `starting_time` and its `rate`, `general/subject/subject_id`, `general/session_id`, `intervals/trials/{timestamps_Maintenance,loads,response_accuracy}`, and the zero-based ragged `units/spike_times_index`. It validates full local file identity, example identity and index bounds. HDF5 orientation is explicit, not inferred from the larger dimension. No file is downloaded by the evaluator.

LFP epochs use the source inclusive maintenance interval [−0.5,+3] seconds, trim 0.5 seconds at each edge, use18 phase bins, LF2:2:14 with width2Hz and HF30:5:150 with half-width equal to the current LF center. The source filter is a single symmetric FIR with per-trial constant endpoint padding and group-delay compensation, not forward/reverse filtering. Its Hamming parameter is25/46, its transition width is `min(max(low*0.25,2),low,Nyquist-high)`, its even order is `2*ceil(3.3*fs/transition/2)`, and the separately DC-normalized lowpass kernels are subtracted to form the bandpass. Native equivalence is untested.

Tort probabilities normalize the mean amplitude of each phase bin, not total amplitude or occupancy. Exact +π belongs to the final `histc` edge and is excluded, matching inspected source semantics. Empty or zero-amplitude bins produce explicit undefined values; no pseudocount, silent NaN omission or mathematical zero-limit repair is introduced. JSON serializes undefined values as `null` with status fields. Optional nulls independently permute whole amplitude trials for each frequency pair, preserving each trial’s samples, spectrum and task-phase sequence; they do not preserve the original cross-trial pairing. Sample SD (`ddof=1`) determines the z score. The example helper requests zero surrogates; the paper used200. This implementation uses an explicit seed rather than the source's shuffled runtime seed and does not claim identical random permutations.

## Single-unit interpretation and explicit repair

The author helper selects sub26/ses1, correct load3 trials excluding its artifact list, LFP epochs [−1.5,+4] seconds, theta3–7Hz, seven-cycle Morlet frequencies70:5:140Hz supported on [−1,+1] seconds, and1.5-second edge cuts. It z scores each gamma frequency across all selected trial samples using sample SD, averages frequencies, divides at the median, and counts binary spike occupancy in10 theta×2 gamma bins. Theta covariates use left bin edges. This descriptive example preserves the source's all-selected-trial normalization; it is not a held-out predictive estimator.

Full design columns are intercept, cos(theta), sin(theta), high-gamma indicator, cos×high-gamma and sin×high-gamma. The no-interaction comparison removes the final two columns (2df). The no-gamma comparison removes only the gamma main effect while retaining interactions (1df). Counts have no occupancy offset, as in the author helper; occupancy is reported to make that interpretation visible. Maximum likelihood uses a finite-MLE recession-direction check and rejects separated zero-count designs instead of inventing regularization. Reported chi-square p values are the source comparison family, with no population-level FDR or neuron classification inferred.

Two source defects matter. Both NWB helpers construct an N+1-element clock for N LFP samples; this implementation uses the actual N-element clock. In the SU helper, inclusive LFP windows have2201 samples at400Hz while binary spike windows have2200; after source edge cuts these become1001 and1000. The implementation therefore requires explicit `--alignment prospective_right_edge_bins_v1`: drop the first inclusive LFP sample, aligning LFP to the right edge of each original (left,right] spike bin. This is a prospective repair, not an author-verified correction. It accepts only sample-grid maintenance onsets and fails on off-grid onsets pending a frozen cross-clock rule. LFP-only epochs use actual source inclusive comparisons, accept equal-length off-grid windows, and reject unequal or incomplete windows. No resampling or silent trial removal occurs.

The paper’s SU window description [−0.5,+3] differs from the helper’s padded [−1.5,+4], although both aim at the final maintenance interval. This remains disclosed. The full paper classifies PAC neurons using both model comparisons at FDR-adjusted p<0.01 over channel combinations, either load, and chooses among multiple significant channel combinations using full-model R². This package evaluates the single example; it does not implement or claim that full-population classification.

## Prospective patient extension

The extension receives JSON containing `roster` and `records`. Roster rows carry nonempty string `patient`, `session`, `channel`, an explicit Boolean `eligible`, and a reason for each exclusion. Each eligible row must have exactly one matching record with finite `load1_mi` and `load3_mi` arrays of shape7×25 in the source frequency order. Duplicate, missing, extra or undefined eligible records fail. A failed computation requires an explicit roster/protocol decision, not silent deletion.

The prospective endpoint averages paired MI differences over LF4/6 and HF70:5:140. Channels receive equal weight within session, sessions equal weight within patient, and patients equal weight overall. A seeded paired patient bootstrap produces a percentile95% interval; a single patient gets no interval. This endpoint, weighting, eligibility boundary and bootstrap are new proposed choices, motivated by the canonical requirement to treat patients rather than units as independent. They are not historical paper policy or currently registered grading rules. The 44 files/36 participants in archive metadata do not establish44 eligible sessions or36 eligible PAC patients.

## Execution and controls

Use existing Python with NumPy and SciPy; h5py is needed only for local NWB reads and generated loader controls, and pytest only for tests. Development used Python3.11.6, NumPy2.4.6, SciPy1.17.1, h5py3.16.0 and pytest9.1.1. No installation is performed.

From the implementation directory:

```sh
python3 evaluator.py lfp-example /approved/local/example.nwb --receipt /approved/local/receipt.json --output /approved/local/lfp-result.json
python3 evaluator.py su-example /approved/local/example.nwb --receipt /approved/local/receipt.json --alignment prospective_right_edge_bins_v1 --output /approved/local/su-result.json
python3 evaluator.py patient-contrast /approved/local/cohort.json --output /approved/local/cohort-result.json --seed 0
python3 -m pytest -q tests
```

The commands above document the interface, not permission to acquire or analyze authentic recordings in this construction phase. Only bounded generated controls were run. There is no binary reward, score target, performance claim, candidate sandbox, grading tolerance or native reference registration. Public example results remain historically exposed. Access-condition equivalence and protected replay are unresolved.

The original project is BSD3 at its top level, while `pop_eegfiltnew`, `firfilt`, `firws` and `windows` carry GPL-2.0-or-later notices by Andreas Widmann. The entire original dependency closure must not be called BSD-only. Source provenance preserves component notices; no original implementation code or paper text is redistributed in this package. Full-text/stimulus rights, reimplementation reuse qualification and actual exposure remain task-specific review gates. Original MATLAB closure includes MatNWB2.6.0.2, signal operations, statistical functions and bundled helpers; listing that closure does not demonstrate native execution.
