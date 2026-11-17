# Optogenetic source contact timing: released Figure 1H analysis

Use the complete released `optoData` MATLAB struct array to reconstruct the control
and inactivation contact-time distributions used by `plotOptoHists` for Figure 1H
of *Mouse sensorimotor cortex reflects complex kinematic details during reaching
and grasping*. Start with all 3,304 trials, both mice and all eight sessions. Retain
every input trial identity in your output, including excluded trials.

This is a reconstruction of the **pinned data/code release**, not a test of the
article's quantitative percentages. Independent preparation found that the text's
reported contact-within-three-seconds percentages do not match the unshifted
release calculation. The native timer origin is unvalidated, so this is not
evidence that the published percentages are wrong. The article's total inactivation-trial
count refers to the raw stimulation population; the plotted selected population
is smaller. Report this limitation in any scientific interpretation. Do not adjust
selection to force the text's numbers. The native function labels its horizontal origin as cue. However, the exact
release has not established whether grabTimeC is already cue-relative: another
author event-analysis helper subtracts waterTime. Treat physical timing relative
to stimulation as unresolved. The task does not establish a causal effect or
population generality.

Both access conditions receive exactly this contract, the complete native MAT,
the pinned article XML, an identity-only trial roster, a submission schema and
source attribution. The official-code condition additionally receives the exact
pinned plotting function, its parent figure script and CC0 license. This is
selected source access, not a complete runnable author environment. Standard
numerical tools and dependencies must be supplied equally by an operator before
any solver study. No tool or model runs are part of this construction release.

The following source-derived conventions are shared with both conditions so the
comparison does not depend on guessing undocumented benchmark choices. This makes
it a method-assisted reconstruction condition, not independent method discovery.
Select rows with success=1, optoProblem=0, wrongGrabFirst=0 and grabTimeC greater
than liftTimeC. NaN timing fields fail that comparison. Separate by optoTrial=0
(control) and 1 (opto); pool all sessions and both animals within each group.
The native plotted value is grabTimeC/1000 seconds, without subtracting liftTimeC
or waterTime. This preserves the published function's arithmetic; it does not
validate a physical cue-relative clock.
Use 30 equally spaced edges from zero through nine seconds (29 bins), left edge
inclusive and right edge exclusive except the final right edge inclusive. The
probability denominator is every selected trial in its group, including times
outside the displayed window. Preserve the outside-window count.

Submit one JSON file conforming to `submission-schema.json`, or a MATLAB MAT
containing one struct variable named `submission` with the same fields. A MATLAB
`trials` struct array contains all identities and per-trial outputs; numerical
vectors are row or column vectors. Integer-valued MATLAB doubles are accepted
for trial IDs and count fields. For excluded rows use JSON null or MATLAB NaN for
contact_seconds; selected rows require finite contact_seconds. Do not include
extra variables, private references or copied operator artifacts. Output order
may differ; identity coverage may not.

The operator freezes all submitted bytes before parsing or grading and preserves
invalid attempts. Grading reports condition/selection mismatches, contact-time
RMSE and histogram count/probability errors. These are reconstruction diagnostics
without a scientific pass threshold. Full neural decoding, trajectories, raw
tracking/segmentation and whole-paper replication remain outside this component.
Shared-host authoring access is a protocol restriction, not a security sandbox.
