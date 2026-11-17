# Stable contact-count scorer

This bounded revision repairs cancellation in the secondary Poisson-deviance
calculation. It keeps the registered contact-onset count target, primary MSE,
prediction schema, complete trial roster checks, nonnegative finite predictions,
fixed-reference gain sign, and equal-trial/session/mouse aggregation unchanged.
It is an operator-private in-memory scorer, not a data loader or participant
execution route.

For positive target count `y` and floored mean `mu`, the original expression
`mu-y + y*(log(y)-log(mu))` subtracts nearly equal quantities near a correct
prediction. Its final nonnegativity clip can hide a positive residual loss.
The revision uses `y*(r-log1p(r))`, where `r=(mu-y)/y`, evaluated as a polynomial
through degree 24 when `abs(r) <= 1/8`. The omitted absolute half-deviance tail
is bounded by `y*abs(r)**25/(25*(1-abs(r)))` in that region. Larger residuals
keep the original expression. The original `mu=max(prediction,1e-12)` convention
is retained, including deviance `2e-12` for target and prediction both zero.
No observations, predictions, counts, or losses are rounded to create equality.

`score.py` preserves the API:

```python
score_predictions(expected, predictions,
                  baseline_predictions=fixed_reference,
                  mouse_binding=operator_binding)
```

Results and biological identity bindings remain private. A supplied binding
permits arithmetic only; it does not authenticate mice. This low-level API
accepts a supplied roster, as its predecessor did. The existing complete-panel
contract remains responsible for all 16 sessions, 5/5/6 grouping, five mice,
10/20-bin responses, and all four matched input conditions.

The predecessor bodies are preserved unchanged in `registered-runtime`,
`neural030-four-cell`, `cerebellar-contract`, and `cerebellar-executor`; each has
SHA-256 `4b4186e14063235f99f0eab8a09bb4edbc6d3cb1f0c9bd9184e194e89cbb7e0a`.
This revision is not automatically selected by those packages. Integration must
replace their scorer through each package's reviewed source capture/manifest
mechanism and rerun the relevant package controls before using it there.

`test_score.py` uses generated values and a 90-digit Decimal logarithm oracle
independent of the polynomial. It preserves a predecessor counterexample,
checks both sides of the numerical transition, verifies unequal hierarchical
weights by hand, and exercises existing invalid-roster and prediction refusals.
It imports the sibling predecessor only for the regression comparison. Under
the repository's coordinated test pool, run `python -I -B test_score.py` with
the already provisioned NumPy environment. No dependency installation is needed.

No authentic source data were opened or prepared, and no model ran. The Dryad
payload, genuine five-mouse map, clocks, QC support, native runtime, reference
strength, uncertainty protocol, and scientific qualification remain unresolved.
This numerical repair cannot establish decoding performance or direct neural
interpretation.

Provenance: the unchanged task refers to Garcia-Garcia et al., Neuron (2024),
[paper](https://doi.org/10.1016/j.neuron.2024.05.019),
[data](https://doi.org/10.5061/dryad.bk3j9kdm6), and
[author repository](https://github.com/wagnerlabnih/garcia-garcia-neuron-2024)
at revision `124c83e1af83e9680e05f9827448579d02345fa3`. This repair uses the
repository-owned scorer and supplied source record; it does not redistribute
author MATLAB or dataset content. No source availability was rechecked.
