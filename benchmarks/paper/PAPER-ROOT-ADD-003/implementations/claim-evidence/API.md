# Claim-to-evidence API

The entry is `adjudicate_engine(engine, report_node, claims, expert_reviews=())`. It consumes the current source-owned `Engine.products`, `Engine.plan['nodes']`, and `Engine.reference_selections` without mutating them. `adjudicate_collected(...)` exposes the same pure check for an already captured trusted operator context. Neither function verifies a signed issuer, starts a campaign, opens a target or returns scientific approval.

The O26 role is `all_main_and_SI_obligation_reports`, containing `language_complete_scientific_report_v2`. Its exact full S8 scope and all 184 ordered handles are mandatory. Each evidence envelope has the original `operator`, `cell`, `profile`, `status`, `data`, `pin` and `scientific_execution` fields. Evidence must be among that handle's `source_products`; the trusted plan's producer identity must match. Engineering markers and unavailable products cannot support scientific claims. This is meaningful only when the caller supplies actual operator-owned objects.

Every claim has exactly these fields:

```python
{
    'id': 'unique local claim ID',
    'kind': 'point_gain',
    'handle': 'an exact handle in the current source roster',
    'product': 'actual-node.candidate_reference_summary',
    'selection': {'method': 'actual method ID'},
    'asserted': -0.1,
}
```

At most 128 claims are admitted per report. An invalid overall report, unknown handle, duplicate claim ID or malformed closed envelope raises `ContractError`. An unavailable or inconsistent cited product gives a `blocked` claim without silently discarding it. A well-defined statement contradicting available values gives `unsupported`. A matching bounded statement gives `supported`; it is not a significance, causal or population verdict.

| Kind | Required original role | Selection | Asserted value |
| --- | --- | --- | --- |
| `correlation` | O14 `pooled_and_within_condition_metrics` | Exact `group` and `metric`: `pooled`, `condition_centered`, `B`, `D` or `S` | Numeric coefficient, or `None` for an explicitly undefined constant |
| `positive_within_condition_correlation` | Same O14 role | Exact `group` | `True`; both D and S must separately be defined and positive |
| `point_gain` | O27 `candidate_reference_summary` | `method` | Signed selected-reference loss minus method loss |
| `biological_participant_counts` | Same O27 role | Empty mapping | Exact search/modify unique-person counts, not row counts |
| `descriptive_A_B_difference` | Same O27 role | Frozen `contrast` name | B gain minus A gain on the source-declared method pair |
| `conditional_interval` | O28 `paired_intervals` | `method` | `{'low': ..., 'high': ..., 'interpretation': 'conditional_sensitivity'}` |

Point support is checked against `node['config']['inference']['method_roster']` and `cohort_people`. The selected reference is taken from `reference_selections[node['reference_selection_scope']]['selection']['reference_id']`; it is not a candidate-selectable comparator. Descriptive A/B pairs come from `node['config']['inference']['A_B_pairs']`. Point strata must have all D/S observations, exactly three search and two modification people with disjoint identities, identical full method support and nonnegative loss. Cohort and overall loss arithmetic, signed gains and declared counts must agree. The checker reads summary metadata, not prediction or target arrays, so it cannot independently prove the original acquisition or measurement truth.

Interval checks bind the complete returned manifest to `Engine.resampling['manifest']`, the draw count to `node['config']['global_resampling']['B']`, and support identity to both that global plan and `config['inference']`. They retain every planned draw, every method and source-produced bounds, verify available draw losses/gains, and reject failed/removed joint draws. They do not regenerate random indices or recompute quantiles. The original source's global family/person draw law, numerical tests, practical margin and calibration remain independent obligations. Returned scopes, observations and expert lists are detached from all source objects.

These known-upgrade kinds take an empty selection and `asserted=True`: `population_generalization`, `causal_code_benefit`, `neural_understanding`, `novel_intervention_gain`, `model_independent_ceiling`, `formal_significance`, and `meaningful_improvement`. Given a bound current product, each returns its specific unsupported inference rather than treating an expert's supported flag as a waiver. They describe claims stronger than this fixed source supports; a future independently measured/calibrated study would need a different explicit scientific contract.

Numeric equality uses a fixed `1e-12` absolute/relative floating-point consistency tolerance. This is solely representation/summary arithmetic checking. Sign is taken from the actual source value, with no hidden significance cutoff; the tolerance is not a practical effect size, calibration rule or candidate-selected parameter. Group identity is typed: Boolean and numeric metadata are distinct.

External expert records have exactly `criterion`, `status`, `reviewer_ref`, `rationale`, and a nonempty unique list of exact `handles`. Reproduction criteria are `complete_scope`, `selection_split`, `units_aggregation`, `metric_decomposition`, `historical_formula`, `dependence_sensitivity`, and `claim_interpretation`. Improvement criteria are `complete_scope`, `prespecified_change`, `selection_split`, `fixed_support_comparator`, `signed_outcome`, and `biological_exposure_limits`. Missing criteria are listed. A record cannot remove a failed claim, alter a scalar outcome or produce automatic scientific-task completion.

The returned ledger preserves all upstream statuses, signed observations, machine reasons, external reviews and missing expert criteria. `scientific_qualification` stays false and `benchmark_count_delta` stays zero. It carries no raw targets or source files; output review is still required because trusted product group labels or reviewer references can contain private identities. This module does not certify a ledger as public-safe.
