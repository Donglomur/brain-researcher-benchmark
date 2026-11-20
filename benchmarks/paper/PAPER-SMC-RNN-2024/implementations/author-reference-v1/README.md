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

The producer profile remains 7,200 CPU-seconds, 10,800 wall-seconds, six threads
and 8 GiB per model. Its adequacy for the full original inference and the private
grader remains unmeasured. Later execution requires the existing owner gate and
fresh runtime/resource qualification; no cap or recipe reduction is implied.

## Generated source controls

`controls/test_reference_route.py` contains all 22 previously accepted generated
source controls. Its model, Provider and scientific scorer boundaries are stubs.
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
