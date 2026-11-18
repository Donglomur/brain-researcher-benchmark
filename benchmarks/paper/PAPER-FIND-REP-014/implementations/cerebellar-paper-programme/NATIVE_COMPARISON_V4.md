# Declared metadata identity in six historical branches

`native_compare_v4.py` adds a source-typed metadata guard for MainData,
learningCurves_DA, CF_novice, passiveMFB, gtacr1 and learningCurves_gtacr1.
It delegates numeric reconstruction to unchanged v3/v2. This is an additive
comparison component; the published programme still uses `native_compare`.

The six branches retain their original 48 roots. The other three IO branches
retain v3 unchanged, for 67 historical roots overall. Matched fractions, status
codes, root/leaf support, source shape/type and the continuous tolerance
`1e-8 + 1e-6*abs(reference)` are unchanged. Exactness concerns source-declared
counts, ordinals, group indices and logical masks, including integer-valued
MATLAB doubles serialized as JSON floats. Fractional drift cannot earn a perfect
calibration score merely because it falls inside a continuous tolerance.

| Branch | Newly guarded metadata | Preserved continuous or unresolved metadata |
| --- | --- | --- |
| MainData | Scalar session count; complete 37 group fields with exact positive integer index leaves, order and empty vectors preserved | GrC/CF clocks continuous; `dirTable` typing unresolved |
| CF_novice | Scalar session count; exact session cell counts | Existing string condition unchanged |
| passiveMFB | Scalar session count | Original final-session clock convention |
| gtacr1 | Scalar collection count; exact per-group counts | Source plotting labels unchanged; no invented count-to-label relationship |
| learningCurves_DA | Positive scalar mouse/day ordinals, scalar movement counts, logical completion and optional masks | `normTime` and `dtb` continuous; helper `group` optional |
| learningCurves_gtacr1 | Same learning fields; source script requires `group` | `normTime` and `dtb` continuous; original group strings |

`NATIVE_COMPARISON_V4_SOURCES.json` records the exact retained six author scripts,
six export wrappers, shared metadata helper and immutable BINDINGS pins. No data
arrays are included. MainData source lines49-124 define all37 groups by `find`
or subsets of those indices. That justifies discrete indices, not interpreting
arbitrary numeric `dirTable` columns as identities. The result explicitly lists
`dirTable` under `metadata_typing_holds`; equal supplied references cannot close
that hold. Reference/candidate equality also does not authenticate animals,
sessions, provenance or biological claims. Invalid self-identical discrete
values are rejected, but no new cross-field biological consistency audit is
claimed.

## Validation seam

From this implementation directory, run:

```sh
python3 -I -S -B test_native_compare_v4.py
```

The standard-library generated tests exercise only the six newly guarded
branches: all48 root declarations, fractional-drift regressions against v3,
invalid self-comparisons, masks, complete groups/order, optional DA group,
continuous tolerance acceptance, full support and both private grade arms.
The accepted three-IO test suite is not replayed. This validates comparison
behavior on generated fixtures, not successful native paper reconstruction.

## Selection remains separate

At immutable commit `8e9eeddf8327094d631a2f015d9334b9078e98f5`,
`worker.py:747-750` dispatches `final_evaluate` with native-grade schema by
importing `grade` from `native_compare`. B15's selected future overlay adds v3
source only. This package changes neither that call site nor a source manifest.

A later admitted selection must explicitly point that import to
`native_compare_v4`, include its unchanged dependencies `core.py`,
`native_compare_v3.py` and `native_compare_v2.py`, and regenerate/review the
worker and recursive source pins in `EXECUTABLE_SOURCE_MANIFEST.json` and the
central-integration source/dependency/qualification records. This is a
technically straightforward private derivative, but selecting a new frozen
execution source set is an already-held runtime admission decision for the
owner/integrator. It is not accomplished by adding this file or by these tests.

Neither biological branch reconstruction nor a new paper SOTA is established.
Reproduction and same-task improvement remain separate scientific outcomes;
this correction adds no metric, substitute prediction task, win threshold or
new benchmark. Original data, native runtime admission and scientific outcome
holds remain.
