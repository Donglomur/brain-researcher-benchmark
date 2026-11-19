# Cross-laboratory auditory brainstem threshold inference from complete waveform stacks

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-SCOPE-20261114-ABR-TRANSFER`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Expert threshold in dB SPL for each animal×stimulus series, or an explicitly documented censored interval; it is an annotation of averaged physiology.

**Source delivery:** partial\_delivery. Threshold-loss arithmetic and complete prediction ledgers are delivered, but the evaluator deliberately emits aggregate scores only for generated engineering controls. Native annotation semantics, complete waveform census and source-only comparators must be authenticated before an actual transfer score can be admitted.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Complete numeric or fixed waveform stack plus four labeled source stacks is scientifically meaningful. No tools, source lookup or target labels; all levels and samples must fit the frozen context. | Authentic serializer, complete packet capacity and transport not delivered. |
| Typed viewer | not\_delivered | A typed waveform-stack viewer could expose time/level panels without raw export. Actions must retain full stack access and hide annotations; no viewer currently exists for this registration. | Typed action protocol and observation-only renderer. |
| Tool assisted | not\_delivered | Per-case numerical investigation of the same complete stack and identical calibration support. No target feedback; models fitted on extra support form a separately named information condition. | Candidate investigation interface, fixed tools and isolated episode. |
| Frozen program | not\_delivered | Freeze waveform predictor and fitting recipe before held-lab cases. Identical four-stack evidence in matched mode; full-support source-only programme reported separately. | Only scoring exists; no waveform predictor/executor or qualified authentic input route. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 35927 bytes; SHA-256 `901977bc05022d4923efd865161b344a20c46f1e1be12ddcfd01f53a92ec07d1`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Native inputs v1](implementations/native-inputs-v1) — Reviewed source component.
  Scope: Complete original three-archive native source producer with authenticated successful preparation and independent output audit: 104 animals, 936 target cases and all support traces retained. The three above-range target annotations, physical/acoustic binding, biological support mapping and competent comparison remain unresolved; candidate conditions and primary scoring are not admitted by source preparation.
- [Release annotation agreement v1](implementations/release-annotation-agreement-v1) — Reviewed source component.
  Scope: Separately named zero-labelled-support release-annotation-code agreement condition for all 936 cases/104 animals. Primary equal-animal exact code agreement and descriptive code-unit errors preserve numeric source code 100 without physiological reinterpretation. Exact generated controls passed; authentic model delivery/scoring and the original calibrated expert-threshold/four-stack task remain unadmitted. This component adds no benchmark family.
- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepared-threshold engineering evaluator with a complete prediction/failure ledger, equal-animal metrics, paired bootstrap and separate historical/paper threshold-rule diagnostics. Authentic aggregate scoring is unavailable: the native target/support census, annotations and censoring, physical units, waveform adapters, rights, source-only baselines and protected qualification remain held. The existing components-abr-protected-fold-runner relationship is retained as related source only; its runner capabilities are not inherited by this owned evaluator.
- [Series evaluator v2](implementations/series-evaluator-v2) — Reviewed source component.
  Scope: ABR threshold scorer: one case per animal and stimulus. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

## Related scientific source (different or narrower scope)

These artifacts provide related scientific context; they are not assigned implementations of this task.

- [Background classification runner](../../shared/abr/background-classification-runner) — Alternative released background classification diagnostic.
  Scope: 104-animal background classification is not the registered primary cross-laboratory threshold-transfer endpoint; shared cohort establishes relatedness only.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/ucsdmanorlab/abranalysis/tree/0369a215b429002c115af2ac1f0922bb190d5c1f)
- [Source](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13018588/fullTextXML)
- [Source](https://www.nature.com/articles/s41598-026-38045-1)
- [Source](https://zenodo.org/api/records/15619100)
- [Source](https://zenodo.org/api/records/17584961)
- [Source](https://zenodo.org/records/15619100)
- [Source](https://zenodo.org/records/17584961)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
