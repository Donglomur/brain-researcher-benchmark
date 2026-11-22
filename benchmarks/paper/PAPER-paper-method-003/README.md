# REVE: A Foundation Model for EEG – Adapting to Any Setup with Large-Scale Pretraining on 25,000 Subjects

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-003`
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

**Disposition:** design\_ready. The complete original PhysioNet-MI panel is authenticated and prepared: 654 imagery EDFs from all 109 participants yield 9,837 epochs on the original split, and the full-test numerical scorer/comparator has passed an authentic-data software control. This establishes source preparation and scoring, not an author baseline. Historical preprocessing, Table 12 classifier/checkpoint parity and seed/run aggregation remain unresolved. Candidate outcome pending: no candidate comparison has run; absence of that attempt is not a benchmark-construction blocker.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Paper source preparation](../../../docs/status/reve-source-preparation-20261116.json): Complete authentic PhysioNet-MI source preparation under the released direct-200-Hz profile and a fixed-output full-test scorer/comparator software control. This is not trained REVE performance, author-baseline qualification, historical paper reproduction or same-task improvement.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-paper-method-003`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18826 bytes; SHA-256 `5efe0f0b62682a35184be87a91a64ac7c8d9ec78f9076297e80dc78483923423`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Authentic participant-material export receipt](docs/authentic-material-export-20261117.json)
- [CPU compatibility evidence (2026-11-22)](docs/cpu-compatibility-20261122.json)
- [CPU compatibility result and limitations (2026-11-22)](docs/cpu-compatibility-20261122.md)

## Implementation artifacts

- [Paper paper method 003](implementations/paper-paper-method-003) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original physionet](implementations/original-physionet) — Original panel preparation and scoring.
  Scope: Original 109-participant PhysioNet acquisition/preparation, full-panel pooled balanced-accuracy/kappa/weighted-F1 scoring and strict author checkpoint adapter. Preparation and fixed software controls do not establish source classifier, historical seed roster, filter/checkpoint parity, paired candidate execution, same-task superiority or current SOTA.
- [Development boundary v1](implementations/development-boundary-v1) — Reviewed source component.
  Scope: Reviewed original-reference and development-boundary source. Development/test packaging, GPU execution, qualified reference/candidate material, and Table12 preprocessing/checkpoint/seed uncertainty remain separately unresolved. No scientific result or runtime qualification follows from source ownership.
- [Matched reference v1](implementations/matched-reference-v1) — Reviewed source component.
  Scope: Reviewed original-reference and development-boundary source. Development/test packaging, GPU execution, qualified reference/candidate material, and Table12 preprocessing/checkpoint/seed uncertainty remain separately unresolved. No scientific result or runtime qualification follows from source ownership.
- [Candidate materials v1](implementations/candidate-materials-v1) — Reviewed source component.
  Scope: Complete original 654-record, 109-person map/export/restore source with shared opaque test-epoch shuffling in both paper conditions and unchanged private source-order scoring support. Authentic export, protected candidate delivery, pretrained-access provisioning and qualified historical reference remain separate requirements; generated metric controls are not model results.
- [Opaque submission v1](implementations/opaque-submission-v1) — Reviewed source component.
  Scope: Opaque submission adapter source preserves original participant, collection and scoring boundaries. Generated adapter controls are separate from protected runtime/image execution, authentic candidate execution and scientific reproduction or improvement. Existing runtime gates and canonical selectors remain unchanged.
- [Phase materialization v1](implementations/phase-materialization-v1) — Reviewed source component.
  Scope: Reviewed source for development and opaque-test phase materialization on the declared full panel. Generated software controls do not establish authentic material delivery, model execution, paper reproduction or improvement, scientific access qualification, or Table 12 parity.
- [Release restoration v1](implementations/release-restoration-v1) — Reviewed source component.
  Scope: Reviewed source binding release, arm, profile, roster, material and prediction identities through the existing inverse restoration and native-score interface. Generated software controls do not establish deployment, authentic candidate execution, paper reproduction or improvement, or scientific readiness.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2510.21585)
- [Code](https://github.com/elouayas/reve_eeg)
- [Code](https://huggingface.co/brain-bzh/reve-base)
- [Code](https://huggingface.co/datasets/brain-bzh/reve-dataset)
- [Code](https://physionet.org/content/eegmmidb/1.0.0/)
- [Code](https://proceedings.neurips.cc/paper_files/paper/2025/hash/20a917f77773ac0fa8bea2bdd6606b66-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/elouayas/reve_eeg/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/LICENSE)
- [Code](https://raw.githubusercontent.com/elouayas/reve_eeg/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/README.md)
- [Paper](https://proceedings.neurips.cc/paper_files/paper/2025/hash/20a917f77773ac0fa8bea2bdd6606b66-Abstract-Conference.html)
- [Source](https://physionet.org/content/eegmmidb/1.0.0/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
