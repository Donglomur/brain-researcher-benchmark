# Mandatory owner-only scope clarification

`prepare_fold` and all returned views are trusted-owner preparation interfaces. Every role, including `test`, retains aligned behavior payloads. The test behavior values are held targets, not participant/model inputs. Returning an aligned test view to the owner is not authorization to expose it to a candidate or use it for behavioral-prioritized fitting, tuning, normalization or representation learning.

A future protected producer must independently enforce role visibility: only permitted training/development information may reach the participant/model; held behavior targets stay with the trusted evaluator. It must also enforce the frozen source/census identity, train-only transform provenance, complete supported evaluation, filtering/context purge, model reset use, and matched A/B permissions. The lazy view emits reset information but cannot force a downstream model to reset state.

This component proves no process isolation, protected target boundary, actual loader body authentication, runtime execution or scientific result. Its bridge intentionally leaves input_boundary_preserved and every scientific readiness flag false. No source/test bytes or selected numerical policy changed for this clarification; no replay is required.
