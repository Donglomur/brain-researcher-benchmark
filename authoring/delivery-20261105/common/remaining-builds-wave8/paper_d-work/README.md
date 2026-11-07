# OFC TCA input tensor component

This additive source component advances the task-aligned population-factor branch of `PAPER-ROOT-ADD-018`. The existing OFC package implements 48 response curves for Figures 3/7; it explicitly leaves TCA, behavioral inference and inactivation unfinished. Its original author `makeTensor_TCA.m` is present, but no portable implementation of that transformation was found in the inspected OFC package. This component supplies that transformation. It does not replace the response-curve implementation or finish the canonical paper task.

`ofc_tca_inputs.py` accepts already decoded, externally authenticated `S`/`SU` observations. It performs the original tensor arithmetic without fitting or importing a model. Session records carry explicit `session_id`, `animal_id`, `cohort`, `S` and `SU`; the docstring defines their shape. It returns a neurons × concatenated event-time × block tensor, its exact time layout, unit identities and session-level diagnostics. There is no file reader, acquisition client, scientific scorer, MAT decoder, native execution command or candidate runner.

The held source is `ofc-belief/private/author_code/analysis/Electrophysiology/makeTensor_TCA.m`, revision `b7b68ca8c107d8ce4a061e16da214307f175c3e5`. Its MIT notice is retained in `LICENSE.author`; exact local source pins and primary documentation URLs are in `SOURCE_EVIDENCE.json`.

The implementation preserves these scientific details:

- Sessions need at least five units and four block transitions. Four transitions do not prove all three block types exist. An absent block remains visible through the original zero-initialized slice.
- Event order is COFF, SON, SOFF, Rew, Opt. The first unit's COFF axis selects all event windows after three-decimal rounding. The first three windows include −1 through 1 seconds; Rew/Opt include −1 through 0.8. The standard 241-column source axis yields 197 concatenated positions.
- Each unit/event is normalized using every non-NaN element of its original matrix and sample SD with denominator N−1. Violation trials and columns outside the output window still contribute to this normalization. Only block averaging removes violations.
- Block order is low/mixed/high, encoded 3/1/2. Original trial order and all units remain. One NaN mean anywhere in an event/block's units × times matrix suppresses assignment of the *entire* slice, preserving its source zero initialization. Constant or all-missing units can therefore zero other units' values; this is audited source behavior, not an endorsed missing-value repair.
- Session, animal and unit identities remain in reports for transformed, source-excluded and unsupported sessions. Source exclusions are distinct from portability refusals. `prepare_cohort` requires the full source-ordered 191 Expert or 96 Naive sessions and never pools the two cohorts. One unsupported session prevents any concatenated tensor from being admitted.

The complete roster must be independently authenticated. Count and ordered-ID agreement with a caller-supplied list do not establish that the caller supplied the true source roster. The author function is generic across input directories; the 191/96 wrapper preserves the existing canonical source selection. It does not claim that a Naive TCA tensor corresponds to a published TCA panel. No authentic roster bodies or observations were opened during this build.

The existing `prepare_observations.m` projects only four events and omits Opt. It cannot feed this five-event component. A future complete raw-field projection/decoder must retain Opt and prove source identity, order, time geometry and numeric precision. No zero Opt substitute is permitted.

Near rounding ties, singleton selected-trial blocks, duplicate unit identities, normalization overflow or underflow to zero on nonconstant inputs, nonfinite/incompatible inputs and cross-session time-grid differences stop the relevant transformation. These are explicit compatibility holds, never reasons to silently drop a session. MATLAB's one-trial default mean dimension is distinct from the multiple-trial path, and the subsequent nonscalar assignment branch has not been qualified. Python binary64 reductions are mathematically source-compatible on the supported domain, with no claim of MATLAB-version or float32/float64 bitwise equivalence.

Both access conditions remain unchanged: paper/data/common observations in A; the same material plus approved author code in B. This derived implementation and its intermediates are operator-only unless a separately reviewed exposure policy specifies otherwise. It is not mounted into A as undeclared official-code assistance; neither arm receives private reference outputs. No arm views were built or changed here.

Run the invented controls from the repository root:

```sh
python3 -I -B authoring/delivery-20261105/common/remaining-builds-wave8/paper_d-work/test_ofc_tca_inputs.py
```

The 23 controls cover a closed-form sample variance calculation, all five event windows, global normalization versus cropped/filtered normalization, matrix-wide missingness, absent blocks, constant/all-NaN units, numerical underflow refusal, source exclusions, identity retention, complete invented 191/96-session coverage, incompatible axes and refusal of partial tensors. They use no real neural arrays, roster bodies or native MATLAB execution. No files are written by the tests.

Remaining whole-task work includes authentic complete source joins and MAT projection; source precision/native parity; TCA rank/restart/seed and decomposition behavior, unresolved native helpers and commented-out saved outputs; all behavioral/inactivation branches; trusted outputs and execution isolation; scientific and resource qualification. Source `runTCA.m` uses nonnegative CP fitting on the prepared tensor although eventwise z-scores can be negative; this component neither resolves nor silently changes that downstream issue. Registration, preferred-interface, scientifically verified and submission-ready counts are unchanged.

The all-12 inspection and nonselected gaps are in `SCAN.json`. Existing failures/cost histories remain authoritative at their referenced paths; this work neither retries acquisition nor erases them. `HANDOFF.json` describes the bounded change and exact remaining limits.
