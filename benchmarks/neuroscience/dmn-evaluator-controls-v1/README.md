# Functional-balance evaluation component

This component compares all 56 functional-balance cells: two cohort aggregates, two extents, two directions and seven networks, with 10,000 null profiles per cell. It supplies strict stream validation, complete failure accounting, scalar KL calculations and a protected-admission interface.

It is an evaluator component, not a provisioned benchmark or full-paper reproduction. Authentic matrices, targets, participant records, reference outputs and acquisition credentials are not included.

## Run the invented-data checks

Python 3.11 on a POSIX host is sufficient; these checks do not import NumPy. Choose two fresh absolute output paths whose parents exist:

```sh
python3 -I -S -B analytical_controls.py --output /absolute/new/dmn-analytical
python3 -I -S -B numerical_boundary_controls.py --output /absolute/new/dmn-boundary
```

The complete roster is 28 analytical checks and three numerical boundary checks. It includes complete 56-cell / 560,000-null traversals. Reports and small witnesses are retained; virtual stream comparisons do not imply retention of large wire bodies. This portable version needs its own successful complete validation on each admitted runtime.

These checks use fixed invented values, run no model, and do not call the complete numerical reference kernel. Their whole-operation timers are 1,200 and 300 seconds. They are not an arbitrary-program sandbox or external process owner.

## Scientific semantics and limits

The historical tail is the strict count divided by 10,000. A separately named plus-one diagnostic does not replace it. Wire tolerance remains absolute 1e-12 / relative 1e-10; tail/count agreement is exact. Approximate profile agreement can coexist with a failing strict tail.

Finite-strength sum overflow and positive-subnormal loss are explicit unsupported boundaries. The stable-log test helper is diagnostic only, not adopted production arithmetic. No epsilon, input cutoff, null omission or post-result tolerance selection is introduced.

Full matrix/reference functions retain the NumPy 2.4.6 guard and require separate runtime and authentic-input admission. Scalar/stream checks do not validate those native functions, cross-platform numerical equivalence, full-paper reproduction, neural understanding, frontier improvement or data rights.

All 13 existing admission gates remain: matrix lineage and orientation; complete matrix/label joins; extended endpoint; type mapping; wall/spin semantics; producer/consumer fields; six-type rows; null-network columns; empirical/null masks; undefined values; strict tails; private evaluation rights. A trusted owner must authenticate evidence and isolate candidate execution. Supplied strings alone are neither independent proof nor a sandbox.

## Relocation

All numerical/scoring function bodies are preserved. Source lookup is relative to this directory and exact source bytes are pinned. A new portable binding names the kernel as `functional_balance.py`; the old private absolute binding is not interchangeable. Boundary tests pin the relocated protocol's new bytes and digest. See `PROVENANCE.json`.
