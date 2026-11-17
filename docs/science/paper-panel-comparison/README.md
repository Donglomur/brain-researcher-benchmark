# Complete paper panels

`paper-panel-comparison/v1` adds a strict metadata comparator for papers whose original task has several required outcomes. It preserves their units, directions, source support and individual results. It produces no pooled average or win-count score. Existing `paper-improvement/v1` contracts and selectors are unchanged.

The comparator checks declared evidence consistency and a finite numerical rule. **It does not authenticate artifacts, execute a scientific evaluator, establish scientific superiority or certify current SOTA.** Its `paper_win` and `scientific_superiority` outputs are always `null`, including when the numerical rule passes. Registry adoption, task-specific inferential evaluation and independent result review remain separate.

## Scientific groups, source coordinates and controls

A group names a scientific endpoint and its independent unit. A comparison coordinate represents an explicitly adopted, source-aligned result quantity, such as an original reported group statistic or contrast. It does not automatically represent each raw participant, neuron, session or time-support row. The source-to-endpoint mapping must be resolved before selecting comparison coordinates. Complete cohort, audit and paired-uncertainty support can remain outside the numerical comparison roster and must still be preserved by the task-specific evaluator. For the resulting adopted comparison quantities, the exact contract fixes every coordinate, group, role, metric, unit, direction and support key; a result cannot omit, duplicate, relabel or add coordinates.

Every group and coordinate has an explicit role:

- `score`: an original outcome to compare in its original direction. Every score coordinate is protected against regression; only the predeclared eligible subset can supply the meaningful gain.
- `control`: a required negative control or fidelity output with a separately justified inclusive interval or one-sided bound. Controls never supply a gain, have no improvement direction and cannot be marked gain-eligible. Missing or unresolved control criteria prevent admission. A better shuffled-label score does not count as scientific improvement.

The candidate panel is not automatically the shape of every author baseline table. For example, several author model variants may supply competing references for one candidate endpoint. The task-specific source manifest and protected evaluator must identify the scientifically comparable reference for that candidate coordinate. They must not require the candidate to invent outputs for author model variants it does not implement. Source reproduction may separately require a larger original-author panel. This comparator checks the frozen resulting mapping and values; it does not recover or authenticate that mapping.

## Finite numerical rule

For each score coordinate, the comparator selects the strongest of the frozen published value, the current reproduced-author value, and any frozen reproduced-author value. It uses declared decimal numeric values throughout, including mixed integer/float ordering, domains, tolerances and budgets.

The finite numerical rule passes only when all of the following hold:

1. Every required coordinate and every source/evaluator/condition/freeze/budget binding passes admission.
2. Every reproduced-author value is within the source-justified reproduction tolerance of its published value. A pinned reproduced reference cannot be replaced by a weaker reference beyond tolerance; even within tolerance, the stronger pinned value remains in the comparison.
3. No score coordinate regresses against its strongest reference. This comparison has no hidden epsilon or allowance for a small regression elsewhere.
4. At least one predeclared eligible score coordinate meets its positive, justified meaningful-gain threshold using its frozen strict or inclusive operator.
5. All mandatory controls satisfy their separate frozen constraints.

A positive result means dominance under this **prospective finite benchmark rule**, not that the original paper used that superiority rule. Task authors must first recover the actual source result unit. Raw participant or trial scores are ordinarily support for the reported statistic and its uncertainty; they must not automatically become pointwise nonregression constraints. This generic comparator does not authorize changing an original group-level objective into participant-level Pareto dominance. It does not handle uncertainty by treating every support row as independent or by converting the number of wins into evidence.

Unknown reference selection, source support, direction, reproduction tolerance, meaningful gain, control constraints or execution bindings remain explicit blockers. An author SEM, rounding precision or convenient epsilon must not be substituted for a tolerance or meaningful effect. The examples retain these unknowns.

`metadata_ready` means only that this finite metadata policy is complete. `compare()` rejects execution admission for a `source_unresolved` or `design_ready` declaration. There is no `improvement_ready` value in this interface. Invalid metadata is `rejected`; incomplete policy is `unqualified_contract`; structurally admitted final evidence is `admitted_on_declared_evidence`. Numerical failure is then reported separately through the reproduction, nonregression, control and dominance fields.

## Source, assistance and episode bindings

The module reuses the scalar contract's strict JSON parser/schema primitives, source-paper evidence vocabulary, original same-task anchors, candidate and evaluation provenance, chronological freeze and cumulative access/resource budget structures. It adds panel identities, source-manifest and lineage descriptors, and exact assistance-condition manifests. The scalar source remains unchanged.

The two assistance conditions bind the same paper, data and tool policy; official code is their sole declared addition. `paper_data` has no official-code manifest; `paper_data_official_code` requires one. Each result's exact condition and manifest digest must also appear in both its candidate-freeze and final-evaluation records, so changing only top-level labels is rejected. The evaluator-owned author reference can legitimately be shared between arms and use author code; it is explicitly labeled as a reference, not falsely labeled as a paper-only participant.

All these records are declarations. Trusted collection must still verify their artifact hashes, exposure rules, timing, full cumulative costs, held-out isolation and original evaluator execution. Setting a source status to `verified` or furnishing plausible hashes cannot turn the module's result into independent scientific proof. Claimed scientific booleans and unsupported result fields are rejected.

## API

```python
from neurobench.paper_panel_comparison import (
    contract_validate, contract_digest, loads_contract, compare,
)

contract = loads_contract(contract_json)
errors = contract_validate(contract, task_id="PAPER-...")
report = compare(contract, loads_contract(result_json))
```

`loads_contract` rejects duplicate keys, non-finite/out-of-range JSON numbers and unpaired Unicode surrogates. Both contract and result objects undergo the same strict checks before comparison. The module performs no artifact I/O when comparing objects; `load_contract(path)` reads only the explicitly supplied JSON metadata file.

The exported [schema](contract.schema.json) contains both contract and result definitions. Admission includes additional cross-field/source-reference checks in Python. `scientific_inference` preserves the task's declared method, independent unit and multiplicity policy, but this module does not execute it or accept a caller-controlled scientific-success flag.

## Blocked source examples

- [Cardiac ECG reconstruction source mapping](examples/cardiac-source-endpoint-mapping.json): a non-executable mapping, not a comparison contract. Its 120 participant-condition r rows remain mandatory cohort, audit and paired-uncertainty support in six source groups. The exact original reported group statistics or contrasts and fold-to-r reduction must be recovered before any comparison target is defined. Neither pointwise nonregression, an automatic six-group Pareto objective nor a pooled 120-row mean is adopted. Source score-table identity is retained; no score-table body was reread.
- [NEDS](examples/neds-nine-metrics.contract.json): all nine original encoding/decoding metrics retain their different units. Known rounded NEDS summary values are preserved, but NEDS is not assumed to be the strongest relevant author comparator in every metric. Alternative comparator values, replay, tolerances, meaningful gains and paired animal-level inference remain unresolved. Published SEMs are not used as tolerance bounds.

[Source example evidence](examples/SOURCE_EXAMPLES.json) records exact metadata descriptors and limitations. NEDS remains a blocked comparison-contract illustration. Cardiac is solely an unresolved source mapping and is deliberately rejected by the comparison-contract validator. Neither is an activated benchmark or has an evaluator/condition/budget admission policy. No scientific data, author model or candidate result was generated for these examples.

## Validation

Run the generated contract controls with:

```sh
python -I -S -B -m unittest discover -s tests/framework -p 'test_paper_panel_comparison*.py' -v
```

These controls exercise complete rosters, hidden regressions, scalarization rejection, score/control separation, decimal arithmetic, stronger references, assistance binding, invalid metadata and unqualified scientific claims. Their numeric fixtures are invented software-test inputs, never benchmark results. Adding this component does not change any benchmark's readiness or result count.
