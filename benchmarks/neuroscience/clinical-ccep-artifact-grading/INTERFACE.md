# CCEP primary JSON interface and interpretation


All objects have exact keys; duplicate JSON keys, NaN/Infinity, unknown fields,
unknown/duplicate/missing case IDs, bool-as-number, malformed probability vectors
and symlink leaves fail admission. FIFO/device/directory inputs are rejected before
ordinary-file open; nonblocking open and a second descriptor check cover replacement races. IDs are opaque ASCII `[A-Za-z0-9_.-]` tokens,
starting alphanumeric and at most 96 characters. No paths or anatomy labels go
in case IDs. All hashes are lowercase 64-digit SHA-256. Files must be regular,
nonempty UTF-8, at most 8 MiB each. At most 20,000 complete blocks are supported
by this implementation. These are engineering ceilings, not authorized exclusions:
if the authentic complete census exceeds them, stop and prospectively revise
the implementation, rather than selecting a smaller cohort. Authentic peak
memory/runtime remain unprofiled.

**Operator policy**, schema `ccep-operator-policy-v1`:

- `task_id`: `clinical-ccep-stimulation-attribution`; `contract_sha256`:
  `71ffec5855733039437c65a2b26fb1e7236ecb61e259211f517b5b94d3c4783b`;
  `release`: `ds004457:1.0.2`.
- `class_order`: exactly `hippocampus`, `amygdala`,
  `lateral_temporal_cortex`, `other_mixed`, in that order. This is the contract's
  **planned** four-compartment taxonomy. The actual atlas/contact mapping and
  mixed-pair policy must be authenticated and frozen separately. BPC categories
  are forbidden substitutes. Any required scientific taxonomy revision needs a
  new reviewed source version; a contestant cannot delete an unsupported class.
- `patients`: exactly five distinct opaque person IDs; `folds`: five objects
  with `held_patient` and `training_patients`. Each person occurs once as held,
  and each training list is the exact other four people. This verifies declared
  LOPO membership, not authentic biological identity or actual model fitting.
- `scope_assertion`:
  `all_five_patients_all_VTC_contacts_all_site_blocks_all_repetitions`.
- `provenance`: exact keys `source_census_sha256`,
  `anatomical_mapping_sha256`, `packet_manifest_sha256`,
  `exposure_audit_sha256`. Values pin external authenticated documents; this
  scorer does not open or authenticate their scientific contents.
- `targets_sha256`: exact original-byte hash of the private target document.
- `numeric_policy`: `log_base: "natural"`, operator-chosen `loss_floor` strictly
  between zero and 0.25, `sum_tolerance` in [0, 1e-8],
  `tie_break: "first_class_in_frozen_order"`, `calibration_bins: 10`.
  There is no default floor/tolerance and no contestant override. Freeze both
  before outcomes. Loss is exactly `-ln(max(p_true, loss_floor))`; other entries
  are not clipped and vectors are never renormalized or repaired. This explicit
  capped log-loss policy is a prospective implementation detail, not a measured
  historical author choice. Vectors must already lie in [0,1] and sum to one
  within the frozen absolute tolerance.
- `cases`: every original block exactly once, with exact keys `case_id`,
  `patient`, `session`, `site_block`, `VTC_contact`, `repetitions`,
  `packet_sha256`, `coverage`, `coverage_reason`. Person/session/site/contact
  are opaque evaluator-only tokens; the four-field block tuple is unique.
  Repetitions are positive integers at most 1,000,000. `packet_sha256` binds
  the separately prepared complete input packet, which this scorer never reads.
  Coverage is `ready`, `unsupported_anatomy`, `invalid_signal`,
  `ambiguous_timing`, `context_overflow` or `other_unresolved`.
  Ready rows have an empty reason; all others have a nonempty reason of at most
  256 characters. Every person needs at least one declared block. Any unresolved
  row makes the full primary unestablished, retaining the entire census and all
  reasons; targets are then not opened. This is not available-case averaging.

**Submission**, schema `ccep-predictions-v1`, has exactly `schema`, `task_id`,
`policy_sha256`, `class_order`, `condition: "original_full_scope"`, `rows`.
Each row has only `case_id` and a four-number `probabilities` list, once per
complete declared case. Ordering of rows is irrelevant. Targets, grouping,
weights, floors and class dictionaries cannot be supplied in a prediction row.

**Private targets**, schema `ccep-targets-v1`, has exactly `schema`, `task_id`,
`rows`. Each row has only `case_id` and integer `class_index` in 0..3.
Every policy case appears exactly once. The operator derives these from
authenticated stimulation/contact/anatomical joins, not from waveform clusters,
model outputs or generated fixtures. No such original mapping is supplied here.

## Scores, coverage and interpretation

The report includes every patient fold, true-by-predicted confusion matrix,
held and outer-training class support, class recalls and explicit missing
training classes. Missing training classes never drop a person. Recall for a
class absent in a held person is null; `macro_recall_observed_classes` averages
that person's supported classes, while `macro_recall_all_four_classes` is null
unless all four are present. The secondary overall recall equally averages the
five observed-class macros and is labelled accordingly; it is not a full-class
balanced-accuracy claim when support differs.

Calibration is descriptive and per person, per class: ten equal-width bins
[0,.1), ...,[.9,1], with counts, mean predicted probability and observed class
fraction. Empty bins are explicit nulls. No ECE, calibrated uncertainty interval,
permutation p-value, independent-block population inference or pass threshold
is invented. A source-only five-person implementation does not establish broad
human generalization. The primary uses every original block and equal people.

The adjacent [pairing interface](../clinical-ccep-pairing/INTERFACE.md) supplies
prospective target-free whole-block derangements and support-matched paired
null summaries. This primary command still rejects a transformed-condition
submission. Normalized source equivalence and authentic paired execution remain
unqualified; an unvalidated null or training-label shuffle does not establish them. Competent train-only
prevalence/template/regularized references, all access arms, protected export,
complete source/rights/census/anatomy/timing/preprocessing, context feasibility,
exposure accounting and authentic evaluation remain held. There is no new task
ID, scientific result, model run or readiness increase.
