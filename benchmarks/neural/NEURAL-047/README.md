# Post-reversal turn probabilities from SAAV history in held-out worms

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-047`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Binary direction: dorsal=1 if the mean dorsal-positive head curvature in the first two native frames after reversal end is positive, ventral=0 if negative; zero direction is an explicit source exclusion. This is a measured behavior target, not agreement with the paper narrative.

**Source delivery:** partial\_delivery. A complete-panel preparation/scoring and F/I programme source exists for a specified processed-SAAV landmark task. Native animal/clock/SAAV admission and deployment remain unconfigured, so source completeness is not an executed held-worm benchmark.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Possible future no-tools case view of numeric or rendered matched SAAV/behavior histories. Freeze display, demonstration labels and query histories; require all query probabilities without tools or held labels. | No direct-response packet/transport or direct model trial. |
| Typed viewer | not\_delivered | Possible waveform/history viewer with typed time/channel actions. Only permitted past history; no raw source lookup, future curvature or evaluator output. | No task-specific typed viewer or rendering equivalence proof. |
| Tool assisted | source\_available | I source permits fresh per-outer-fold/arm investigation and programme creation from the same training/query histories as F. Seal agent policy before study exposure; no cross-fold/arm state or private feedback; account tools and compute. | Deployment and physical case isolation are unqualified. |
| Frozen program | source\_available | F source applies one precommitted method and fit/adaptation recipe to all N/B/NB animal folds. Freeze programme before any outer context; only current training-worm labels may support fitting and inner selection. | Authentic prepared input, references and full execution remain unqualified. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15027 bytes; SHA-256 `bc879ac1ebd895f9fd4a4a056f896772acf23c7f8a5ed3854677251984b67eae`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Neural 047](implementations/neural-047) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://datadryad.org/dataset/doi:10.5061/dryad.8sf7m0cz2)
- [Source](https://datadryad.org/terms)
- [Source](https://github.com/flavell-lab/SAAV_Decoding)
- [Source](https://raw.githubusercontent.com/flavell-lab/SAAV_Decoding/c7e7e18a84cde5dc02df9d63492293b38402eb2c/DecodingMain.ipynb)
- [Source](https://raw.githubusercontent.com/flavell-lab/SAAV_Decoding/c7e7e18a84cde5dc02df9d63492293b38402eb2c/kfold.py)
- [Source](https://raw.githubusercontent.com/flavell-lab/SAAV_Decoding/c7e7e18a84cde5dc02df9d63492293b38402eb2c/load_data.py)
- [Source](https://www.nature.com/articles/s41593-026-02257-5)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
