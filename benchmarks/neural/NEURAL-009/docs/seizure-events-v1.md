# Current complete-recording event evaluator

[The normalized evaluator](../implementations/seizure-events-v1/README.md) covers
all 686 pinned CHB-MIT recordings and 23 biological people, with `chb01` and
`chb21` held out together. It checks complete sample-score coverage, evaluates
exact source event semantics, and reports sample diagnostics plus full-support
constant controls. The [prospective policy](../implementations/seizure-events-v1/recommended_policy.json)
fixes the 10 Hz score grid, threshold, causal context, source-default tolerances,
merging/splitting and complete leave-one-person-out folds.

This source component measures tolerant retrospective event coverage. Processed
events are not original clinical seizure counts, and F1 does not establish onset
timeliness. Training recipes must be frozen before outer evaluation, with all
fitting/calibration/preprocessing restricted to permitted outer-training people
and inner person-held-out selection for tuning. Held-out-person fitting is not
authorized by this profile.

The operator must supply complete normalized metadata and private references.
Public support excludes reference events, annotation status and annotation hashes.
Candidate commitments use only that public projection. Original EEG payloads,
normalization, clocks/montage, protected execution, competent EEG-derived and
timing/montage-only baselines, paired uncertainty and scientific qualification
remain required. Generated checks establish software behavior only.

See the package guide for input schemas, resource declarations, source-verification
commands, scoring commands, interpretation and the retained qualification gates.
