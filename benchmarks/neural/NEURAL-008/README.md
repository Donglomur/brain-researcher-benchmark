# EOG information beyond EEG and sleep timing

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-008`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Expert hypnogram stage labels for both observation arms and the deterministic paired differences from their independently committed prediction panels. The sign of the EOG contribution is unknown before evaluation and may be zero or negative.

**Source delivery:** partial\_delivery. Historical two-person paired scoring is documented, but the shipped score.py bridge points to an absent historical dependency. The current portable contribution helpers operate on an already admitted full153 grade; they do not deliver paired training or a raw-signal investigation. Restore the scorer/runner binding before advertising a runnable task.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Potential direct matched EEG versus EEG+EOG waveform interpretation using identical epochs, scales and context. Separate model contexts for each arm; no pretrained probabilities or feedback, and no opportunity to see EOG before the EEG-only response. | No delivered direct paired response collector, authentic waveform packet or model trial. |
| Typed viewer | not\_delivered | Potential typed multichannel waveform viewer with EOG disabled in EEG-only arm. The observation policy must be enforced by the viewer transport and paired response commitment, not a written instruction. | No task-specific typed-viewer or paired transport implementation. |
| Tool assisted | not\_delivered | Shared full153 investigation/report helper source, including matched signal contrasts and evidence-linked numerical claims. Requires separately admitted complete programme grade; helper arithmetic is not a standalone candidate episode. | The supplied contribution helper computes report arithmetic, not a per-case investigator episode; current complete delivery and authenticated grade producer are absent. |
| Frozen program | not\_delivered | Historical declared same-source programme executed independently in physically separated feature views. Both prediction panels must be committed before labels; existing manifests are lineage only. | Historical paired runner/scorer dependencies absent from this public closure; restore before claiming source-delivered execution. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 17978 bytes; SHA-256 `c6210c2c158e520cd087151c9c39f662e6b3091c794dc278c16086682a5e7b00`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Repository-depth locator corrected after relocation; 1 local scorer dependency is absent from the public source baseline and relocation ledger. Historical dependency names/pins remain unchanged. This bridge has not been made runnable or newly qualified by the reorganization. Other task artifacts are outside this finding.
- [Comparison contract](../../shared/sleep-eog/comparison-contract) — Comparison contract.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Historical fixed rf v1](implementations/historical-fixed-rf-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Paired program v1](implementations/paired-program-v1) — Reviewed task source component.
  Scope: Accepted source and generated-control evidence only. Artifact enrollment does not change task IDs, access modes, runtime selection, submission readiness, reproduction or improvement qualification.
- [Raw epoch companion v1](implementations/raw-epoch-companion-v1) — Reviewed source component.
  Scope: Separate neural008\_raw\_epoch\_four\_panel\_v1 source companion: restricted epoch viewer and same-epoch numerical programme, EEG-only versus EEG+EOG over5450 epochs nested in two exposed development people. Generated controls only; authentic assembly, provider/native qualification and scientific outcomes remain separate. Historical task/conditions and benchmark counts unchanged.
- [Finite paired scorer](implementations/finite-paired-scorer) — Reviewed source component.
  Scope: Finite paired sleep-stage scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/mne-tools/mne-python)
- [Source](https://physionet.org/content/sleep-edfx/1.0.0/)
- [Source](https://physionet.org/files/sleep-edfx/1.0.0/RECORDS)
- [Source](https://physionet.org/files/sleep-edfx/1.0.0/SHA256SUMS.txt)
- [Source](https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/SC4001E0-PSG.edf)
- [Source](https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/SC4001EC-Hypnogram.edf)
- [Source](https://raw.githubusercontent.com/mne-tools/mne-python/0265fc9a575f125d95c5c92f672fd0bb85cfab2d/mne/datasets/sleep_physionet/age_records.csv)
- [Source](https://raw.githubusercontent.com/mne-tools/mne-python/0265fc9a575f125d95c5c92f672fd0bb85cfab2d/tutorials/clinical/60_sleep.py)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
