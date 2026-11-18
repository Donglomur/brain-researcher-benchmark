# Figure 5 coefficient alignment diagnostic

This component makes two unresolved Figure 5 source issues inspectable before
implementing a biological reproduction verifier. It performs no fit and makes
no paper-reproduction or improvement decision. The registered task, original
notebook and all existing scorers remain unchanged.

The deposited `IO-fig5-variability.ipynb`, cell 9, reads the cell intercept from
`model.fixef`, calls it a random effect, and then adds the population intercept
and baseline-fluorescence contribution. In inspected [pymer4 v0.8.2 source](https://github.com/ejolly/pymer4/blob/v0.8.2/pymer4/models/Lmer.py),
`fixef` comes from R's `coef(model)` while `ranef` is extracted separately.
The [lme4 documentation](https://lme4.github.io/lme4/reference/merMod-class.html)
defines `coef` as the fixed-plus-random coefficients for each group. Thus,
**conditional on this API being used**, adding the population intercept again
introduces a common intercept offset. The deposited environment does not pin
pymer4, lme4 or lmerTest versions. This is not proof of which historical runtime
produced the paper, and the component does not silently repair its notebook.

The common offset changes the intercept location. In exact arithmetic it does
not change within-group intercept differences or variance; this observation
alone does not invalidate the paper's variability finding. Effects on integrated
and normalized curves require the original source inputs and fit provenance.

Cell 9 also obtains baseline fluorescence using value deduplication,
`pd.unique(df['basef'])`, then aligns that vector positionally to coefficient
rows. Equal fluorescence in distinct cells, or different row order, makes that
an unreliable identity join. `coefficient_alignment.py` instead joins explicitly
on operator-supplied cell identities, retains repeated fluorescence values
across different cells and rejects varying baseline within a single cell.

Use `diagnose_panel` on an export containing exactly `activated` and `suppressed`.
Each group supplies an ordered expected-cell roster, fixed coefficients,
separate conditional and random coefficient tables, and per-trial cell/baseline
rows. Exporting those tables from authenticated original fits is **not delivered
here**. The declared conditional semantics must be `fixed_plus_random`; the
declaration is not itself provenance proof. Integer and text cell identities are
never silently coerced, so an authenticated factor-to-dataframe mapping must be
made explicit upstream.

For each cell, the diagnostic retains both the literal notebook algebra and
the conditional-model algebra. It reports the conditional/random coefficient
identity residuals without choosing an acceptance tolerance. It neither picks a
preferred branch nor selects any biological units, historical trials or new
superiority criterion. It validates support only relative to the supplied roster;
it cannot establish that this roster is the full original cohort.

An additional source observation remains outside the executable diagnostic:
cell 4 concatenates paired and spontaneous arrays on the default first axis;
cells 12/13/29 index the first `len(intercepts)` rows. If those inputs are
cell-by-trial matrices, as the later per-cell trial means imply, the integration
support uses paired rows rather than the union of both conditions. Actual array
dimensions and original cell alignment were not inspected in this source-only
work. Do not replace that operation by a trial-axis concatenation without a
separate source decision.

Run the generated controls from this component directory:

```sh
python3 -I -S -B test_coefficient_alignment.py
```

These controls use invented scalar tables and require only the standard
library. They test identity joins, both algebraic branches, failure handling and
panel completeness. They do not execute R, pymer4, NumPy, any authentic source
arrays or candidate models. Registered runtime activation, source-version
binding, fit qualification, Figure 5/S13 permutation rules, animal joins and
same-result improvement remain unresolved.
