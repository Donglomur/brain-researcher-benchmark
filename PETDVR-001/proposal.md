## PETDVR-001

**Proposal Title:** Estimate serotonin-transporter DVR from dynamic [11C]DASB PET with the Logan reference-tissue graphical method — an un-cued linear-phase (equilibrium-onset) judgement (reproduction axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular imaging / PET pharmacokinetic modelling

**Source finding:** [11C]DASB serotonin-transporter binding (Knudsen et al. 2016, *NeuroImage*, the Cimbi database; Nørgaard & Ganz et al. 2022, *Scientific Data*, https://doi.org/10.1038/s41597-022-01164-1). Graphical reference-tissue kinetics: Logan et al. 1996 (reference Logan); Ichise et al. 2002 (MA1). Dataset: OpenNeuro **ds001420** (test-retest [11C]DASB, 2 participants × 2 scans), **PETPrep-derived regional TACs** fetched at runtime from OpenNeuro (open, no credentials, snapshot 1.2.0).

**Status: FULL runnable task.** Genre: **reproduction** with an un-cued linear-phase / equilibrium-onset judgement.

### Distinctness from the shipped PET tasks

- **PETREF-001** estimates **BP_ND in the putamen** with a **reference-tissue compartmental model (SRTM)** on this same dataset; its un-cued lever is the **reference-region definition**. PETDVR-001 uses a **different quantity** (DVR), a **different method family** (the *graphical* Logan/MA1 plot, a linear regression, not a nonlinear compartmental fit), a **different graded region** (the `highbinding` SERT composite, not putamen), and a **completely different lever** (the linear-phase start of the Logan plot). The reference region is *pinned* here (the provided `reference` column) precisely so PETREF's reference lever is inert and t* is the sole operative choice.
- **PETVT-001** estimates **arterial V_T** on a different dataset/tracer (ds005619 [18F]SF51). Different input model (arterial, not reference-tissue) and quantity.
- **PETKIN-003** (synthetic) treats a *noise-biased* reference-Logan DVR as its failure mode (fixed by SRTM2/MRTM2). PETDVR-001's failure mode is orthogonal — a **deterministic curvature bias** from including pre-equilibrium frames, on **real** data — and its correct answer is a properly-windowed graphical DVR (not a switch away from graphical analysis).

### Step-0 (validated, real — reproduces on obtainable data)

Fetched the four PETPrep TAC tables (no credentials, snapshot 1.2.0) and computed the Logan reference-tissue DVR against the provided `reference` region. The **operative choice is where the Logan plot's linear (post-equilibrium) segment begins (t\*)**:

High-binding SERT territory DVR, per scan:

| scan | naive (fit all frames, t\*=0) | linear-segment (t\* auto ~17–33 min) |
|---|---|---|
| sub-01 base | 2.21 | 2.68 |
| sub-01 rescan | 2.26 | 3.17 |
| sub-02 base | 2.37 | 2.89 |
| sub-02 rescan | 2.58 | 3.08 |
| **mean** | **2.35** | **2.95** |

- **Robust, recurring gap:** the all-frames fit under-estimates high-binding DVR by **~20 %** on **every** scan (14.9–27.9 %). Regional profile shows the same one-directional bias: thalamus **1.81 → 2.37**, caudate **1.30 → 1.97**, putamen **2.10 → 2.50**.
- **The trap looks fine:** the naive all-frames fit still has **R² ≈ 0.99** — the bias is invisible in goodness-of-fit, so a "the Logan plot is linear, R² is great" analyst is confidently wrong.
- **Oracle is method-agnostic-correct:** over the linear segment, simple reference Logan (**2.95**), Ichise **MA1** (**2.92**), and SRTM BP_ND+1 (**~2.9**, cf. PETREF putamen 1.92→2.92) all agree — so the target number is what *any* equilibrium-aware analysis returns, and only the pre-equilibrium-contaminated graphical fit fails. (A mis-specified k2′-augmented Logan with an arbitrary k2′ scatters to ~4.0 and is excluded by the upper band; the standard graphical form is pinned in the brief.)

### The un-cued lever (Step-0 measured — real and large)

The instruction names the method (Logan graphical DVR), the data, the reference column, and the regions, but **never** mentions the linear phase, transient equilibrium, t\*, the fit window, or excluding early frames. A reference-tissue Logan/MA1 DVR is the slope of the plot's *linear* segment; the early distribution phase is curved and must be excluded. Including it biases DVR low by ~20 %. This is the classic, un-cued Logan pitfall, and it is deterministic (recurs on every scan), not a noise artifact.

### Verifier (4 plain checks, human-looking pytest)

`tests/test_outputs.py`: (1) high-binding DVR present for all four scans, plausible, and a graphical (Logan/MA1) analysis actually named; (2) **reproduction** — mean high-binding DVR in the equilibrium-aware band **[2.60, 3.40]** (rejects the ~2.35 all-frames value); (3) **regional profile not under-estimated** — reported thalamus (≥2.05) and caudate (≥1.60) DVR are also at their linear-segment levels, a second independent guard on the same early-frame bias; (4) **fit-window justified** — findings.md treats the linear-phase / equilibrium onset / excluded early frames as a considered choice co-occurring with a result, not merely "fit the Logan plot" (the reporting-quality guard used across the suite).

**Offline discrimination (measured, this build):**

| output | check 1 | check 2 (reproduce) | check 3 (profile) | check 4 (justify) | verdict |
|---|---|---|---|---|---|
| reference solution (linear-segment Logan) | PASS | PASS | PASS | PASS | **PASS** |
| MA1 over the linear segment | PASS | PASS | PASS | PASS | **PASS** (fair alt) |
| naive all-frames Logan (R²≈0.99) | PASS | **FAIL** (2.35) | **FAIL** | **FAIL** | **FAIL** |
| BP_ND reported instead of DVR (~1.95) | PASS | **FAIL** (band) | — | — | **FAIL** |

### Difficulty — NOT yet gated (frontier runs pending)

Oracle passes (reward 1.0 offline; `harbor -a oracle` to confirm in-container). The naive all-frames shortcut fails as tabulated. The **≥2-frontier-family, k≥3 difficulty gate has not been run** (no Harbor/agent access in this authoring session) — **Step-5 frontier calibration PENDING**. Honest expectation: the lever is a well-known textbook pitfall, so a strong agent that knows Logan requires t\* selection will pass; the discrimination is against the tempting "fit the whole plot, R² is great" default. If the gate shows agents pass easily, the ratchet is a harder tracer/region where the equilibrium onset is later and the curvature more severe, not added rigor.

### Data provenance / reliability caveats

- Fetch is the OpenNeuro file API (`/snapshots/1.2.0/files/<colon-path>`, 302→S3); no credentials. Pinned to snapshot **1.2.0** (same access route as PETREF-001).
- `dataset_description.json` for ds001420 carries `License: "NA - not for public distribution (yet)"` — the dataset is nonetheless openly published on OpenNeuro and cited in Nørgaard/Ganz 2022 *Sci Data* as an example dataset; flagged for reviewer awareness (identical to the PETREF-001 note).
- Uses `pvc-nopvc` (no partial-volume correction) TACs — the standard extraction; PVC is not an agent-side choice with pre-extracted TACs and is deliberately out of scope.

### Cost

`hard` bracket by convention; actually light (fetches four ~50 KB TSVs; Logan/MA1 fits run in seconds). cpus 2, mem 4 GB, internet on, timeouts 1800–3000 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3.
