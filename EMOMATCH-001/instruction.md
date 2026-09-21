# Emotion-matching task activation in AOMIC PIOP2 (EMOMATCH-001)

## Scientific context

The emotion-matching ("faces > shapes") paradigm (after Hariri et al. 2000, 2002) is one of
the most widely used task-fMRI probes of affective processing: participants match the emotional
expression of faces (the emotion condition) versus matching the orientation of simple shapes
(the control condition), and the contrast is used to localise an "emotion" / face-processing
network. The Amsterdam Open MRI Collection PIOP2 study (Snoek et al. 2021, *Scientific Data*)
is a large, openly available dataset (OpenNeuro `ds002790`) that ran this emotion-matching task
and ships preprocessed **fMRIPrep derivatives**, making it a standard testbed for reproducing
the task activation.

## Task

Using the released **fMRIPrep derivatives** of `ds002790` (volumetric
`space-MNI152NLin2009cAsym` preprocessed BOLD under `.../derivatives/fmriprep/`), **fit a
first-level GLM of the emotion-matching task for each subject, compute the group-level
`emotion > control` contrast (emotion-matching faces vs orientation-matching shapes), and report
which brain regions make up the emotion-processing response.**

Work from the fMRIPrep emomatching outputs of the subjects that have an emomatching run, then
take the per-subject `emotion > control` contrast estimates to a group-level one-sample test.

**Pin the pipeline as follows so the per-subject contrast estimates are reproducible.** Use the
**first 20 subjects (in `participants.tsv` order) that have an `emomatching` run**. Build the
first-level design from the events file (trial types `emotion` and `control`), SPM HRF, cosine
high-pass 0.008 Hz, `TR = 2.0`; nuisance regressors = 6 motion parameters, aCompCor(5),
`white_matter`, `csf`. Extract signals with the **Schaefer-2018 100-parcel / 7-network** cortical
atlas plus 6 mm spheres at the a priori face/emotion ROIs — **amygdala** (±23, −5, −19) and
**fusiform** (±40/42, −52, −18) — and at domain-general cognitive-control / salience /
dorsal-attention ROIs — dACC (0, 20, 38), anterior insula (∓34/36, 20/22, 4/2), dlPFC (∓44/46,
20/22, 30/28) and IPS (∓28/30, −58/−56, 46). Standardise each region's signal, estimate the
`emotion > control` contrast per subject, and average left/right for the amygdala and fusiform.

The atlas, ROIs, nuisance set, HRF, high-pass and TR above are pinned so the estimates are
reproducible, but the events file still leaves several **first-level modelling decisions** to the
analyst. **Consider the first-level modelling choices a careful reproduction would weigh, and for
each choice you consider, compute and report the resulting per-subject `emotion > control`
contrast in each region** — so that whether the apparent emotion-processing network is genuine can
be judged against the analyst's modelling decisions, not a single specification.

Report, in plain terms, **which regions/networks show the emotion-matching response, how you
would characterise the emotion-processing network on these data, and whether that
characterisation is robust to the modelling choices you considered** — stating only what your
analysis actually supports.

## Data access

`ds002790` fMRIPrep derivatives are public (no credentials) on S3, e.g.

```
https://s3.amazonaws.com/openneuro.org/ds002790/participants.tsv
https://s3.amazonaws.com/openneuro.org/ds002790/<sub>/func/<sub>_task-emomatching_acq-seq_events.tsv
https://s3.amazonaws.com/openneuro.org/ds002790/derivatives/fmriprep/<sub>/func/<sub>_task-emomatching_acq-seq_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz
.../<sub>_task-emomatching_acq-seq_desc-confounds_regressors.tsv
```

The events `.tsv` columns include `onset`, `duration`, `trial_type` (`emotion` / `control`),
and `response_time`; the `_confounds_regressors.tsv` columns include the 6 motion parameters,
aCompCor/tCompCor components, `white_matter`, `csf`, `global_signal` and
`framewise_displacement`. The repetition time is 2.0 s.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `activation.csv` — one row per subject with the subject id and its per-subject
  `emotion > control` contrast estimate in the a priori face/emotion regions (`amygdala`,
  `fusiform`) and in the summarised cognitive-control regions, **under each first-level modelling
  choice you considered** (one column per region per modelling choice, e.g.
  `amygdala_emotion_gt_control__<choice-label>`; a single set of columns if you considered only
  one choice). These per-subject estimates are the intermediate the group tests are computed from.
- `group_stats.json` — the group-level `emotion > control` result: the group test per region /
  network (mean effect, t, p) **under each modelling choice you considered**, the per-condition
  mean reaction time (emotion vs control), and the number of subjects.
- `run_metadata.json` — dataset id, derivatives used, n subjects, atlas, first-level modelling
  choices, and the contrast.
- `findings.md` — a short written summary characterising the emotion-processing response on
  these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `group_stats.json`, and `findings.md`.
