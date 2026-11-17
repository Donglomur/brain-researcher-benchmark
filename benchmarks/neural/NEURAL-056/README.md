# Image-to-EEG visual-response encoding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-056`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

The measured full80-repeat test-image EEG mean, with17 released noise-normalized coordinates ×100 source time samples per image.

**Source delivery:** partial\_delivery. A documented shared source dependency contains a complete ten-person image-to-EEG programme/scorer, but it is not a new primary runtime registration. This encoding endpoint intentionally differs from the source paper random-half endpoint and has no authentic execution or checkpoint qualification.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | The task gives images and withholds neural responses; revealing neural traces would change/leak its encoding target. Image-only prediction could be a separate direct-model condition but is not interpretation of observed neural data. | A separate measured-neural-input target is needed for direct neural interpretation. |
| Typed viewer | not\_suitable | Viewing held neural target waveforms is incompatible with this encoding endpoint. A stimulus-image viewer would preserve image encoding but cannot be reported as neural-observation interpretation. | Define a separate neural-input assay if that ability is desired. |
| Tool assisted | not\_delivered | No per-query tool-assisted investigation is delivered. I inspects its own training X/Y through bounded Python tools before sealing train/query source. Fresh context per inner/final training context and arm; no query inputs/held responses during investigation; only aggregate development selection crosses contexts. | Provider/tool boundaries and full input/execution qualification.; Implement a participant-facing held-query investigation condition if this capability is required; do not relabel training-only investigation as query interpretation. |
| Frozen program | source\_available | F commits complete train/query code and configuration roster before neural views. Independent training and query processes; frozen model and train-only statistics; all arms complete. | Actual native execution and complete checkpoint/source qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15596 bytes; SHA-256 `46be3d1606b768849a8836cccaf6ac51709c074718531eb3bdd79e15a259880b`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Four programmes source v1](../../shared/four-programmes/_four_programmes_source_v1) — Shared source distribution.
  Scope: NEURAL-056 is a documented dependency, not a new primary runtime registration. CriticalInit is named in the notice, but its exact registered-ID relationship is not inferred here. Keep combined-distribution license and provenance records attached to the closed source tree.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.osf.io/v2/licenses/563c1cf88c5e4a3877f9e96a/)
- [Source](https://api.osf.io/v2/nodes/anp5v/files/osfstorage/)
- [Source](https://api.osf.io/v2/nodes/y63gw/files/osfstorage/)
- [Source](https://doi.org/10.1016/j.neuroimage.2022.119754)
- [Source](https://github.com/gifale95/eeg_encoding)
- [Source](https://osf.io/3jk45/)
- [Source](https://raw.githubusercontent.com/gifale95/eeg_encoding/101997d4f14c41b615bcaf8c0907740106d260c5/04_synthesizing_eeg_data/linearizing_encoding_utils.py)
- [Source](https://raw.githubusercontent.com/gifale95/eeg_encoding/101997d4f14c41b615bcaf8c0907740106d260c5/LICENSE.md)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
