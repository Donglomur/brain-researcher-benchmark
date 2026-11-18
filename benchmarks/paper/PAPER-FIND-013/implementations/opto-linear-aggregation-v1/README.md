# Optogenetic linear-classification aggregation

This component calculates a narrow part of the primary inhibition comparison
from supplied derived row statistics. It does not fit trajectories, reproduce
the paper, or qualify an improvement.

The pinned [author pooling script](https://github.com/antoinemadar/BTSPvsSTDP/blob/7a6ecc2bbf8f1e1fbca3b769a0db53299ee8171c/COMtraj/Opto/OptoCOMtraj_Pooled.m)
uses all rows for pooled fractions, but only classified rows for per-mouse
fractions. Its p-only shifting helper also counts significant zero-slope rows
that the directional masks leave unclassified. The implementation retains these
differences, explicit missing statistics, both timing branches, nine declared
mice, and optogenetic-minus-control contrasts. Empty denominators remain null.

Call `summarize_bytes(rows_bytes, roster_bytes, expected_roster_sha256)` with an
independently frozen operator roster. The JSON roster contains `schema`,
`source_revision`, nine `mice`, and ordered `rows`. Each row binds `id`, `branch`,
`row1`, `mouse`, and integer `opto_on`. Derived rows add `slope_cm_per_lap` and
`p_value`; null denotes an explicitly missing source statistic. IDs are
`opto_first/1`, etc. Branches retain their complete contiguous table coordinates.
Derived rows may arrive in any order; metadata must match the operator roster.

Source-table acquisition, native row derivation, immutable cohort authentication,
bootstrap inference, numerical reproduction criteria and mechanistic controls
remain separate requirements. A self-consistent replacement roster is not
original-source evidence. Generated controls exercise software behavior only.

Run `python3 -B test_aggregation.py` through the project's bounded test pool.
Integration requires enrolling this new task-local command in component CI.
