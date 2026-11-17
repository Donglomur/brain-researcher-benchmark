# DoSEI secondary ordinal metrics and paired uncertainty

This additive evaluator completes a specified set of secondary reports on the existing DoSEI artifact interface: ordinal MAE, per-category recall, classwise calibration tables/ECE, and biological-participant paired intervals for original-arm RPS and MAE. It uses the exact unchanged [primary scorer](../ordinal-and-paired/dosei_score.py), preserving its complete `score_admitted` report bodies. Standalone per-artifact hash metadata is replaced by the new whole-bundle input identities; no unreceived standalone prediction-byte identity is invented. The existing [transformed-packet diagnostic](../ordinal-and-paired/README.md) remains separate and unchanged.

The [canonical task](../../task.json) requests these metric families but does not fix a point-decision rule, calibration functional/bin partition, or interval construction. This package therefore requires a separately hash-bound prospective policy with every choice explicit. The [recommended profile](RECOMMENDED_PROFILE.json) proposes a coherent construction protocol with rationale and alternatives; it is not an author-reported protocol or an amendment to the canonical definition. The [interface](INTERFACE.json) records exact fields and bounds. No authentic data, model run or qualified physiological reference is included.

## Scope and decisions

The unchanged primary admission requires all 171 recording records, 7,328 original assessment slots and 1,129 separately counted transitions, with an explicit biological-person mapping and complete grouped outer folds. Those are enforced declared counts, not independently authenticated source facts. A case is evaluable under the original label/window/timing/artifact conjunction. Each arm must supply every original assessment row, with an admitted five-category distribution for every evaluable case and an explicit `not_evaluable` row otherwise. Missing evaluable predictions refuse the whole submission. Every arm is admitted before the CLI opens protected targets.

The hard-category policy supports either the lower probability median (first category with CDF at least 0.5) or the lowest-index probability mode. No rule is inferred from the predictions. The recommended median minimizes expected absolute ordinal loss; MAE and recall use the same selected decision. The absolute error is measured in unit steps of the collapsed released category index 1–5; it does not assume equal clinical-severity distances. MAE averages eligible assessment errors within each biological person, then equally across all declared people. Any person without an evaluable original assessment makes that full-person MAE undefined, matching the primary RPS support rule.

Per-category recall first reports each person's true-category support, correct decisions and recall. Its cross-person summary averages only people with that true category and lists every person without support. A category absent everywhere has a null recall, not zero. This explicitly limited category-support summary does not replace the full-person primary score.

Calibration uses classwise reliability tables. Each eligible assessment has weight `1 / (P * n_p)`, where `P` is the number of declared people and `n_p` is that person's eligible assessment count. Exact decimal bin edges must strictly partition `[0,1]`; bins include their left edge and exclude their right edge, except the final bin includes 1. For each category/bin, the report gives raw assessment/person counts, weight mass, weighted mean probability, observed category frequency and absolute gap. Empty bins have zero mass and null means/gaps. Classwise ECE is the sum of bin mass times absolute gap; macro ECE equally averages the five category ECEs. These are descriptive, bin-dependent summaries, not a certification that probabilities are calibrated.

If any declared person lacks evaluable support, full-person calibration is undefined. Actual bin assessment/person counts are still reported for the remaining cases, while weights, means, gaps and ECE remain null. No favorable supported-person calibration score is silently substituted. The recommendation uses five fixed equal-width bins to avoid outcome-fitted partitions, and retains all bin supports so sparse estimates remain visible.

## Paired participant intervals

Every directed contrast is named in the frozen policy. The reported sign is comparison minus reference, so a negative RPS or MAE difference favors the comparison arm. First compute each person's difference between the two complete original-arm scores. Each replicate samples the full biological-person roster with replacement; all of a sampled person's assessments and repeated recordings remain together. Identical draws are used across arms, metrics and contrasts. This resamples participant means rather than assessment rows, preserving equal-person weighting.

The supported interval family is a percentile interval of the paired participant-bootstrap means, with explicit confidence, replicate count, seed and type-7 linear quantiles. The recommended construction profile uses 2,000 replicates and 95% intervals. It is conditional on the fixed predictions and fitted models: models are not refit, uncertainty in training or fold selection is not estimated, and empirical coverage is not verified. Cross-fitted predictions can share overlapping training folds: this remains descriptive conditional uncertainty, not a validated new-patient/generalization confidence interval. Biological-person exchangeability and sufficient cohort support require separate scientific justification. These intervals are neither permutation p-values nor clinical evidence.

The deterministic generator is fully specified in `INTERFACE.json`: SHA256 of a domain-separated seed and unsigned 64-bit replicate/position/rejection counters; rejection sampling removes modulo bias. Person order is the declared primary-policy order. The report records the seed, settings, person order and SHA256 of the complete canonical draw-index matrix. Any person without original evaluable support makes every full-person paired endpoint/interval null; no participant is dropped. Intervals are supplied only for original-arm RPS and MAE. Calibration/recall uncertainty and transformed-versus-original diagnostic intervals are not implemented or claimed here.

## Running

Python 3.11 and the standard library suffice. From the repository root:

```sh
python3 -I -S -B \
  benchmarks/neural/clinical-dosei-responsiveness/implementations/ordinal-metrics-v2/dosei_metrics.py \
  --primary-source benchmarks/neural/clinical-dosei-responsiveness/implementations/ordinal-and-paired/dosei_score.py \
  --policy COMPLETE_POLICY.json --expected-policy-sha256 POLICY_SHA256 \
  --secondary SECONDARY_POLICY.json --expected-secondary-sha256 SECONDARY_SHA256 \
  --predictions ALL_ARMS.json --expected-predictions-sha256 PREDICTIONS_SHA256 \
  --targets PROTECTED_TARGETS.json --expected-targets-sha256 TARGETS_SHA256 \
  --output FRESH_REPORT.json

python3 -I -S -B -m unittest discover -s tests/construction -p test_dosei_v2.py -v
```

The operands above are placeholders, not distributed authentic artifacts. The secondary policy binds the primary-policy hash, same-packet-set receipt, exact arm roster, directed contrasts, all metric choices and external before-outcome/input-parity receipts. Hash equality records the chosen values; it does not prove true person identity, physical packet equality, target-free preprocessing or pre-outcome custody. The recommended profile supplies metric choices only and cannot itself be submitted as a complete policy.

The callable `score_artifacts` takes four already caller-owned byte strings plus the exact original primary-source path and four expected hashes. It is not a protected sandbox. The CLI rejects malformed policy/candidate content before opening protected targets, checks regular bounded files without following final symlinks, and requires a fresh output path. Trusted ancestors and hostile concurrent filesystem isolation remain outside this component. Write failure can leave a partial output; successful process exit is required. All original reports remain evaluator-owned: per-assessment losses and per-person/category summaries must not be exposed as an adaptive score oracle during protected evaluation. Query budgets, reference custody and candidate process isolation require the surrounding evaluation system.

Format caps are 4 MiB primary policy, 16 MiB prediction bundle, 1 MiB targets, 128 KiB secondary policy and 40 MiB output; 2–8 arms, 1–28 directed contrasts, 1–20 calibration bins and 2–4,096 bootstrap replicates. Exceeding a cap refuses rather than truncates. These are format ceilings, not measured maximum-workload CPU/RAM guarantees. Inputs, primary reports and draw indices are materialized. Authentic complete execution needs separate deployment resource qualification.

## Evidence and remaining requirements

The tests use explicitly invented full-count metadata and independently calculated small eligible subsets to exercise aggregation, decision rules, bins, missing support and deterministic paired intervals. They establish software behavior only. [Provenance](PROVENANCE.json) separates the prospective definitions from the primary report and selected official classifier code; no author code is copied into this package.

The initial qualification comparison should include an outer-training participant-weighted category prior, a causal spectral/entropy ordinal model and a train-only random forest, all using the identical declared packet and training evidence. Their exact implementations, native causal feature extraction and competence remain unqualified; this metrics package supplies none of those models. Source event timestamps alone do not establish the beginning of a bedside assessment, so genuinely pre-assessment 30-second extraction also remains held. Authentic scale/assessment clocks, unique biological people across recordings, complete original labels, source/data rights, causal raw EEG preparation, training-only references, physical input parity, protected execution and independent scientific agreement remain unresolved. This source extension adds no benchmark ID, model result or scientific qualification.
