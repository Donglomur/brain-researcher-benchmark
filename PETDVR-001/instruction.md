# Serotonin-transporter DVR from dynamic [11C]DASB PET (PETDVR-001)

## Scientific context

[11C]DASB is the standard PET radioligand for the serotonin transporter (SERT). It is a
reversibly-binding tracer with no arterial input, so its regional binding is summarised by
the **distribution volume ratio DVR** — the equilibrium ratio of the total distribution
volume in a target region to that in a reference region assumed free of specific binding.
For a reversible tracer with a reference region, DVR is obtained directly from the
**Logan reference-tissue graphical plot**, whose slope is the DVR (Logan et al., 1996,
*JCBFM*; Ichise et al., 2002, *JCBFM*, MA1). Data: Knudsen et al., 2016, *NeuroImage*
(the Cimbi database); Nørgaard & Ganz et al., 2022, *Scientific Data*,
https://doi.org/10.1038/s41597-022-01164-1.

## Data

OpenNeuro `ds001420` (a [11C]DASB test-retest dataset: 2 participants, each scanned
twice). Use the **PETPrep-derived regional time-activity curves** (TACs), which are
motion-corrected and sampled on a FreeSurfer segmentation. Fetch the four TAC tables at
runtime from OpenNeuro (open, no credentials), snapshot `1.2.0`:

```
https://openneuro.org/crn/datasets/ds001420/snapshots/1.2.0/files/<PATH>
```

where `<PATH>` is the file path with `/` replaced by `:` (the endpoint 302-redirects to
the file; follow redirects). The four TAC files are:

```
derivatives:PETPrep1:sub-01:ses-baseline:pet:sub-01_ses-baseline_pvc-nopvc_desc-mc_tacs.tsv
derivatives:PETPrep1:sub-01:ses-rescan:pet:sub-01_ses-rescan_pvc-nopvc_desc-mc_tacs.tsv
derivatives:PETPrep1:sub-02:ses-baseline:pet:sub-02_ses-baseline_pvc-nopvc_desc-mc_tacs.tsv
derivatives:PETPrep1:sub-02:ses-rescan:pet:sub-02_ses-rescan_pvc-nopvc_desc-mc_tacs.tsv
```

Each TSV has one row per PET frame. Columns include `frame_start`, `frame_end` (seconds),
a pre-computed `reference` column (the reference-tissue TAC), a `highbinding` column (the
SERT high-binding composite), and one column per FreeSurfer region, among them
`left_thalamus`, `right_thalamus`, `left_caudate`, `right_caudate`, `left_putamen`,
`right_putamen`, all in Bq/mL. **Use the provided `reference` column as the reference
tissue** so the reference region is fixed across the analysis.

## Task

For **each of the four scans**, estimate the [11C]DASB **distribution volume ratio DVR**
with the **Logan reference-tissue graphical method** (DVR is the slope of the Logan plot),
using the provided `reference` tissue. Report DVR in the **high-binding SERT territory**
(the `highbinding` region) and, as a regional profile, in the bilateral **thalamus**,
**caudate**, and **putamen**. Summarise the values across the four scans.

Standard implementation choices the graphical framework leaves to the analyst — the frame
weighting and the details of fitting the plot — should follow common practice **for this
tracer**; the brief does not spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `dvr_estimates.csv` — one row per scan and region, with columns `subject, session,
  target, reference_region, model, DVR` (extra columns such as a cross-check estimator are
  welcome).
- `run_metadata.json` — dataset id, snapshot, target regions, reference region, model, and
  the per-scan and mean high-binding DVR plus the per-region mean DVR.
- `findings.md` — a short written summary: the per-scan and mean high-binding DVR, the
  regional DVR profile, and an account of how you fit the Logan plot and why. State only
  what your analysis supports.

## Failure handling

If the dataset cannot be fetched or the expected TAC columns are absent, exit non-zero with
`failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `dvr_estimates.csv`, and `findings.md`.
