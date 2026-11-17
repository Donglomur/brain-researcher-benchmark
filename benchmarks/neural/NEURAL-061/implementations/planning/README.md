# NEURAL-061 study planning component

This component supplies standard-library Python source for inspecting the prospective structure of NEURAL-061: study choices, expected prediction records, author contexts, and symbolic operation demand. It is incomplete and does not run a neuroscience benchmark. It contains no recordings, cohort identities, target values, fitted models, results, or execution environment.

The seven Python modules are an unchanged, import-complete subset of the programme source. Python 3.10 or later is required by the type syntax. Only Python's standard library is imported; no installation command, scientific execution entry point, or data download is supplied.

## What it can represent

The current policy is A0: a source-frozen programme (F), without a task-trained reference tool (T0), and one method-authoring repeat. T0 still permits ordinary Python fitting in the intended future benchmark. It does not mean that the participant has no tools.

The selected scientific axes are signed wheel velocity, ten units in each matched population, real anatomy, all ten matching seeds, and every region of an earlier complete grey-matter ontology. The reference has six arms (B, BR, BC, R, C, ZERO); candidate programmes use BR and BC. B is a common background population, R the selected region, and C a matched control population. The eventual comparison concerns conditional predictive information, not causal necessity or a ranking of regions.

The metadata contract specifies 423 source sessions from 126 animals and 29 evaluation sessions from 13 disjoint animals, with five whole-animal source folds. These are prospective source requirements. This release supplies no authentic roster and does not establish that a user's data satisfy them. The actual region count and eligible support are unknown.

A1, A2, and A3 describe future paired F/I, tool, and repeated-authoring extensions. They are inspectable definitions; `StudyPolicy.require_selected()` refuses them. The full reference sensitivity and exploratory catalogues remain explicitly represented as prospectively unselected work. Their presence is not evidence that any such work ran.

## Interfaces and input obligations

| Module | Public use |
| --- | --- |
| `contracts.py` | Closed structural checks and fixed study vocabulary, including cohort and atlas metadata requirements. |
| `policy.py` | Construct and inspect the initial policy or prospective tier definitions. |
| `catalogue.py` | Build the complete selected output-key graph and retain the full held catalogues. |
| `access.py` | Describe source-only F contexts or isolated animal/cell/arm I contexts; check declared view relationships. |
| `admission.py` | Identify missing concrete runtime producers and refuse native admission. |
| `resource_demand.py` | Enumerate the planned preparation, reference, candidate, publication, grading, and cleanup operations. |

`catalogue.build(selected, regions, public)` expects a complete, previously checked 452-session metadata map. Each map entry needs a unique ordinal, animal, and source/evaluation role. Its region tuple must be the sorted, unique, complete earlier region roster. The wider programme's authentic metadata capture and alias producer are not included. Structural checks are not data authentication, privacy enforcement, or a secure sandbox.

After a valid catalogue exists, `resource_demand.compile_plan(catalogue)` exposes ordered operation records. All input, output, state, native-limit, and provider-limit extents remain unknown (`None`). `OperationPlan.require_native_allocation()` always raises `MissingNativeProducers`. Neither a valid catalogue nor an operation count grants permission or resources to execute it.

For source inspection from this component directory, a minimal policy example is:

```python
from n061.policy import policy

selected = policy()
selected.require_selected()
# Inspect selected.head, selected.seeds, selected.panels, and selected.reference_arms.
```

This example was not executed as part of the publication audit. Validation of this release was limited to reading the exact source, parsing its syntax, checking its import closure, and auditing outgoing content. No scientific or numerical computation, data acquisition, model run, or runtime qualification was performed.

## Incomplete programme and open gates

All 15 qualification gate groups remain open:

1. Original data access and custody.
2. Authentic cohort, probe, animal, atlas, and excluded-session joins.
3. Interval, dtype, mask, and physical-unit parity.
4. Authentic matching, quality control, and biological support.
5. Resource feasibility, capacity enforcement, and equal panel budgets.
6. A concrete launcher, provider broker, and isolated child.
7. Dependencies, safe state capture, and trained-tool transport.
8. Reference implementation parity.
9. Authentic scoring, leakage, and missingness checks.
10. Scientific sensitivity checks and a valid temporal null.
11. Exposure and privacy assessment.
12. Subsequent runtime and source qualification.
13. Inferential power and population limitations.
14. Precommitted claims and a blinded reasoning rubric.
15. Complete operation observers and the late target boundary.

The full preparation, numerical reference, participant controller, scoring, and reporting modules are outside this small release. Its context checks do not implement physical isolation. Its operation records do not demonstrate affordable execution. It supplies no empirical qualification, new benchmark registration, or increase in ready benchmark count.

The intended evaluation is observational and retrospective. Sessions and matching seeds do not increase the number of independent animals. A0 alone cannot establish an F-versus-I or trained-tool effect. These constraints remain relevant when extending this source.

## Provenance and license

This is project-authored planning code under the accompanying MIT license, also used by the repository root. No third-party implementation or primary article is bundled. The upstream task vocabulary is anchored to the public [BrainWideBench source revision](https://github.com/brainbench-org/ibl-bwb/tree/6fbd666fe8170a2165f5198c1f490911424a654d); the same identifier appears in `contracts.COMMIT`. That reference identifies background vocabulary and data conventions, not a source of runtime authority or a license for external datasets.

Only the component's source, this README, and the MIT notice belong to its public payload. No private review records, acquisition artifacts, tool outputs, or historical repository content are part of it.
