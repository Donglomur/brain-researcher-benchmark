## PETREF-001

**Proposal Title:** Estimate serotonin-transporter BP_ND from dynamic [11C]DASB PET with a reference-tissue model — a clean reproduction / easy control

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular imaging / PET pharmacokinetic modelling

**Source finding:** [11C]DASB serotonin-transporter binding (Knudsen et al. 2016, *NeuroImage*, the Cimbi database; Nørgaard & Ganz et al. 2022, *Scientific Data*, https://doi.org/10.1038/s41597-022-01164-1). Reference-tissue kinetics: Lammertsma & Hume 1996 (SRTM); Logan 1996 (reference Logan); Ichise 2003 (MRTM/MRTM2). Dataset: OpenNeuro **ds001420** (test-retest [11C]DASB, 2 participants × 2 scans), **PETPrep-derived regional TACs** fetched at runtime from OpenNeuro (open, no credentials, snapshot 1.2.0).

**Status: EASY CONTROL — grader re-validated on real data.** First **PET / molecular-imaging** task in the suite — breaks the fMRI-connectivity monoculture on both **modality** and **dataset** axes (all prior tasks sit on ds000228 resting-state fMRI). Genre: **reproduction**.

### Fairness fix (why this revision exists)

The earlier revision added a third grader check, `test_reference_region_justified`, meant to be the "un-cued reference-region judgement." But it was **cued**: the instruction explicitly asked the write-up for "an account of the reference region and model you used **and why**." A discriminator the brief tells the agent to satisfy is not an un-cued judgement, and both defensible reference regions (cerebellar gray matter ~1.92 and whole cerebellum ~1.86) reproduce the value anyway. This revision therefore **drops the justify-requirement** (from the grader and from the instruction) and keeps PETREF-001 as a **clean easy-control reproduction** whose grader passes any valid reference-tissue estimate.

### Why this exists (new modality + new axis)

Every shipped task is resting-state fMRI on ds000228. This is human dynamic **PET** with genuine **kinetic modelling** (SRTM / Logan-ref / MRTM implemented in numpy/scipy). The deliverable — BP_ND in a SERT-rich target — is a real published measurement with an independently reproduced oracle (SRTM/Logan/MRTM agree to ~2%, the "kinfitr≈PMOD" regime).

### Step-0 (validated, real — reproduces on obtainable data)

Fetched the four PETPrep TAC tables (no credentials) and fit reference-tissue models to the **putamen** (bilateral) against the **cerebellar gray-matter** reference:

| scan | SRTM | Logan-ref | MRTM | MRTM2 |
|---|---|---|---|---|
| sub-01 base | 1.910 | 1.942 | 1.953 | 1.936 |
| sub-01 rescan | 1.961 | 1.982 | 1.981 | 1.987 |
| sub-02 base | 1.890 | 1.902 | 1.900 | 1.905 |
| sub-02 rescan | 1.918 | 1.937 | 1.941 | 1.937 |

Mean putamen BP_ND ≈ **1.92**, test-retest ~2–3%, and **all four estimators agree to ~2%** — a clean, reproducible oracle in the published [11C]DASB striatal range. (Thalamus ~2.8–3.0, caudate ~1.2, high-binding composite ~2.2 also reproduce textbook values.)

### Reference region (a real but modest choice — no longer graded)

The TAC file ships a column literally named `reference` (**whole cerebellum**, which folds in cerebellar **white matter** and the **vermis**) alongside separate `*_cerebellum_cortex` (gray matter) columns. For [11C]DASB the field-standard reference is cerebellar **gray matter**; the convenient `reference` column is a defensible-but-suboptimal choice.

- whole-cerebellum vs cerebellar-GM reference: putamen BP_ND **1.86 vs 1.92 (~3%)**, consistent in sign across all four scans — **both pass** the reproduction band.
- reference-tissue **model** choice (SRTM/Logan/MRTM/MRTM2): **~2%** — negligible on these clean regional TACs.

This ~3% lever (at the edge of DASB test-retest, ~5–8%) is too small and too cued to gate a hard task, so the grader now **accepts either reference region**. The bigger PET lever, **partial-volume correction** (putamen nopvc 1.85 vs agtm 2.46, **+33%**), is not gateable here: it cannot be an agent-side choice when pre-extracted TACs are provided (applying PVC needs the images + segmentation), so it is excluded rather than faked.

### Verifier (2 plain checks, human-looking pytest)

`tests/test_outputs.py`: (1) putamen BP_ND present for all four scans, physiologically plausible, and a reference-tissue model actually named; (2) **reproduction** — mean BP_ND in the cross-model-validated band [1.65, 2.20] AND the four estimates are reproducible (CV < 8%). The previous check 3 (reference-region "justified") was **dropped** as cued.

**Offline discrimination (re-validated on real data, this revision):**

| output | check 1 | check 2 (reproduce) | verdict |
|---|---|---|---|
| reference solution (SRTM, cerebellar GM, mean 1.92) | PASS | PASS | **PASS** |
| whole-cerebellum reference, **no justification prose** | PASS | PASS | **PASS** (fair alternative — previously failed the cued check 3) |
| minimal SRTM, bare "cerebellum reference", no "why" | PASS | PASS | **PASS** (fair — previously failed) |
| non-kinetic SUV-ratio (claims SRTM) | PASS | **FAIL** (CV 13%) | **FAIL** |
| wrong magnitude (~2.9) | PASS | **FAIL** (range) | **FAIL** |

Check 2 separates real kinetic modelling from a target/reference ratio (which, on this ~54-min non-equilibrium scan, scatters ~13% across scans) — the one real discriminator that survives as a clean control.

### Positioning

Retained as an **easy control** with calibration value (a real PET kinetic-modelling reproduction against an independently reproduced oracle), not a hard task. It exercises SRTM/Logan/MRTM in numpy/scipy and grades a reproducible published measurement; every free choice (reference region, estimator) is accepted, so a competent agent passes.

### Data provenance / reliability caveats

- Fetch is the OpenNeuro file API (`/snapshots/1.2.0/files/<colon-path>`, 302→S3); no credentials. The version-less S3 path 404s (annexed content), so the API route is required. Pinned to snapshot **1.2.0**.
- `dataset_description.json` for ds001420 carries `License: "NA - not for public distribution (yet)"` — the dataset is nonetheless openly published on OpenNeuro and cited in Nørgaard/Ganz 2022 *Sci Data* as an example dataset; flagged for reviewer awareness.
- Uses `pvc-nopvc` (no partial-volume correction) TACs — the standard extraction.

### Cost

`hard` bracket by convention; actually light (fetches four ~50 KB TSVs; SRTM/Logan/MRTM fits run in seconds). cpus 2, mem 4 GB, internet on, timeouts 1800–3000 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3.
