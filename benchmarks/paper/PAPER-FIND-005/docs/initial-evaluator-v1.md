# Initial single-cell endpoint implementation

The deliverable is a complete local calculation from sorted per-unit spike times and versioned trial records to stimulus, choice and feedback sensitivity, regional fractions, and a separate mouse-weighted summary. It implements the paper's single-cell branch, not its population decoding, trajectory analysis, GLM or whole atlas. It is useful for auditing exported source data and prospective comparison of the paper's choice window with its pinned example. No empirical data have been loaded or scored.

## Scientific sources and scope

The primary paper is [A brain-wide map of neural activity during complex behaviour](https://www.nature.com/articles/s41586-025-09235-0), Methods: Inclusion criteria; Single-cell correlates of sensory, cognitive and motor variables; Assessing significance. The source snapshot is [IBL paper-brain-wide-map 118fc36cb3602934466ad2c6087c2b3b441f9f1f](https://github.com/int-brain-lab/paper-brain-wide-map/tree/118fc36cb3602934466ad2c6087c2b3b441f9f1f). Source functions are `Time_TwoNmannWhitneyUshuf`, the three `get_*_time_shuffle` functions, and their working-example wrappers. The supplied roster must identify the `2023_12_bwm_release` session/probe/mouse objects, spike-sorting revision `2024-05-06`, and trials modified before `2024-07-10`.

The implementation's input inventory is explicit and complete **relative to the supplied export roster**. This cannot establish that the supplied roster is the authentic complete source population. The source loader's full unit UUID hash is `d16d0b38d392b18c0ce8b615ec89d60d7c901df2eeb3432986b62130af28ef01` for QC threshold >=1. Its canonical hashing procedure and full cohort require independent native verification. No hash assertion here is treated as authentic verification.

## Required source decisions remain visible

There is no default profile:

| Profile | Stimulus window | Choice window | Feedback window |
| --- | --- | --- | --- |
| `pinned-examples` | stimulus onset [0, .1) s | **stimulus onset** [-.1, 0) s | feedback onset [0, .2) s |
| `paper-choice-window-proposal` | stimulus onset [0, .1) s | **first movement** [-.1, 0) s | feedback onset [0, .2) s |

The second profile is a prospective paper-window choice, not evidence that the original analysis used the example's apparent misalignment. Owner adjudication and authentic references remain required. Both profiles retain source labels: stimulus is positive left versus positive right contrast, choice is +1 versus -1, and feedback is rewardVolume >0 versus <=0. Nonfinite reward volume causes an explicit failure; it is not silently made unrewarded. Zero contrast is excluded from stimulus labels and from conditioning strata for choice/feedback, matching source examples.

Sessions with fewer than three feedbackType=-1 trials after the common mask are excluded from calculations and retained in the coverage report with the reason. The common mask combines the exported official `source_mask` with finite choice, probabilityLeft, feedbackType, feedback_times, stimOn_times and firstMovement_times, and reaction time in [.08, 2] s. An actual exported source mask must include the source engagement truncation and any source interval exclusions. This implementation does not recreate native hardware, RIGOR, histology or engagement qualification. `bwm_units` has a conflicting .2 s upper RT default, while working examples explicitly use 2 s; that discrepancy remains a qualification gate. The paper and source signature use >=5 good units per region/session; one source docstring says 10. No silent historical resolution is asserted.

## Statistical calculation

Spike windows are half open. Good units have source quality label >=1, source gray-matter membership, and belong to the declared region family; root/void are excluded. All probes sharing a session are pooled for regional denominators. Units with no spikes are retained. The input must contain every original trial row, including excluded rows, and every inventoried unit. Trial and source masks are applied identically across endpoints.

The source conditional test has four strata. Stimulus conditions on probabilityLeft (.8/.2) and choice (+1/-1); choice and feedback condition on probabilityLeft and positive stimulus side. Contiguous block identities are formed after the source trial mask, matching pinned examples. For each stratum, rank sums are permuted only within contiguous blocks containing both labels. Forward and reverse directional U statistics use **independent** permutations before taking their elementwise minimum; the code intentionally preserves this nonstandard source null. The condition-combined statistic divides the sum of these minima by the sum of opposing-label pair counts. The p-value is the observed entry's average rank among observed plus null statistics divided by 3,001. Lower values are stronger. This source convention disagrees with the paper's greater-tail prose. All tied responses therefore yield 1501/3001, not 1; this is deliberately tested and disclosed. No cross-condition pairs is explicitly not estimable, never silently nonresponsive.

The simple two-sided Mann–Whitney test uses SciPy's asymptotic tie correction and continuity correction. These software options are a **prospective explicit choice** because they are not frozen in the inspected working examples. A unit is sensitive when simple p<.001 and conditional p<.05. Region/session fractions require at least 5 good units, and a region requires at least 2 such sessions. A nonestimable eligible unit prevents the regional inference rather than shrinking its denominator. The paper's source reconstruction uses a binomial survival probability at k or more sensitive units, with alpha=.001*.05=.00005; combines session p-values by Fisher; and applies Benjamini–Hochberg over the entire declared region family at q=.01. The product threshold is retained as a paper rule, not a newly established calibration of dependent tests. If any declared region is missing or not estimable, BH is withheld for the entire endpoint family.

The additional prospective summary first averages eligible session fractions within each mouse, then averages equally across mice. Its 95% percentile interval resamples mice as complete clusters. With fewer than two mice an interval is withheld. It is not a paper result, a cross-mouse predictive test, or a correction that makes session-wise Fisher evidence independent. No random-neuron or random-session claim of independent biological replication is made.

## Input format and execution

`evaluator.py` accepts JSON with these fields:

| Level | Required fields |
| --- | --- |
| Top | schema_version=1; freeze; source_revision; spike_sorting_revision; trials_modified_before; evidence_kind (`generated_engineering` or `unverified_local_export`); unit_version_evidence; mask_provenance; regions; roster; sessions |
| Roster row | eid, mouse_id, nonempty unique pids |
| Session | eid, mouse_id, pids, expected_trial_count, trials, expected_unit_uuids, units |
| Trial | trial_id (complete ordered 0..N-1), source_mask (boolean), choice, probabilityLeft, feedbackType, feedback_times, stimOn_times, firstMovement_times, contrastLeft, contrastRight, rewardVolume |
| Unit | uuid (globally unique), pid, region, quality_label, gray_matter (boolean), spike_times (finite sorted seconds) |

The contrastLeft, contrastRight and rewardVolume columns must be present on every trial; missing columns cause a schema error. Non-applicable contrast values are JSON null. Missing/nonfinite required common trial fields produce excluded rows. Use null rather than nonstandard JSON NaN. Source export identities, source masks and unit/version provenance need audit outside this program; editable input text is not an authentication mechanism. The declared regions must be fixed before assessment and include the intended full multiple-comparison family. Session/probe/unit omissions relative to the supplied inventories are rejected.

Example execution from the package directory:

```sh
python3 evaluator.py --input local-export.json --output results.json \
  --profile paper-choice-window-proposal --seed 0
```

The default is 3,000 conditional shuffles and 2,000 mouse bootstrap replicates. Lower shuffle counts are allowed only for explicitly generated engineering packets; unverified local exports require 3,000. This is source functionality for future authorized runs, not authorization to acquire or evaluate empirical data. Outputs always state unknown scientific qualification, incomplete full contract, exact profile, source pins, input content hash, coverage and preserved gates. RNG streams are deterministic per seed/session/unit/endpoint and unaffected by input unit/session ordering; they do not claim historical RNG parity.

Run engineering controls with an existing interpreter containing NumPy/SciPy:

```sh
python3 -m unittest discover -s tests -v
```

The controls test endpoint alignments, half-open spike windows, full inventory failures, post-mask/source null semantics, independently enumerated directional-null probabilities, all-tied data, absent exchangeable strata, Simpson confounding, family-level missingness, multiple probes/sessions and mouse weighting. Generated spike timestamps and labels are test fixtures only. They establish arithmetic and engineering behavior, not neural validity or paper reproduction.

## Remaining gates

The task's complete regional claim/assessment manifest is still unfrozen. Authentic source object schemas, complete cohort/region coverage, native mask/UUID reconciliation, exact simple-MW parity, paper/profile adjudication, public exposure policy, private reference protections, meaningful difficulty, reference agreement and target submission remain unqualified. The pinned MIT code license was independently reconciled; data/component terms remain separate. The program does not reconstruct raw AP sorting, and no causal interpretation of neural sensitivity is warranted. Runtime observations are limited to generated controls with existing local dependencies.
