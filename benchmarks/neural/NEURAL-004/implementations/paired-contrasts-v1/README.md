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

The existing source manifests and frozen controller are preserved. Enrolling this
extension in a newly frozen controller/source manifest is an integration action;
the retained historical runtime does not call it automatically. Thus this is an
implemented scoring/reporting component, not a newly qualified runtime or study.
Original 26-person FIF admission, qualified native HMP/reference execution,
matched protected participant delivery, and empirical reference competence remain
open. No authentic predictions or empirical gains were examined or produced here.

Generated checks run with the coordinator's shared two-slot test pool, using
`python3 -I -B test_paired_contrasts.py` as the child command. They include a
nonuniform person-size example with a hand-derived signed macro difference,
failure propagation, support/arithmetic mutations, and the retained real
`person_loss` function applied solely to generated inputs. The exact pool command
and outcome are recorded in the external handoff; checks do not qualify scientific
performance.

Source identities and the prior audit scope are recorded in
`SOURCE_EVIDENCE.json`. All predecessor files and canonical contracts remain
unchanged.
