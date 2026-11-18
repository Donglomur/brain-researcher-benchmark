# Figure 5E PETH fidelity component

`scorer.py` adds the source paper's Figure 5E functional-consistency calculation that the preserved `initial-evaluator-v1` deliberately did not implement. It accepts an operator population and complete frozen DANT, UnitMatch and EMD track assignments, selects consecutive calendar-day pairs, applies the mean ≥1 Hz and peak ≥5 Hz unit filters, calculates Fisher-transformed Pearson correlations, and retains datasets with at least 100 valid pairs in **each original method**. It reports each dataset's median and the tie-corrected three-method Friedman statistic with its asymptotic chi-square p-value.

This is a component for both first-class paper outcomes: reproducing the original findings and testing a same-task improvement. No empirical reproduction or improvement has been run. It does not calculate the Figure 5D tracked-length mixed-model endpoint, a non-degradation decision, or neuron-identity accuracy. The historical all-13-dataset/split diagnostic remains unchanged.

Run with an existing Python 3.11+ installation; only the standard library is used:

```sh
python3 scorer.py /operator/figure5-peth-packet.json /operator/figure5-peth-result.json
python3 -I -B tests/test_scorer.py
```

During the coordinated build, run all Python through the shared test pool. The second command is a generated software control, not scientific validation. The output file must not already exist. The CLI records the exact input byte SHA-256 and writes strict JSON output; infinite Fisher values are explicit strings, and undefined values are null.

The operator packet has these fields; `tests/test_scorer.py::packet` is a complete generated example:

| Field | Required meaning |
|---|---|
| `schema_version` | `figure5-peth/v2` |
| `source_kind` | `generated_engineering_control` or `operator_prepared_source`; a declaration does not authenticate provenance |
| `peth_schema` | `press_release_poke_3x1000_bins_1ms_plus_minus_500ms` |
| `rate_unit` | `Hz` |
| `rate_measurement_provenance` | Operator evidence describing the source mean-rate computation and PETH rates in Hz; mean rate is not inferred from raw spike-count units |
| `population_provenance` | Evidence binding the original selected population, dates, filters and source identities |
| `units` | All common units, with `dataset`, nonnegative original `unit_id`, positive `session_id`, `shank`, ISO `recording_date`, `mean_rate_hz`, and exactly 3000 finite nonnegative `peth` rates in Hz; peak rate is computed directly as the maximum PETH bin |
| `methods` | Objects keyed by `DANT`, `UnitMatch`, `EMD`, and optionally `candidate` |
| Each method | `peth_excluded_from_matching_and_selection: true`, `execution_provenance`, and a complete `assignments` list |
| Each assignment | `dataset`, `unit_id`, and `track_id`; `-1` is unmatched and positive integers identify tracks within a dataset |

No units are intersected or silently dropped. Unknown, duplicate or missing assignments fail. A track cannot contain two units from one session or cross shanks. Original IDs may be sparse; no renumbering or newly invented animal split is imposed. Session ordinals do not establish elapsed days: only dates differing by exactly one calendar day are included by this kernel. Multiple sessions on the same day do not count as consecutive days. The intended source date interpretation and rate-metadata preparation need native source parity before empirical use.

Reports expose all track-pair counts and the disjoint exclusions for nonconsecutive days, rate-ineligible pairs and constant PETH vectors. A constant PETH has undefined correlation and never counts toward the 100-pair threshold. Pearson endpoints use the predecessor's explicit eight-machine-epsilon numerical snap and signed infinity; this is an engineering policy, not an author-specified tolerance. Median is computed over pairs within each dataset. The Friedman analysis uses dataset medians, not pairs as independent samples. An undefined retained median prevents the statistical comparison rather than silently removing that dataset. All methods tied within every dataset makes the Friedman denominator zero and yields an explicit undefined result.

Optional candidate output is evaluated on the **baseline-selected dataset support**. Candidate failure to reach 100 pairs is visible and does not remove that dataset or alter the original three-method Friedman statistic. These descriptive outputs do not define an improvement rule; a justified joint non-degradation criterion remains necessary.

The Figure 5 comparison originally used 41,591 units in 12 datasets from 10 rats, including the source's first-31-session truncations for rats #2/#4 and rat #6 exclusion. Figure 5E retained eight datasets after its support filter. This component does not assert that an operator packet is that population. The original dataset-file/rat/session mapping, exact rate computation, authentic date/PETH preparation, independent PETH exclusion throughout matching/tuning, and original reference outputs still require verification. UnitMatch half-session waveforms, Figure 5D Equation 19, joint-sort precision/recall, unmatched-pair controls and cross-shank validation remain outside this component. A local source packet label cannot establish unseen targets, source execution, scientific qualification, or whole-paper reproduction.

For paired participant conditions, the same operator population and scorer apply to paper+data and paper+data+author-code deliveries; this component does not deliver either participant package. Do not combine or double-count the separate reproduction and improvement scores. See `provenance.json` for source evidence and exact construction limits.

## Pair-level verification

Use `--pair-audit` (or `score(packet, include_pair_audit=True)`) to add the optional `figure5-peth-pair-audit/v1` record. The default report and numerical decision path are unchanged. The record contains every supplied unit with its date/rate/geometry metadata and a domain-separated SHA-256 of its normalized validated PETH vector. It also retains every positive track's complete unit membership, every unmatched unit, and every consecutive-calendar-day pair with its rate-ineligible, constant-PETH or valid outcome. Valid pairs include the exact encoded Fisher value used by the existing median. Nonconsecutive pairs remain algebraically counted and can be reconstructed from the complete membership and dates; they are not materialized quadratically. Multiple sessions on one date retain all cross-day combinations.

Pair records are sorted by dataset, track and original IDs; input ordering cannot hide identities. The unchanged baseline-only support rule still applies to candidate comparisons. This manifest permits an independent verifier to reconstruct pair selection and aggregate counts. It is not an independent recomputation and does not authenticate source membership, preprocessing or matching/PETH-exclusion provenance. The semantic PETH digest is not a raw-source-file checksum; the CLI's separate `input_sha256` binds the submitted packet bytes. Original Figure5D model rows, source population and all other qualification gates remain unresolved.
