# Paired visual-session grading for NEURAL-021

This component compares complete `direct_observation` and `typed_viewer`
submissions on the same original packet. It validates both observation histories
and all 92 submitted trajectories before opening the protected target generation
once. Both arms then use the unchanged original numerical scorer on the same
captured targets.

The endpoint remains 52 active and 40 perturbation queries, all 30 signed x/y
velocity pairs in m/s per query, and the equal-condition mean of variance-weighted
trajectory R². All 272 calibration trials remain available to both conditions.
No trial, axis, time bin, condition, score formula or success threshold is added
or removed.

## Comparison and exposure

The result includes both original scores, per-condition and mean R² differences,
axis R² differences, and squared Euclidean loss differences. Every difference is
**typed viewer minus direct observation**. Higher R² or lower squared loss favors
the viewer numerically. Undefined R² remains null, negative R² is retained, and
loss differences remain available when R² is undefined.

The same packet means the same available observations and calibration labels.
It does not mean the participant viewed the same calibration examples or spent
the same compute. The result therefore includes each arm's ordered calibration
view indices, total and distinct calibration views, total query views and cropped
query views. Even matching calibration sequences do not establish matching view
timing relative to queries. Source replays retain the complete event histories.

These are descriptive paired results from one retrospective macaque session.
There is no independence claim across time bins, significance test, superiority
threshold or causal attribution to viewer access. A valid receipt can be produced
by an operator programme. It does not prove actual image delivery, participant
identity, absence of tools, runtime isolation, native understanding or scientific
readiness.

## Operator interfaces

The pure API accepts the exact two modes, one trusted original `Packet`, immutable
submission/receipt bytes and an operator-owned target callback:

```python
grade, sources = compare.load_grade()
result = compare.compare(
    grade, sources, packet,
    {
        "direct_observation": {"submission": direct_submission, "receipt": direct_receipt},
        "typed_viewer": {"submission": viewer_submission, "receipt": viewer_receipt},
    },
    load_private_targets,
)
```

`Packet.from_arrays` supports generated controls only unless its values have
independently authenticated provenance. The production CLI enters through the
original `load_public` and fixed public/target generation pins. It requires four
independently selected artifact identities: `--direct-submission`,
`--direct-receipt`, `--viewer-submission`, and `--viewer-receipt`, each with its
`-bytes` and `-sha256` options, plus `--public-root`, `--private-targets` and a new
`--output`. Run `python3 -I -B compare.py --help` for the argument list.

All four artifact paths, protected targets and output must be distinct and outside
the public packet and source trees. Four public captures are checked before
loading observations; both complete replays finish before target access. A target
error returns no partial comparison. Outputs never overwrite an existing result.
Arm bytes are snapshotted before replay, so a target callback cannot replace the
accepted submissions or exposure records. Target bytes are captured once and
reparsed for each original scorer invocation.

The grader and its three dependencies remain unchanged and are authenticated by
their existing content pins. This additive source introduces no replacement
runtime selection. Existing Python 3.11+ is required; the original public NPZ
loader needs the operator's existing NumPy. The component installs nothing.
Input limits and original view budgets remain unchanged; a 1 MiB captured target
and 256 KiB comparison result bound this component's serialized records, not host
CPU or RAM. An authentic grading operation needs its own declared resource and
target-custody scope.

## Generated controls and remaining work

`test_compare.py` exercises a complete generated 272/92 packet and both original
visual sessions: analytic non-perfect and negative scores, undefined targets,
unequal calibration/crop exposure, invalid second-arm admission before target
access, swapped/missing conditions, one target capture with independent score
objects, callback mutation of caller-owned arm mappings, and target/path failures. An isolated candidate test can pass
`--implementations-root` pointing to the existing implementation directory.

These controls are software evidence. No authentic observations, protected labels,
participant predictions, model calls or new scientific scores were used. Matched
participant execution, actual display/readability, isolation, competent comparators,
and evidence beyond the historically exposed one-session population remain open.
