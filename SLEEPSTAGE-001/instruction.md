# Subject-held-out sleep staging (SLEEPSTAGE-001)

## Scientific target and data

Evaluate a fixed EEG sleep-staging baseline on six original Sleep-EDF recordings:
subjects 0–5, night 1. The target is accuracy and pooled Cohen kappa on a held-out
subject; every subject's epochs must stay together in leave-one-subject-out (LOSO)
evaluation. This is a modern method case on an acquired public dataset, not a
reproduction of Kemp et al.'s slow-wave feedback result or a clinical validation.

The original PSG and expert hypnogram EDFs are staged under
`/app/data/sleep-edf/`. Its `data_manifest.json` identifies the twelve files,
subject/night/role, source URLs, sizes, SHA256 checksums and ODC-By-1.0 attribution.
Use these local inputs; execution is offline. The source is
[Sleep-EDF Expanded 1.0.0](https://physionet.org/content/sleep-edfx/1.0.0/),
DOI 10.13026/C2X676.

These are historical Rechtschaffen–Kales annotations. Collapse W,1,2,3/4,R into
`W,N1,N2,N3,REM`; merging stages 3 and 4 does not constitute expert AASM rescoring.
Exclude movement and unscored annotations. Interpret results only for this small
selected cohort, not all ages, clinical populations, or every Sleep-EDF recording.

## Public numerical contract

Use MNE 1.12.1 and scikit-learn 1.8.0 provided in the image.

1. Read the two channels in this order: `EEG Fpz-Cz`, `EEG Pz-Oz`, at 100 Hz.
   Crop annotations from the second annotation onset minus 1800 seconds through
   the penultimate annotation onset plus 1800 seconds. This is an annotation-index
   rule, not a claim that those annotations always mark sleep onset/offset.
   Match `mne.Annotations.crop` and `events_from_annotations(chunk_duration=30)`;
   keep complete scored 30-second epochs (3000 samples, no baseline correction).
   Preserve each epoch's original EDF start sample; do not renumber after cropping.
2. Compute Welch PSD for each epoch/channel: 300-sample Hamming segments,
   `n_fft=n_per_seg=300`, overlap 0, remove each segment's mean, average segment
   PSDs, and keep frequencies 0.5–30 Hz inclusive. Normalize by the sum of those
   PSD bins. For each band, take the mean normalized PSD bin, using lower-inclusive,
   upper-exclusive boundaries: [0.5,4), [4,8), [8,12), [12,16), [16,30).
   Concatenate bands in this order, channels within band, giving ten features.
   These are mean normalized-bin features, not integrated band-power fractions.
3. Fit `RandomForestClassifier(n_estimators=200, random_state=0, criterion="gini",
   max_depth=None, min_samples_split=2, min_samples_leaf=1, max_features="sqrt",
   bootstrap=True)`, other defaults unchanged. Use at most two CPU workers.
   Concatenate subjects in order 0–5 and epochs chronologically within subject.
   For each of six folds, train on the other five subjects and predict every
   retained epoch of the held-out subject.
4. Compute each subject's 5-by-5 confusion matrix, accuracy and Cohen kappa.
   Sum the six matrices before calculating headline accuracy and kappa. Pooled
   kappa is not the mean of the six subject kappas. A random-epoch comparison is
   optional and is not required for acceptance.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `epoch_predictions.csv`: `subject,recording,onset_sample,true_class,predicted_class,heldout_subject`.
  Every retained source epoch appears exactly once; recording is 1, subject and
  heldout_subject are the same numeric ID (0–5), and classes use the labels above.
- `per_subject.csv`: `subject,n_test_epochs,accuracy,kappa`.
- `confusion_counts.csv`: all 25 cells for each subject, including zeros, with
  `subject,true_class,predicted_class,n_epochs`. Counts are nonnegative integers.
- `staging_results.json`: `cv_scheme="leave-one-subject-out"`, `accuracy`,
  `cohen_kappa`, `n_subjects=6`, `n_epochs`, `n_classes=5`.
- `run_metadata.json`: the dataset and estimator contract described below.
- `findings.md`: a short account of the measured results, held-out unit and
  limited scientific scope. No specific keywords or random-fold discussion are
  required by the verifier.

Use this metadata contract; extra descriptive fields are allowed:
`pipeline_id="sleepedf-loso-v2"`, `dataset_id="sleep-edfx-1.0.0"`,
`subjects=[0,1,2,3,4,5]`, `recording=1`, `channels=["EEG Fpz-Cz","EEG Pz-Oz"]`,
`epoch_sec=30`, `sfreq=100`, `classes=["W","N1","N2","N3","REM"]`,
`cv_scheme="leave-one-subject-out"`.
Include `source_sha256`, mapping each manifest-relative filename to its checksum.
The `preprocessing` object has:
`crop_rule="second_annotation_minus_1800_to_penultimate_plus_1800"`,
`n_fft=300,n_per_seg=300,n_overlap=0,window="hamming",remove_dc=true,average="mean"`,
`fmin=0.5,fmax=30.0,normalization="sum_psd_bins",band_reduction="mean"`,
`feature_order="band_then_channel"`, and
`bands=[[0.5,4],[4,8],[8,12],[12,16],[16,30]]`.
The `classifier` object has `name="RandomForestClassifier"` and the parameters
specified in step 3 (except the implementation worker count).

The verifier compares source-keyed labels and predicted classes to the declared
pinned recipe and recomputes every confusion cell and metric. CSV row order and
equivalent integer representations do not matter. Report subject metrics to at
least six decimals (absolute tolerance 1e-6) and pooled metrics to at least five
decimals (tolerance 1e-5). There is no private performance threshold, required
between-subject variability, or required random-split gap. Output agreement does
not itself prove how a submitted training program was executed.

## Failure handling

If an input or source identity cannot be verified, exit nonzero and write
parseable results/metadata with `status="failed_precondition"`, a nonempty reason,
and a short findings report. Never replace unavailable EDFs with simulated data.
