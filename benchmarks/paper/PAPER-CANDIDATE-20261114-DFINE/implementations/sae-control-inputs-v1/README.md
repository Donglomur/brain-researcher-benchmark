# DFINE SAE control-input construction

This small component implements the original motor missing-observation Methods'
two SAE input controls: replace a missing neural observation with zero, or with
the arithmetic mean of the last and next available observations. The latter uses
future information and belongs to the noncausal SAE control. It must never be
reported as causal DFINE filtering.

Source: [DFINE Methods, Inference analyses with missing observations](https://pmc.ncbi.nlm.nih.gov/articles/PMC11735406/).
The retained primary JATS was authenticated at 312,940 bytes, SHA-256
`645c69dfa4735c0ae3fe4045dcc324172aa3aafb7e41abe1d3ec619a04e47887`.

`impute_sae_observations(masked_rows, mask_bits, method, feature_count)`
accepts the existing numeric component's `1` observed / `0` missing convention
and method names `sae_zero_smooth` or `sae_average_smooth`. Every dropped row must
already be `None`; this function does not receive its original neural values.
The output includes every original timepoint. All missing points between two
available observations receive the same endpoint mean, rather than linearly
interpolated or recursively imputed values. Inputs are left unchanged.

The paper does not specify the neighbor-average rule for leading or trailing
missing runs. That method refuses such panels with `UnresolvedBoundaryError`.
No edge replication, zero fallback, clipping, timepoint deletion or unmasking is
introduced. This refusal is a documented remaining original-source requirement,
not proof that original masks had complete endpoint observations. Zero replacement
does not require neighbors and therefore supports these positions.

This is a source-grounded mathematical input adapter, not an inference executor
or a complete original-data run. Python float64 arithmetic is not historical
float32/native bitwise parity. The caller must authenticate masks, time order,
preprocessing and selected neuron support before using it. No masks, folds,
neuron selections, readout parameters or experiment identities are generated here.

The existing `missing-observation/scorer.py` remains unchanged. The adapter creates
inputs for the source SAE control models; the scorer consumes their eventual
N-by-4 behavior predictions. Original models/readouts, the empirical analysis
manifest, full ratio grid, mask realizations and granular Figure 7e / Extended
Data 6e–f reference export remain unavailable. No reproduction, improvement,
causal-boundary qualification, new benchmark or scientific-readiness claim follows.

The focused data-free checks cover multi-step gaps versus interpolation, distinct
neighbor pairs, all observed/all missing cases, unsupported one-sided gaps,
absence of dropped values, unchanged input support, and finite arithmetic. They
do not use original neural observations or run a model.
