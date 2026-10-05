# Class-wise sleep-staging performance on six original Sleep-EDF recordings

Measure a fixed two-channel EEG classifier with leave-one-subject-out (LOSO)
validation. Report both pooled class-recall mean and pooled epoch accuracy:
they answer different questions, and neither is inherently an inflated metric.
No particular performance, difference, class ranking or narrative is required.

This is an **easy tutorial-derived method control**, not a reproduced paper
finding or clinical validation. The original
[Sleep-EDF resource](https://physionet.org/content/sleep-edfx/1.0.0/) links the
sleep-cassette age cohort to Mourtazaev et al. (1995), and requests Kemp et al.
(2000) attribution. These are data-resource references, not evidence for this
six-subject random forest's performance. The
[MNE sleep tutorial](https://mne.tools/1.12/auto_tutorials/clinical/60_sleep.html)
motivates the workflow, but its current default PSD and example cohort differ.
Released annotations follow Rechtschaffen–Kales (R&K); merging stages 3 and 4
does **not** create newly scored AASM ground truth. The legacy task ID is retained.

## Original inputs and epoch identity

Use the twelve original PSG/hypnogram EDF files in `/app/data/aasmstage` for
subjects 0–5, recording 1, Sleep-EDF Expanded 1.0.0. The source manifest binds
file paths, published SHA-256 checksums, sizes and attribution under ODC-By-1.0.
Run offline; do not substitute derived features, synthetic recordings or a
different cohort. The public `/app/method_contract.json` specifies every required
output field, source rule, estimator parameter and numerical tolerance.

Select exactly `EEG Fpz-Cz` then `EEG Pz-Oz`. Both are stored at 100 Hz, but other
channels have different sample rates. Apply each channel's EDF affine digital-
to-physical calibration and convert microvolts to float64 volts. Keep original
header values; their historical prefilter text is not an instruction to apply
another filter or evidence of modern anti-alias quality. Add no rereferencing,
resampling, baseline correction, amplitude rejection or signal-dependent QC.

Preserve every original annotation index and TAL index. The requested crop is
original annotation 1's onset minus 1,800 seconds through original penultimate
annotation onset plus 1,800 seconds. These indices are a tutorial convention,
not a semantic first/last-sleep rule. Intersect annotations with that crop and
the recording's `[0, n_samples/100]` support **before** creating chunk grids.
For these sources, annotation origin is null and onsets are recording-relative;
matching header dates do not justify a separate origin shift or invented timezone.

Anchor each annotation's 30-second chunks at its final clipped onset. Use the
published completeness tolerance and ties-to-even sample rounding. Each retained
epoch is exactly `[onset_sample, onset_sample+3000)` in the original PSG. Keep
all complete candidate chunks in the epoch ledger, including unsupported-stage
chunks with explicit rejection status; account for partial tails in the
annotation ledger. Map W/1/2/3+4/R to class IDs 1/2/3/4/5. Movement and unscored
annotations are not a sixth class and must not be silently relabelled. Reject
ambiguous overlaps or duplicate source epoch keys rather than deduplicating.

## Public features and classifier

For each epoch/channel, estimate Welch density with eleven nonoverlapping
256-sample segments, periodic Hamming windows, segment-wise mean removal,
256-point real FFT, one-sided scaling and arithmetic averaging. The final
184 samples are not used in the PSD; they remain part of the source epoch.
Normalize over the 75 selected bins in 0.5–30 Hz (FFT indices 2–76).

The ten features are **mean normalized PSD-bin heights**, not integrated
bandpower fractions: delta `[0.5,4.5)`, theta `[4.5,8.5)`, alpha `[8.5,11.5)`,
sigma `[11.5,15.5)`, beta `[15.5,30)`, in band-major/channel-minor order. Band
bin counts are 10/10/8/10/37; their weighted feature sum per channel is one,
whereas the unweighted sum need not be. Also report each channel's positive
absolute selected-bin PSD sum in V²/Hz. Nonfinite values or zero denominators
are failed prerequisites, not imputed features or permission to discard epochs.

Fit six fresh 200-tree random forests, seed 42, with the complete settings in
the contract. Training rows are ordered by subject, then original onset sample;
each held-out person is absent from their model's training set. No scaler,
balancing, class weighting, tuning or extra selection is added. Feature receipts
are float64; the pinned classifier converts its inputs to float32. This is a
specified computational recipe, not equivalence across arbitrary forest engines.

Report five held-out probabilities per retained epoch. Predictions must be the
argmax of those submitted probabilities, breaking exact ties toward the smaller
class ID. Probabilities must agree with the source-bound calculation within
the public tolerance. A legitimate rounding-induced near-tie flip is not subject
to an additional hidden exact-label rule; all metrics must follow the actual
accepted predictions.

## Outputs and interpretation

Write all nine contract-defined artifacts to `${OUTPUT_DIR}` (default
`/app/output`): `annotations.csv`, `epochs.csv`, `epoch_features.csv`,
`epoch_predictions.csv`, `per_subject.csv`, `confusion_counts.csv`,
`staging_results.json`, `run_metadata.json`, and nonempty `findings.md`.
Complete source keys, truth, features, probability vectors and fold membership
are required; a plausible confusion matrix or model description alone is not.
CSV row/column ordering and ordinary prose variation are not errors.

The headline `accuracy` is explicitly pooled balanced accuracy: compute class
recalls from the **sum** of held-out confusion matrices, then average supported
classes. Also report epoch-weighted overall accuracy, per-class support/recall,
subject metrics and kappa. Keep absent-class recall and degenerate kappa null
with their stated statuses. Do not substitute the mean of subject balanced
accuracies for the pooled headline; it is a different descriptive endpoint.

The independent validation unit is a person, not each correlated epoch. Six
selected recordings support a small within-resource demonstration, not clinical
or population generalization. No epoch-wise confidence interval or required
accuracy gap is part of this task. If a source/schema/numerical prerequisite
fails, exit nonzero with parseable failure results and metadata, a nonempty
reason and findings. Preserve earlier evidence and never fabricate completion.
