# Coding-direction projection component

This adds the missing coding-direction **projection** calculation to the source
components for PAPER-FIND-REP-007. It consumes the existing initial evaluator's safe
in-memory imaging bundle. It does not read source NPY dictionaries, select a
scientific cohort, run the author repository, grade reproduction or assess
improvement. The existing canonical task and initial evaluator are unchanged.

The named variant follows
[Get_coding_direction at the pinned author revision](https://github.com/MouseLand/zhong-et-al-2025/blob/ba64ac697f5d9914926baac79399e80707a5f3a6/utils.py).
Raw moving-corridor frames from even zero-based trials determine the two
percentile populations within each of V1, mHV, lHV and aHV. Responsive cells must
exceed moving-gray activity for either reference stimulus. Upper and lower 5%
thresholds include ties. Each selected cell is centered on all-session gray bins
42:52 and scaled by the sum of its two reference-stimulus population SDs over bins
0:40, with a factor of two. These statistics include all reference trials. Ten
positions from the preceding trial are prepended to each 60-position trace.
Reference-stimulus projections retain odd zero-based trials; other stimuli retain
all trials. The output preserves both populations, all four areas and seven
stimulus slots. This is the source's population-mean projection, not a fitted
linear decoder or a train-only normalization rule.

Call `coding_direction(bundle, reference_ids=(2, 0))`. A caller using another
source pair must establish its experiment-specific recipe independently; the
function does not authorize any pair/cohort as a benchmark. Required fields are
the existing imaging bundle plus `frame_trial`, `frame_gray` and `interp_spks`.
The latter must retain every source cell, every trial and all 60 positions.
Moving-corridor frame/trial stimulus labels must agree. The initial evaluator is
loaded by a fixed SHA-256 binding before its validation and arithmetic helpers are
used. The dependency is part of this repository, not a supplied participant file.

The returned document records source axes, selected cell indices, trial indices,
normalization diagnostics and complete trial-by-position projections. The first
trial has no preceding tail: those ten positions remain null with an explicit
missing-history flag. Absent stimuli retain empty, labeled slots. Empty areas,
nonfinite d-prime thresholds, centers, scales or normalized values retain undefined states;
the component does not invent a value or remove inconvenient trials/cells.
Undefined-state reporting is an engineering policy, not verified byte-for-byte
behavior of the author runtime. Projection averaging and previous-tail assembly
are reordered to avoid a second full cell-by-trial-by-position tensor; their
linear equivalence is covered by generated controls, but authentic numerical
parity is unverified.

This closes only a source-construction gap. Figure-specific similarity indices,
orthogonalization summaries, original animal/session joins, indispensable
controls, source numerical targets, agreement tolerances and complete native
preparation remain unresolved. The sequence paper/code discrepancy is unaffected.
No result from this module can make a biological contrast into an improvement
criterion. Reports explicitly retain `scientific_qualification: "unknown"`,
`full_contract_complete: false` and `scientific_improvement_assessed: false`.

Fourteen generated controls cover an analytic normalized-trace oracle, both
populations, source trial roles, inclusive percentile ties, missing previous
history, undefined normalization/selection, source alignment failures, immutable
inputs and dependency tampering, plus nonfinite gray centers and trial-varying
history that distinguishes the preceding original trial from the preceding
same-stimulus trial. They use no original observations. Run through
the repository's authorized test process, for example:

```sh
python3 -I -B benchmarks/paper/PAPER-FIND-REP-007/implementations/coding-direction-v1/tests/test_coding_direction.py
```

NumPy is the only nonstandard dependency. A real original-data execution still
needs a separately measured memory/runtime profile and admission. This component
establishes neither participant isolation nor a paper-plus-data/author-code access
comparison. Integration requires independent review and explicit CI enrollment;
the accompanying handoff proposes the existing NumPy construction group.
