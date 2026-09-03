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

### Verifier (4 plain checks; `tests/test_outputs.py`)

Grades the reported deep-gray susceptibilities against the **held-out STI χ₃₃ reference** (targets hardcoded from measurement): (1) report present/well-formed and physiological; (2) globus pallidus is the iron-rich extreme (GP ≫ putamen — any valid reconstruction has the right contrast); (3) a real susceptibility map was written (finite, 160³, non-trivial range); (4) **globus pallidus and putamen within ±12 ppb of χ₃₃** (158.8 / 72.2). Because χ₃₃ is **not shipped** to the agent, the targets cannot be guessed — only a faithful reconstruction of the pinned recipe on the correct scale lands near them.

### Discrimination (re-validated end-to-end via pytest on real data)

| submission | GP / PUT (ppb) | verdict |
|---|---|---|
| reference (pinned CF-L2, native scale, **median**) | 153 / 78 | **PASS** |
| reference (pinned CF-L2, native scale, **mean**) | 151 / 75 | **PASS** |
| CSF/ventricle-referenced (−14 ppb) | 139 / 64 | **FAIL** (ignored the cued native-scale referencing) |
| plain Tikhonov (wrong regularizer) | 98 / 50 | **FAIL** (wrong recipe) |

Any correct-referenced reconstruction of the pinned recipe passes; a wrong recipe or a report re-referenced off the cued native scale fails.

### Data handling (why staged, not runtime-fetched)

The challenge archive contains **both** the inputs and the χ₃₃/COSMOS reference maps in one zip. Fetching it at agent runtime would put the answer in the agent's reach (reading χ₃₃ ≈ the graded targets). The three real input volumes (`phs_tissue`, `msk`, `evaluation_mask`) are therefore extracted from the public no-login archive and staged in `/app/data`, with the STI reference **held out**.

### Positioning

Retained as one of the **easy controls** with calibration value, not a hard task. It exercises a real reconstruction pipeline (a 160³ FFT dipole inversion) and grades against a real held-out ground-truth reference, but every free choice (recipe, regularization, referencing, statistic) is cued or accepted — so a competent agent passes and it is not forced to be hard.

### Cost

`hard` bracket by resources but computationally light: one 160³ FFT dipole inversion. cpus 2, mem 8 GB. Data staged (~3.8 MB real niftis); deps numpy/scipy/nibabel. Timeouts 3600 s (generous).
