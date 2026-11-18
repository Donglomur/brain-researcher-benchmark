# Retrospective held-horizon prediction of goal-aligned movement from odor-memory dynamics

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Time-weighted mean calc\_speed(t)×cos(heading(t)−goal\_heading) over the five seconds after verified physical odor offset; goal\_heading is the circular mean in the final pre-offset second.

**Source delivery:** partial\_delivery. Complete native inspection, PID command preparation and an evaluator-only paired fly-macro point scorer exist. The scorer consumes supplied frozen numerical targets; it does not construct the five-second behavioral answer or validate its calibration. A verified physical-offset/identity bridge and complete fly-grouped target producer remain missing; parser or scorer delivery is not forecast success.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Bounded histories could support direct numerical interpretation after exact episode extraction. No future behavior, derived bump duration or target feedback; finite representation must preserve the registered history. | No authenticated forecast packet or complete no-tools transport. |
| Typed viewer | not\_delivered | A trace viewer could show aligned permitted neural/behavior histories. No post-offset scroll and no label-bearing derived summaries; current inspector is operator code, not a viewer. | Target-aligned visual representation and typed episode boundary. |
| Tool assisted | not\_delivered | Per-case signal/behavior analysis with numerical tools over the same history. Matched tools and source-only fitted parameters; operator inspection outputs do not grant candidate access. | No candidate-facing investigation episode or forecast response collector. |
| Frozen program | not\_delivered | Precommitted model predicts all eligible offset episodes after fly-grouped training. Freeze recipe before query; no held-fly target refresh, whole-test normalization or future-bump selection. | Target producer, competent baselines and frozen executor. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

**Specification alias:** This registered ID refers to specification HOLD-NEURAL-FRONTIER-FLYMEMORY-20261114; the alias does not establish another independent study or dataset.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 27771 bytes; SHA-256 `4d0dbb3cb692456670f030a2eb9b69977641e096fbcf4f2ee795afdf43300cfb`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Native inspection](implementations/native-inspection) — Native inspection.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Pid preparation](implementations/pid-preparation) — Pid preparation.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Fly group splits v1](implementations/fly-group-splits-v1) — Reviewed source component.
  Scope: Selected inactive source component for the existing task. The package documentation and source contracts define its retained scope; runtime admission and scientific qualification remain separate.
- [Fly increment score](implementations/fly-increment-score) — Reviewed source component.
  Scope: Paired fly-level neural-increment scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/nagellab/Kathmanetal2025)
- [Paper](https://www.nature.com/articles/s41467-026-75945-2)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
