# Natural-video EEG response encoding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-079`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Held video EEG response arrays, independently joined to each participant, channel and time coordinate; the answer is measured EEG rather than the source paper narrative.

**Source delivery:** partial\_delivery. A full encoding-source programme and grader exist, but deployment and authentic numerical execution remain unqualified. Its delivered target is held EEG prediction, not native interpretation of observed EEG; preserve the scoped distinction.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | The query observation is a video feature tensor and the requested answer is held EEG; showing the target EEG would reverse the task. A direct neural-waveform interpretation assay would require a separately specified endpoint and must not inherit encoding scores. | No direct neural-observation condition for this encoding target. |
| Typed viewer | not\_suitable | A viewer of held EEG would expose the prediction target; viewing stimulus material does not become neural-signal interpretation. Any future stimulus viewer must preserve the encoding target and be assessed separately. | No typed neural-viewer endpoint is delivered. |
| Tool assisted | source\_available | Controller.investigate supplies an actual provider action loop with run\_python, optional fit\_helper and finish actions over the permitted current context; source is unconfigured and not executed here. Fresh query state, same permitted information within each paired tool condition, no query labels or grading feedback; provider/runtime qualification remains external. | Unconfigured native/provider transport and authentic full-input execution. |
| Frozen program | source\_available | Controller.preseal freezes run(request) source before numeric exposure and run\_candidates executes it for training, each current video and report; provider transport rejects F calls after exposure. Commit global policy before numeric exposure; no source revision or provider call during frozen execution; native reproduction is separate. | Authenticated training/query installation and independent execution qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 20475 bytes; SHA-256 `19abad85a0fc2e571676afafb21180d1876ba0037e07ff1c1579e5579200b69a`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Neural 079](implementations/neural-079) — Task source archive.
  Scope: Source archive remains an implementation resource; relocation does not establish configured deployment or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://arxiv.org/abs/2608.28768)
- [Source](https://github.com/OpenNeuroDatasets/ds008257)
- [Source](https://github.com/gifale95/EMD)
- [Source](https://openneuro.org/datasets/ds008257)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
