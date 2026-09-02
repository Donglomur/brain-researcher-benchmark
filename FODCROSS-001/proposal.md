## FODCROSS-001

**Proposal Title:** Crossing-fibre fraction in the centrum semiovale — an un-cued single-shell-vs-multi-shell fODF trap (hard reproduction)

**Scientific Domain:** Life Sciences / Neuroscience / Diffusion MRI (fibre orientation distribution, crossing fibres)

**Source paper (method):** Jeurissen, Tournier, Dhollander, Connelly & Sijbers (2014), *Multi-tissue constrained spherical deconvolution for improved analysis of multi-shell diffusion MRI data*, NeuroImage, https://doi.org/10.1016/j.neuroimage.2014.07.061 (single-tissue CSD: Tournier et al. 2007). Dataset: dipy's pinned `sherbrooke_3shell` multi-shell acquisition (b = 0, 1000, 2000, 3500 s/mm^2), fetched at runtime via `dipy.data.fetch_sherbrooke_3shell` / `read_sherbrooke_3shell`.

**Status: FULL runnable task, oracle + naive validated locally (Step-0 + oracle re-run). Step-5 frontier calibration PENDING (maintainer step).**

### Genre
Reproduction (numeric match). Everything that makes the crossing fraction well defined is pinned in the instruction — the ROI (voxel box `[45:83, 45:90, 31:36]` & brain mask & 0.30<FA<0.90 = 5060 voxels), the peak/crossing definition (`peaks_from_model` on `default_sphere`, `relative_peak_threshold=0.5`, `min_separation_angle=25`, `npeaks=3`, crossing = >=2 peaks), and `sh_order_max=8`. The **only** thing left to the agent is HOW the fODF is estimated from this acquisition.

### The un-cued lever (PRIVATE — never named in instruction.md)
Single-shell CSD vs multi-shell multi-tissue CSD (MSMT-CSD). The acquisition is genuinely multi-shell, so the correct fODF estimator is MSMT-CSD (models WM/GM/CSF jointly), which suppresses the spurious fODF lobes that single-tissue single-shell CSD produces from grey-matter / CSF partial volume. Single-shell CSD **over-detects** crossings in exactly the lower-FA, partial-volume voxels of this ROI. The instruction never says "multi-shell", "MSMT", "single-shell", "partial volume", or "response function"; it only says "estimate the fODF by spherical deconvolution". The task id is a neutral topic id (crossing-fibre fraction), not the lever.

### Step-0 result (measured; ROI = 5060 voxels)
| fODF estimator | crossing fraction |
|---|---|
| **MSMT-CSD (correct, multi-shell)** | **0.349** |
| single-shell CSD, b=1000 only | 0.457 |
| single-shell CSD, all mixed shells | 0.484 |
| single-shell CSD, b=3500 only | 0.696 |

MSMT gives materially FEWER crossings; every single-shell answer is inflated by partial volume and lands >= 0.108 above the MSMT value (up to 2x for the b=3500 shell). The naive/MSMT gap is stable across the individual ROI slices (per-slice mean-peaks diff +0.21 to +0.24). Correct direction = MSMT reduces spurious peaks.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) numeric reproduction — the reported crossing fraction is within **0.08** of the MSMT value **0.349** (schema-robust: the fraction is found at any depth in `crossing.json`); the nearest single-shell value (0.457) is 0.108 away, so every single-shell answer fails. (2) light honesty check — `findings.md` discusses crossings and reports a fraction consistent with `crossing.json`. No weighted rubric, no score.json.

### Discrimination (validated locally)
| solution | crossing fraction | verdict |
|---|---|---|
| reference / oracle (MSMT-CSD) | 0.349 | **PASS** |
| single-shell CSD, all mixed shells | 0.484 | **FAIL** |
| single-shell CSD, b=3500 | 0.696 | **FAIL** |

### Cost
`hard`. cpus 2, mem 8 GB, internet on (dipy fetches `sherbrooke_3shell`, ~a few hundred MB, at runtime). MSMT deconvolution + `peaks_from_model` over 5060 voxels via cvxpy is the runtime cost (~10-15 min single-thread). Deps: dipy 1.12.1 + cvxpy + numpy/scipy/nibabel/h5py.

### Notes / caveats
- The naive value is shell-dependent (0.457-0.696); tol 0.08 fails the mildest single-shell (b=1000, 0.457) with a 0.028 margin and the dominant tutorial-style all-shell CSD (0.484) with a 0.055 margin. If a maintainer wants a wider margin, lowering `relative_peak_threshold` widens the MSMT-vs-single-shell gap.
- Step-5 frontier calibration (>=2 frontier families, k>=3, hand re-scored) is the maintainer gate and is PENDING; this proposal ships the oracle-pass + naive-fail evidence.
