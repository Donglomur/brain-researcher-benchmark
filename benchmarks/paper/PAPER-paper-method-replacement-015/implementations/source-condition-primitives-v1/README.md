# Spinal CASCADE source-condition producer

This component connects the original 44 spinal MAT files to the existing five-method metric kernel. It creates a **new, explicitly seeded current-source realization**, using the recovered author sampling/noise recipe and paper target smoothing. It does not claim to replay the paper's unknown random realization, recover its optimized alignment, reproduce every figure, or improve a paper result.

The previous `prospective_native_400ms` packet remains a different condition. No prepared targets or predictions from that packet enter this producer. The native MAT field extraction and authenticated source inventory are reused.

One admitted [authentic preparation](AUTHENTIC_PREPARATION.json) has authenticated all 44 neurons and 132 recordings. It produced 116 recording arrays across all 44 neurons; 16 original recordings remain explicitly unavailable because their native noise exceeds the requested level 7. The complete-recording metric bridge consequently remains fail-closed. This was input preparation, with no model execution or scientific prediction score.

## Source and condition

The paper is *Spike Rate Inference from Mouse Spinal Cord Calcium Imaging Data*, [DOI 10.1523/JNEUROSCI.1187-24.2025](https://doi.org/10.1523/JNEUROSCI.1187-24.2025), [PMC12044035](https://pmc.ncbi.nlm.nih.gov/articles/PMC12044035/). The numerical reference is [Cascade](https://github.com/HelmchenLabSoftware/Cascade) revision `1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f`, function `calibrated_ground_truth_artificial_noise` in `cascade2p/utils.py`. Exact source bytes are retained in `upstream/utils.py`; controls extract that single function without importing its unrelated model dependencies. The producer's source-derived numerical component and retained upstream file are distributed under GPLv3; see `LICENSE`.

`NATIVE_INVENTORY.json` authenticates all 44 files (6,225,113 bytes) by SHA256 and Git blob identity. Their established census is 21 glutamatergic + 23 GABAergic neurons, 132 uninterrupted recordings and 434,390 native fluorescence samples. Original native events remain on their 10,000 Hz electrical clock. Nonfinite event placeholders are counted; out-of-recording events are counted rather than clipped into boundary bins. Native time and fluorescence rows must be finite, equally sized real vectors with increasing uniform timestamps. Format tolerance is `rtol=1e-6, atol=1e-10`, inherited from the native parser; it is not a scientific success tolerance.

The default uses the paper Figure 4 d–f nominal parameters: **30 Hz, standardized noise 7 and target Gaussian sigma 50 ms**. The paper's ordinary sampling schedule is available as seven distinct conditions:

| Nominal rate (Hz) | Target Gaussian sigma (seconds) |
|---|---|
| 2.5 | 0.4 |
| 5 | 0.2 |
| 10 | 0.1 |
| 15 | 0.1 |
| 20 | 0.1 |
| 25 | 0.05 |
| 30 | 0.05 |

The full original noise sweep and matched-temporal-precision grids are not recovered. `--noise-level` accepts a separately declared exploratory level; this does not identify it as an original figure condition. The demo's `[2,4,6,8]` is not adopted as a paper noise grid. These conditions are within the existing task; they do not create additional benchmark IDs.

## Numerical contract and deliberate differences

1. Each source recording receives a deterministic MT19937 stream keyed by a frozen bank seed, original path and SHA256, recording ordinal, nominal rate/noise, and single-assessment role. All eight little-endian words of SHA256 initialize NumPy `RandomState`. The author code used a process-global random stream with unknown seed/order. This per-record reset is **new benchmark policy**: changing iteration order, method, or held-neuron membership cannot change its assessment observation. NumPy/SciPy versions and each key digest are recorded.
2. Preserve all 60 author calibration probes, including the zero-scale draw: add Gaussian noise with SD `i/100 * sqrt(native_rate)`, then measure `median(abs(diff(trace))) * 100 / sqrt(native_rate)`. Use the author's `interp1d(test_noise, range(60), kind='linear')`, including its sorting behavior. Do not replace it with a fitted monotonic calibration. Degenerate/interpolation-out-of-range results remain explicit unavailable records.
3. Like current source, reject a recording when its native noise exceeds the requested level. When relative rate difference exceeds 5%, Fourier-resample to `round(native_length * requested_rate/native_rate)` and multiply added-noise SD by `sqrt(requested_rate/native_rate)`. Otherwise retain native length. This can **upsample** low-rate recordings. The paper's textual eligibility sentence appears inconsistent with its intended downsampling; the current-source behavior is named here rather than presented as resolved original-paper policy.
4. Keep the source's event-bin convention: centers are `linspace(original_first_time, original_last_time, output_length)`, with its last edge extension and half-nominal-bin subtraction. These centers are not the discarded SciPy resampling timestamps. Actual center spacing and nominal rate are recorded separately. Spike counts are not silently re-binned to a more convenient grid.
5. Draw one final heteroscedastic Gaussian noise array, scaled by `sqrt(abs(trace+1))/median(sqrt(abs(trace+1)))`. Retain source single-replica 800,000-sample-cap behavior as an explicit unavailability reason. Requested and realized noise levels need not match exactly. No training replica bank or trained model is generated.
6. Smooth target counts **within each original recording**, with the paper sigma schedule, SciPy Gaussian `reflect` boundary and default truncate 4, then multiply by nominal rate to obtain Hz. Keep separate recording arrays, rather than padding/concatenating them across boundaries. Fixed scoring context removes 16 bins at each end below 15 Hz and 32 bins at each end otherwise, matching the source 32/64 symmetric context windows. Short recordings stay present with zero scored bins; a neuron without at least two scored bins cannot receive a complete-condition metric.
7. Alignment is the simultaneous hardware/event clock with **zero additional model-specific shift**. Neither this producer nor the metric bridge chooses shifts or smoothing using assessment targets. The paper's dataset-optimized ±1-second alignment and exact OASIS smoothing choices are not recovered. This fixed-clock condition must not be labeled the paper's optimized alignment.
8. All 44 files and 132 recordings remain in the source census, including four names omitted by the later author `*_mini.mat` glob (one glutamatergic and three GABAergic). Those names are not evidence for the paper's unspecified high-rate inhibitory training exclusion. No such exclusion is inferred. `training_records(bank, held_neuron)` removes **every** recording of that neuron from training; it never mutates the assessment bank.

These differences prevent an assertion of exact historical realization identity. They do not prevent a prospectively frozen, scientifically reviewed current-source comparison of methods on a shared condition. Root/operator adoption of the proposed condition and authentic preparation are recorded separately from code controls.

## Execution and metric connection

Existing Python with NumPy and SciPy is required; generated controls were checked with Python 3.11, NumPy 2.4.6 and SciPy 1.17.1. No TensorFlow, model weights, installation, network access or GPU is required for this component. Generated-only controls:

```sh
python -B -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-015/implementations/source-condition-primitives-v1 -p test_prepare.py -v
```

Within this research program, run that command through the shared bounded test pool described in `PLAN.md`. A separately admitted full-input preparation is:

```sh
python -B benchmarks/paper/PAPER-paper-method-replacement-015/implementations/source-condition-primitives-v1/prepare.py \
  --original /operator/original \
  --output /operator/private/new-bank \
  --bank-seed FROZEN_BEFORE_PREPARATION \
  --rate-hz 30 --noise-level 7
```

`--original` is the parent of `Ground_truth`. It must contain the exact inventory files; the CLI offers no alternate inventory. Output must not already exist. The output directory is mode 0700; NPZ files and `BANK.json` are mode 0600. **This is an operator-only bundle containing targets. Do not expose it to an assessment solver.** Observation-only participant transport is a separate step. All unavailable recordings appear as named rows with explicit reasons; an output bank can be a valid preparation report while still being unscorable as a complete condition.

The in-memory API `build_bank(read_native(original), Condition(30,7), seed)` returns the same arrays and provenance. `score_bank(bank, predictions)` links these original recording boundaries to `original-endpoint-metrics-v1/metrics.py`, pinned by SHA256. Predictions are keyed by every recording ID and then by four required method names (`oasis`, `default_cascade`, `glutamatergic_cascade`, `gabaergic_cascade`), with an optional candidate on every recording. Each entry is `{"values": one_dimensional_real_array, "unit": unit}`. Raw fluorescence is fixed by the bank and cannot be replaced by submitted predictions. OASIS uses `arbitrary`; CASCADE/candidate use `hz` or `expected_spikes_per_bin`. The latter convert using nominal rate. Method values must already meet the declared fixed alignment/smoothing contract; no hidden transformation is fitted by the bridge.

The bridge joins a neuron's recording arrays while retaining each record's fixed mask, and the existing kernel computes separate per-neuron correlations, rate diagnostics and equal-neuron cohort summaries. It rejects missing recordings/methods, partial candidate coverage, nonfinite scored values, unavailable originals, and insufficient whole-neuron support. It does not choose masks from prediction values or substitute pooled correlations. Rate diagnostics remain the existing single-pass diagnostics; they are not relabeled reproduction of the later demo's double-smoothed error/bias calculation. `score_bank` is an operator API, not an untrusted submission sandbox; prediction provenance/model qualification is separately required.

Limits checked before allocation: 8 MiB total pinned input files, 500,000 native samples and 1,000,000 projected output bins across the complete condition. A conservative 32 MiB output-byte check precedes directory creation; cumulative file bytes are also checked while writing. Bounds fail instead of truncating the cohort. Prior native metadata imply at most 716,232 bins for the ordinary 30 Hz condition; this estimate is not a new authentic preparation result.

## What this closes and what remains

This closes the executable native-source → sampled/noised observation + original-condition target → fixed-support five-method metric path, with deterministic bank construction and full-neuron training exclusion. Generated controls include exact vendored-source parity at unchanged, downsampled, upsampled and within-5% rates, complete 44/132 native-format parsing, noise/order invariance, checksum and malformed-input rejection, event-clock/binning checks, private output, and metric-bridge failure controls.

It does **not** supply trained or qualified five-method predictions, the original 80-neuron cortex comparator, historical random realization or paper-era alignment correction, original exact eligibility/exclusion masks, the full noise/matched-precision panels, a frozen reproduction acceptance region, or improvement evidence. Current Cascade includes a 2026 alignment correction; paper-era equivalence is not assumed. Code controls and authentic input preparation alone do not establish that this task or either paper outcome is finished.
