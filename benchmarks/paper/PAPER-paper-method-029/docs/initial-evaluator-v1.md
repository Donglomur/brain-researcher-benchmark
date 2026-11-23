# Initial neural conversion evaluator

This package implements the scoped Deeprecon neural-conversion evaluation for five subjects, all 20 directed nonself source–target pairs, both content-loss and brain-loss converters, and the six source ROIs. It performs actual converter inference and trial-level correlation calculations, joins pinned noise-ceiling tables, and produces raw and normalized per-feature/per-pair summaries. It does not refit converters. Scientific qualification remains **unknown**: no authentic fMRI, weights, decoder assets or ceiling artifacts were acquired or run.

The immutable contract remains `task.json` (SHA256 `8dd236212e98ac90d995fe5d524c16a7240f551d0c3f0104f3b9a50d30bece91`). Source semantics come from [Wang et al. (2025)](https://www.nature.com/articles/s43588-025-00826-5) and [official revision c264167](https://github.com/KamitaniLab/InterSiteNeuralCodeConversion/tree/c264167c2b5a0fa71709a58ae5b50a042f6d7a79). `SOURCE_PROVENANCE.json` records exact URLs and content hashes. The upstream MIT notice is included; neural-input, feature, decoder, weight and stimulus rights remain separate.

## What is calculated

Public mode requires the five `sub01`–`sub05` subjects, 50 NaturalImageTest stimulus identities, 24 repeats per image, and all 40 pair/method combinations. Each subject declares the same 1,200 training stimulus identities and five training repeats. These identities must be disjoint from the test roster. These declarations validate packet consistency; they do not prove the actual 6,000-trial fitting population or normalization lineage.

For each target ROI (`VC`, `V1`, `V2`, `V3`, `V4`, `HVC`), pattern correlation is the arithmetic mean of the **24 × 24 individual repeat-pair Pearson correlations across voxels**, separately for each image. It is not the correlation between averaged responses. Target normalization is method-specific: the content converter uses target decoder `fc6` normalization; the brain converter uses its fitted `y_mean`/`y_norm`. Exporting one common normalization without proof is not valid.

Profile correlation groups images by sorted image index, retains within-image trial order, and computes each voxel's mean correlation over every source–target repeat pairing across images. The source scripts denormalize profile predictions; the implementation uses the mathematically equivalent positive per-voxel affine invariance of Pearson correlation. Its independent source-function controls check both axes.

ROIs preserve target BData global-column order mapped into VC, including overlapping voxels. `V4` maps to `ROI_hV4`. Converters receive individual trials without repeat averaging. Brain-loss inference applies the source affine matrix to normalized inputs with an appended bias coordinate. Content-loss inference reproduces the pinned three-Linear topology with two per-trial InstanceNorm/LeakyReLU stages (hidden width `input_voxels // 2`, epsilon `1e-5`, slope `.2`). Exported weights and training statistics are never fitted to test data.

When both author-style ceiling and threshold CSV pairs are supplied, exact `(target, ROI, axis, feature)` coverage is required. Rows survive only when `ceiling > Threshold 1`; retained raw correlations are divided by ceiling and clipped to `[-1,1]` before the within-pair image/voxel average. Missing tables leave normalized results held. Missing, duplicate, nonfinite, mismatched or invalid ceiling joins fail. The source's silent `nan_to_num` conversion is deliberately not inherited: undefined correlations remain null, and eligible undefined rows make their pair mean null. Excluded rows and counts remain visible.

Observed equal-pair means and signed `content_minus_brain` differences are reported without an assumed favorable sign. The paper describes neural conversion correlations as comparable or slightly lower with content loss; improved decoded features/reconstructions are distinct endpoints. Optional `--source-bootstrap` reproduces the figure's seed-42, 1,000-replicate sampling of 20 accepted nonself source–target pairs and reports its bootstrap mean separately from the observed mean. Sampling preserves the author's first-occurrence orders after the sorted `Source`/`Target` groupby: sources `sub01` through `sub05`, targets `sub02`, `sub03`, `sub04`, `sub05`, `sub01`. The different target order matters for the finite seed-42 sample. Earlier evaluator versions sampled both axes in source order; their bootstrap summaries do not exactly replay the author sampler. The correction leaves observed pair means and the 20-pair sampling unit unchanged. This is not an independent-subject confidence interval. Leave-one-subject-out paired differences are explicitly prospective descriptive sensitivity, not validated improvement inference.

## Operator-prepared input interface

The evaluator accepts only hash-bound, trusted operator-prepared NPZ arrays (`allow_pickle=False`) and JSON. It does not load arbitrary candidate Python, torch pickle files or downloaded models. The JSON manifest has:

- `schema_version: 1`, `task_id: "PAPER-paper-method-029"`, `source_commit: "c264167c2b5a0fa71709a58ae5b50a042f6d7a79"`.
- `population: "public_deeprecon"` or `"generated_engineering_control"`; generated mode permits smaller image/repeat counts and is always labeled as generated. Neither mode grants scientific admission.
- `training_regime: "shared_stimulus_fig2"`, unique numeric `stimulus_ids`, and integer `repeat_count`. Nonshared-category Supplementary Fig. 7, site transfer, artificial images, THINGS, NSD, auditory conversion and image synthesis remain outside this deliverable.
- Five `subjects` entries: `id`, `file: {"path": "relative-or-absolute.npz", "sha256": "..."}`, `training_stimulus_ids`, and, in public mode, `training_repeat_count: 5`.
- Forty `models` entries: `source`, `target`, `method` (`brain_loss` or `content_loss`), a pinned `file`, `source_fit_stimulus_ids` and `target_fit_stimulus_ids`. Fit rosters include training data used for decoder/normalization fitting and must match the corresponding subject training identities.
- Optional `noise_ceilings`: exactly two entries with `axis` (`pattern`, `profile`), pinned `ceiling_file`, and pinned `threshold_file`.

Subject NPZ keys are `x` (trials × VC voxels), numeric `labels`, unique string `trial_ids`, unique string `voxel_ids`, and ascending integer vectors `roi_VC`, `roi_V1`, `roi_V2`, `roi_V3`, `roi_V4`, `roi_HVC`. VC must cover all selected voxels; every ROI needs at least two voxels. No averaging occurs during ingestion.

Every model NPZ contains exact ordered `source_voxel_ids` and `target_voxel_ids`, plus source `x_mean`/`x_norm` and target `y_mean`/`y_norm` vectors. Brain models contain `M` with shape `(source_voxels + 1, target_voxels)`. Content models contain `W0`, `b0`, `W1`, `b1`, `W2`, `b2`; PyTorch Linear weights are exported unchanged in `(out,in)` order from `model.0`, `model.3`, `model.6`. For content, `y_mean`/`y_norm` are the target decoder `fc6` **x** normalization, renamed for this interface; they are not DNN feature y statistics. Scaling must be finite and strictly positive. Exports require separately reviewed source artifact, preprocessing, native dtype and normalization provenance; local SHA256 integrity is not authenticated provenance.

Ceiling CSVs require `Subject`, `ROI`, `Correlation`, and `Image index` for pattern or ROI-local `Vox_idx` for profile. Threshold CSVs use the same key columns and `Threshold 1`. Subject spelling `sub-01` is canonicalized to `sub01` before a duplicate-checked join. Overlapping voxels retain separate ROI-local identities. The inspected code did not establish ceiling-generation implementation or authenticate those artifacts; supplying tables enables the computation without closing that gate.

## Commands and controls

With an existing Python/NumPy environment, from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-paper-method-029/implementations/initial-evaluator-v1/tests -v
python3 benchmarks/paper/PAPER-paper-method-029/implementations/initial-evaluator-v1/ncc_evaluator.py evaluate /absolute/path/manifest.json --output /absolute/path/result.json
```

The unit tests construct a complete five-subject, 20-pair generated control in temporary files; they cover scalar independent Pearson/inference oracles, the repeat-mean counterexample, both correlation axes, complete coverage, leakage, file tampering, voxel identity/order, public-population dimensions, source bootstrap labeling, the exact 1,000-draw author sampling order, complete bootstrap pair coverage and strict ceiling joins. `tests.test_evaluator.build_control(directory)` is an executable, bounded input example, explicitly labeled generated engineering data.

The optional trusted H5 adapter hashes the supplied file before invoking an already-installed `bdpy.BData`, selecting the exact source BData keys:

```sh
python3 benchmarks/paper/PAPER-paper-method-029/implementations/initial-evaluator-v1/ncc_evaluator.py prepare-bdata /absolute/path/NaturalImageTest.h5 --sha256 EXPECTED_SHA256 --output /absolute/path/subject.npz
```

No dependencies are installed. BData/H5 native ingestion was not executed here; upstream `env.yaml` does not pin bdpy, and native schema/version validation remains held. A generated source-topology comparison can validate arithmetic without establishing authentic pretrained-model parity, fit quality or task difficulty. Float64 evaluator arithmetic and source PyTorch float32 behavior must remain part of later native tolerance qualification.

## Remaining qualification

The package supplies complete source-stage numerical behavior and strict coverage checks. It does not supply the authentic acquisition/selection receipts, verified neural/features/decoder/converter bundle, full training/repetition provenance, independently accepted ceiling/threshold artifacts, figure-specific reference outputs/tolerances, matched refitting/resource envelopes, rights clearance or a protected improvement set. Public test images and paper results are exposed development material. No binary reward, scientific success, whole-paper reproduction, model competence or code-access causal comparison is registered by this work.
