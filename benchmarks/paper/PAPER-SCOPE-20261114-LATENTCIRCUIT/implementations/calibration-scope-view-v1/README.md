# Exact historical calibration-scope view

The retained population index labels the R profile's validation-fitted calibration
as `training_only`. Its separate mandatory correction record preserves that defect
and defines the effective value `validation_fitted_reconstruction_only` for both
animals. This component applies that existing correction to an independent in-memory
view. It does not rewrite historical metadata or inspect any referenced neural array.

`scope_view.effective_index(index_bytes, correction_bytes)` verifies the complete
byte identity of **both** existing records before JSON parsing, requires the exact
two original paths and expected values, and changes only those two scope strings.
The R profile remains ineligible for protected prediction. The I profile, common
training calibration, training PCA and error transforms remain unchanged. A different
source version is refused; the public API has no caller-provided hash override.

The exact inputs are the existing `POPULATION_OUTPUT_INDEX.json` (135382 bytes,
SHA256 `9f3ca6d958b673671143371ded10f617e768dd384b9788f22fef5249e723f891`)
and `EFFECTIVE_CALIBRATION_SCOPE_V1.json` (3115 bytes,
SHA256 `96ed0f533e651d3ccf4cef77e9ef7fee1cf80dc19432232a37f7f391db693588`).
They remain owner-side; private paths and payloads are not vendored here.

An operator may print a path-free summary with:

```sh
python3 scope_view.py --population-index /operator/index.json --scope-correction /operator/correction.json
```

Generated controls use the public entry point with fixture pins patched **only in
tests**, checking stale sources, wrong animals/fields, scope changes, before-decode
authentication, no array traversal and preservation of all other metadata:

```sh
python3 -B -m unittest discover -s benchmarks/paper/PAPER-SCOPE-20261114-LATENTCIRCUIT/implementations/calibration-scope-view-v1/tests -v
```

This is a metadata consumer component. Adoption by a future source-native empirical
loader remains necessary; adding this directory alone does not change existing
consumers or source preparation. It does not authenticate the referenced arrays,
establish original preprocessing/metric parity, qualify the I profile for protected
execution, admit either scientific outcome, or make the task runnable. The separate
paper reproduction and same-task improvement contracts remain source unresolved.
