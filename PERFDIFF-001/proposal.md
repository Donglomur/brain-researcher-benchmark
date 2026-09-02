## PERFDIFF-001

**Proposal Title:** IVIM perfusion fraction f in a diffusion-MRI ROI — an un-cued **estimator-dependence / over-claim** trap (judgement genre)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion/perfusion MRI (IVIM)

**Source finding / method:** Le Bihan et al. (1988), *Radiology*, https://doi.org/10.1148/radiology.168.2.3393671 (separation of diffusion and perfusion by IVIM); fit-method sensitivity: Barbieri et al. (2016), *Magn. Reson. Med.* (impact of the fitting algorithm on IVIM parameters); While (2017), *Magn. Reson. Med.* (IVIM estimation). **Dataset:** the dipy-shipped IVIM subject, fetched at runtime via `dipy.data.fetch_ivim` / `read_ivim` — real, public diffusion MRI, 21 b-values from 0 to 1000 s/mm². Real data, no synthetic/planted truth.

**Genre:** over-claim / judgement (mirror of GRADIENT-001). The honest answer is that f is choice-dependent; the task grades whether the write-up **discovers and reports the dependence** rather than asserting one confident value.

### The un-cued lever

The IVIM biexponential is ill-conditioned: the perfusion compartment (f, D\*) is constrained almost entirely by the few low-b (< ~200 s/mm²) points, so f and D\* trade off strongly and the result **depends materially on the fitting algorithm** — a well-known IVIM pitfall. dipy's default `IvimModel` is the full-biexponential Trust-Region NLLS (`fit_method='trr'`); a segmented two-step fit (D from high-b, then f) is the other classic estimator. The instruction names the deliverable (f, D, D\* in a fixed ROI) and pins the ROI, but **never** mentions fit-method, estimator, robustness, or that f is choice-dependent. An un-cued agent calls `IvimModel(gtab).fit(...)` (which defaults to `trr`) and reports one confident f ≈ 0.21.

### The trap (Step-0 validated, real data)

Same ROI (slice z=33, box x[90:120] y[90:120], ~850–900 tissue voxels), same voxels, two standard estimators:

| estimator | f (ROI mean) | f (median) | D* (mm²/s) |
|---|---|---|---|
| Full biexponential Trust-Region NLLS (`trr`, dipy default) | **0.213** | 0.200 | 6.5e-3 |
| Segmented two-step fit | **0.121** | 0.085 | 1.7e-2 |

ROI-mean f ranges **0.12–0.21** across estimators; per-voxel it spans ~**0.03–0.36**; D\* differs ~3×. (A variable-projection fit, dipy `fit_method='varpro'`, lands in between at f ≈ 0.15 — the same downward shift.) So f is **not** a single well-determined number on these data — the honest deliverable is a range with the estimator-dependence stated, not one confident value.

### Verifier (3 plain checks, mirrors GRADIENT-001)

`tests/test_outputs.py`: (1) a real biexponential IVIM fit — plausible f plus a pseudo-diffusion D\*; (2) **estimator sensitivity was checked** — ≥2 per-method fits, or ≥2 named estimator families, or an explicit reported f-range; (3) **the dependence is not over-claimed** — findings link the perfusion fraction to a fit/estimator-dependence statement (a range, not a point), not a single confident f. The dependence phrase must **co-occur** with an f / D\* token, so merely naming two fitters in a methods list does not pass. No rubric, no score file; numbers searched at any json depth with a findings.md fallback.

**Offline discrimination (locked):** oracle (trr + segmented, reports the range) → **3/3 PASS**. Two realistic naive outputs, built from real runs: (a) single default `trr`, confident "f = 0.21" → checks 2 **and** 3 FAIL; (b) *ran both* fitters but still reports one confident f and only names the methods in a pipeline line → check 3 **FAIL** (the pipeline-naming false-pass the GRADIENT/DEVCONN reviews warned about, defeated here). So the failure is the un-cued over-claim, not a format bug.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0** (locked locally). The ≥2-frontier-family gate (does GPT-5.x / Claude volunteer the estimator-sensitivity check and report f as a range, or fit once and assert a single perfusion fraction?) is a maintainer step. Prior: IVIM fit-method dependence is a specialist caveat an un-cued agent is unlikely to volunteer — the dipy IVIM tutorial fits a single estimator — so the over-claim trap has teeth.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy fetches the IVIM subject, ~1 download). trr fit + a pure-numpy segmented fit over the ROI ≈ tens of seconds; timeouts agent 3600 s / verifier 900 s. Deps: dipy 1.12.1 + numpy/scipy/nibabel (no cvxpy — the second estimator is a pure numpy/scipy segmented fit, so the environment stays dependency-light and build-robust).
