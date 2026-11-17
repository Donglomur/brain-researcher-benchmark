# C4 V3 captured member lineage

This is a source repair for C4V2-W03. It changes no scientific model, cohort,
target policy, numerical reduction, fold, repetition, transfer or grouped recipe.
All 83 operative/source-context roles and all 25 open gates remain selected.

The `c4_probability_capture_v3` identity includes a closed `member_support`
record with `layout` and `row_model_indices`. The tensor remains unit by five
classes by the members actually predicting that row. Equal-member reduction
remains `mean(axis=2)`; identity fields are support, never measurements.

For `unit_loo_10`, the complete model roster contains each `(repeat, held unit)`
once for every unit and each repeat 0 through 9. At the published 202-unit
support this is all 2,020 identities, not ten identities shared across units.
`row_model_indices[row][repeat]` selects the corresponding index in that full
roster. Each index must refer to exactly that row's unit and repetition; all
indices occur exactly once across the map. The tensor is `(N, 5, 10)`. The
producer constructs the map during the same loop that assigns the held
probability into the tensor. The global roster retains fitted-model order;
the mapping does not assume repeat-major sorting or reorder models.

Both capture admission and authenticated capture readback validate the map,
complete roster, biological row order and repeat identity. A missing model,
duplicate pair, cross-unit reference, repeated/wrong repetition, boolean or
out-of-range index, missing row, alternative layout, or incompatible tensor
extent refuses the whole prediction. No broadcasting, available-case subset,
model truncation or first-ten reuse is permitted. Readback reconstructs the
LOO model UnitKey identities and retains the complete roster and row map in
the returned Prediction before a target-consuming function is called.

For `global_members`, `row_model_indices` is null and the tensor must remain
`(Q, 5, len(models))`. This preserves full external/behavior transfer through
all 10*N models. The separately selected grouped reference retains `(N, 5, 1)`
with its existing single cross-fit composite identity linked to the complete
captured fit-job support manifest. No grouped model or full fit support is
removed. Its training-only feature, scaling, tuning and biological grouping
rules remain unchanged.

ScientificDriver.classify passes the producer's explicit member support. Its
model, Hessian, calibration, training, oversampling and RNG captures still
cover every fitted model before transfer admission. Transfer and grouped
callers use the global layout. Scoring and behavior continue to read captured
bytes via read_prediction, rather than the mutable in-memory Prediction cache.

This is a new capture schema. Old V2 identity records fail the exact schema
check; there is no automatic reinterpretation or migration of old captures.
The predecessor packet and failure evidence remain immutable in place. No
authentic V2 execution or output is claimed. Genuine filesystem/native owners,
source/QC/target authority and complete capacity remain unqualified. The
metadata controls use invented identities and categorical tensor leaves;
they establish caller/support behavior, not numerical NPY parsing, scientific
parity, model quality or native execution.
