# Hippocampal working-memory sequences and implicit timing

Task ID: `PAPER-FIND-ADD-003`. Reconstruct the canonical central results of
[Dorian et al., Cell Reports 2025](https://doi.org/10.1016/j.celrep.2025.116383)
from the complete selected observations: all 23 behavioral animals and all 11 CA1
imaging animals, with their last two standard and first two reversal days. Keep
all 140 trials per selected session and the complete 402-frame imaging axis.
These are source-declared geometries awaiting actual-file verification, not a
claim that observations have been acquired or inspected.

The target is unexpected-delay behavior, odor-selective sequence structure and
odor/time encoding. It is not raw-movie processing, every paper panel, spike-time
recovery, or proof that CA1 causes the behavior. Original animal ordering is
explicit in the source preprocessing scripts and in `PROTOCOL.json`; imaging
animals are the last 11 members of the 23-animal behavioral cohort. Cells are
session-specific and must not be treated as tracked across days.

## Required result

Produce `submission.json` following `OUTPUT_SCHEMA.json` and the stricter
executable `contract.py`. Any implementation may produce the result; invoking
the author program is not required. The operator supplies one fixed, authenticated
`QUERY.json`. Its complete ordered element lists are mandatory:

- Behavioral accuracy and median lick latency for all four cue/delay conditions
  on all four selected days. Accuracy uses outcomes 1 or 4. Latency includes
  both correct and incorrect licks, with the first retained lick strictly inside
  `(0, 3)` seconds after second-odor onset. No lick remains undefined.
- Both-cue peak distributions from the short-window sequence detection, pooled
  across the two reversal days within animal, using the exact source frame-bin
  edges. Include sequentiality indices for both short/long detection windows,
  both cue classes and all sessions. Significant-cell inference must be rerun
  from observations; the published selection files are not independent inputs.
- Seven-bin elapsed-time decoding correlations and full confusion matrices for
  both standard cue classes, every session, and real/shuffled training labels.
  The source uses leave-one-complete-trial-out ECOC; confusion matrices have
  predicted rows and actual columns, divided by the number of trials.
- Every real/shuffled accuracy family in `BinaryDecoding.m`, including complete
  second-odor-aligned arrays; retain structurally undefined elements. Include
  per-cell mean odor-information curves for all four conditions and both reversal
  days from `MutualOdorInformation.m`.

Return these same complete result families under `source_preprocessing` and
`no_smoothing_no_flooring`. The second is a **prospective sensitivity analysis**,
not a second published reproduction or an automatic improvement. Behavioral
values must be identical across these variants. Do not download a saved decoder,
selection or time-decoding answer as the input or independent gold. Both large
observation variants, not just the small result files, are required.

The private verifier reports continuous absolute errors in each endpoint's own
units, complete undefined-value agreement, and equal-animal macro errors. It
does not average seconds with accuracy, select favorable cells/animals, or invent
a binary success threshold. A candidate's missing value invalidates the affected
complete-support metric rather than silently improving it. Behavioral contrasts
compare standard with reverse **at the same actual delay**, then contrast long
versus short violations. An undefined session remains visible. No statistical
test or scientific significance claim is made by the verifier.

## Access arms and separate improvement

`paper_and_data` and `paper_data_official_code` receive the same paper, protocol,
observations and resources. Only the latter receives the exact author snapshot
`5e74479bbf97d47c14133cab5fea40a496ec7d94`. Private grading code, reference results,
other attempts and operator-only adapters are excluded from both candidate views.
The static stager is not isolation enforcement, data provisioning, or a runtime.
The public paper/results are exposed development material: no blind evaluation
or causal code-benefit claim is established.

The separately declared improvement is seven held-out 20-trial blocks per
session, with cell discovery and nuisance fits using training trials only, then
animal-level paired assessment across all 11 mice. `improvement_folds.py` provides
the complete deterministic split plan. Locomotion/licking-only, neural-only and
combined controls, training-only tuning, the exact nuisance models and a fresh
qualified evaluation remain to be bound; do not substitute this plan for the
author's trial-LOO reproduction or score it as completed. Temporal ordering can
reveal time labels, so an artifact reconstruction cannot itself certify that an
arbitrary candidate used neural features or avoided evaluation-label access.

## Source conventions and limitations

The supplied source is retained unchanged. Its nearest-standard matching uses
`blockof5-1*5`; changing this to `(blockof5-1)*5` changes the selection and belongs
in a separately declared correction. Sequence reliability accepts equality at
0.2, despite comments suggesting “more than”; the implementation controls. The
Fig2F histogram uses the short-window selection for both cue classes. Published
time plots flatten 44 sessions for some inferential procedures; this benchmark
retains all session values and uses mice for error aggregation, without claiming
to reproduce those statistical tests. FDR plotting code and its rank indexing
are not reproduced or certified by this comparator.

The source-scope package is partial. It has no authentic observation arrays,
validated structural observation, independent numerical reference, measured
MATLAB environment, qualified candidate executor or scientific test run. A
full-payload schema mismatch must be resolved explicitly, not by dropping an
animal, trial, frame, output family or preprocessing variant.


Paper-access successor: the complete primary body is locally supplied identically in A and B at `paper/article.pdf`; see `PAPER_MATERIALS.json` for exact identity/version and missing artwork or separate supplements. Stage static source materials with `private/paper_access.py --package PACKAGE --arm A|B --output FRESH`; use the preserved task-specific packet/data procedure separately. Source-only staging does not supply missing data or certify process isolation. All original scientific endpoints, input support, private targets, source behavior and unresolved full-project branches are unchanged.
