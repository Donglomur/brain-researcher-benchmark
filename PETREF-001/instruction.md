# Serotonin-transporter binding from dynamic [11C]DASB PET (PETREF-001)

## Scientific context

[11C]DASB is the standard PET radioligand for the serotonin transporter (SERT). It has
no arterial input, so binding is quantified with a **reference-tissue** model against a
region taken to be free of specific binding (the cerebellum). The headline outcome is the
non-displaceable binding potential **BP_ND** in SERT-rich target regions (Knudsen et al.,
2016, *NeuroImage*, the Cimbi database; Nørgaard & Ganz et al., 2022, *Scientific Data*,
https://doi.org/10.1038/s41597-022-01164-1; SRTM: Lammertsma & Hume, 1996).

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
and one column per region, among them `left_putamen`, `right_putamen`,
`left_cerebellum_cortex`, `right_cerebellum_cortex`, `left_cerebellum_white_matter`,
`right_cerebellum_white_matter`, `vermis`, and a pre-computed `reference` column, all in
Bq/mL.

## Task

For **each of the four scans**, estimate the serotonin-transporter binding potential
**BP_ND in the putamen** (bilateral) using a **reference-tissue kinetic model**, and
summarise the test-retest reproducibility. Report BP_ND per scan.

Standard implementation choices the reference-tissue framework leaves to the analyst
(the reference-region definition, which reference-tissue model/estimator, frame weighting,
and fitting details) should follow common practice **for this tracer**; the brief does not
spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `bp_estimates.csv` — one row per scan, with columns `subject, session, target,
  reference_region, model, BP_ND` (extra columns such as `R1`, `k2` are welcome).
- `run_metadata.json` — dataset id, snapshot, target region, reference region, model, and
  the per-scan and mean putamen BP_ND.
- `findings.md` — a short written summary: the per-scan and mean putamen BP_ND, the
  test-retest reproducibility, and an account of the reference region and model you used
  and why. State only what your analysis supports.

## Failure handling

If the dataset cannot be fetched or the expected TAC columns are absent, exit non-zero with
`failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `bp_estimates.csv`, and `findings.md`.
