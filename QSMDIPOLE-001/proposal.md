## QSMDIPOLE-001

**Proposal Title:** Reproduce the deep-gray susceptibility of the QSM-2016-challenge STI reference by single-orientation dipole inversion — an un-cued referencing-convention trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative susceptibility mapping / brain iron

**Source paper / data:** Langkammer et al. (2018), *Magn Reson Med*, "Quantitative susceptibility mapping: report from the 2016 reconstruction challenge" (https://doi.org/10.1002/mrm.26830). Data: the **QSM Reconstruction Challenge 1.0 (2016)** archive `20170327_qsm2016_recon_challenge.zip` (~245 MB, `neuroimaging.at`, **public, no login**).

**Genre:** reproduction (numeric). **Un-cued failure axis:** referencing convention.

### STEP-0 (validated on the real data)

- **Fetch:** the 245 MB challenge archive downloads over plain HTTP with **no credentials** (the server is throttled/flaky — needs resumable download with retries, but no auth). PASS.
- **Reproduces:** the archive ships the single-orientation local tissue field `phs_tissue` (already normalised to ppm), a brain mask, a labelled ROI mask (`evaluation_mask`: deep-gray nuclei labels 1–6, white matter >6), and the held-out STI **χ₃₃** reference (12-orientation susceptibility-tensor solution — the challenge ground truth). The pinned closed-form L₂ dipole inversion of the single-orientation field recovers the deep-gray susceptibility of χ₃₃:

  | nucleus (label) | STI χ₃₃ (ppb) | CF-L2 recon (ppb) | \|Δ\| |
  |---|---|---|---|
  | globus pallidus (3) | 158.8 | 153.3 | 5.5 |
  | putamen (2) | 72.2 | 78.0 | 5.8 |
  | red nucleus (6) | 99.1 | 99.4 | 0.2 |
  | caudate (1) | 66.5 | 53.7 | 12.9 |
  | thalamus (4) | 65.0 | 76.3 | 11.3 |
  | substantia nigra (5) | 144.2 | 85.8 | 58.4 |

  Globus pallidus and putamen (the graded nuclei) reproduce within ~6 ppb. (SN/caudate/thalamus reproduce poorly — a *known* single-orientation limitation, susceptibility anisotropy that only STI/COSMOS recover — so they are reported but not graded.)

### The trap (un-cued referencing)

Absolute QSM values are only defined up to a **reference**: the dipole kernel is ~null at k=0, so an overall susceptibility offset is chosen by convention (CSF/ventricles, whole-brain mean, or a white-matter region). χ₃₃ is on the **native dipole scale** (brain-mask mean ≈ 0). The provided tissue field is itself zero-mean, so a closed-form inversion returns a map already on that scale — reporting it directly reproduces the reference. **Subtracting a CSF/ventricle or white-matter reference offset — the standard habit when reporting "absolute" deep-gray susceptibility — shifts every value off the reference scale.** The instruction never mentions referencing; whether the agent volunteers an (here wrong) re-reference is the un-cued judgement.

Measured offsets on this subject: CSF/ventricle ≈ **14 ppb**, white matter ≈ **20 ppb**. (Honest note: this is *tens* of ppb, not hundreds — because the provided field is already zero-mean, the naive "do-nothing" report is already correctly referenced; the failure mode is *adding* a re-reference. To make the referencing offset separable, the reconstruction recipe is **pinned publicly** in `protocol.json`; without pinning, inversion-method/regularisation variance — plain Tikhonov gives GP 98 ppb, TKD 130 ppb vs CF-L2 153 ppb — would dominate and confound the referencing signal.)

### Verifier (4 plain checks; `tests/test_outputs.py`)

Grades the reported deep-gray susceptibilities against the **held-out STI χ₃₃ reference** (targets hardcoded from STEP-0): (1) report present/well-formed and physiological; (2) globus pallidus is the iron-rich extreme (GP ≫ putamen — any valid reconstruction has the right contrast); (3) a real susceptibility map was written (finite, 160³, non-trivial range); (4) **globus pallidus and putamen within ±12 ppb of χ₃₃** (158.8 / 72.2). Because χ₃₃ is **not shipped** to the agent, the targets cannot be guessed — only a faithful reconstruction on the correct scale lands near them. Public recipe + grade-vs-real-reference (no hidden estimator, no synthetic data).

### Discrimination (validated locally, end-to-end via solve.sh + pytest)

| submission | GP / PUT (ppb) | verdict |
|---|---|---|
| reference (pinned CF-L2, native scale) | 153 / 78 | **PASS** |
| CSF/ventricle-referenced (−14 ppb) | 139 / 64 | **FAIL** (GP off 19.7) |
| whole-brain → white-matter re-reference (+19 ppb) | 173 / 97 | **FAIL** |
| differently-regularised inversion (plain Tikhonov) | 98 / 50 | **FAIL** |

Two independent kernel implementations (challenge meshgrid-normalised vs standard `fftfreq`) of the pinned recipe agree to **0.00 ppb**, so ±12 ppb passes any faithful implementation (native ~5–8 ppb off χ₃₃; robust to mean-vs-median and reg ±0.02) while failing every re-reference and every other inversion.

### Data handling (why staged, not runtime-fetched)

The challenge archive contains **both** the inputs and the χ₃₃/COSMOS reference maps in one zip. Fetching it at agent runtime would put the answer in the agent's reach (reading χ₃₃ ≈ the graded targets — a shortcut that trivially passes). The three real input volumes (`phs_tissue`, `msk`, `evaluation_mask`) are therefore extracted from the public no-login archive and staged in `/app/data`, with the STI reference **held out** — the QSMTOTAL/IRONMAP staging pattern, but with **real** challenge data and the **real** ground-truth reference held out. (A build-time-fetch variant that downloads the archive and discards the reference maps is possible but depends on the flaky challenge server at build time.)

### Difficulty gate — NOT yet run

This proposal covers STEP-0 + the built, oracle-validated task (oracle reward 1.0 locally; adversarial re-reference / wrong-method shortcuts fail). The ≥2-frontier-family difficulty gate (skill Step 4) has **not** been run here. Honest caveat for that gate: the recipe is fully pinned and the referencing offset is modest (~14 ppb), so a competent agent that simply implements the pinned recipe and reports the native-scale values will pass — the trap only catches an agent that *volunteers* a CSF/WM re-reference. If the gate shows agents pass, the ratchet options are to loosen the recipe pinning and switch the graded quantity to a method-robust one, or to move to a dataset where absolute referencing genuinely spans 100s of ppb.

### Cost

`hard` bracket by resources but computationally light: one 160³ FFT dipole inversion. cpus 2, mem 8 GB. Data staged (~3.8 MB real niftis); deps numpy/scipy/nibabel. Timeouts 3600 s (generous).
