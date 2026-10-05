# Held-run EEG condition decoding (MOTORIMAGERY-001)

Compute an offline hands-versus-feet condition decoder and its within-run
pair-preserving permutation reference distribution for ten fixed participants. Use the public
recipe below. This is a method-control analysis of cue-labeled conditions,
not a reproduction of a named BCI2000 performance result or an online BCI test.

## Original public data

The 30 original EDF+ recordings from PhysioNet EEG Motor Movement/Imagery
version 1.0.0 are under `/app/data/eegbci/S001/S001R06.edf`, etc.
Use subjects 1–10, runs 6, 10 and 14. The image includes the original embedded
annotations, published checksums and attribution in `data_manifest.json`.
Runtime access is offline. The dataset is ODC-By 1.0:
https://doi.org/10.13026/C28G6P.

T1 means imagined both fists (class 0); T2 means imagined both feet (class 1);
T0 is rest and is not an epoch. Top/bottom visual cues covary with condition,
so decoding does not isolate motor-imagery physiology from cue/attention effects.
Schalk et al. (2004), https://doi.org/10.1109/TBME.2004.827072, is system
provenance, not the specific ten-subject analysis reproduced here.

## Public computation contract

The complete library settings and source hashes are provided in
`/app/method_contract.json`. Use MNE 1.12.1, scikit-learn 1.8.0,
NumPy 2.2.6 and SciPy 1.17.0, or a numerically equivalent implementation.

- Process each acquisition run separately. Retain all 64 EEG channels in
  original order, standardize channel names and use the standard_1005 montage.
  Do not rereference, interpolate, apply ICA or fit preprocessing across runs.
- Apply a run-local 7–30 Hz FIR filter: automatic length/transition widths,
  zero phase, Hamming window, firwin design, reflect_limited padding,
  skipping edge/bad_acq_skip annotations. Use one numerical worker.
- Build epochs from 1.0 through 2.0 seconds after every T1/T2 cue: 161 samples
  at 160 Hz, including both endpoints. No baseline, projection, detrending,
  amplitude rejection or decimation. Respect BAD annotations and record
  out-of-bounds/annotation exclusions; do not silently remove other trials.
  Assign `event_index` as the zero-based chronological **T1/T2-only** index
  within each run, before exclusions. `event_sample` is the original run-local
  cue sample, with rounded annotation onset; duplicate cue samples are invalid.
- Within each subject, leave out one entire acquisition run at a time.
  Fit CSP and LDA only on the other two runs. CSP: four components, empirical
  concatenated-class covariance, no regularization/trace normalization,
  log mean-power features, mutual-information component ordering; remaining
  rank/restriction defaults are explicit in the template. LDA: SVD solver,
  empirical class priors, tolerance 1e-4, no shrinkage.
- Save the decision score for class 1 minus class 0. Positive score predicts
  class 1; zero or negative predicts class 0. Observed accuracy is pooled over
  all held-out epochs of that subject, **not** an unweighted fold mean.

### Conditional permutation analysis

The original source schedule has one hand and one foot cue in every adjacent
pair of task events (indices 0/1, 2/3, ..., 12/13); event 14 is a singleton.
Preserve that structure. Replicate 0 uses the original labels. For each subject
independently initialize `numpy.random.RandomState(0)`. Generate replicates
1 through 200 in order; inside each replicate visit runs 6, 10, 14 in order,
then original pair IDs `event_index//2` in ascending order. For each complete
retained two-event pair call `rng.permutation(original_labels_of_pair)`.
Keep singleton labels fixed, including any surviving member whose pair partner
was excluded. Do not compact retained rows into new pairs. Always permute the
original labels, not the preceding permutation. Keep source membership and
held-run folds fixed. Refit CSP and LDA within every fold of every replicate.

Use the same pooled out-of-fold accuracy for observed and permuted data.
For each subject:
`perm_p=(1+count(null_accuracy >= observed_accuracy))/201`.
Compute null mean and population SD (`ddof=0`), and Holm-adjust the ten
per-subject p-values as one family. Use strict `p<0.05` for counts.
The minimum p is 1/201; this is a coarse Monte Carlo calculation, not proof
that a subject is above or below an exact physiological threshold.

This shuffle assumes label exchangeability within the original adjacent pairs.
It preserves the observed scheduling constraint but does not establish the
historical randomization mechanism or eliminate all temporal dependence.
It is a conditional method reference, not a verified causal randomization test.
Do not choose another null or tune the pipeline to obtain a desired significant
count. No particular count or accuracy direction is required by the grader.

Average subject accuracies and subject Cohen kappas equally across ten people.
`finite_sample_null_sd` is the mean of the ten individual null SDs, not a
pooled-null SD or a significance cutoff. Also report the two-sided one-sample
t statistic and p-value of subject accuracies versus 0.5. If between-subject
variance is zero, report JSON null for both. The selected ten participants
do not support an unrestricted population claim.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). CSV rows may be reordered;
identities, coverage, integer counts and permutation membership must be exact.

- `source_epochs.csv`: every original T1/T2 event, including exclusions:
  `subject,run,event_index,event_sample,source_class,retained,drop_reason`.
  `retained` is 0 or 1. Retained rows have empty reason; excluded rows use
  `out_of_bounds`, `annotation`, or both joined by a semicolon.
- `oof_predictions.csv`: every retained event × all 201 replicates:
  `subject,run,event_index,event_sample,replicate,source_class,target_class,
  predicted_class,decision_score`. Original `source_class` is unchanged;
  `target_class` is that replicate's possibly permuted label.
- `fold_receipts.csv`: every subject × replicate × held-out run:
  `subject,replicate,test_run,n_train,n_test,n_train_class0,n_train_class1,
  n_test_class0,n_test_class1,accuracy`. Counts refer to that replicate's
  target labels; accuracy recomputes from its held-out rows.
- `per_subject.csv`: ten unique rows:
  `subject,n_epochs,n_runs,accuracy,kappa,perm_p,holm_p,null_mean,null_sd,
  n_null_ge_observed`.
- `decoding_results.json`: `status:"ok"`,
  `pipeline_id:"eegbci-paired-null-held-run-csp-v3"`,
  `n_subjects,n_epochs_total,n_classes,chance_level,accuracy,cohen_kappa,
  finite_sample_null_sd,group_t_vs_chance,group_p_vs_chance,
  n_subjects_significant_perm_p05,n_subjects_significant_holm_p05,
  n_subjects_below_chance,n_subjects_above_half_nominal,
  permutation_p_resolution`.
- `run_metadata.json`: the public contract plus `status:"ok"`,
  `n_subjects,n_epochs_total,n_source_events,n_dropped_epochs,channels,sfreq`
  and `n_epochs_by_run`, a list of
  `{subject,run,n_source_events,n_retained,n_dropped}`.
- `findings.md`: a short numerical summary and the limits above. Offline
  nonsignificance is not evidence that someone cannot operate an online BCI.

The verifier checks source-bound decision scores (atol 1e-7, rtol 1e-5),
their predicted signs, all label permutations, folds and recomputed summaries
(atol/rtol 1e-6). Retain adequate decimal precision. Numerically equivalent
scores near zero can change a predicted sign; resulting statistics must still
be computed from the submitted scores/predictions. No prose keywords or
performance/significance bands are graded. Scoring is all-or-nothing.
Authoring-only model/source arrays are not participant outputs.

If input verification, epoch construction or a required fit fails, exit nonzero
and write parseable result and metadata JSON with `status:"failed_precondition"`
and a nonempty reason, plus findings. Do not fabricate, pad or drop data to pass.
