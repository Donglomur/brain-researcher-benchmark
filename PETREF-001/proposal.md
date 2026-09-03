## PETREF-001

**Proposal Title:** Estimate serotonin-transporter BP_ND from dynamic [11C]DASB PET with a reference-tissue model — an un-cued reference-region judgement (robustness / reporting-quality axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular imaging / PET pharmacokinetic modelling

**Source finding:** [11C]DASB serotonin-transporter binding (Knudsen et al. 2016, *NeuroImage*, the Cimbi database; Nørgaard & Ganz et al. 2022, *Scientific Data*, https://doi.org/10.1038/s41597-022-01164-1). Reference-tissue kinetics: Lammertsma & Hume 1996 (SRTM); Logan 1996 (reference Logan); Ichise 2003 (MRTM/MRTM2). Dataset: OpenNeuro **ds001420** (test-retest [11C]DASB, 2 participants × 2 scans), **PETPrep-derived regional TACs** fetched at runtime from OpenNeuro (open, no credentials, snapshot 1.2.0).

**Status: FULL runnable task.** First **PET / molecular-imaging** task in the suite — breaks the fMRI-connectivity monoculture on both **modality** and **dataset** axes (all prior tasks sit on ds000228 resting-state fMRI). Genre: **reproduction** with an un-cued reference-region judgement.

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

### The un-cued lever (Step-0 measured — real but MODEST)

The TAC file ships a column literally named `reference` (**whole cerebellum**, which folds in cerebellar **white matter** and the **vermis**) alongside separate `*_cerebellum_cortex` (gray matter) columns. For [11C]DASB the field-standard reference is cerebellar **gray matter**; the convenient `reference` column is a defensible-but-suboptimal choice.

- whole-cerebellum vs cerebellar-GM reference: putamen BP_ND **1.86 vs 1.92 (~3%)**, consistent in sign across all four scans.
- reference-tissue **model** choice (SRTM/Logan/MRTM/MRTM2): **~2%** — negligible on these clean regional TACs.

**Honesty note (no-fake-traps discipline):** the numeric lever here is only ~3% (at the edge of DASB test-retest, ~5–8%), so this is **not** framed as a dramatic significance-flip like SOCIALBRAIN's GSR. The un-cued judgement is a **reporting-quality / robustness** one — a mature reference-tissue analysis *states and justifies its reference region for the tracer* rather than silently using a pre-labelled `reference` column — which is a fair expectation independent of the effect size. The bigger PET lever, **partial-volume correction** (putamen nopvc 1.85 vs agtm 2.46, **+33%**), is NOT gateable here: it cannot be an agent-side choice when pre-extracted TACs are provided (applying PVC needs the images + segmentation, not bare-python-feasible), so it is deliberately excluded rather than faked.

### Verifier (3 plain checks, human-looking pytest)

`tests/test_outputs.py`: (1) putamen BP_ND present for all four scans, physiologically plausible, and a reference-tissue model actually named; (2) **reproduction** — mean BP_ND in the cross-model-validated band [1.65, 2.20] AND the four estimates are reproducible (CV < 8%); (3) **reference-region justified** — findings.md reports the reference as a considered choice (the gray-matter / white-matter / vermis distinction, or that BP_ND depends on the reference definition), not merely "I used the cerebellum" (pipeline vocabulary — the same false-positive class guarded against in SOCIALBRAIN/DEVCONN).

**Offline discrimination (measured, this build):**

| output | check 1 | check 2 (reproduce) | check 3 (justify) | verdict |
|---|---|---|---|---|
| reference solution (SRTM, cerebellar GM) | PASS | PASS | PASS | **PASS** |
| whole-cerebellum reference + justification | PASS | PASS | PASS | **PASS** (fair alternative) |
| non-kinetic SUV-ratio (claims SRTM) | PASS | **FAIL** (CV 12%) | PASS | **FAIL** |
| correct BP, generic "cerebellum reference" only | PASS | PASS | **FAIL** | **FAIL** |
| wrong magnitude (~2.9) | PASS | **FAIL** (range) | PASS | **FAIL** |

Check 2 separates real kinetic modelling from a target/reference ratio (which, on this ~54-min non-equilibrium scan, scatters ~13% across scans). Check 3 is the un-cued reference-region judgement.

### Difficulty — NOT yet gated (frontier runs pending)

Oracle passes (reward 1.0 offline; `harbor -a oracle` to confirm in-container). Adversarial shortcuts fail as tabulated. The **≥2-frontier-family, k≥3 difficulty gate has not been run** (no Harbor/agent access in this authoring session). **Honest expectation:** because the numeric lever is modest, this may calibrate as an **easy control / weak hard candidate** — its discrimination rests mainly on check 3 (does the agent volunteer a justified reference choice) and check 2 (kinetic vs ratio). If the gate shows agents pass, the ratchet is to switch to an image-space extraction variant (where PVC and reference-mask definition become genuine un-cued choices) rather than adding rigor. Recorded here per the no-overstatement rule.

### Data provenance / reliability caveats

- Fetch is the OpenNeuro file API (`/snapshots/1.2.0/files/<colon-path>`, 302→S3); no credentials. The version-less S3 path 404s (annexed content), so the API route is required. Pinned to snapshot **1.2.0**.
- `dataset_description.json` for ds001420 carries `License: "NA - not for public distribution (yet)"` — the dataset is nonetheless openly published on OpenNeuro and cited in Nørgaard/Ganz 2022 *Sci Data* as an example dataset; flagged for reviewer awareness.
- Uses `pvc-nopvc` (no partial-volume correction) TACs — the standard extraction.

### Cost

`hard` bracket by convention; actually light (fetches four ~50 KB TSVs; SRTM/Logan/MRTM fits run in seconds). cpus 2, mem 4 GB, internet on, timeouts 1800–3000 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3.
