# Diagnose the NeuroPictor SSIM environment

`probe.py` makes the exact source SSIM call on two small, generated grayscale patterns in float32 and float64. It distinguishes two-dimensional spatial filtering from last-axis channel filtering, or reports an exception/unclassified/inconsistent result. A package version string never selects the answer. This is an executable environment diagnostic; it does not score NSD reconstructions or resolve which environment produced the paper's table.

The pinned author [metric script](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/eval_metrics.py) first converts RGB images to grayscale, then supplies `multichannel=True` to SSIM. Its [environment file](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/env.yaml) does not pin scikit-image. Consequently, replay requires observing the callable, not assuming the keyword's effect. The [scikit-image 0.19.3 source](https://github.com/scikit-image/scikit-image/blob/v0.19.3/skimage/metrics/_structural_similarity.py) documents the last dimension as independent channels under that legacy keyword. On a two-dimensional grayscale array, that interpretation treats columns as channels. Version 0.19.3 is a documented possible behavior, **not an identified NeuroPictor dependency**. These are browser-observed sources, not newly acquired raw-source hashes.

Use a pre-existing, operator-selected Python environment with NumPy, SciPy and scikit-image:

```sh
python -B benchmarks/paper/PAPER-paper-method-043/implementations/ssim-semantics-probe-v1/probe.py \
  --output /operator/new-neuropictor-ssim-diagnostic.json
```

There are no downloads, installations, model calls, file inputs, participant hooks or authentic images. Output creation is exclusive. The command fingerprints the called wrapper and exposed unwrapped implementation separately, retaining their actual source-file paths and code origins even when decorators copy another function's module/name. The exposed wrapper chain is limited to 16 callables and unique source reads to 2 MiB total; unavailable source is explicit. Hidden closures and imported dependencies are not a complete runtime fingerprint. It also records package versions, exact call arguments, input dtype, observed values, warnings/exceptions and both mathematical reference scores. Missing libraries fail without installation. An unclassified/inconsistent result is retained in the output and exits nonzero. A consistently classified callable exits zero, while historical environment, native metric parity, reproduction and improvement flags remain false.

The references independently evaluate the Gaussian weighted population moments with sigma 1.5, radius 5, data range 1, K1 .01 and K2 .03. Spatial mode uses the valid interior in both axes; channel mode filters/crops only the row axis and averages all columns. Asymmetric textures and horizontal-edge changes prevent constant-image agreement from falsely resolving the axis. Both dtypes must agree on one hypothesis within explicit tolerances. Nonfinite, nonscalar, boolean or mutating callables are rejected. This diagnostic does not certify floating-point bit identity.

The existing `initial-evaluator-v1` and `bounded-panel-v2` retain their explicit `ssim_2d_prospective` endpoint unchanged. No automatic source-policy migration occurs. The complete four-subject/982-stimulus population, eight metrics, original membership/exposure, generation/extraction parity, author reference and separate reproduction/improvement admission requirements remain unresolved as recorded by the task. A recovered historical environment and actual trusted image/extraction comparisons are still needed.

Generated controls compare scalar weighted-moment calculations with an independent SciPy separable-filter implementation, check analytic constant-image values, classify both axes, reject mixed-dtype behavior, preserve exceptions and enforce exclusive reporting. Focused review controls additionally bind distinct decorator/implementation source files, reject wrapper cycles/oversized sources and prevent numeric strings from being accepted as scores. Run them through the project's shared test pool during construction:

```sh
python -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-043/implementations/ssim-semantics-probe-v1/tests -q
```

These tests use generated mathematical inputs and callable stand-ins. They do not execute the installed scikit-image probe or establish a historical/native result. This new component still requires registry/CI enrollment by the sole integrator; no shared enrollment files were changed here.
