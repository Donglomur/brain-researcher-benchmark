## PVFA-001

**Proposal Title:** Fractional anisotropy of periventricular white matter from multi-shell diffusion MRI — an un-cued **CSF partial-volume / free-water** confound (rigor/judgment genre; graded like DEVCONN-001, not a point-match)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI microstructure

**Source finding / method:** Pasternak et al. (2009), *Magn. Reson. Med.*, https://doi.org/10.1002/mrm.22055 (free-water elimination); Hoy et al. (2014), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2014.09.053 (free-water DTI, the dipy `fwdti` implementation); Metzler-Baddeley et al. (2012), *NeuroImage* (periventricular CSF partial-volume in DTI). **Dataset:** the dipy-shipped Sherbrooke 3-shell single subject, fetched at runtime via `dipy.data.fetch_sherbrooke_3shell` / `read_sherbrooke_3shell` — real, public human diffusion MRI, b = 0/1000/2000/3500 s/mm².

**Genre:** rigor / judgment (grade the write-up's discovery, DEVCONN-001 style). Real data, no synthetic/planted truth.

> **HARDENING NOTE (fairness reframe, this revision).** The first cut strict-point-matched the free-water fwDTI value (0.615 ± 0.04) and auto-**failed** any single-tensor FA. That was **unfair**: the instruction says "estimate the diffusion tensor", which endorses a single-tensor fit, so an honest single-tensor FA (~0.53) is a legitimate number and must not fail on the value. Per the tb-science bar the failure must be an **un-cued metacognitive** miss, not a hidden point value. The verifier now grades the **judgment** (DEVCONN-style): does the write-up VOLUNTEER that a periventricular FA is confounded by CSF partial volume — linking CSF partial volume → FA deflation → a free-water/two-compartment correction? The reported number (single-tensor **or** free-water) is not point-matched.

### The un-cued lever / confound

Periventricular white matter borders the ventricles and is heavily contaminated by **cerebrospinal-fluid (CSF) partial volume** (here ~40% of the signal is free water). CSF is fast and isotropic (FA ≈ 0); a single diffusion tensor conflates it with the tissue, so the apparent FA is **deflated** relative to the true tissue anisotropy. The recognised remedy is to model an explicit **free-water compartment** (free-water DTI, dipy `fwdti`) and report the *tissue* FA. The instruction names the deliverable (FA in periventricular white matter) and the data, and pins the reproducibility-critical preprocessing (brain mask, 1.25 mm FWHM smoothing, the exact CSF-seed / periventricular-region definition, shells b ≤ 2000) — but it **never** mentions free water, CSF partial volume, or a two-compartment model, and it endorses estimating a diffusion tensor. A knowledgeable agent recognises the partial-volume confound in periventricular tissue and reports it (ideally free-water-correcting); a naive agent fits a single tensor and reports the CSF-deflated FA **as if it cleanly measured the tissue**, never flagging the confound. That un-cued omission is the failure this task grades.

### The trap (Step-0 validated, real data)

Pinned periventricular region (CSF seed grown 2 voxels, `0.8<MD<1.5`×10⁻³, `FA>0.25`; 1740 voxels; mean free-water fraction f = 0.39), model estimation on b ≤ 2000:

| fit | mean FA |
|---|---|
| **free-water-accounted (fwDTI, correct)** | **0.617** |
| single-tensor DTI, b ≤ 2000 (naive) | 0.527 |
| single-tensor DTI, b ≤ 1000 (naive, standard DTI) | 0.427 |
| single-tensor DTI, b ≤ 3500 (naive, all shells) | ~0.55 |

The gap between the free-water-accounted tissue FA and any single-tensor variant is **≥ 0.09** (≈ +17% recovery of tissue anisotropy), and the mean free-water fraction is 0.39 — so the partial-volume confound is large and real. These numbers are the *ground for the confound*; the grader does **not** point-match them. With the region and preprocessing pinned, the only material free choice left is whether to account for (or at least flag) the free-water compartment. (Smoothing is a strong nuisance axis — without the pinned 1.25 mm smoothing the fwDTI estimator becomes unstable — so it is pinned.)

### Verifier (3 plain checks — judgment, not point-match)

`tests/test_outputs.py`: (1) an FA fit produced a physically-plausible periventricular WM FA (single-tensor ~0.53 or free-water ~0.62 both pass — the value is **not** the discriminator); (2) a periventricular white-matter region (voxel count or definition) was actually reported; (3) **the write-up recognises the CSF partial-volume confound** — it must LINK a CSF/partial-volume/free-water term to the anisotropy being *deflated* (single-tensor) or *recovered* by a two-compartment model, in either order and within a bounded window. **False-positive guard (critical):** the pinned ROI is grown from a "CSF seed", so every submission's method names CSF and the ventricles — that is *pipeline vocabulary*, not the insight. The check never passes on a bare "csf"/"ventricle"/"FA<0.2" mention; the confound term must co-occur with a *bias/recovery statement about the anisotropy* (the same pipeline-vocab guard used in SOCIALBRAIN-001 / DEVCONN-001). Numbers are searched at any json depth; no rubric, no score file.

**Offline discrimination (locked, re-validated on real data this revision):**
| submission | test 1–2 | test 3 (judgment) | reward |
|---|---|---|---|
| **oracle** (free-water 0.617 + explains deflation/recovery) | PASS | **PASS** | **1.0** |
| **defensible-correct** (single-tensor 0.527 + flags CSF-PV deflation & free-water remedy) | PASS | **PASS** | **1.0** |
| naive-default (single-tensor 0.527, describes the CSF *seed*, no confound insight) | PASS | **FAIL** | 0 |
| over-claim (single-tensor 0.527 read as "reduced microstructural integrity") | PASS | **FAIL** | 0 |
| hedge (name-drops "partial volume effects" as a generic caveat, no link to FA) | PASS | **FAIL** | 0 |

So an honest single-tensor answer that recognises the confound **passes**, and the failure is the un-cued metacognitive omission — never the choice of estimator or an output-format bug.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0** (locked locally). The ≥2-frontier-family gate (does GPT-5.x / Claude spontaneously recognise the CSF partial-volume confound in periventricular tissue, or report a bare periventricular FA as a clean tissue measurement?) is a maintainer step. Prior: computing FA in a named ROI is the overwhelming default of every DTI tutorial, and none flag the periventricular partial-volume confound unprompted — so the un-cued omission is the natural default and the trap has teeth.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy fetches the Sherbrooke 3-shell subject, ~1 download). A DTI fit plus a region-restricted fwDTI fit ≈ 60 s locally; timeouts agent 3600 s / verifier 900 s. Deps: dipy 1.12.1 + numpy/scipy/nibabel/h5py.
