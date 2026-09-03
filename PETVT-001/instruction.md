# Distribution volume of a TSPO radioligand from dynamic [18F]SF51 PET (PETVT-001)

## Scientific context

[18F]SF51 is a candidate PET radioligand for the 18 kDa translocator protein (TSPO), a
marker used to study neuroinflammation. TSPO has no brain region free of specific binding,
so its ligands are quantified with an **arterial input function** (an invasive study with
blood sampling) rather than a reference-tissue model. The headline outcome is the **total
distribution volume V_T** (mL.cm-3) — the equilibrium ratio of tissue to
(parent-in-plasma) radioligand concentration. TSPO binding is also modulated by the common
*rs6971* single-nucleotide polymorphism, which sorts people into high-, mixed- and
low-affinity binders. (Source study: OpenNeuro `ds005619`; Yan et al., the first-in-human
evaluation of [18F]SF51; monkey precursor Yan et al. 2023, *EJNMMI*; Logan et al. 1990;
Ichise et al. 2002, MA1.)

## Data

OpenNeuro `ds005619` (CC0): seven healthy participants, one baseline brain scan each,
dynamic [18F]SF51 acquired ~0–120 min with concurrent arterial blood sampling. Use the
**PETPrep-extracted regional time-activity curves** (TACs) and the **arterial blood
recording**, fetched at runtime from OpenNeuro (open, no credentials), snapshot `1.1.0`:

```
https://openneuro.org/crn/datasets/ds005619/snapshots/1.1.0/files/<PATH>
```

where `<PATH>` is the file path with `/` replaced by `:` (the endpoint 302-redirects to the
file; follow redirects). For each participant `sub-XX` in
`{sf02, sf05, sf06, sf07, sf08, sf09, sf10}` there are two files:

```
derivatives:petprep_extract_tacs:sub-XX:ses-baseline:sub-XX_ses-baseline_trc-sf51_desc-gtmseg_tacs.tsv
sub-XX:ses-baseline:pet:sub-XX_ses-baseline_trc-sf51_recording-manual_blood.tsv
```

* The **TAC** TSV has one row per PET frame. Columns include `frame_start`, `frame_end`
  (seconds) and one column per FreeSurfer/gtmseg region, among them the cortical
  gray-matter regions `ctx-lh-*` / `ctx-rh-*`, plus subcortical and cerebellar regions, all
  in **Bq/mL**. The TAC values are **decay-corrected to injection time**.
* The **blood** TSV has one row per sample. Columns are `time` (seconds, relative to
  injection), `plasma_radioactivity` (Bq/mL), `metabolite_parent_fraction` (the intact-parent
  fraction of plasma radioactivity, from HPLC), and `whole_blood_radioactivity` (Bq/mL). The
  samples are recorded **at draw time**. Rows with `time == 0` after the first sample are
  padding and should be ignored.

## Task

For **each of the seven participants**, estimate the [18F]SF51 total distribution volume
**V_T in the cerebral cortex** (cortical gray matter) using an **invasive (arterial-input)
kinetic model**, and summarise the cohort: the average cortical V_T and how it varies across
participants.

Standard implementation choices the invasive-input framework leaves to the analyst — **how
to construct the model input from the blood recording**, which V_T estimator (graphical or
compartmental), the frame weighting, and the fit window — should follow **common practice
for an arterial-input, reversibly-binding brain radioligand**; the brief does not spell them
out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `vt_estimates.csv` — one row per participant, with columns `subject, session, target,
  input, model, VT` (extra columns such as a cross-check estimator are welcome).
- `run_metadata.json` — dataset id, snapshot, target region, the model/input you used, and
  the per-participant and mean cortical V_T.
- `findings.md` — a short written summary: the per-participant and mean cortical V_T, how
  V_T varies across the cohort, and an account of the model input you built from the blood
  recording and the estimator you used and why. State only what your analysis supports.

## Failure handling

If the dataset cannot be fetched or the expected TAC/blood columns are absent, exit non-zero
with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `vt_estimates.csv`, and `findings.md`.
