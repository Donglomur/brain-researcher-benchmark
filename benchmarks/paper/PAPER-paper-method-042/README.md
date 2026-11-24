# UMBRAE: Unified Multimodal Brain Decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-042`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The source v2 Table 2 provides a complete ordered grounding endpoint for all four original subjects. This design preserves that per-subject result vector, rather than an invented pooled paper score. Native annotation/order, author-scoring parity, baseline execution and a valid improvement decision are not yet admitted.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Released output scoring reference](docs/released-author-reference-rescore-20261124.v1.json): Complete released-output scoring for four subjects and 2,419 query identities per subject: two source-seed 80-cell panels plus one keyed float64 panel. Rounding agreement is not new fMRI inference or universal scorer equivalence.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-paper-method-042`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 127335 bytes; SHA-256 `670a1e5086fa514fc88ffb097d97702b8bc26a9c063f63d09c1541233b4ecc55`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [Complete released UMBRAE author-reference rescore](docs/released-author-reference-rescore-20261124.md)
- [Released UMBRAE author-reference rescore aggregate evidence](docs/released-author-reference-rescore-20261124.v1.json)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective BrainHub referring-expression grounding scoring with per-subject All-category accuracy at strict IoU greater than 0.5, secondary salience summaries, paired controls and shared-image uncertainty. Authentic annotation/order membership, model/reference execution, actual exposure and intervention fidelity, rights and protected isolation remain held. Captioning, transfer and subject adaptation are outside this component; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Raw response parser v1](implementations/raw-response-parser-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Released reference rescore v1](implementations/released-reference-rescore-v1) — Reviewed source component.
  Scope: Trusted operator scoring route for complete released UMBRAE author outputs: four subjects, original 982-image/2,419-query support and the complete 80-cell panel under two prespecified source hash seeds, with separate keyed/order/precision diagnostics. Observed agreement is limited to those released outputs and is not universal scorer equivalence for future candidates. Independent fMRI inference, exact historical table-producing lineage, protected participant execution, candidate improvement, whole-paper reproduction and full benchmark readiness remain unestablished.
- [Endpoint vector v2](implementations/endpoint-vector-v2) — Reviewed source component.
  Scope: UMBRAE original endpoint vector. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2404.07202)
- [Code](https://github.com/weihaox/UMBRAE)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/download_data.sh)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/inference.py)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/train.py)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/train_brainx.py)
- [Code](https://huggingface.co/datasets/pscotti/naturalscenesdataset/tree/main/webdataset_avg_split)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/LICENSE.txt)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/README.md)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/main/umbrae/download_data.sh)
- [Code](https://weihaox.github.io/UMBRAE)
- [Paper](https://arxiv.org/abs/2404.07202)
- [Source](https://huggingface.co/api/datasets/pscotti/naturalscenesdataset)
- [Source](https://huggingface.co/datasets/weihaox/brainx/resolve/main/all_images.pt)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
