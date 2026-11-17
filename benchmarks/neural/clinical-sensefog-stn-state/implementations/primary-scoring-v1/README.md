# SenseFOG protected probability scoring

This adds the missing **ordinary participant-macro multiclass log loss** and a
consumer for the existing complete-recording lag mapper. It preserves that
mapper and the registered task. It is evaluator software, not a prepared clinical
benchmark, a decoder, or evidence of direct neural interpretation.

`score(grid, policy, targets, predictions, max_cases=..., paired_predictions=None)`
is the API in `sensefog_score.py`. Python 3.11+ standard library suffices. The
sibling `recording-lag-controls/sensefog_pairing.py` is an exact pinned dependency
(SHA-256 `d833d2c7637d73ce047578788a75c0ab30a98cee89b694efde27b5f79fe8ef40`).
The dependency validates all 12 people, all outer folds, the complete recording
case grid, continuous segments, channels, masks and the 20 fixed lag rules.
It is invoked even for primary-only scoring, so null-unavailable records remain
in the original case census. No supplied map can replace its support decisions.

## Frozen evaluator inputs

All documents have strict exact fields. The example below describes schema, not
an authentic class dictionary or clinical acquisition rate. Generated tests use
invented 1 Hz geometry; this is **not** SenseFOG's native rate.

- `grid`: the unchanged mapper's `sensefog_target_free_pairing_input_v2` document.
- `policy`: `schema="sensefog_score_policy_v1"`, `task`, ordered `classes`,
  `finite_probability_floor`, `bootstrap_replicates` (1–10,000), and a nonnegative
  integer `bootstrap_seed`. Freeze actual classes, floor, replicate count and seed
  before predictions. No labels or classes are inferred from candidate output.
- `targets`: `schema="sensefog_protected_targets_v1"`, `task`, `grid_sha256`,
  `label_protocol_sha256`, and `rows`. Each row contains `case_id`, `participant`,
  `status`, and `label`. Every original case must occur exactly once.
  Status is `evaluable`, `ambiguous`, `missing_annotation`, `missing_signal`, or
  `artifact`; only `evaluable` has a non-null label from the fixed class list.
  Artifact/signal exclusions need an independently authenticated prospective
  rule. A hash-shaped label-protocol receipt does not authenticate that rule.
- `predictions`: `schema="sensefog_predictions_v1"`, `task`, `grid_sha256`,
  `policy_sha256`, and `rows`. Every original case occurs exactly once with
  `case_id` and `probabilities` in the policy's class order, including cases with
  unknown targets. Missing, duplicate, extra or invalid predictions fail the
  entire score. This version has no abstention or prediction-failure imputation.
- Optional `paired_predictions`: same outer fields with
  `schema="sensefog_paired_predictions_v1"`; rows contain `case_id`, `multiple`,
  and `probabilities`. Supply every and only map-supported `(case_id, multiple)`
  pair, including unknown targets. All twenty requested lags remain reported.

`task` is always `clinical-sensefog-stn-state`. `grid_sha256` and `policy_sha256`
are the output of `canonical_sha256` on their full JSON objects. The CLI also
requires **independently frozen exact-byte hashes** for every file, including
protected targets and predictions. Labels and output reports remain evaluator
owned; never place targets, null donor maps or this scorer's output in a
participant's input. The scorer does not verify code freeze, model training
custody, packet byte identity across arms, or whether submitted probabilities
were actually computed from the claimed original/transformed signal packet.

## Metric and support

Probabilities must be finite numbers in [0,1], with sum within 1e-9 of one.
Booleans are refused. The prospective finite-probability rule is
`q[k] = max(p[k], floor) / sum_j(max(p[j], floor))`; loss is `-ln(q[true])` in
**nats**. Floor is explicit, positive and at most `1/K`. The implementation uses
a difference of logarithms to avoid underflow at tiny floors. It does not change
class prevalence, balance classes or weight long recordings more heavily.

Average evaluable case losses within each person, then equally over all 12
people. A person without evaluable windows makes the full-cohort primary score
and its interval undefined. Every fold, unknown/excluded status count, class
count and recording remains in the report. No reduced-cohort mean is renamed
as the primary endpoint. A person without freezing remains scored normally.

For each fixed lag, take transformed minus original loss on exactly the same
map-supported evaluable cases, average within person, then equally across
people with evaluable support. Report all 12 folds, unsupported case identities
and reasons, complete map coverage, and target/status coverage. People lacking
map support or usable labels are explicitly listed. An optional summary equally
averages valid transform-level deltas; it does not pool windows or unequal lag
coverage. Original full-coverage primary scoring remains unchanged. Missing
training-dependence information may remove every lag diagnostic, never a primary
case. Positive deltas mean worse loss after the shift.

95% percentile intervals resample participant means (or within-person paired
mean differences) with replacement using the frozen seed and replicate count.
They are descriptive small-cohort uncertainty, not a window-level standard
error, calibrated null test, simultaneous interval across lags, or causal claim.
An interval for fewer than two evaluable participants is undefined. This does
not select a scientifically adequate replicate count or certify bootstrap
coverage; those belong in the frozen clinical evaluation protocol.

## Command line and controls

The CLI uses `--grid`, `--policy`, `--targets`, `--predictions`, and optionally
`--paired-predictions`, each accompanied by `--NAME-sha256`. Also supply
`--output`, `--max-input-bytes` (per input), `--max-output-bytes`, and
`--max-cases`. Use ordinary trusted files and an operator-owned private workspace
with umask 077. Duplicate JSON keys and nonfinite JSON constants are rejected.
Logical byte/case caps fail the complete operation; they never truncate the
population. Output creation is exclusive. This is not a hostile-file sandbox,
atomic publication mechanism, process/RAM limiter, or provenance verifier.
An I/O failure after creation can leave a partial output.

`test_score.py` exercises the actual scorer and CLI on generated fixtures:
unequal person coverage, hand-computed natural prevalence loss, unknown labels,
undefined whole-cohort scores, exact case/group joins, probability errors,
class-order bindings, target/recording completeness, unequal paired support,
missing null support, per-case support mismatch, participant bootstrap,
source identity, frozen bytes, caps and exclusive output. Run through the shared
resource pool during coordinated construction. No authentic recordings, labels,
arrays, predictions or clinical metadata are included or processed.

## Source and remaining scope

The scientific endpoint follows the unchanged registered `task.json` and
`understanding.v1.json`. Original source routes remain the
[Brain paper](https://academic.oup.com/brain/article/147/12/4056/7831184),
[Mendeley release v1](https://data.mendeley.com/datasets/c9ckcvjxc7/1), and
[author repository](https://github.com/PKlocke/SenseFOG-Documentation).
Those records establish the source route, not an authenticated local cohort.
No new source acquisition or original-author execution occurred for this component.

Still missing: authenticated complete native LFP/annotation preparation and
clinical clock reconciliation; actual category dictionary and exclusion rule;
physical original/transformed packets and equal-arm transport; frozen decoders
and reference models; event-onset matching, freezing sensitivity,
voluntary-stop confusion, and false alarms per recorded minute. This component
cannot infer event boundaries or exposure durations from overlapping windows.
There is no model/human trial or new clinical performance result. Primary and
paired metric source availability does not qualify the complete endpoint or any
access mode, and frozen-program scores must not be interpreted as direct or
viewer-mediated understanding. Existing canonical registration and contracts
are unchanged pending independent integration review.

Native interpretation and creation/use of tools, models or pipelines are separate
first-class neural outcomes on matched cases. This scoring function can score
probabilities from either condition; it cannot infer which condition produced
them. An evaluator must retain separate condition reports and provenance while
reusing the same frozen grid, policy, targets and physical packets. Running a
pipeline does not establish native interpretation, and separate outcomes do not
double the task count.
