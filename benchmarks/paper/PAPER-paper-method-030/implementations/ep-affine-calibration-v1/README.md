# Grader-side affine voltage calibration

This component fills one stage between the existing optical ROI extractor and
electrical-reference assessment: converting already aligned fluorescence traces
from arbitrary units to mV by an affine least-squares fit to EP. It does **not**
read ABF files, choose channels or ROIs, detrend, align clocks, run a denoiser,
reconstruct Figure 3, or qualify a paper improvement.

The original paper describes grader-side affine L2 calibration after trace
preparation. Its exact fitting boundaries and alignment choices remain
unrecovered. This component therefore requires explicit operator-frozen fitting
indices and retains `historical_equivalence_unresolved`; it supplies no default
mask and does not infer historical support from the saved inventory.

## Computation and access

For each method and recording, fit `EP[i] = gain * optical[i] + offset` by
unweighted least squares over the supplied indices. The same indices and EP
reference apply to raw, CellMincer, SUPPORT, PMD, N2S and every candidate. The
affine transform is applied to all 5,000 samples. No gain-sign restriction,
regularization, peak search, clipping or sample omission is introduced. Constant
optical fitting support is non-identifiable and fails explicitly. Nonfinite or
unrepresentable inputs/results also fail.

Both inputs and outputs remain **grader-only**. The calibrated output depends on
EP, including when the declared fitting support contains the assessed samples.
It must not be returned to the candidate or used for candidate training or
selection. Declaration validation does not establish process isolation.

The output deliberately names the alignment policy
`grader_ep_fitted_affine_l2_not_external_no_test_ep_fit`. It is **not** directly
compatible with `initial-evaluator-v1`, which requires independent calibration
without test EP fitting. Do not relabel one policy as the other. A separately
qualified original-paper evaluator and source-resolved preparation are needed
before this stage can participate in historical reproduction or same-task
improvement assessment.

## Input contract

`calibrate_panel(panel)` accepts an in-memory operator dictionary. The generated
test fixture is a complete machine-readable example, not empirical data.

- The panel pins the unchanged `initial-evaluator-v1/population.json`: all 22
  saved recordings and their nine filename-derived groups. This is not evidence
  that these are the original 22 evaluation recordings or all 26 training
  recordings. No train/test split is created.
- Every record supplies an already aligned, detrended 5,000-sample EP vector in
  mV and one same-grid fluorescence-AU vector for every method, at 500 Hz.
- `fit_sample_indices` is a strictly increasing list of at least two distinct
  native frame indices within `[0, 5000)`. It is shared across methods within
  that record. The component never selects or optimizes that support.
- Preparation, alignment and fitting-support evidence SHA-256 strings are
  required. They identify operator records; a valid-looking hash is not proof
  of source fidelity, provenance, frozen chronology or exposure control.
- `support_status` is exactly
  `operator_frozen_historical_equivalence_unresolved`. A historical-verification
  claim cannot be asserted through this interface.

The output contains each method's full calibrated trace, gain, offset, fitting
support identity/count and fitting RMSE, alongside the private-access and
unresolved-science declarations. RMSE here is a calibration diagnostic, not a
new benchmark endpoint. There is no CLI, native data loader or automatic output
publication; an admitted operator must enforce the surrounding lifecycle.

## Validation and integration

This package uses only the Python standard library. From this directory:

```sh
python3.11 -B -m unittest discover -s tests -v
```

Thirteen distinct generated controls cover known affine coefficients, negative
gain, constant EP, scaling extremes, unselected-EP invariance, missing/duplicated
coverage, common method support, invalid coordinates and access/policy claims.
The full saved 22-recording generated panel preserves all 5,000 samples and all
source methods. Twelve controls passed initially; after a zero-slope numerical
edge-case correction, the new control and three affected controls passed. The
remaining passing controls were not replayed. No authentic signals were read or
processed, and no baseline or model performance was measured.

The sole repository integrator must register this new component and its test
command with the existing component-discovery mechanism. This source package
does not edit the central registry, outcome contracts or scientific readiness.

Remaining prerequisites include native EP channel/units, the original timing
and filtering recipe, shared raw-derived masks, historical fitting support,
26/22 cohort membership, all original prominence and spectral conventions,
fresh source-method outputs and protected comparison/inference. The source
evidence and unchanged dependency identities are in `SOURCE_BINDINGS.json`.
