# Dataset-1 Figure 5 prediction scorer

`scorer.py` supplies the missing **prediction metric computation** for the active
paper-improvement contract: all 19 Dataset-1 participants in Figure 5b,c. It
computes balanced accuracy, tie-correct ROC AUC and the exact empirical ROC
curve for each participant, equal
participant means, descriptive subject SEM, and paired candidate-minus-author
differences. Reproduction and improvement are separate first-class outcomes:
the report retains each arm's offset from the rounded source anchors separately
from candidate-minus-author differences, without assigning either a verdict.
It requires both methods to cover exactly the same frozen target
observations. It never pools windows across participants or tunes a decision
threshold against the targets.

This component does not prepare authentic inputs or run the author classifier.
The existing `initial-evaluator-v1` implements static ISD state contrasts and is
preserved separately. Neither package establishes a paper improvement.

## Scientific definition and source

The [primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11502666/), Figure 5
and Methods, “Training and evaluation of machine learning models,” establishes:

- The original task predicts awake versus loss of responsiveness (LOR) with
  leave-one-subject-out validation over 19 Dataset-1 participants.
- Balanced accuracy is the mean of sensitivity and specificity. This scorer
  codes awake as 1 and LOR as 0. Both classes must exist in each participant.
- The paper reports 93% balanced accuracy and 0.984 AUC for its random forest.
  These are **rounded source anchors**, not recovered exact numerical targets.
- Figure 5 reports means and SEM across participants. The scorer reports each
  subject’s ROC AUC and its macro mean separately. The article does not fully
  specify how its displayed average ROC curve was constructed; equivalence of
  that curve’s reported AUC to this subject-macro AUC remains unverified.
- Original training uses 18 integration/segregation features from the whole
  brain and eight networks; stable baseline, deep LOR excluding its first and
  last five minutes, and recovery; 20,000 randomly selected points per class;
  100 trees grown to pure leaves; and five randomly considered features per
  split. Those facts do **not** authenticate the submitted predictions.

The [article XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11502666/fullTextXML)
was already cached in the source audit and was read for this component. No new
network acquisition or author execution is required by the scorer. Exact
provenance and remaining gaps are in `provenance.json`.

## Operator-only input interface

All input files and detailed output belong outside the repository and outside
the candidate interface. Do not expose behavioral targets or the resulting
per-participant diagnostic report as candidate feedback. The scorer is an
offline operator utility; it provides no sandbox or access-control service.

The operator freezes the exact target file bytes and supplies its SHA256
independently to the command. The JSON target object requires these fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `task_id` | `PAPER-paper-signal-add-012` |
| `panel` | `figure5_dataset1_loso` |
| `participant_ids` | All 19 distinct original participant identifiers, in reporting order |
| `source_binding_sha256` | Hash of the externally reviewed preparation/source-binding record |
| `observations` | Exact original evaluation windows, with `participant_id`, `window_id`, and integer `awake` (0 or 1) |

The source-binding record must establish the original roster, all applicable
window identities, behavioral labels/timing, preprocessing and window policy.
Its hash is retained as provenance; the scorer does not open or authenticate
that record. It cannot detect a dishonest or incomplete original window set in
an operator-provided target file. **Authentic preparation remains unresolved.**

Each prediction JSON object requires integer `schema_version: 1`, the exact
`target_manifest_sha256`, `access_condition`, and `observations`. The author arm
uses `author_reference`; the candidate arm uses `paper_data` or
`paper_data_author_code`. Run the two candidate access conditions separately
against the same frozen target/source protocol and retain separate scores.
These remain declared conditions requiring enforcement by the surrounding
participant/operator system; they do not double the task count.
Each observation contains:

| Field | Meaning |
| --- | --- |
| `participant_id`, `window_id` | Exact key from the frozen evaluation manifest |
| `held_out_participant_id` | Must equal this observation’s participant |
| `predicted_awake` | Integer 0/1 decision already made by the frozen method |
| `score_awake` | Finite real score, with larger values indicating awake |

Scores may be unbounded; ROC AUC needs their ordering rather than calibrated
probabilities. Exact score ties receive half credit. Hard decisions remain
separate so the scorer never infers or optimizes a candidate’s threshold.
Duplicate JSON keys, duplicate/missing/extra observation keys, different target
digests, nonfinite scores, and mismatched fold names are rejected. Order of
prediction rows does not matter. The fold-name check verifies declared
identity only; it cannot prove the absence of training leakage.

With an existing Python interpreter (standard library only):

```sh
python scorer.py --targets /operator/frozen-targets.json \
  --expected-target-sha256 FROZEN_SHA256 \
  --author /operator/author-predictions.json \
  --candidate /operator/candidate-predictions.json \
  --output /operator/paired-metrics.json
```

Paths above are illustrative, not artifacts. No authentic manifest or predictions
are bundled. The CLI prevents its output from overwriting an input file.

## Retained ROC curve diagnostics

Each participant record in each arm also includes `roc_curve`: an ordered list
of `{threshold, false_positive_rate, true_positive_rate}` objects. It starts at
(0, 0) with a JSON `null` threshold meaning a cutoff above every supplied finite
score. Each remaining point uses `score_awake >= threshold`, with thresholds in
descending order; all tied scores enter together. The final point is (1, 1).
No intermediate points are dropped, so vertical segments and tied-score steps
remain available. The trapezoidal area under this empirical curve equals the
rank-based `roc_auc`, including half credit for ties.

These are separate participant diagnostics on the frozen original support,
retained for both author and candidate. They are operator-only alongside the
other detailed scores and never select the method's hard-decision threshold.
The scorer does not pool scores across participants, average curves, or infer
the paper's `source_roc_summary`. The original Figure 5c curve construction and
its relationship to participant-macro AUC still require authentication; these
curves are useful inputs to that work, not evidence that it is complete.

## Interpretation and remaining work

The scorer makes no reproduction, improvement, pass/fail, or readiness decision.
A small offset from a rounded anchor does not establish reproduction, and a
better mean score alone does not establish source-paper superiority. Source labels and timing, the
complete evaluation-window mapping, original sampling semantics (including what
“non-overlapping” means), author implementation and stochastic calibration,
feature mapping, control/companion metric requirements, exact source precision,
predeclared meaningful effect, and an uncertainty procedure accounting for
overlapping LOSO fits remain unresolved. A new random-window split, static
Dataset-3/5 contrast, or reduced participant set cannot substitute.

The arithmetic SEM is descriptive only. The paired output preserves participant
units for a later justified comparison without silently treating time windows
as independent or imposing an unqualified significance test.

`test_scorer.py` contains generated controls with 19 fictional identities: a
hand-derived tie case; an independent pairwise AUC oracle over 200 generated
cases; unequal window counts exposing pooled-versus-macro aggregation; score
versus decision separation; exact tied-threshold ROC coordinates, independent
threshold/count checks and curve-area equality; reordered observations; missing/extra/duplicate
windows; incomplete rosters and missing classes; invalid values; and a CLI
roundtrip. They establish software behavior only. Tests use the shared bounded
test pool during the parallel build; see the external handoff for actual runs.
