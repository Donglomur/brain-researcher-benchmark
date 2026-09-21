## WMMD-001

**Proposal Title:** White-matter mean diffusivity from a wide multi-b acquisition — an un-cued high-b model-mismatch trap (hard reproduction)

**Scientific Domain:** Life Sciences / Neuroscience / Diffusion MRI (mean diffusivity, tensor vs kurtosis estimation)

**Source paper (method):** Jensen & Helpern (2010), *MRI quantification of non-Gaussian water diffusion by kurtosis analysis*, NMR in Biomedicine, https://doi.org/10.1002/nbm.1518; Veraart, Poot, Van Hecke, Blockx, Van der Linden, Verhoye & Sijbers (2011), *More accurate estimation of diffusion tensor parameters using diffusion kurtosis imaging*, Magnetic Resonance in Medicine, https://doi.org/10.1002/mrm.22603. Dataset: dipy's pinned `cfin_multib` acquisition (b = 0, 200, ..., 3000 s/mm^2, 496 volumes), loaded at runtime via `dipy.data.read_cfin_dwi`.

**Status: FULL runnable task, oracle + naive validated locally (Step-0 + oracle re-run + naive/alt-correct discrimination). Step-5 frontier calibration PENDING (maintainer step).**

### Genre
Reproduction (numeric match). Everything that makes the ROI-mean MD well defined is pinned in the instruction — the brain mask (`median_otsu vol_idx=[0], radius=4, numpass=2, dilate=1`), the reference FA that defines the ROI (a tensor on b<=1000), and the ROI itself (brain & reference-FA > 0.5 = 10084 voxels). MD is a rotationally/convention-invariant physical quantity (mm^2/s). The **only** thing left to the agent is HOW the diffusion signal is modelled to obtain MD/FA.

### The un-cued lever (PRIVATE — never named in instruction.md)
Plain single-tensor (Gaussian / mono-exponential DTI) over all shells vs a model valid at high b (diffusion-kurtosis tensor, DKI). The acquisition extends to b = 3000, where the DW signal departs from a single mono-exponential decay; a plain tensor over the full b-range absorbs the high-b signal curvature into an artificially low apparent diffusivity and **underestimates MD by ~34%**. The correct estimate is the kurtosis-tensor diffusion tensor (the b->0 limit), or a plain tensor restricted to low b (b<=1000). The instruction never says "kurtosis", "DKI", "mono-exponential", "non-Gaussian", "high-b bias" or "restrict shells"; it only says "estimate the white-matter MD and FA … how you model the diffusion signal is left to your judgement." The task id is a neutral topic id (white-matter mean diffusivity), not the lever.

### Step-0 result (measured; WM ROI = 10084 voxels; MD in 1e-3 mm^2/s)
| diffusion model | md_mean | fa_mean |
|---|---|---|
| **DKI, all shells (correct)** | **0.883** | 0.638 |
| DTI, b<=1000 only (also correct) | 0.801 | 0.649 |
| DTI, ALL shells (NAIVE, biased) | 0.586 | 0.660 |
| DTI, ALL shells, OLS | 0.502 | — |

The naive DTI-over-all-shells value is inflated-error LOW by ~0.30e-3 (~34%). The gap is robust to fit method (WLS/OLS) and light Gaussian smoothing (DKI stays 0.86–0.89, DTI-all stays 0.49–0.59). Correct direction = the kurtosis-aware / low-b estimate recovers the higher, unbiased diffusivity; the plain full-range tensor underestimates it.

### Verifier (3 plain checks)
`tests/test_outputs.py`: (1) numeric reproduction — the reported MD is within **0.14** (1e-3 mm^2/s) of the unbiased value **0.883**; the finder is schema-robust (MD found at any depth under a diffusivity-named key, kurtosis/anisotropy keys excluded) and **unit-robust** (normalises mm^2/s, um^2/s and um^2/ms to a common scale). The nearest naive value (0.586) is 0.297 away, so every DTI-over-all-shells answer fails. (2) completeness — a plausible ROI-mean FA is reported. (3) light honesty check — `findings.md` discusses diffusivity and reports a value consistent with `diffusivity.json`. No weighted rubric, no score.json.

### Discrimination (validated locally)
| solution | md_mean | verdict |
|---|---|---|
| reference / oracle (DKI) | 0.883 | **PASS** |
| DTI b<=1000 (alt-correct) | 0.801 | **PASS** |
| DTI all shells (naive) | 0.586 | **FAIL** |
| DTI all shells, OLS | 0.502 | **FAIL** |

### PROOF-OF-WORK REWORK (this revision — reproduction genre, held-out per-voxel reference)

The value-only point-match (fabrication-vulnerable per the suite audit: a plausible in-band
number over fabricated data passes) is replaced by a held-out per-voxel reference + three
pillars. WMMD stays a REPRODUCTION task (QSMDIPOLE model): the un-cued modelling judgement is
graded by the VALUE reproducing the unbiased MD, and the instruction stays un-cued (it names
only "the ROI-mean MD and FA").

- **Held-out reference** (`tests/reference.npz`, sha256 `fbb98ba1…2819f`, ~110 KB, committed,
  never shipped): the per-voxel MD map (1e-3 mm^2/s) over the fixed 10 105-voxel WM ROI for
  three model configs — DKI all-shell 0.883, DTI b≤1000 0.801, DTI all-shell 0.585 — built by
  running the pinned pipeline on the real dipy CFIN subject (numpy 2.2.6 / scipy 1.14.1 / dipy
  1.12.1).
- **Neutral intermediate output** (new, un-cued): `md_voxelwise.csv` — the per-voxel MD the
  standard pipeline already produces (columns `i,j,k,md`, unit-robust).
- **Pillar 1** — the per-voxel table covers the real ROI (≥50 %), is non-constant, and
  correlates ≥0.75 with some real config (a fabricated/constant/guessed table matches none).
- **Pillar 2** — the ROI mean recomputes to the reported `md_mean` and lands in the UNBIASED
  band [0.72, 1.03]: DKI 0.883 and low-b DTI 0.801 pass; the DTI-over-all-shells value 0.585 is
  out of band (its per-voxel map is real, so it passes pillar 1, but the biased value fails).
- **Pillar 3** — secondary: `findings.md` reports an MD consistent with the headline.

**Validation matrix (subprocess pytest per case):** honest (DKI) PASS · honest-numeric (DKI +
reports the DTI-all bias) PASS · no-table / constant / fabricated-non-constant / fabricated-
coords FAIL (pillar 1) · naive DTI-all-shells (real map, value 0.585) FAIL (pillar 2 value,
pillar 1 passes — confirming fabrication and the biased answer are caught by different pillars).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (dipy fetches `cfin_multib`, ~170 MB, at runtime). The DKI fit over 496 volumes on the masked ROI is the runtime cost (~1 min). Deps: dipy 1.12.1 + numpy/scipy/nibabel/h5py.

### Notes / caveats
- Two legitimate correct routes (DKI over all shells, or a plain tensor restricted to b<=1000) both land in the accept band; the single failing behaviour is a plain tensor fit over the full b-range, the realistic naive default. The reference/oracle uses DKI.
- MD has units, so the verifier normalises the reported number to a common scale (1e-3 mm^2/s) before comparison, in addition to being schema-robust.
- Step-5 frontier calibration (>=2 frontier families, k>=3, hand re-scored) is the maintainer gate and is PENDING; this proposal ships the oracle-pass + naive-fail evidence.
