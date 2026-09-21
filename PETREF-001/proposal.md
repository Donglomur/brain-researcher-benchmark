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

---

## Proof-of-work verifier (2026-09)

The prior grader checked only a mean BP_ND band [1.65, 2.20] + a cross-scan CV<8% clustering
heuristic + prose — a constant/duplicated table clustered at ~1.9 passed. This revision
applies the proof-of-work contract (per-scan held-out reference, QSMDIPOLE reproduction model).

**Held-out reference** (`tests/reference.npz`, built from `solution/compute.py` on the real
ds001420 PETPrep TACs, never shipped to the agent): the four per-scan SRTM putamen BP_ND
(cerebellar-GM reference) keyed by real id, the per-scan R1/k2 kinetic parameters, and
`ref_stats` (SRTM/Logan/MRTM/whole-cerebellum + the naive late-window SUVR-1 per scan). sha256
`f58e3007c3d564032d2d3413919f0f82590e78e1873c10d3de3ca6fa252673db`.

The discriminating shortcut is a non-kinetic SUV-ratio: on this ~54-min non-equilibrium scan
SUVR-1 gets the COHORT MEAN roughly right (1.98 vs kinetic 1.92) but its PER-SCAN values
scatter wildly (1.12/2.51/2.11/2.20 vs kinetic 1.91/1.96/1.89/1.92) — so the held-out per-scan
table is the teeth, not the mean.

**Neutral per-item table** (already required): `bp_estimates.csv`. Pillars: (1) per-scan
BP_ND within 0.17 of the held-out kinetic reference (accepts SRTM/Logan/MRTM ~2% and
whole-cerebellum ~3%; rejects SUVR 15-50% off); (2) mean recomputed from rows == reference ==
reported JSON; (2b) test-retest variability recomputed FROM the rows in [0.4, 9]% — a
constant/duplicated table (0%) or a SUV-ratio (tens of %) fails; (3) per-scan closer to the
kinetic reference than the SUVR value, and per-scan R1 matches the held-out kinetic R1 IF the
column is volunteered (a SUVR cannot produce R1); (4) secondary model-named prose.

**Validation** (subprocess pytest per case, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, numpy 2.1.3):

| case | result |
|---|---|
| honest (oracle SRTM) | PASS |
| defensible (MRTM cross-estimator) | PASS |
| no table | FAIL |
| constant table (right mean) | FAIL (2b test-retest = 0%) |
| fabricated (right mean, scattered per-scan) | FAIL |
| naive SUVR-1 | FAIL |

Residual (documented, blunt): the honest per-scan BP_ND is near-degenerate (test-retest ~2%),
so a knowledgeable table clustered at the literature value (~1.9) with ~2% synthetic spread
and no volunteered R1 is the irreducible guessable residual; the per-scan reference,
test-retest band and R1-if-present close fabrication, constant, SUVR and scattered attacks.
`test.sh` now provisions numpy 2.1.3. Data still fetches at runtime; the grader is offline.

---

## Second-pass fix (2026-09): per-scan R1 is now MANDATORY — closes the "clustered guess" residual

The red-team confirmed the residual above was live: because the four real BP_ND are
1.91/1.96/1.89/1.92 (~2% spread) against a ±9%/±0.17 tolerance, a **flat guess at the
published ~1.92 mean passes the per-scan BP_ND check on all four scans** — the per-scan BP_ND
gate was toothless. The fix moves the teeth to the **per-scan R1 (relative tracer delivery)**,
which the earlier grader only checked *if volunteered*.

**What changed**
- `bp_estimates.csv` now REQUIRES an `R1` column (per-scan relative delivery). Instruction.md
  lists it as a required output, described neutrally as "the relative tracer delivery of the
  target region relative to the reference region" — it does **not** name SRTM, "kinetic", or
  "not SUVR".
- `tests/reference.npz` rebuilt to add `ref_R1_whole` (whole-cerebellum-reference SRTM R1) as a
  second accepted delivery set; the committed GM-reference `ref_values`/`ref_R1` reproduce the
  real ds001420 fit to 1e-6 (verified).
- New pillar `test_r1_relative_delivery_matches_reference` (mandatory): R1 must cover all four
  scans, be dispersed (std ≥ 0.03), and match the held-out kinetic R1 on **all four** scans
  within **±0.07** against **one consistent** accepted set — GM-cortex R1 (~1.24/1.16/1.12/1.28)
  **or** whole-cerebellum R1 (~1.09/1.02/1.01/1.16). The real R1 spans ~0.15–0.16 across scans,
  so no single flat value can cover all four within ±0.07 → a flat/guessed R1 fails, and a
  non-kinetic SUV-ratio produces no R1 at all.
- `test_kinetic_params_if_volunteered` (grade-if-present) is **replaced** by the mandatory test.
- Per-scan BP_ND tolerance tightened 0.17→**0.15** (rel 0.09→0.07): still admits SRTM/Logan/
  MRTM/MRTM2/whole-cerebellum/frame-weighted (max real off-set 0.073) but now rejects the naive
  SUVR per-scan directly (0.2–0.8 off), as defense-in-depth.

**Why ±0.07 / all-four / two accepted sets** (measured on the real TACs): SRTM R1 is
init/bounds-invariant; dt-grid and frame-duration weighting move R1 ≤0.035; the whole-cerebellum
reference shifts R1 ~0.13 lower but is itself dispersed. A flat guess needs tol ≥ range/2
(≥0.080 GM, ≥0.0735 whole-ceb) to cover all four — ±0.07 sits below both, so every flat guess
fails 4/4 on both sets while honest kinetic variants (≤0.035 off) pass with margin.

**Adversarial self-validation** (subprocess pytest per case, exact oracle output schema,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`):

| case | BP pillar | test-retest | R1 pillar | verdict |
|---|---|---|---|---|
| honest oracle (SRTM, cerebellar GM) | PASS | PASS | PASS | **PASS** |
| defensible: whole-cerebellum reference | PASS | PASS | PASS (whole-ceb set) | **PASS** |
| defensible: frame-duration-weighted SRTM | PASS | PASS | PASS (GM set) | **PASS** |
| attack A: fabricated table right shape + guessed flat R1≈1.2 | PASS | PASS | **FAIL** | **FAIL** |
| attack C: real naive SUVR BP + over-claim caveat + guessed mean 1.92 + flat R1 | **FAIL** | — | **FAIL** | **FAIL** |
| attack C′: same, R1 column omitted entirely | **FAIL** | — | **FAIL (absent)** | **FAIL** |
| flat guess: BP≡1.92, R1≡1.20 | PASS | **FAIL (0%)** | **FAIL** | **FAIL** |

Attack A (the exact residual) now fails **solely** on the mandatory dispersed-R1 gate — a
right-shape table with a guessed corrected value can no longer pass.

**Honest-limitation (accepted 5(a) mild hint, per SECOND_PASS_BRIEF §5):** requiring a per-scan
`R1` column is at most a *mild kinetic hint* on a reproduction task — it tells the analyst to
report relative delivery (a standard reference-tissue parameter) but not which model or that a
SUVR is wrong. A graphical-only / Logan-only submission that reports no R1 is now out of the
accepted set by contract; this is the deliberate, documented tradeoff that makes the judgment
un-guessable without re-cuing the lever. The SRTM2-with-a-crude-global-k2′ variant can scatter
BP up to ~0.19 (fails the tightened BP band on 2/4) — a poorly-parameterized estimator, not fair
practice; a properly two-stepped MRTM2 (proposal Step-0: 1.936/1.987/1.905/1.937) passes.
