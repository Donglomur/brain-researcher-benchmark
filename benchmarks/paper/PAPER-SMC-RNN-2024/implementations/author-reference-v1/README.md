# Protected author-reference source adapter

This adapter selects two serial jobs, `reference_causal` and
`reference_noncausal`, for the released causal and noncausal author models.
Both jobs use `paper_data_author_code_and_weights` and transport role B.
The participant A/B route remains a separate source component.

Each job preserves the original 192 particles, 32 inference repeats,
`smooth=False`, CPU inference and causal/noncausal seeds 20261117/20261118.
It retains the 20 ms full panel and all four original metrics: co-bps, vel R2,
psth R2 and fp-bps. The 32 repeats produce one averaged inference per model;
they do not establish independent training or biological replication.

## Source dependencies

`author/reference_episode.py` authenticates and loads the maintained public
`full-panel-improvement-v1/full_panel_episode.py` sibling implementation. Keep
the public implementation layout when staging the source. Importing the adapter or collecting its controls
needs no private material or deployment records. The public facade supplies the
retained owner qualification and resource methods; its unused full-panel APIs
are not newly qualified by this contribution.

The existing `../aggregate-owner-v1` and `../aggregate-episode-v1` components
supply owner sequencing, custody, transport and the retained worker. The overlay
compiler authenticates the exact owner before occurrence-checked changes for the
two model phases, B/B exposure and reference clock. Provider, process/cgroup
closure, failure recording and capture machinery are retained.

The seven original helpers remain in `../source-matched-nlb-v1`:
`author_predict.py`, `prepare.py`, `memory_reduction.py`,
`particle_reduction.patch`, `scorer.py`, `source_manifest.json` and
`reference_panel.json`. A separately selected private deployment stages those
exact 50,066 bytes and the existing original protocol. This contribution does
not duplicate that maintained closure or the public facade.

## Protected execution contract

Actual preparation requires a separately assembled, source-authenticated private
component, authentic material bindings, a prospectively selected deployment and
fresh qualification. Those private records remain required by the source APIs
and are not distributed here. Their absence fails closed. Source import,
source construction and generated controls do not authorize execution.

Both method declarations are frozen before either phase. Parent-owned closure of
both jobs precedes grading. Both complete prediction freezes and private snapshots
are validated before the original scorer can read the TEST target. The snapshot
copier retains no-follow, ordinary single-link, exact-size, bounded-copy and
stable-content checks. A failed second model cannot promote the first model into
a complete paired result.

Each new reference protocol requires an explicit CPU allowance: a strict integer
from 1 to 64,800 seconds per model. There is no default. The upper bound is the
fixed six threads multiplied by the unchanged 10,800-second wall envelope;
8 GiB memory and six numerical threads remain fixed. The selected allowance must
match both frozen method declarations, the protocol, execution jobs, qualified
owner profile, worker CPU limit and original helper argument. An allowance is a
ceiling, not evidence that the model will finish within it.

The earlier fixed 7,200-second reference allowance was not supported by authentic
cost evidence: the complete retained causal and noncausal runs used
29,816.929737 and 29,393.194995 CPU-seconds. These measurements concern the historical
CPU environment and do not predict exact cost on a new host. Participant access
profiles, including the 7,200-second improvement profile, are unchanged.

Call `ReferenceEpisode.instantiate(..., cpu_seconds=SELECTED_CPU_SECONDS)` or supply
`--cpu-seconds SELECTED_CPU_SECONDS` to the operator CLI. New method, method-freeze,
protocol, execution-job, actual-declaration and program-result records use their
`v2` schemas. Old frozen `v1` protocols and receipts retain their historical
meaning and are not silently reinterpreted by this source. A fresh source-bound
runtime qualification must include the exact selected reference profile.
No model inference, scientific grading or runtime qualification is performed by
constructing these records.

## Generated source controls

`controls/test_reference_route.py` contains the retained 22 generated source controls and
additional CPU-profile regression controls. Its model, Provider and scientific scorer boundaries are stubs.
The portability change only selects the public facade and locates the controls
and retained owner from the repository. To run all controls, set `ARTIFACT_DIR` to a fresh canonical absolute leaf
outside the repository, beneath an existing ordinary output directory:

```sh
python3 -I -S -B controls/test_reference_route.py --fixture-parent "$ARTIFACT_DIR" -v
```

Run that command from this implementation directory. The artifact leaf must not
already exist; the harness creates it exclusively. Symbolic links, missing parents
and paths overlapping the repository source are rejected. The maintained CI
launcher supplies this external artifact leaf. The harness caps cumulative
generated writes at 512 KiB, including
deleted and failed fixtures, and records its fixture cost. The complete command
is a source-control recipe, not a claim that this public transformation has rerun
all 22 controls. The integration check selects only the portability-relevant
methods from the existing suite; it does not establish model or native readiness.

No scientific result is supplied here. Historical checkpoint-to-published-row
and data-revision linkage, justified reproduction margins and independent
uncertainty remain unresolved. This route is author calibration, not an AI
attempt, improvement result or SOTA claim.
