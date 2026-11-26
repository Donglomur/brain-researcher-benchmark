# Paired prediction contrasts

This operator-side reporting extension fills a specific gap in the retained
NEURAL-004 prediction scorer: it reports matched information-view and mode
comparisons. The existing scorer compares every actor to the independently
selected behavior reference, which does not by itself isolate the benefit of
adding EEG or an HMP tool to the same actor condition.

`paired_contrasts.py` consumes the unmodified result of
`programme-source/implementation-v1/central-integration/successor-v3/effective-parent/grading.py:grade_prediction_panels`.
The scientific target remains logged fractional contrast and the aggregation
remains equal mean over all 26 held people. This adds no forecast, fitting,
source-data acquisition, new target, or direct-observation/viewer condition.

The fixed comparison set is:

- Within each of P and I: E versus B, H versus B, EH versus B, EH versus E,
  and EH versus H. These distinguish neural information and HMP-tool availability.
- Within each B/E/H/EH view: investigator I versus frozen program P.
- Independently selected neural reference N versus behavior reference B. N may
  legitimately select a behavioral fallback; a positive difference is not required.

Every difference is baseline MSE minus alternative MSE in fractional-contrast
squared units. Positive means lower error for the alternative. The report retains
all 26 paired person losses, their signed mean, median and range, and a labeled
delete-one-person sensitivity vector. It does not pool trials or turn overlapping
LOPO fits into independent replicates or a population confidence interval.

If either side has a failed or blocked person, its paired aggregate and all
descriptive aggregates remain undefined. Available paired rows and both original
failure statuses remain visible. Unaffected contrasts can still be reported.
Omitted/duplicated people, mismatched retained trial counts, nonfinite errors,
inconsistent trial/person means, incorrect units, and false completeness claims
are rejected. Context-specific opaque trial IDs are deliberately not joined across
views: the protected predecessor scorer already checks their private bijections
against each person's same canonical answers.

Use `paired_contrasts(grade)` immediately after the protected grader returns, in
the operator/scorer process. Store the result with the existing post-seal evidence.
The input digest and release receipt pin bind this derived report to its source;
they do not authenticate an arbitrary caller-supplied JSON document. Neither this
extension nor its tests open or replace the target-release barrier. Do not deliver
these loss/error-derived reports to a prediction actor.

The integrated central driver now calls this unchanged kernel inside its existing
`prediction_grade` phase and retains `PAIRED_PREDICTION_CONTRASTS.json` beside the
unchanged `PREDICTION_GRADE.json` in private `parent-bodies`. The observer requires
the pair whenever grading completes, even if a later phase fails, and joins the
report's input digest to the exact observed grade bytes. Historical outputs remain
bound to their historical source and do not acquire this new completion claim.

The captured kernel copy is byte-identical to this standalone implementation.
The effective parent/grader, original grade schema/bytes, fifteen phases and
comparison mathematics are unchanged. A failed derivation or retention keeps the
original grade and fails the existing grading phase; normal phase dependencies
continue to apply. Valid incomplete grades still produce incomplete comparisons,
with missing partners and undefined aggregates preserved. Numerical coverage does
not establish HMP qualification: retain the original grade and its
`supplied_HMP_condition_complete` flag. P/I compare tool/program modes, not native
versus tool use; no population confidence interval is added.

The driver charges one logical in-memory grade traversal and reserves temporary
space of four times the retained grade bytes plus one MiB for the fixed report
structures, spanning derivation and serialization. This is a conservative declared
logical allowance, not a Python/OS peak-memory guarantee. Existing inherited
clock, read/live/write/retention, body and file-count ceilings remain in force;
no cap is increased and no authentic runtime or study is qualified.
Original 26-person FIF admission, qualified native HMP/reference execution,
matched protected participant delivery, and empirical reference competence remain
open. No authentic predictions or empirical gains were examined or produced here.

Generated checks run with the coordinator's shared two-slot test pool, using
`python3 -I -B test_paired_contrasts.py` and
`python3 -I -B test_programme_integration.py` as child commands. They include a
nonuniform person-size example with a hand-derived signed macro difference,
failure propagation, support/arithmetic mutations, and the retained real
`person_loss` function applied solely to generated inputs. The exact pool command
and outcome are recorded in the external handoff; checks do not qualify scientific
performance.

The integration controls exercise the actual protected grade, captured driver,
body retention and receipt validator on generated 26-person support. Other
scientific phases and external authority/transport are explicit uncredentialed
doubles. They check original grade bytes, later failure, missing or altered
artifacts, digest linkage, missing partners, and inherited resource refusals.
They do not establish authenticated process custody or scientific performance.

`SOURCE_EVIDENCE.json` preserves the historical standalone audit and its source
pointers, including the then-absent automatic integration.
`PROGRAMME_INTEGRATION.json` records the current integrated source descriptors.
The standalone numerical kernel and effective parent remain byte-identical.
