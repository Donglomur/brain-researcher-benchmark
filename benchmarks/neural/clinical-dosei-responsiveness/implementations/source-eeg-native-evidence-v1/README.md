# Verified complete native EEG preparation

The complete DoSEI source release was prepared and independently checked:
171 recordings, 70,760,492 native rows and both EEG channels. Every source member
was read to EOF with its original hash/CRC and annotations matched; a separate
single pass checked all saved array hashes, timestamps, quality states and
13,174 private annotation joins. Both actual executions exited successfully.

The verified source provides 7,345 grouped MOAAS responsiveness assessments and
1,132 separate LOC/ROC transition events. This differs from the inherited
7,328/1,129 scorer population. Neither truncation nor silent scorer rebinding
was performed. Source recording IDs do not establish biological-person identity.

The native 250 Hz table's channel blanks and endpoint flags are preserved. The
two duplicate timestamps are retained at their exact source rows. No fixed
125 Hz sampling phase, interpolation, fabricated sentinel, person split, clinical
challenge onset or diagnosis was inferred.

`source-verification.json` records the full source, execution, independent review
and completed verification hashes. Raw arrays and evaluator-private labels stay
outside Git. The sibling `source-eeg-preparation-v1` package preserves the exact
executed source and generated controls; its archived native CLI remains bound
to the original admitted environment.

This is completed source preparation for one task. It does not add 171 benchmarks
or establish model performance. Participant case indices, paired viewer/code
delivery and a reviewed successor scoring policy still require construction and
qualification. The intended observation is retrospective marker-associated
responsiveness over the preceding 30 seconds, not proven pre-challenge prediction.
