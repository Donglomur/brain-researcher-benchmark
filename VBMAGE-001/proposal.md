## VBMAGE-001

**Proposal Title:** Strongest age-related cortical atrophy (OASIS VBM) — an un-cued smoothing-dependent peak (the *over-claim / robustness* axis on a new **structural** modality)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural MRI / voxel-based morphometry

**Source finding:** Good et al. (2001), *NeuroImage*, https://doi.org/10.1006/nimg.2001.0786 (VBM of ageing). Data: `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with `tb-science-task-authoring`.** **First task on the structural-MRI modality** — the shipped + session suite was fMRI (×7) + EEG (×1); this adds structural, a third measurement type. The failure axis (**over-claim / robustness**) is shipped (GRADIENT), but on a **new modality** with a **new lever** (spatial smoothing) it fills a fresh axis×modality cell.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/struct_smooth_step0.py`)
OASIS VBM, Harvard-Oxford cortical, n~200, region with the most negative gray-matter–age relationship:

| smoothing kernel | top age-atrophy region |
|---|---|
| native / 4 mm | **Heschl's Gyrus** |
| 8 mm / 12 mm | **Precentral Gyrus** |

The "most-atrophied region" flips across defensible smoothing kernels (an arbitrary VBM choice with no single correct value) — so a single-region claim is an artifact of the smoothing.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) a top age-atrophy region was reported; (2) the submission either reports a **smoothing multiverse (≥2 kernels with different top regions)** OR `findings.md` recognises the top region is **not robust to smoothing** — a flat "region X atrophies most" over-claims. Linked-insight guard: variation words must tie to the region/result, not merely name the kernel used.

Local calibration (`scratchpad/validate_vbmage.py`):

| output | region_computed | smoothing_dependence |
|---|---|---|
| **oracle** | PASS | PASS — reward 1.0 |
| prose (recognises non-robustness) | PASS | PASS |
| structured multiverse (≥2 kernels) | PASS | PASS |
| flat "precentral atrophies most" | PASS | **FAIL** |
| broken (no region) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. Telegraphing: GRADIENT showed frontier agents do NOT volunteer robustness-across-choices un-cued → plausibly hard.
2. **Over-claim axis reused** (3rd, after GRADIENT + DYNFC) — but on a **new modality** (structural) with a **new lever** (smoothing), so it adds an axis×dataset×modality cell.
3. **Moderate flip** (2 distinct top regions across 4 kernels). The smoothing lever is *fair* (no single correct kernel), unlike a "wrong reference" — which is why this was preferred over the EEG-reference candidate (that one had a standard-correct choice → easy-control risk).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM — ~900 MB one-time from NITRC; oracle smooths at 4 kernels, timeout 5400). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
