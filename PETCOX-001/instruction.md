# Cerebral distribution volume of a COX-2 radioligand from dynamic [11C]MC1 PET (PETCOX-001)

## Scientific context

[11C]MC1 is a PET radioligand for cyclo-oxygenase-2 (COX-2), an inducible enzyme studied as
a marker of neuroinflammation. COX-2 has no brain region devoid of the target, so the tracer
is quantified with an **arterial input function** (an invasive study with blood sampling)
rather than a reference-tissue model. The headline outcome is the **total distribution
volume V_T** (mL·cm⁻³) — the equilibrium ratio of the tissue concentration of the tracer to
the concentration of parent radioligand in arterial plasma (Innis et al., 2007, consensus
nomenclature). Data: OpenNeuro `ds004869` (first-in-human evaluation of [11C]MC1 in healthy
humans; Kim et al.). Graphical estimators: Logan et al., 1990; Ichise et al., 2002 (MA1).

## Data

OpenNeuro `ds004869` (CC0): a healthy-human [11C]MC1 cohort with dynamic brain PET
(~0–120 min) and concurrent manual arterial blood sampling. Use the **petfit-extracted
regional time-activity curves** (TACs) and the **arterial blood recording**, fetched at
runtime from OpenNeuro (open, no credentials), snapshot `1.4.0`:

```
https://openneuro.org/crn/datasets/ds004869/snapshots/1.4.0/files/<PATH>
```

where `<PATH>` is the file path with `/` replaced by `:` (the endpoint 302-redirects to the
file; follow redirects).

* **Regional TACs (one file, all participants):**

  ```
  derivatives:petfit:desc-combinedregions_tacs.tsv
  ```

  A long-format TSV with one row per (participant, session, region, PET frame). Relevant
  columns are `sub` (`1`…`27`), `ses`, `region`, `frame_start`, `frame_end`, `frame_dur`,
  `frame_mid` (seconds), and `TAC` (regional activity, **Bq/mL**, decay-corrected to
  injection). The `region` values are combined anatomical regions; the **cerebral-cortex**
  (cortical gray matter) regions are `Frontal`, `Temporal`, `Parietal`, `Occipital`, `ACC`,
  `PCC`, and `Insula` (subcortical regions such as `Caudate`, `Putamen`, `Thalamus`,
  `Hippocampus`, `Amygdala` are also present).

* **Arterial blood (one file per scan):**

  ```
  sub-XX:ses-YYY:pet:sub-XX_ses-YYY_recording-manual_blood.tsv
  ```

  One row per sample. Columns are `time` (seconds from injection), `plasma_radioactivity`,
  `metabolite_parent_fraction` (the intact-parent fraction of plasma radioactivity, from
  HPLC), and `whole_blood_radioactivity`. The blood samples are already on the **same decay
  footing as the TACs** (decay-corrected to injection). Rows with a repeated `time == 0`
  after the first sample are padding and should be ignored.

**Participants and sessions.** Analyse each of the **27 participants** (`sub-01` … `sub-27`)
at their baseline (drug-free) scan: session **`baseline`** for `sub-01`…`sub-10`, session
**`test`** for `sub-11`…`sub-27`. Do not substitute a different or manually-prepared dataset.

## Task

For **each of the 27 participants**, estimate the [11C]MC1 **total distribution volume V_T
in the cerebral cortex** (cortical gray matter) using an **arterial-input kinetic model**,
and summarise the cohort: the average cortical V_T and how it varies across participants.

The model input is the **metabolite-corrected arterial plasma** — the plasma radioactivity
scaled by the parent fraction — placed on the same decay footing as the tissue TACs (both
are decay-corrected to injection, so no further decay handling is required). The **model
form and the fitting details** the kinetic framework leaves to the analyst should follow
**common practice for this tracer**; the brief does not spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `vt_estimates.csv` — one row per participant with the cortical V_T estimate. Include at
  least a participant identifier and the V_T value; a `target`/`region` column may be
  included.
- `run_metadata.json` — dataset, snapshot, tracer, target region, the input function you
  built, the kinetic model you used, the number of participants, and the cohort-average
  cortical V_T.
- `findings.md` — a short written summary reporting the cohort-average cortical V_T of
  [11C]MC1 and how it varies across participants, stating only what your analysis supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `vt_estimates.csv`, and `findings.md`.
