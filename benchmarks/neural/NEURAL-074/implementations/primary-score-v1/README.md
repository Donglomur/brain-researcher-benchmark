# NEURAL-074 selected primary score

This additive scorer implements the prospective primary already stated in the
[current task contract](../../understanding.v1.json): shared-components minus
rank-matched-ridge signed Pearson map correlation. It leaves the historical
agent operator and its scientific modules unchanged.

`primary_score.summarize_primary` consumes the existing fixed-programme
`CaseEvaluation` records for all 13 declared people × 51 endpoints. It verifies
complete, unique case identities and selected family assignments; requires all
three fixed arms; validates finite metric values and undefined-correlation
status; and checks the six recorded signed effects against the arm quantities.
It averages endpoints within family, families within person, then the 13 people.
Negative effects remain negative. Any unpaired or undefined member prevents the
corresponding pooled contrast, while all 663 dispositions and all person/family
cells remain in the result. Full-rank-ridge and direction-aligned MSE/MAE
contrasts remain descriptive companions.

`evaluate_primary` calls the existing complete-batch evaluator before attaching
this selected summary. Thus the predecessor's complete prediction preflight,
independent support check, commitment match, finite prediction decode before
any target read, and target/source/geometry checks still run. The returned
summary binds the prediction commitment, programme protocol, support and
population identities. These labels do not authenticate an operator or prove
that selection preceded outcomes.

The exact version is `neural074-primary-correlation-gain-v1`. An operator must
select and authenticate this source version before protected scoring, along
with the unchanged `agent-operator/source/n074` closure. Put those two source
directories on the evaluator's import path; then call:

```python
from primary_score import evaluate_primary

case_evaluations, report = evaluate_primary(
    committed_result, independently_selected_commitment, selected_population,
    protected_reader, maximum_map_bytes,
    expected_support_identity=selected_support_identity,
    expected_map_length=selected_map_length,
    support_authority=independent_support_authority,
)
```

This entry evaluates the fixed three-arm programme. An arbitrary submitted
agent's `n074_operator.panel.Comparison` records are rejected: they do not
establish that the candidate is the shared-components arm. Neither direct
observation nor viewer interpretation is implemented here.

The score binding does not select population inference. `primary_decision` and
`population_inference` remain `None`: participant-cluster uncertainty, family
dependence and companion multiplicity still need a separate prospective
protocol. The complete authentic map census, reviewed endpoint taxonomy,
independently selected geometry, target custody, native runtime and actual
scientific execution remain unqualified. This source is not a ready benchmark.

## Source and validation scope

The inherited declaration names the official IBC analysis revision
[`2d9a6852bc7e3b164adef28b02b4d38d386c53ac`](https://github.com/individual-brain-charting/public_analysis_code/tree/2d9a6852bc7e3b164adef28b02b4d38d386c53ac).
That is the map-analysis source, not an author implementation of this benchmark's
unseen-task predictor. The registered prospective metric and the unchanged
local `n074` scorer are the implementation basis. No new download, authentic
map read, training, inference or model trial was performed for this component.

`test_primary_score.py` uses generated scalar score records over the full
declared roster. Its deliberately unequal families distinguish the selected
hierarchical average from pooled-map averaging. Controls also cover negative
gains, companion directions, undefined correlations, retained failures,
missing/duplicate identities, changed families, nonfinite and conflicting
scores, condition rejection, ordering, and the existing preflight's rejection
before target access. These are software controls, not scientific outcomes.
Run this file only through the coordinated lightweight test pool during the
parallel construction wave. Existing source-selector/CI enrollment and any
canonical contract update belong to integration.
