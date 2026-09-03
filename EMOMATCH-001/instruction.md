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

Work from the fMRIPrep emomatching outputs of the subjects that have an emomatching run. For
each subject, build the task design from the events file (trial types `emotion` and `control`),
convolve with a haemodynamic response function, include the supplied fMRIPrep confounds as
nuisance regressors and an appropriate high-pass filter, and estimate the `emotion > control`
contrast. Summarise the response using a standard cortical parcellation (for example the
Schaefer-2018 atlas with its Yeo-network labels) together with a priori regions of the emotion /
face circuitry (e.g. amygdala and fusiform), then take the per-subject contrast estimates to a
group-level one-sample test.

Report, in plain terms, **which regions/networks show the emotion-matching response and how you
would characterise the emotion-processing network on these data** — stating only what your
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

- `activation.csv` — one row per subject with the subject id and its `emotion > control`
  contrast estimate in the a priori face/emotion regions and in the summarised
  cognitive-control regions.
- `group_stats.json` — the group-level `emotion > control` result: the group test per region /
  network (mean effect, t, p) and the number of subjects.
- `run_metadata.json` — dataset id, derivatives used, n subjects, atlas, first-level modelling
  choices, and the contrast.
- `findings.md` — a short written summary characterising the emotion-processing response on
  these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `group_stats.json`, and `findings.md`.
