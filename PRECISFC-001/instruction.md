# Test-retest reliability of the individual functional connectome (PRECISFC-001)

## Scientific context

A central result of "precision" resting-state fMRI is that the whole-brain functional
connectome is **individual-specific and highly reproducible across sessions**: given
repeated scans of the same person, the region×region connectivity matrix is stable enough to
act as an individual fingerprint (Gordon et al. 2017, *Neuron*, "Precision Functional Mapping
of Individual Human Brains"; Laumann et al. 2015). The **Midnight Scan Club** (MSC) dataset
(OpenNeuro `ds000224`) was built for exactly this: ten subjects, each scanned across ten
separate resting-state sessions, with a released **volume-pipeline** that provides, per
session, a processed resting-state BOLD run in a common (Talairach) space.

## Task

Using the MSC volume-pipeline resting-state derivatives of `ds000224`, **quantify the
test-retest reliability of the individual functional connectome across sessions** for the
following subjects and sessions:

- subjects: `sub-MSC01`, `sub-MSC02`, `sub-MSC05`, `sub-MSC06`, `sub-MSC08`, `sub-MSC09`
- sessions per subject: `ses-func01`, `ses-func02`, `ses-func03`

For each subject and session, extract mean BOLD time series from the **Power et al. (2011)
264-ROI coordinate atlas** (`nilearn.datasets.fetch_coords_power_2011`, 5 mm spheres) and
form the ROI×ROI correlation matrix (Fisher-z). Define each subject's **cross-session
reliability** as the mean pairwise similarity (correlation) between that subject's per-session
connectome edge-vectors, and summarise a **group-level reliability** across subjects.

Report, in plain terms, **how reliable the individual functional connectome is across
sessions on these data** — stating only what your analysis actually supports.

## Data access

The MSC volume-pipeline derivatives are public (no credentials) on S3. Per session, the
directory `.../talaraich/` contains two files:

```
https://s3.amazonaws.com/openneuro.org/ds000224/derivatives/volume_pipeline/sub-<ID>/processed_restingstate_timecourses/ses-<SES>/talaraich/sub-<ID>_ses-<SES>_task-rest_bold_talaraich.nii.gz
.../sub-<ID>_ses-<SES>_task-rest_bold_talaraich_tmask.txt
```

The `*_talaraich.nii.gz` is the processed resting-state BOLD run (all acquired frames); the
accompanying `*_tmask.txt` is a per-frame binary vector for that run (one value per BOLD
frame).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `reliability.csv` — one row per subject:
  `subject_id, n_sessions, n_frames, reliability`.
- `reliability_stats.json` — the per-subject reliability values and a group-level reliability
  summary, plus the number of subjects.
- `run_metadata.json` — dataset id, subjects, sessions, atlas, the reliability metric, and the
  preprocessing choices you made.
- `findings.md` — a short written summary stating how reliable the individual functional
  connectome is across sessions on these data. State only what your analysis supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `reliability_stats.json`, and
`findings.md`.
