# NEURAL-095 evaluator data: attribution, reuse and exposure

This notice accompanies the three unchanged JSON artifacts in the [NEURAL-095 evaluator release](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/neural-095-four-cell-reference-v1). It can travel with those files without downloading a recording or running the converter. The artifacts retain their original names, bytes and values; this notice supplies no new targets or predictions.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `reference_grade.json` | 23,286 | `414e09845d11548e96c921b202491bc7680ad6ecec96a0433b2676feeec5d823` |
| `reference_commit.json` | 473 | `238d86371eccca7fe32635c63e36f004eab499f8f5d4781f17cb9ccb387a4dfe` |
| `reference_audit.json` | 585 | `eaf3ad0f754f8096dfdfd68a584f541ece0ea1190ad0b1a947a41900297c3272` |

## Source attribution and permission

Credit **Hansem Sohn and Mehrdad Jazayeri (2024)** for *DMFC_RSG: macaque dorsomedial frontal cortex spiking activity during time interval reproduction task*, [DANDI 000130, version 0.241017.1448](https://doi.org/10.48324/dandi.000130/0.241017.1448). The [version's primary metadata](https://api.dandiarchive.org/api/dandisets/000130/versions/0.241017.1448/) specifies **Creative Commons Attribution 4.0 International**. The selected asset is `c90cbccc-31a5-4815-88e6-822d8c5ca68c`, `sub-Haydn/sub-Haydn_desc-train_ecephys.nwb`; its [version-specific metadata](https://api.dandiarchive.org/api/dandisets/000130/versions/0.241017.1448/assets/c90cbccc-31a5-4815-88e6-822d8c5ca68c/) establishes membership in that release.

The associated paper is Sohn, Narain, Meirhaeghe and Jazayeri (2019), [*Bayesian Computation through Cortical Latent Dynamics*](https://doi.org/10.1016/j.neuron.2019.06.012).

Subject to [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), licensed data may be shared and adapted. Retain applicable creator credit, source and license links, and modification notices. The license provides a [disclaimer of warranties and liability](https://creativecommons.org/licenses/by/4.0/legalcode.en#s5) and does not imply the original authors endorse this benchmark. This notice does not replace the license text or change its terms.

Project-authored implementation remains under its [MIT license](../../../benchmarks/neuroscience/neural-095-four-cell/LICENSE). Data attribution is separate from software licensing. No manuscript or RSG2prior code is included: an explicit repository-wide grant for [RSG2prior](https://github.com/hansem/RSG2prior) was not identified in the metadata, complete tree names or README checked on 15 November 2026. That bounded check is not a review of every source-file header. Public visibility and the DANDI data license do not supply permission to redistribute that separate code or article. The separately MIT-licensed nlb_tools package is not required or vendored here.

## Changes represented by the artifacts

The existing authored conversion selects all 748 TRAIN and 258 development trials from Haydn's 20161211 session, orders each split by observed Set, and retains all 40 held-in units. Neural features count spikes in four half-open 50 ms bins within `[Set−0.2 s, Set)`. The released behavioral `tp` is retained in milliseconds; it is not replaced by Go−Set. The paired cue-only view omits neural counts. Training folds, cues and elapsed clock remain fixed; there is no target or outlier filtering.

These three artifacts record the existing five fixed-reference grades, their production commitment and an arithmetic audit. They are project-derived evaluation metadata, not source-paper reported results. This notice performs no fitting or recomputation and changes no numerical operand. Preserve the existing conversion's generated `DATA_NOTICE.md` when redistributing complete derived packets; use this notice for the separately distributed evaluator artifacts.

## Evaluation access is distinct from reuse permission

“Evaluator-only” describes the benchmark protocol: keep labels and reference artifacts outside producer mounts and scoring feedback until predictions are committed. It is not an additional restriction on rights granted by CC BY 4.0. Isolation during a run cannot undo earlier public disclosure.

The source and development labels are historical public material. The published grades also expose individual absolute-error information for singleton condition 23. Report results as descriptive performance on this exact one-animal, one-session development panel, not a secret test, an independent animal replication or demonstrated resistance to training contamination. Prior model exposure is not established by an offline run.

The [official NLB announcement](https://neurallatents.github.io/) states that its former private test evaluation data were released after EvalAI submissions ended in January 2026. Moving to that historical NLB test split therefore does not establish hidden evaluation. NLB's neural co-smoothing benchmark and this observed-Set behavioral prediction task also have different endpoints; their scores are not interchangeable.

The companion [rights and exposure record](NEURAL_095_RIGHTS_PROVENANCE_20261115.json) pins the inspected primary metadata. This notice closes the standalone artifact-notice gap; it does not assert an earlier licensing violation, certify a new host, or establish scientific qualification or submission readiness.
