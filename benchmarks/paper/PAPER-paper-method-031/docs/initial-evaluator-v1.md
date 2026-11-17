# Initial FAST measurement evaluator

This package computes a usable, **prospective** comparison from complete, explicitly exported movie arrays: fixed-ROI fluorescence traces, ΔF/F, zero-lag temporal agreement, event timing/amplitude diagnostics, synthetic-only image error, and declared end-to-end latency. It compares the exact pinned FAST method, one or more candidates, and an internal raw-input baseline on the same frozen panel. It does not train or run FAST, ingest the original TIFF/ZIP payloads, certify a reference, award a scalar reward, or complete the scientific benchmark.

Canonical task: `PAPER-paper-method-031`; immutable task SHA256 `1b43d761bbefff82386fa2a5ae7f03a6a83dc3a62c38abbbfd63b520cdd67b90`. Official FAST commit: `6f92663f7a36589507cac57c8d24cfd8adbce7b1`. The package is a new independent implementation of measurement formulas and input checks; no author code is copied or vendored.

## Scientific basis and prospective choices

The [paper](https://doi.org/10.1038/s41467-025-64681-8), also available as [PMC12552699](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12552699/fullTextXML), uses Pearson correlation of fluorescence ΔF/F traces with synthetic clean traces or synchronized electrophysiology (Fig. 3). Synthetic fast dynamics include 2/4/6/8 ms spikes. The real single-cell voltage recording is 1000 Hz and has patch-clamp measurements; the neuronal calcium collection is 8 Hz. These are source facts, not newly reproduced results.

The frozen canonical scope includes both real single-cell voltage and neuronal calcium. This evaluator accepts either collection and a separately labeled synthetic control, but completeness of any supplied panel is only completeness against its declared roster. It does not prove that a roster contains every original recording, pixel, neuron, or required collection. A panel that supplies only synthetic controls never satisfies the real-data scope. The native archive/schema and full-population checks remain holds.

The paper does not establish an unambiguous ΔF/F baseline rule, SNR estimator, PSNR range, grading tolerance, or protected benchmark split in the inspected main text/source. The current recipe therefore explicitly chooses:

- Fixed binary ROI masks and baseline/event frame identities frozen before predictions; no output-specific mask, baseline-window search, lag, sign, gain, smoothing, or reference calibration. Within each ROI, `F` is the spatial mean; `F0` is the mean over the same declared baseline frame indices for every method; ΔF/F is `(F-F0)/F0`. Each method's numerical `F0` is reported. Nonpositive baselines fail rather than receiving an epsilon. This recipe is not claimed to be the exact paper preprocessing.
- Zero-lag Pearson correlation on every original frame. A constant trace returns JSON `null`, and undefined correlations are never removed to improve an aggregate. Electrophysiology is only a temporal comparator; it is never clean fluorescence. Its prealigned array must have one column per fixed ROI and the operator must supply synchronization provenance. The code does not infer or optimize synchronization.
- An explicitly named **event-to-baseline-standard-deviation proxy**: oriented event-window maximum ΔF/F divided by baseline sample standard deviation. Zero baseline variance returns `null`. This is a prospective signal/noise diagnostic; denoiser smoothing can improve it while destroying spikes. The report always retains traces, event peaks, and timing. Synthetic reference comparisons additionally report event peak ΔF/F error; ephys comparisons do not compare unlike amplitude units. Event polarity is declared for fluorescence and, separately, ephys.
- Full movie MSE and `20 log10(data_range) - 10 log10(MSE)` only when `kind=synthetic` and a clean array is supplied. The range is fixed in the panel; it is not inferred independently per method. An exact match has `psnr_db=null` and `psnr_status=positive_infinity_exact_match`, preserving standard JSON without imposing a finite cap. Real records reject clean-image targets and data ranges, including raw or smoothed pseudo-targets. No SSIM implementation is claimed.
- Equal ROI means within recording, equal recording means within biological/recording group, and equal group means separately for each data-kind/reference stratum. Pixels and frames are not biological replicates. No pooled real/synthetic score, confidence interval, significance test, reproduction tolerance, or improvement success is reported.

The recipe is **prospective recording/group-disjoint improvement**, not native transductive reproduction. Panel groups may appear in only one of train/validation/test. Each method declares fit groups, which must belong only to the panel's training split, and disclaims test-stack adaptation and protected-reference exposure. Declarations are not independently attested. Native FAST's self-supervised same-stack fitting is a legitimate separate source route; it is outside this recipe and must not be described as author leakage merely because this stricter prospective path rejects it. Externally pretrained provenance also requires review.

## Interface

Runtime: Python 3 with NumPy. No network calls, installation, GPU, model load, or dataset download occurs. Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/paper/PAPER-paper-method-031/implementations/initial-evaluator-v1/evaluate.py \
  --panel /absolute/path/frozen-panel.json \
  --panel-sha256 SHA256_OF_FROZEN_PANEL \
  --submissions /absolute/path/submissions.json \
  --output /absolute/path/report.json
```

`--panel-sha256` must come from the operator's independent freeze process. The evaluator checks bytes but cannot establish that a panel was frozen before predictions. Array descriptors are `{"path":"relative-to-own-manifest.npy","sha256":"64-hex-digest"}`. Only numeric, finite, non-pickled `.npy` arrays are accepted. The source-to-array export must be done and audited separately; source checksum strings and provenance are declarations, not acquisition evidence. Original source hashes retain their algorithms and must not be relabeled SHA256.

A panel has `task_id`, `recipe: "prospective-v1"`, `freeze_provenance`, and a nonempty `records` list. Every record has:

| Field | Meaning |
| --- | --- |
| `id`, `group_id`, `collection_id`, `split` | Unique recording identity; highest shared biological/recording grouping; source collection; train/validation/test assignment |
| `kind` | `real_voltage`, `real_calcium`, or `synthetic` |
| `source_asset`, `source_checksum`, `export_provenance`, `roi_provenance` | Declared source identity/checksum algorithm, export/alignment procedure, and mask origin |
| `original_frame_count`, `frame_ids` | Full original frame count (at least 3); exactly `[0,...,count-1]`, with no crop or reordered declaration |
| `frame_rate_hz`, `exposure_ms` | Positive source sampling and exposure; exposure cannot exceed frame interval |
| `raw`, `rois` | Array descriptors: raw `(time,y,x)` and binary masks `(roi,y,x)`; every ROI nonempty, no identical duplicate masks |
| `baseline_frames`, `event_windows`, `event_polarity` | At least two unique baseline frame indices; explicit disjoint-from-baseline `[start,stop)` windows (may be empty); ±1 fluorescence event orientation |
| `clean`, `data_range` | Required only for synthetic data; clean movie must match raw shape exactly |
| `electrophysiology`, `synchronization_provenance`, `reference_event_polarity` | Optional real-voltage-only aligned `(time,roi)` comparator plus alignment provenance and ±1 reference event orientation |

Overlapping nonidentical ROI masks are allowed and reported at the recording/group aggregation level. They are never treated as independent biological replicates. Inactive train/validation records retain full metadata but their arrays are not opened by the scoring path. Inclusion is operator-owned; making an archive export match a panel does not establish native inclusion validity.

Submissions have `task_id` and `methods`. At least one `candidate` and exactly one `official_fast` method with the pinned `code_commit` are required. Other methods may have role `matched_baseline`. Each has a unique `id` other than `raw`, `implementation_provenance`, `fit_provenance`, `fit_group_ids` (possibly empty for a declared frozen model), `raw_test_adaptation: false`, `protected_reference_exposure: false`, `temporal_window_frames`, `stride_frames`, and `future_context_frames`. These preserve declared temporal context and do not certify native settings. Every method's `predictions` list contains every test recording exactly once, with `record_id`, matching `frame_ids`, `output` array descriptor and `timing` receipt. Output shape must equal the raw movie; no missing frames, hidden spatial crop, or mirrored inference tail is admitted. A false frame declaration or transformed source array cannot be detected from shape alone; native export and attempt audit remain required.

A timing receipt has:

```json
{
  "boundary": "input_available_through_output_available_including_io_transfers_preprocess_inference_postprocess",
  "hardware": "exact device and host description",
  "resource_budget_id": "operator-frozen comparable budget",
  "measurement_provenance": "independent receipt/clock origin",
  "clock": "monotonic_seconds",
  "start_s": 0.0,
  "end_s": 1.0,
  "input_available_s": [0.0, 0.1, 0.2],
  "output_available_s": [0.2, 0.3, 0.4]
}
```

The example has three frames; actual lists must cover every frame. Start/end include required I/O, transfers, preprocessing, model work, and output availability; original acquisition-ready times preserve buffering/context delay. The evaluator rejects impossible times, nonchronological input, partial timelines and output before declared future context availability. It computes throughput across the entire interval and per-frame median/p95/max latency. Hardware and budget identifiers must match across methods within a recording. These are declared receipts, not measured by this evaluator. Matching string identifiers do not establish compute equivalence; clock synchronization, queue policy, warmup, native temporal context, training costs, motion correction, and downstream pipeline boundaries still require independent audit. Throughput alone never triggers a real-time pass.

The JSON report includes all denoised ROI traces and baselines, individual recording/method measures, stratified grouped temporal agreement, the panel/submission byte hashes, source identities, explicit `scientific: false`, `full_contract_complete: false`, no binary reward, and preserved holds. No native run or outcome is fabricated.

## Provenance and preserved discrepancies

[provenance.json](../implementations/initial-evaluator-v1/provenance.json) maps source requirements to implemented behavior and keeps inspected primary-source pins. [Pinned author inference](https://raw.githubusercontent.com/FDU-donglab/FAST/6f92663f7a36589507cac57c8d24cfd8adbce7b1/test.py) and [dataset source](https://raw.githubusercontent.com/FDU-donglab/FAST/6f92663f7a36589507cac57c8d24cfd8adbce7b1/datasets/dataset.py) append a reversed tail, operate on temporal windows, and save clipped uint16 output. Native ingestion must check the original frame count after that tail and full file coverage. The author path's sequential overlap averaging and augmented-stack mean are not silently replaced by a new inference implementation here. Paper versus code weight decay (`1e-4` versus `0.9`) and spatial mask descriptions also require route-specific resolution before native reproduction.

The [deposit README](https://zenodo.org/api/records/15872025/files/README.md/content) says reused real files 1/3/4 remain under their original source licenses; only original synthetic/astrocyte files 2/5 are explicitly CC BY 4.0 there. Deposit-level metadata must not clear all real recordings. Official code is GPL-3.0; weights, data, and exports require their own terms. This new measurement code does not redistribute those assets.

Authentic source-array ingestion, complete real calcium and voltage inclusion, protected independent references, exact figure normalizations/tolerances, native FAST/matched baseline results, measured end-to-end resources, broader five-collection endpoints, and scientific/improvement qualification all remain open. This additive package does not change canonical task history or registration status.

## Engineering verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-031/implementations/initial-evaluator-v1/tests -v
```

Tests use small generated arrays and declared synthetic timing, never authentic data or model inference. Controls cover analytically known MSE/PSNR, exact-match infinity, scale-invariant correlation, one-frame shifts, constant predictions, temporal smoothing that loses a narrow event, signed spikes, masks/baselines, real-target rejection, full coverage and frame identity, grouped leakage, future-context timing, wrong hardware, and CLI content pins. Passing these checks establishes engineering behavior only.
