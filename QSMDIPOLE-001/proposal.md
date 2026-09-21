## QSMDIPOLE-001

**Proposal Title:** Reproduce the deep-gray susceptibility of the QSM-2016-challenge STI reference by single-orientation dipole inversion — a clean reproduction / easy control

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative susceptibility mapping / brain iron

**Source paper / data:** Langkammer et al. (2018), *Magn Reson Med*, "Quantitative susceptibility mapping: report from the 2016 reconstruction challenge" (https://doi.org/10.1002/mrm.26830). Data: the **QSM Reconstruction Challenge 1.0 (2016)** archive `20170327_qsm2016_recon_challenge.zip` (~245 MB, `neuroimaging.at`, **public, no login**).

**Genre:** reproduction (numeric). **Status: EASY CONTROL — grader re-validated on real data; fully cued.**

### What this task is (and why it is an honest control, not a trap)

A faithful **reproduction**: reconstruct one QSM-Challenge-2016 subject's susceptibility map from the single-orientation local tissue field with the **fully pinned** closed-form L₂ dipole inversion (`protocol.json`), and report the deep-gray susceptibility so it reproduces the held-out STI **χ₃₃** reference (globus pallidus ≈ 159 ppb, putamen ≈ 72 ppb).

The earlier revision framed this as an **un-cued referencing-convention trap** (subtracting a CSF/WM reference offset moves values off the STI scale). That framing was **unfair as a hard task**: the provided tissue field is already zero-mean, so the naive "do-nothing" report on the native scale is *already correctly referenced* — the trap fired only on *commission* (an agent that volunteered a re-reference), and CSF-referencing is itself a defensible convention. This revision therefore **accepts it as a clean easy control**: the referencing is now **cued explicitly** in `instruction.md` ("report on the native scale; do not subtract a CSF/ventricle or white-matter offset"), so following the pinned recipe passes and nothing is hidden.

### Ground truth (re-validated on the real staged data, this revision)

Pinned closed-form L₂ (Tikhonov, gradient-regularized) dipole inversion, `reg=0.09`, native scale:

| nucleus (label) | STI χ₃₃ (ppb) | median recon | mean recon |
|---|---|---|---|
| globus pallidus (3) | 158.8 | 153.3 | 150.8 |
| putamen (2) | 72.2 | 78.0 | 74.9 |

Both statistics reproduce the graded nuclei within tolerance (`±12 ppb`) at the pinned `reg`, so a correct **mean- or median-based** report passes — the grader does not unfairly prefer one. (SN/caudate/thalamus reproduce poorly from a single orientation — a known susceptibility-anisotropy limitation only STI/COSMOS recover — so they are reported but not graded.)

### Verifier (5 checks; `tests/test_outputs.py`; grades the **submitted map**, not the reported CSV)

A shape-only map check plus a hardcoded-target CSV grade would let a noise/painted map + the published GP/PUT numbers pass. The verifier therefore holds out `tests/reference.npz` = the in-brain-mask voxel vector of the **deterministic pinned-recipe susceptibility map** (built by running the pinned inversion on the shipped data; 4.9 MB, in-mask voxels only) plus the ROI voxel indices for the two graded nuclei. Checks: (1) report present/well-formed and physiological; (2) globus pallidus is the iron-rich extreme (GP ≫ putamen); (3) a real 160³ map with dynamic range was written; (4) **the submitted map matches the pinned-recipe reference in-brain-mask at Pearson r ≥ 0.95** — a noise/painted map (r≈0) or a differently-regularized inversion (plain Tikhonov, r≈0.81) fails, while an offset/scale variant still passes here (r is offset- and scale-invariant); (5) **the GP/PUT susceptibility is RECOMPUTED from the submitted map** (mean or median, whichever is closer) at the shipped ROI voxels and graded within **±12 ppb of χ₃₃** (158.8 / 72.2). Because r is offset-invariant, check (5) is what enforces the native-scale referencing and kills a copied-published-numbers CSV — the CSV report is no longer the graded quantity.

### Discrimination (re-validated end-to-end via subprocess pytest on real data)

| submission | recomputed-from-map GP / PUT (ppb) | in-mask r | verdict |
|---|---|---|---|
| reference (pinned CF-L2, native scale, **median** CSV) | 153 / 78 | 1.00 | **PASS** |
| reference (pinned CF-L2, native scale, **mean** CSV) | 151 / 75 | 1.00 | **PASS** |
| pure-noise 160³ map + **published** GP=153/PUT=78 CSV | 7 / 7 | ≈0 | **FAIL** (r + recompute) |
| **real** CF-L2 map CSF-referenced (−14 ppb) + CSV copied from paper (158.8/72.2) | 137 / 61 | 1.00 | **FAIL** (recompute: off native scale) |
| plain Tikhonov (wrong regularizer) | 75 / 40 | 0.81 | **FAIL** (r + recompute) |

Any correct-referenced reconstruction of the pinned recipe passes (mean or median); a fabricated/painted map, a wrong recipe, or a real map re-referenced off the native scale (even with the published numbers copied into the CSV) fails — the discriminator is recomputed from the submitted map, not read from the report.

### Data handling (why staged, not runtime-fetched)

The challenge archive contains **both** the inputs and the χ₃₃/COSMOS reference maps in one zip. Fetching it at agent runtime would put the answer in the agent's reach (reading χ₃₃ ≈ the graded targets). The three real input volumes (`phs_tissue`, `msk`, `evaluation_mask`) are therefore extracted from the public no-login archive and staged in `/app/data`, with the STI reference **held out**.

### Positioning

Retained as one of the **easy controls** with calibration value, not a hard task. It exercises a real reconstruction pipeline (a 160³ FFT dipole inversion) and grades against a real held-out ground-truth reference, but every free choice (recipe, regularization, referencing, statistic) is cued or accepted — so a competent agent passes and it is not forced to be hard.

### Cost

`hard` bracket by resources but computationally light: one 160³ FFT dipole inversion. cpus 2, mem 8 GB. Data staged (~3.8 MB real niftis); deps numpy/scipy/nibabel. Timeouts 3600 s (generous).
