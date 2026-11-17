# CellMincer optical ROI extraction

This operator component converts the complete **saved 22-recording optical inventory** into fluorescence traces. It streams TIFF frames and averages each frame over one frozen raw-derived soma mask shared by raw, CellMincer, a matched PMD or N2S comparator, and any candidate movies. It closes an optical input-preparation gap in `initial-evaluator-v1` without assigning new splits or replacing the paper endpoint.

**It has not processed authentic movies.** The saved 22 recordings do not establish the paper's original 26-training/22-evaluation membership. Masks must be supplied: the original seed pixels, thresholds and watershed decisions are unavailable. Mask provenance is an operator declaration plus an evidence hash, not a claim that historical masks or raw-only selection have been independently verified.

## What the executable checks

- Exact coverage of all 22 saved recording IDs and their nine filename-derived cell groups; no recording omission or duplication.
- Raw object name, generation and size against the unchanged frozen population, plus raw content MD5 against cached official GCS metadata. Every movie also requires an operator-frozen SHA-256.
- Identical method coverage and one binary nonempty y,x ROI bound to the raw movie hash. Per-method ROI selection is not supported.
- Exactly 5,000 MINISBLACK grayscale TIFF pages with top-left orientation, matching spatial dimensions, finite numeric pixels, and a stable input file during reading. TIFF decoding uses one worker and one image at a time. RGB images, palette indices, rotated/flipped orientations and alternate stack layouts fail explicitly.
- Complete fluorescence AU traces, source checksums, mask evidence hashes, and optical frame origin. No local input paths are copied into the output.

MD5 checks agreement with the recorded GCS object metadata; it is not a substitute for collision-resistant content identity. SHA-256 freezes the acquired file for subsequent use. The source metadata and hashes alone do not establish acquisition authorization, dataset rights, actual denoiser execution, historical cohort membership, or method competence.

## Input

Use an existing Python environment with NumPy and tifffile. Generated validation passed with Python 3.11.6, NumPy 2.4.6 and tifffile 2024.8.30. The executable performs no dependency installation or source download. The operator JSON has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "task_id": "PAPER-paper-method-030",
  "population_sha256": "SHA256_OF_initial-evaluator-v1/population.json",
  "methods": ["raw", "cellmincer", "n2s", "candidate"],
  "recordings": ["ALL_22_RECORDING_OBJECTS"]
}
```

Each recording object contains `recording_id`, `cell_id`, `shape_yx`, `roi`, and `movies`. Copy identity and raw object fields verbatim from `../initial-evaluator-v1/population.json`. Obtain dimensions from authenticated native metadata; this component does not infer or assert original height/width. The maximum float64 frame representation is 64 MiB, an explicit implementation resource bound, not a scientific selection rule.

`movies` maps every method name to `{"path": "local.tif", "sha256": "..."}`. The `raw` entry additionally contains `source_object`, the exact `raw_tiff` object from the frozen population. Paths are absolute or relative to the panel JSON. They stay in operator storage outside Git. A matching published denoised file does not establish a fresh baseline run.

`roi` contains exactly:

```json
{
  "path": "operator-roi.json",
  "sha256": "SHA256_OF_EXACT_MASK_FILE",
  "source_raw_sha256": "SHA256_OF_RAW_TIFF",
  "selection_policy": "raw_only_frozen_before_method_comparison",
  "evidence_sha256": "SHA256_OF_OPERATOR_RAW_ONLY_SELECTION_RECORD"
}
```

The mask file is a JSON matrix of integer 0/1 or boolean values, with the declared y,x dimensions and at least one selected pixel. This input represents an externally frozen ROI; no automatic segmentation or historically unsupported threshold is supplied.

Run from this implementation directory, using absolute operator paths:

```sh
python extract.py --panel /operator/optical-panel.json --output /operator/optical-traces.json
```

All validation and extraction must finish before output publication. Existing output files are not replaced. The command reads each source twice (checksum pass, then streaming decode); it does not hold a full movie in RAM. Actual 22-recording execution requires the program's native-data resource protocol and is not authorized by the generated test command.

The output is **not directly accepted by the existing mV scorer**. It retains fluorescence arbitrary units and the optical clock. Grader-side electrophysiology channel/units conversion, one-second fluorescence detrending, 51-point cubic EP filtering, peak-based temporal mapping, interpolation, and affine L2 calibration remain separate unresolved preparation steps. The published EP-fitted calibration must not be silently replaced by the existing prospective held-out calibration policy. Original prominence bins, spectral mask, aggregation, authentic baselines, original-finding reproduction, and same-task improvement remain unresolved. Reproduction and improvement are distinct first-class outcomes; this component establishes neither.

## Source and validation scope

The [primary paper, single-neuron trace methods](https://www.nature.com/articles/s44303-024-00055-x) states that raw-derived ROIs are reused for raw and denoised traces. This implementation performs that ROI average; it does not recreate unavailable ROI selection decisions. `source-provenance.json` pins the already retrieved manuscript and raw metadata and identifies the source 5,000-frame, 500-Hz manifest.

Fifteen generated tests passed: hand-computed ROI means, full 5,000-frame extraction, one-mask reuse, independent raw checksum rejection, omitted/duplicated recordings, wrong identities, truncated movies, spatial/color/palette/orientation errors, nonfinite pixels, input mutation, and duplicate JSON keys. They establish software behavior only. Run with `python -m unittest discover -s tests -v` in this directory; the coordinated construction used the reviewed shared test pool. No training, inference, EP target inspection, authentic numerical preparation, or paper-performance result is included.
