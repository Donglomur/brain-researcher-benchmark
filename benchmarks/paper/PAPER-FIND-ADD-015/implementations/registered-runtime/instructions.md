# Optogenetic attenuation: executable numerical reconstruction control

Existing candidate: **PAPER-FIND-ADD-015**. This local control reconstructs processed-trace intermediates for Figures 2N/O, 3C/D/G/H/I, and the deterministic smoothing/integration subset of Figure 4A/B of *Cellular-resolution optogenetics reveals attenuation-by-suppression in visual cortical neurons* (PNAS 2024, doi:10.1073/pnas.2318837121).

The separate primary open-paper research task is described in `paper_task.md`. The executable score below measures a specified numerical reconstruction, not scientific reasoning, whole-paper reproduction, or an improvement over the paper. A valid submission can have any finite error; there is no binary scientific pass floor.

## Inputs and identities

`public_assets.json` locates the exact existing primitive NPZ inputs and the article XML. Mount the named files individually; never mount an authoring directory, the operator package, or a parent directory. `input_schema.json` describes original fields and the flattened object-container translation. There is no pickle in these inputs. Source observations were preserved without truncation or precision reduction. The source optical preprocessing, registration, distance selection and upstream opto-response selection were not rerun.

The eleven Figure 2 files contain 364 cells. The multi-opto file contains three experiment arrays totaling 52 cells. The multi-vis file has six cells with two visual conditions and one shared opto condition. Preserve experiment and cell identity. Seven repeated filename suffixes are only putative animal groups; row-level biological linkage is not established. The paper reports two animals for multi-vis and three for multi-opto, but their exact per-cell mapping is unavailable here.

## Fixed-control calculation

Let `pre` and `post` be the means over windows of `nOptoFr` frames immediately before and after `optoFrStart`, after averaging trials. Trial axis is 1 for Figure 2/multi-opto and 2 for multi-vis. Figure 2 uses:

- `vis = paired_pre`
- `opto = opto_post − opto_pre`
- `paired_raw = paired_post − paired_pre − (vis_post − vis_pre)`
- `paired = max(paired_raw, 0)`
- `delta = paired − opto`
- `delta_unclipped = paired_raw − opto`
- `opto_baseline = opto_pre`
- `delta_baseline_corrected = paired − (opto_post − opto_pre)`

For multi-opto, calculate these fields separately for `lo` and `hi`. `multiopto__visual_state` is the mean of the two paired prewindows. Preserve all three experiment arrays and source order.

For multi-vis, preserve the notebook's different convention: `opto = opto_post` without baseline subtraction; the single opto column broadcasts to two visual conditions. Keep the explicitly baseline-corrected sensitivity as its own field. Require the six timing entries to agree. Visual condition 0 is the source activated configuration and 1 the suppressed configuration.

For the Figure 4 subset, apply LOESS_1D version 2.1.2 to the Figure 2 `vis, delta` vectors with `degree=1`, `frac=0.8`, `rotate=True`, `xnew=None`, `npoints=None`, `sigy=None`; sort the returned x and y using NumPy 2.2.6 default `argsort`. Subtract the minimum smoothed y, cumulatively integrate with the trapezoidal rule and initial zero, then divide by its maximum. Export `x`, `smoothed_delta`, `shifted_delta`, and `normalized_integral`. This is a selected reconstruction dependency, not a proven author version. Its restrictive license prevents us from redistributing the local source. The operator's exact pinned local dependency is required for this compatibility target; independent implementations may incur nonzero curve error. No Ricciardi fit, bootstrap band or deconvolution zero-point claim is requested or scored.

## Submission and score

Write one uncompressed NPZ (`numpy.savez`) with the exact 42 fields, shapes and ordered identities in `submission_schema.json`; all 37 numeric fields must be finite real float32/64, C-order, absolute magnitude below `1e100`. Identity arrays use the declared values/dtypes. No object, complex, compressed, duplicate, extra or missing arrays. Maximum file size is 2,000,000 bytes. No program is imported or executed by the scorer.

Run from the repository root:

```sh
python3 benchmarks/neuroscience/paper-find-add-015/score.py --submission /absolute/submission.npz --output /absolute/new-score-directory
```

The primary metric is equal-experiment Figure 2 delta RMSE (lower is better, units of source ΔF/F percentage points). Separate metrics report low-power, high-power and high-minus-low multi-opto reconstruction; multi-vis cell×condition error; and normalized Figure 4 curve error. Every numerical field also gets RMSE/MAE/max error. These errors are not averaged across scientific capabilities. An exact reference scores zero error, not a reward of one. Invalid files receive no scientific score.

The scorer uses the exact existing offline Docker image with two CPUs, 4 GiB and an 18-second invocation envelope, and requires lazy local artifacts listed in `operator_assets.json`. It validates submitted arrays before decoding the numerical reference. Operator integrity hashing does read reference bytes beforehand; a zero `private_numeric_reference_loads` field means zero numerical NPZ decodes, not zero private filesystem access. It neither verifies candidate program provenance nor proves that answers were derived from the inputs.

## Limits

The artifact set is development material already inspected by the operators. All observations are exposed reconstruction inputs, not a prospective confirmation panel. Current numerical tests use SciPy 1.15.3; the author's historical statistical environment is unpinned. Two published p-values do not match the released-data reconstruction and remain unresolved. Cell-level source significance tests do not establish independent-animal population inference. The article XML omits figure/supplement binary assets; this is not a complete-paper packet or a rights-cleared public release. Local scoring verification, scientific adjudication, blind agent difficulty, improvement evaluation and hosted portability are separate gates.
