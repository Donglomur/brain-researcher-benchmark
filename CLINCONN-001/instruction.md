# Resting-state connectivity in schizophrenia vs. controls (CLINCONN-001)

## Scientific context

Resting-state functional connectivity (FC) has been widely proposed as a biomarker of
schizophrenia, with many reports of altered cortico-cortical connectivity in patients
relative to healthy controls. The UCLA Consortium for Neuropsychiatric Phenomics (CNP)
study (Poldrack et al. 2016, *Scientific Data*) is a large, openly available dataset
(OpenNeuro `ds000030`) that includes a schizophrenia group and a healthy-control group with
resting-state fMRI, and it ships preprocessed **fMRIPrep derivatives**, making it a standard
testbed for case-vs-control resting-connectivity comparisons.

## Task

Using the released **fMRIPrep derivatives** of `ds000030` (legacy release `R1.0.5`, under
`.../derivatives/fmriprep/`), **compute resting-state functional connectivity for the
schizophrenia group and the healthy-control group and report whether — and how — resting FC
differs between the two groups.**

Work from the fMRIPrep resting-run outputs of every subject that has a rest run in the two
groups (diagnosis `SCHZ` and `CONTROL` in `participants.tsv`). For each subject, build a
region×region connectivity matrix from a standard cortical parcellation (for example the
surface `space-fsaverage5` outputs with a Destrieux/Schaefer atlas, or the volumetric
`space-MNI152NLin2009cAsym` outputs with a volumetric atlas), applying common resting-state
preprocessing to the parcel time series (nuisance regression using the supplied confounds,
temporal filtering, normalisation). Summarise each subject's connectivity (e.g. mean edge
strength, and short- vs long-range edges by inter-node distance), then compare the
schizophrenia group with the control group — both a subject-level summary and an edge-wise
comparison.

Report, in plain terms, **whether resting-state functional connectivity differs between the
schizophrenia group and controls on these data** — stating only what your analysis actually
supports.

## Data access

`ds000030` fMRIPrep derivatives are public (no credentials) on S3, e.g.

```
https://s3.amazonaws.com/openneuro/ds000030/ds000030_R1.0.5/uncompressed/participants.tsv
https://s3.amazonaws.com/openneuro/ds000030/ds000030_R1.0.5/uncompressed/derivatives/fmriprep/<sub>/func/<sub>_task-rest_bold_space-fsaverage5.L.func.gii
.../<sub>_task-rest_bold_space-fsaverage5.R.func.gii
.../<sub>_task-rest_bold_confounds.tsv
```

(the `_confounds.tsv` columns include the 6 motion parameters, aCompCor/tCompCor components,
WhiteMatter, GlobalSignal, and FramewiseDisplacement).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.csv` — one row per subject:
  `subject_id, group, mean_fc, short_range_fc, long_range_fc`.
- `group_stats.json` — the schizophrenia-vs-control comparison: `group_means` per measure,
  the group test per measure, an edge-wise summary of how many connections differ between
  groups, and the group sizes.
- `run_metadata.json` — dataset id, derivatives used, n subjects per group, atlas,
  distance bins, and the preprocessing choices you made.
- `findings.md` — a short written summary stating whether resting-state FC differs between
  the schizophrenia group and controls on these data. State only what your analysis supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `group_stats.json`, and `findings.md`.
