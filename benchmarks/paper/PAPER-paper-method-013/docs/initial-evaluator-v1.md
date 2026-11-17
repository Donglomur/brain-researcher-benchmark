# DeepCaImX assembled-output evaluator v1

This package computes ROI detection and fluorescence-trace metrics for every one of the ten recordings in `PAPER-paper-method-013`, compares a candidate with declared baselines, and emits a fixed tile-coordinate plan. It is a complete **post-assembly numerical evaluator**, not a DeepCaImX inference pipeline or a qualified paper reproduction. It performs no model execution, data acquisition, native reconstruction or private-reference admission. Scientific qualification remains unknown.

## Scientific boundary and sources

The immutable task specification is 30,161 bytes, SHA-256 `10ddbdc9848384c6c39c42c55e13e78b4720e2b8649f59c5bddb9f8c03842a12`. [The primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12327232/) defines strict IoU greater than 0.5 and selection of the greatest overlap when several predicted ROIs match a reference ROI. Its trace comparison uses reference neurons detected by **all compared methods**, with Pearson correlation. Its computation timing excludes loading and writing. The evaluator implements these rules; it does not infer an unverified published numeric target.

The [official source revision](https://github.com/KangningZhang/DeepCaImX/tree/305a4827929b2c6e82e44c5c69b2ea9d410e20a4) is fixed, including the [experimental preprocessing notebook](https://github.com/KangningZhang/DeepCaImX/blob/305a4827929b2c6e82e44c5c69b2ea9d410e20a4/Preprocessing%20of%20Experimental%20Samples/Prepro_Exp_Sample.ipynb) and [MATLAB tailor](https://github.com/KangningZhang/DeepCaImX/blob/305a4827929b2c6e82e44c5c69b2ea9d410e20a4/Data%20Tailor/tailor.m). The notebook constructs trace targets from fluorescence preprocessing and manual ROI averaging. They are **author-constructed fluorescence targets, not electrical ground truth**. This package does not redistribute source notebooks, labels, checkpoints or recordings. Source provenance and unresolved semantics are also recorded in `provenance.json`.

## Cohort, coordinates and frames

| Depth (µm) | Allen recording IDs |
| --- | --- |
| 175 | 501271265, 501704220 |
| 275 | 524691284, 531006860 |
| 375 | 607040613, 679353932 |
| 550 | 603516552, 604145810 |
| 625 | 669233895, 671162628 |

All ten recordings are mandatory for every method. Arrays represent the full 488 × 488 field and 5,000 ordered samples under the original annotated window label **18501–23500**. The label is retained without claiming verification of the raw HDF5 source-index mapping. No padded temporal samples enter scoring. Pixel coordinates are zero-based row/column. ROI rows are stable identifiers within each file; predicted row `j` is matched to reference row `i` through footprint overlap, never a trace correlation optimized assignment.

`tile-layout` emits 1,053 tile coordinates: 9 × 9 spatial positions at stride 53, 13 temporal positions of length 400, and explicit valid stops. The final temporal tile has only 200 valid frames. The row axis advances first, consistent with the pinned generic tailor. The output is a geometry plan only. It does not reconstruct source normalization, spatial or temporal ROI merging, trace-zero insertion, or model output decoding.

## Metrics and explicit prospective conventions

For each reference ROI, the largest binary-mask intersection-over-union must be strictly greater than 0.5. A boundary IoU of exactly 0.5 fails. Additional detections are false positives. If two references select the same prediction, scoring stops with an ambiguity hold: the inspected paper does not resolve this collision. It does not substitute a different assignment that could change the paper's best-overlap rule.

An equal maximum among predictions selects the first declared prediction row. This is a **prospective tie rule**, independent of trace values. Submissions acknowledge policy `deepcaimx-assembled-prospective-v1`. No deduplication or threshold tuning occurs in the evaluator. Masks must already be binary, nonempty for each declared ROI, in the full-field coordinate system. Empty prediction sets are valid failures; empty manual-reference sets are rejected.

Precision is TP/(TP+FP), recall is TP/(TP+FN), and F1 is 2TP/(2TP+FP+FN). No predictions yields precision zero. Every recording has a nonempty reference. Reports include each recording, pooled ROI counts and equal-recording macro F1; each depth contains its two recordings. Pooling and macro summaries are explicitly prospective reporting choices and are not asserted to reproduce the paper figure's exact averaging or uncertainty procedure.

For traces, Pearson correlation uses the complete 5,000 samples without shifting, resampling, clipping, smoothing, baseline subtraction or post-hoc normalization fitted to references. Positive scale and offset do not affect the metric. A constant trace has undefined correlation, represented by JSON `null` and explicit counts. Nonfinite inputs fail. Per-method matched-set trace summaries are diagnostic: populations can differ. The primary trace comparison is `all_method_common_reference_trace_endpoint`, the reference-ID intersection detected by **every submitted method**. Each method's per-recording mean is `null` if that intersection is empty or any included correlation is undefined. Paired mean-correlation deltas use this common population. Coverage and per-reference values remain visible; adding a baseline can change this population and therefore the endpoint.

Runtimes are supplied measurements, not measured by the scorer. Every row must declare positive wall seconds, identical hardware/environment identities, and scope `processing_excluding_data_loading_and_writing`. Paired runtime ratios report baseline/candidate. This strict comparability policy is prospective; identity strings do not independently establish equal compute, timing honesty or baseline competence. No uncertainty, significance, speed superiority or scientific pass/fail is inferred.

## Local file interface

Use Python 3 with the already available NumPy runtime. There is no installer. The scorer accepts a separately supplied operator reference JSON and a submission JSON. It never obtains reference arrays from a submission. Each referenced NPZ is bound to SHA-256, uses `allow_pickle=False`, and contains **only**:

- `masks`: binary array `[n_rois, 488, 488]`.
- `traces`: finite numeric array `[n_rois, 5000]` in the same ROI order.

Every reference or method object has the following common fields:

```json
{
  "schema_version": 1,
  "task_id": "PAPER-paper-method-013",
  "frame_labels_inclusive": [18501, 23500],
  "frame_count": 5000,
  "image_shape": [488, 488],
  "coordinate_system": "zero_based_row_column",
  "recordings": [
    {
      "recording_id": "501271265",
      "depth_um": 175,
      "array_file": "501271265.npz",
      "array_sha256": "REPLACE_WITH_ACTUAL_SHA256"
    }
  ]
}
```

The displayed row is illustrative; all ten are required. Paths resolve relative to their owning manifest. Reference JSON additionally requires `reference_kind: "author_constructed_fluorescence"` and a nonempty `source_transformation_receipt` identifying upstream extraction/assembly evidence. This receipt is recorded input context, not proof that the reference is authentic. The operator must maintain the reference outside candidate access in any future controlled evaluation; this package alone is not a sandbox or access broker.

Submission JSON contains `policy_id`, `reference_manifest_sha256`, and a `methods` list. Each method has the common fields above, a unique `method_id`, `role` (`candidate` or `baseline`), and `implementation_identity` naming source revision and checkpoint identity. Exactly one candidate and at least one baseline are required. Each method recording adds:

```json
{
  "runtime": {
    "wall_seconds": 12.5,
    "hardware_id": "OPERATOR_FROZEN_HARDWARE_ID",
    "environment_id": "OPERATOR_FROZEN_ENVIRONMENT_ID",
    "scope": "processing_excluding_data_loading_and_writing"
  }
}
```

The output path must not already exist. The CLI refuses to overwrite a manifest, NPZ, or other existing file. Duplicate JSON keys, incomplete cohorts, wrong depths/windows/shapes, changed hashes, nonbinary/empty masks, nonfinite traces and unpaired runtime contexts fail explicitly.

From the repository root:

```sh
python3 benchmarks/paper/PAPER-paper-method-013/implementations/initial-evaluator-v1/evaluator.py score --reference /operator/reference.json --submission /candidate/submission.json --output /operator/new-report.json
python3 benchmarks/paper/PAPER-paper-method-013/implementations/initial-evaluator-v1/evaluator.py tile-layout --output /operator/new-layout.json
python3 -m unittest discover -s benchmarks/paper/PAPER-paper-method-013/implementations/initial-evaluator-v1/tests -v
```

## Requirement mapping and remaining holds

| Registered requirement | Implemented behavior or remaining gate |
| --- | --- |
| Ten exact manual-ROI recordings, annotated window | Exact roster/depth/window/full-field validation and full-cohort scoring; authentic files and source index mapping held |
| Segmentation precision/recall/F1 | Strict paper threshold and per-reference best match; shared-prediction collision fails closed |
| Calcium-trace comparison | Pearson on cross-method common reference ROIs; imaging-derived identity retained |
| Runtime baseline comparison | Paired full-cohort timings with equal declared context and I/O excluded; native measurement held |
| Patch/tile assembly | Exact geometry plan; normalization, merge identity and authentic assembly held |
| Exact checkpoint/source/environment | Source revision retained; caller-declared implementation identity; checkpoint hash and runnable native environment held |
| Recording/mouse generalization | Recording/depth reports; donor identities and tuning partitions unverified, no generalization claim |
| Protected references, equal access, rights | Separate operator manifest and pins; operational isolation, public exposure and rights admission remain held |

The Allen noncommercial conditions remain distinct from code, checkpoint, ROI and paper redistribution rights. Historical public exposure is retained. Neither this package nor its generated controls establishes blind performance, electrical fidelity, a competent baseline, authentic reproduction, a full model benchmark, or scientific qualification. The original task and historical manifests remain unchanged.
