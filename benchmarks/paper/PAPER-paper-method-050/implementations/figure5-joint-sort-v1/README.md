# Figure 5H/I joint-sort fidelity component

`scorer.py` computes precision and recall against the paper's joint Kilosort2.5 reference. It fills a companion-endpoint gap alongside the existing Figure 5E PETH scorer. It does not run spike sorting or tracking, authenticate the original reference, fit the Figure 5D mixed model, or establish reproduction or improvement.

The [primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC13494646/) defines the comparison in Methods 4.17, JATS paragraph `p0495`, Equations 17–18. An individually sorted unit enters the comparison if strictly more than half its spikes coincide with a joint-sort unit, using an inclusive 1 ms coincidence window. Included units from the two sessions sharing a joint cluster form reference matches. TP, FP and FN count unit pairs. Figure 5H/I uses ten pairs of consecutive-day recordings from five rats. Tracking methods are run on the full selected session population before the pairwise comparison.

The scorer derives method matches from complete full-session assignments, restricted to each reference's included units. It exposes every TP/FP/FN pair and every excluded unit in the selected sessions. A predicted match involving an unmapped unit is outside this reference assessment, not automatically an FP. Dropping an unassessed session from the assignment table is rejected. DANT, UnitMatch and EMD use the same population and reference panel; an optional candidate cannot change either.

Use Python 3.11+ and the standard library:

```sh
python3 scorer.py /operator/joint-sort-packet.json /operator/joint-sort-result.json
python3 -I -B tests/test_scorer.py
```

During a coordinated build, use its shared test slot. The second command runs generated software controls only. The CLI records SHA-256 of the exact input bytes, emits strict JSON, and refuses to overwrite an existing output.

The generated `packet()` in `tests/test_scorer.py` is a complete example. The input schema is:

| Field | Meaning |
|---|---|
| `schema_version` | `figure5-joint-sort/v1` |
| `source_kind` | `generated_engineering_control` or `operator_prepared_source` |
| `population_provenance` | Evidence identifying original selected units and full sessions |
| `complete_selected_session_population` | Explicit `true` declaration; not proof of completeness |
| `dataset_to_rat` | Complete dataset-to-biological-rat mapping; regions from one rat must retain its same identity |
| `units` | Complete population rows with `dataset`, nonnegative `unit_id`, positive `session_id`, nonnegative `shank`, and ISO `recording_date` |
| `references` | Full frozen validation panel, each row described below |
| `methods` | `DANT`, `UnitMatch`, `EMD`, and optionally `candidate` |

Each reference supplies unique `pair_id`, `dataset`, ordered `left_session_id` and `right_session_id`, `mapping_provenance`, `complete_overlap_mapping: true`, `spike_time_tolerance_ms: 1`, and `included_units`. The sessions must differ by one calendar day. Each included unit supplies `unit_id`, nonnegative `joint_cluster_id`, positive `individual_spike_count`, and `coincident_individual_spike_count`. The latter counts individual spikes with at least one coincident joint-cluster spike; it cannot exceed the individual count and must exceed half of it. A unit appears once in a reference; both sessions need included units. Mapping counts do not verify actual spike times, clock alignment, coincidence computation or source membership.

Several individual units may map to one joint cluster. All resulting cross-session reference pairs are retained. The article does not establish a one-to-one mapping restriction or a tie rule when a unit overlaps several joint clusters. The operator must supply one resolved mapping per included unit and document that resolution; source parity for ambiguous mapping remains unresolved.

Each method supplies `execution_provenance`, `full_session_tracking: true`, `joint_reference_excluded_from_matching_and_selection: true`, `peth_excluded_from_matching_and_selection: true`, and complete `assignments` rows (`dataset`, `unit_id`, `track_id`). Track IDs are positive within dataset, or `-1` for unmatched. Positive singleton tracks are allowed. Tracks cannot cross shanks or contain two units from one session. These declarations guard against accidental circular evaluation; they do not verify external execution or exclusion from tuning.

Precision is `100*TP/(TP+FP)` and recall is `100*TP/(TP+FN)`, separately for every declared pair. Summaries weight pairs equally. They do not pool counts or treat ten pairs as ten independent rats. Undefined denominators produce `null` and block that metric's panel mean and SD, preserving the affected pair identities. Sample SD uses denominator `n-1` and is undefined for one pair. The article does not specify SD denominator or undefined-ratio policy, so these explicit numerical choices remain unverified for exact source parity. No pair is silently removed. The report states the published ten-pair/five-rat dimensions but never treats matching dimensions as authentication.

Remaining scientific gates include authentic full-population and original pair identities, joint-sort preprocessing and overlap-map verification, the complete original method executions, source statistical parity (including Friedman/Nemenyi), and justified equivalence/non-degradation rules. The source's Figure 5D row construction and mixed-model EMM, Figure 5E PETH checks, unmatched-pair controls and cross-shank controls remain separate. Joint-sort agreement is an indirect fidelity reference, not direct neuron identity; this component makes no performance or whole-paper qualification claim.
