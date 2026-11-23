# Original behavioral reference profile

This operator component turns the existing complete93 MotorMINT primary reference assessments into the selected Figure5 profile:15 behavioral groups over Area2_Bump, MC_Cycle, MC_Maze and MC_RTT. It preserves every per-dimension value and failed or missing run. It adds the missing selected-panel reduction to the existing per-case scorer; it does not rerun that scorer or fit a method.

`build_reference_profile(cases, assessments, support_by_case)` consumes the existing original causal `primary_behavior` reproduction cases and `assess_case` outputs. Supply exactly93 case definitions. An omitted assessment remains an explicit missing run. Supply a trusted operator mapping from each caseID to the SHA256 of its ordered sample/trial/5ms-mask manifest, excluding behavior columns. All methods and runs for a dataset must share the same sample-manifest identity. Hash equality is a consistency condition; this component cannot authenticate the manifest, source payload, split chronology or original mask by itself.

Per-dimension R2 values are averaged equally within each original group. Feedforward and GRU group scores average all10 initializations. A method's dataset score averages its eligible groups equally, so the39-dimensional muscle groups do not outweigh a two-dimensional position group. Kalman retains only its source-eligible position/velocity groups. Its dataset aggregate therefore has different group support from full-variable methods; there is no automatic cross-method dataset winner. The output records the exact group support. The extra naive-Bayes reference is confined to MC_Maze.

All original eligible methods must have complete numeric assessments before a group's strongest-reference value is available. A failed comparator cannot improve a rival's apparent result by disappearing. Ties retain every method. The component retains input commitments and reported failure reasons, rejects duplicate/missing case slots, altered dimensions, mismatched sample support and nonfinite/non-numeric R2 values. Numeric outputs must carry the existing scorer commitments and match the current case input, metric-recipe and source-recipe identities. Reusing an old assessment under the same caseID is rejected when any of those identities changes. Supplied assessment artifact metadata is retained, but this is not independent artifact authentication. It independently recomputes group means;1e-12 is only an internal arithmetic-consistency tolerance on an already recorded group value, not a reproduction tolerance.

The output is an author-reference profile. It does not label the `candidate` field of each reproduction assessment as one improved method. It provides no global scalar, confirmatory improvement decision, paper win, reproduction claim or SOTA claim. Biological uncertainty, complete native recipes, authentic original support, historical reference values, phase units/5ms aggregation and protected paired candidate evaluation remain unresolved. Existing paper+data versus paper+data+author-code conditions are unchanged.

## Generated controls

`python3 -I -S -B test_panel.py` from this installed component runs14 focused controls. For a private checkout, add `--source-task /absolute/path/to/PAPER-paper-method-011`. Controls use retained source metadata and generated assessment values, never neural arrays. They cover unequal group dimensions, all10 initializations, missing/undefined runs, source eligibility, sample-mask substitution, case/output aliases, forged group scores, invalid R2, ties, input immutability and missing/stale assessment commitments.

The original12 controls passed. Independent review then identified a missing assessment-to-case commitment join. The fixture was corrected to the real scorer interface and the affected14-control suite passed in a second pool invocation; the first result and costs are retained. CI enrollment is not included in this private proposal: the integrator must add the command to the task component's integrity enrollment. No shared registry or source-binding is changed by this package. `SOURCE.json` pins retained source authority and identifies the four limited web observations. No raw source or data acquisition was performed.

## Candidate comparison on the original panel

`compare_candidate_profile(reference_cases, reference_assessments,
reference_support, candidate_cases, candidate_assessments, candidate_support,
candidate_program_sha256=..., reference_metric_recipes=...,
candidate_metric_recipes=...)` adds the previously missing numeric comparison
against the complete original panel. It calls `build_reference_profile` on the
93 raw reference case/assessment inputs; it never trusts a caller-supplied
strongest-method score. Supply exactly four candidate cases, one per original
dataset, with `purpose: improve`. The existing runtime's `MINT:0` output slots
identify the paired original reference; the candidate values come from each
assessment's `candidate` field. Those source-slot method tags do not identify
the candidate algorithm.

All four cases must retain the original causal mode, full dimensions, ordered
sample/trial/5-ms-mask commitment, source-support identity, input index,
source recipe and original MINT reference source. Provide the four original
MINT metric recipes and four candidate metric recipes keyed by their case IDs.
Each complete recipe must match its own case digest and uncertainty list.
The remaining recipe contents must match exactly across the pair; only
`uncertainty_requirements` may differ. This permits a historical trial-bootstrap
policy for reproduction and the runtime-required prospective paired-gain policy
for a candidate without changing scoring semantics. Both policies and full
recipe commitments are retained; the comparator does not evaluate uncertainty. The configuration hash
may differ and is retained. A successful candidate assessment must carry the
current scorer commitments and a complete numeric reference companion; if the
panel's MINT assessment is numeric, its per-dimension values must match that
companion exactly. This detects contradictory saved assessments; it does not
establish native equivalence or recover a missing historical result.

Every original group reports candidate-minus-MINT, candidate-minus-each-eligible
method and candidate-minus-strongest-original. Comparator network scores still
average all ten initializations, and a missing comparator keeps the strongest
comparison unavailable. Missing or failed candidate assessments keep all groups
and reasons in the report. Four candidate dataset summaries average groups
equally. No cross-method dataset winner is selected because Kalman eligibility
differs. All original and candidate per-dimension values remain available.

This interface describes one operator-declared candidate realization. It does
not invent a candidate seed-aggregation policy, significance test, meaningful
effect, full-vector success rule or global scalar. The program SHA256 is an
operator declaration, not proof that all four executions used those bytes.
Execution provenance, authentic sample manifests, original phase units and
aggregation, matched input conditions/budgets, chronology and protected paired
uncertainty remain external requirements. Numerical completeness never changes
`scientific_qualification: false`, `improvement: unknown` or `paper_win: null`.

The source basis remains the selected Figure 5
[endpoint](../../primary-endpoint-v1/selection.v1.json) and its
[improvement contract](../../primary-endpoint-v1/improvement.v1.json), the
[paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11790250/), and the existing
`catalog.primary_slots`, `bindings.validate_identity` and `scoring.assess_case`
interfaces pinned in `SOURCE.json`. The official
[MATLAB evaluator](https://github.com/seanmperkins/mint/blob/347206a402ac71ea528752365eebea17e3c770da/run/utils/evaluate_and_save.m)
confirms 5-ms evaluation and per-dimension R2; it does not resolve native Cycle
phase semantics. Historical source manifests retain their original hashes.

Run `python3 -I -S -B test_comparison.py` from this component, optionally adding
`--source-task /absolute/path/to/PAPER-paper-method-011` for a staged candidate.
It runs the existing 14 reference-profile controls and 15 new generated
comparison controls. These check the full group roster, equal group weighting,
all comparator initializations, eligibility, failures, conflicting MINT
companions, stale commitments, support/metric substitutions and separately
bound historical/prospective uncertainty policies. No scientific
run is performed. The integration owner must enroll this command and update
current source bindings; shared CI/registry files are outside this component.
