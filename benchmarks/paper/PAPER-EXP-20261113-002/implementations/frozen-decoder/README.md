# Frozen six-class neural decoder helpers

These standard-library Python helpers transport saved linear-model coefficients and predict one neural-count window. They do not train a model or establish a benchmark result. No fitted coefficients, neural observations, labels, participant identifiers, or private file locations are included.

The format belongs to a six-class Horrocks reference component. It preserves an original feature axis of 1–984 positions, an ordered subset of selected features, six coefficient columns, and six intercepts. A mask with no selected features requires all-zero intercepts and predicts class 1.

## Files

- `predict_one.py` validates a frozen model and implements one-window inference.
- `convert_model.py` converts one pinned mask/beta/intercept NPY triple into `model.json`.
- `test_transport.py` contains sixteen retained invented numerical and wire-format controls.
- `test_public_cli.py` contains three invented controls for the public conversion CLI.
- `PROVENANCE.json` describes the source lineage, unchanged components, and scope of validation.

Python 3.11 and a POSIX filesystem are the tested environment; no third-party packages are needed. The bounded file reader uses POSIX `O_NOFOLLOW` and `O_NONBLOCK`.

## Convert saved coefficients

Supply SHA-256 digests from the source you intend to trust. The output must be a new file inside an existing directory.

```sh
python3 -I -S -B convert_model.py \
  --mask mask.npy --mask-sha256 "$MASK_SHA256" \
  --beta beta.npy --beta-sha256 "$BETA_SHA256" \
  --intercept intercept.npy --intercept-sha256 "$INTERCEPT_SHA256" \
  --out model.json
```

The converter accepts NPY versions 1 and 2, a canonical Boolean mask (`|b1`), and finite binary64 beta/intercept arrays (`<f8` or `>f8`). Beta supports C and Fortran memory order. Object arrays and pickle are rejected. Each input is bounded to 65,536 bytes. The mask must match the full feature width, beta must contain one row for each true mask position and six columns, and the intercept must have six entries.

The output contains only the numerical model schema, arithmetic identifier, feature count, selected positions, beta, and intercept. It preserves binary64 coefficient bits through JSON, including signed zero. It does not contain source filenames or input digests. A small completion receipt containing the output digest is written to standard output.

The command authenticates its unchanged sibling `predict_one.py` before loading its validation functions. If that file is intentionally changed, its embedded digest and the provenance require a corresponding review.

## Predict one window

A benchmark host mounts the chosen model as `/model/model.json` and runs the standalone `predict_one.py`. That absolute path is the public sandbox interface, not a private data location. The predictor needs no sibling modules.

Send exactly one newline-terminated JSON object with these fields:

```json
{"schema":"horrocks-current-window-v1","token":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","counts":[2,0,1]}
```

The three counts above are an invented illustration and require a model with feature count three. Real requests must supply the complete original feature axis. Counts must be integers between 0 and 2,147,483,647; the token must contain exactly 64 lowercase hexadecimal characters. The reply contains that token and a class prediction from 1 through 6.

The host then sends the exact line:

```json
{"schema":"horrocks-window-end-v1"}
```

The predictor processes one window and exits. Requests with extra fields, malformed tokens, duplicate JSON keys, nonfinite coefficients, or a mismatched feature axis are rejected. The host remains responsible for isolation, time/resource limits, preventing access to other data, and assigning the correct model to each case.

## Numerical scope

For each class, the predictor computes binary64 products and uses `math.fsum` on those products together with the intercept. Exact score ties select the lowest class number. This operation can differ from NumPy/BLAS accumulation, especially near cancellation or a decision boundary. Coefficient transport does not establish prediction parity with a previous implementation.

These helpers do not reproduce an entire paper, validate a dataset, measure model performance, or supply a complete protected benchmark runner. Any such claim needs its own complete evaluation and provenance. Model values and feature width can also carry identifying information; the absence of explicit identifiers is not an anonymization guarantee.

## Invented tests

```sh
python3 -I -S -B test_transport.py
python3 -I -S -B test_public_cli.py
```

The sixteen retained test methods are unchanged from previously reviewed passing controls. Their parent suite had eighteen controls plus a later staging control; the two fixed-cohort orchestration tests and staging test are not part of this public single-model helper. They were not rerun merely to package the unchanged component. The three new public CLI controls passed for pinned conversion, digest mismatch rejection, and preserving an existing output. This evidence concerns invented inputs only.

## Scientific context

The study is Horrocks, Rodrigues and Saleem (2024), [Flexible neural population dynamics govern the speed and stability of sensory encoding in mouse visual cortex](https://doi.org/10.1038/s41467-024-50563-y), Nature Communications 15, 6415. The authors provide [their analysis code](https://github.com/eabhorrocks/Horrocksetal24_TemporalDynamics) and [version 1 of the data deposit](https://figshare.com/articles/dataset/Data_for_Horrocks_et_al_2024/26031226/1). These are source references; neither the original study data nor its trained models are distributed here.

This package is a separately reviewed coefficient-transport and prediction implementation. It does not establish equivalence to the authors' complete MATLAB pipeline.
