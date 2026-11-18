# Retain the uncached scientific route

The accepted route runs two arbitrary frozen programmes in ten fresh folds
each. Transparent reuse of original DBA intermediates is **not proved
byte-equivalent** to those executions and is not implemented.

The complete original feature schedule has 376 category windows × six ordered
ROI pairs × twenty phases = **45,120 DBA calls**, assuming no early solver
failure. A single extraction has 2,256 such calls. These are schedule counts,
not measurements: an exception stops the remaining pairs for that window.

The original selected feature first standardizes all four ROIs with sample SD,
then detrends them, calls the six source-ordered native DBA pairs, and takes the
maximum squared CS↔PFC barycenter. Failures in unrelated pairs can invalidate
the entire window. A cache of selected scalars alone must not erase those
failure paths, diagnostics or source operation order.

Two independent source reviews found these unresolved obligations:

- The existing producer checks the `tslearn==0.6.3` distribution version, not
  immutable native code, complete numerical dependencies, platform, threading,
  RNG state or all relevant runtime state. Existing tolerance-based generated
  numerical controls do not prove exact byte reproducibility on authentic
  inputs across the proposed phase schedule.
- Arbitrary improved programmes may choose features using training labels,
  fold identity, RNG or previous computation. Their immutable source hashes do
  not prove that a particular intermediate is a pure function of raw input.
  Including all those inputs in a valid key may leave no cross-fold reuse.
- Whole-window failures, warning/error outcomes and resource-dependent native
  failures need an explicit semantic policy. Reusing a prior success can
  suppress a failure that the original invocation would have encountered.
- Original four-category QC/imputation is global and transductive. Classifier
  fitting, mixed-sigmoid training statistics and held-batch extrema remain
  fold-specific; they must never be silently cached across folds.
- A and B must not share candidate-derived intermediates. Giving A an
  evaluator-computed original feature bank changes its declared paper+data
  assistance. The published winner and discovery-selection exposure also
  remain fixed; a cache must not turn that selection into blind prespecification.

A future separately declared fixed feature stage would have to bind exact
source/runtime/environment identity, all four input ROI tensors and their order,
sample times, dtype, preprocessing semantics, all six ordered pair arguments,
every solver option/default, stage/programme/role identity, determinism evidence
and failure/diagnostic semantics. Complete native barycenter payloads alone
would occupy 18,048,000 bytes for one full no-failure extraction, before keys,
provenance and diagnostics. None was computed or stored here.

The implementation instead adds a protected delivery audit, retaining the
original scientific inputs and all twenty fresh programme phases. A cache may
be reconsidered only as an explicitly reviewed stage with the required evidence;
it must not inherit scientific validity from an engineering cache test.

Read-only audit cutoffs, retained in the external construction evidence:

- Source/solver audit: 10,889 bytes, SHA256
  `7995ae9be05854bedc10b7c0df3cc0a2bd33132c33e890a458ff352ea32dd09a`.
- Independent leakage/selection audit: 11,618 bytes, SHA256
  `763f6e567427b233c7f1c5c55c64fe22d22c763a22831977cc6b0298760f5359`.

No authentic arrays, solver calls, model fits, Docker operations, downloads or
new runtime installations were used in either audit.
