# AASMSTAGE-001: source-bound class-wise sleep-staging method control

Keep the six original Sleep-EDF recording-1 pairs and an honestly labelled
tutorial baseline. Do not claim AASM rescoring, Kemp's algorithm performance,
a named paper finding, clinical validation or demonstrated model difficulty.

The source resource provides original EEG and R&K labels under ODC-By-1.0:
[Sleep-EDF Expanded 1.0.0](https://physionet.org/content/sleep-edfx/1.0.0/).
Mourtazaev et al. (1995) describes the age-study cohort; Kemp et al. (2000) is
the resource's requested reference. The
[MNE tutorial](https://mne.tools/1.12/auto_tutorials/clinical/60_sleep.html)
provides methodological inspiration, not this task's expected outcome.

## Repair the actual mismatch before measuring performance

The previous instruction requested Welch but `Epochs.compute_psd()` omitted
`method`, selecting multitaper in the pinned MNE version. Publish one completely
specified Welch-256 recipe before inspecting new EEG features or forest results;
do not relabel the previous bank. Normalized band-bin **means** are not integrated
bandpower. Keep their units, bin counts, ordering and absolute PSD normalization
diagnostics explicit. Preserve the source EDF calibration and original channel
identities instead of relying on generic reader channel types.

The original second/penultimate annotation-index crop remains public. Clipping
annotations before chunk construction is part of the definition: clipping can
move a chunk anchor. Bind all annotation/TAL and original sample coordinates,
including unsupported movement and out-of-crop annotations. Retain complete
candidate dispositions and partial-tail accounting, with no signal-dependent
exclusions. R&K stages 3+4 merge into one class; that is not a new AASM rating.

## Distinct metrics without an invented superiority law

Pooled mean class recall and pooled epoch accuracy weight the same predictions
differently. Report both, with all six source-identified LOSO folds and five
classes. Do not demand a particular gap, class ordering, variability or minimum
performance. Per-subject metrics remain descriptive; many correlated epochs do
not create many independent participants. New confidence intervals are not
needed to claim a six-subject method-control result, and would require a
separately disclosed inferential protocol.

## Replace summary-based acceptance with source-bound evidence

The old verifier can accept duplicated epochs with doubled counts or shuffled
within-class predictions because its checks only constrain scalar summaries.
Its metadata is unvalidated and broad numerical bands do not test a specific
Welch model. Replace these with exact original annotation/sample/class coverage,
complete numerical features, all five model probabilities, fold identities,
150 explicit confusion cells and recomputed metrics. Publish all schemas and
undefined cases; eliminate prose keywords, mandatory score variation and
hidden accuracy ranges. Use each submitted probability vector's own argmax
with the public tie rule and derive all summaries from its accepted predictions.

Three original-source routes should independently reconstruct EDF calibration,
epochs and Welch features before comparison. Fresh forests use the same pinned
scikit-learn backend; disclose that shared fitting implementation. Independent
tree traversal verifies saved-model-to-prediction consistency, not proof of
correct training. Retain model states privately for the authoring audit, but
do not place fitted models, reference arrays or oracle code in the runtime image.

Construct the replacement bank from originals before consulting oracle output.
Accept equivalent row ordering, serialization and independent implementations
within predeclared tolerances. Reject missing/invented samples, scaled or
misordered features, coherent fake probabilities, wrong training membership
and incorrect metric weighting. After baseline agreement, a separately gated
actual multitaper recomputation can establish rejection of the original bug;
changing only its metadata would not establish this.

Source authentication, structural checks, method freeze, source-free fixtures,
numerical pilot, independent full reconstruction, fresh source-only bank,
genuine verifier controls and clean-commit Harbor are separate evidence stages.
Engineering acceptance must not be described as scientific replication or
Sol-hardness. No push, merge, model calibration or public image release is implied.
