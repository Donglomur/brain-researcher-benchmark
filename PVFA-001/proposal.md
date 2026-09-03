## PVFA-001

**Proposal Title:** Fractional anisotropy of periventricular white matter from multi-shell diffusion MRI — an un-cued **CSF partial-volume / free-water** trap (reproduction genre)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI microstructure

**Source finding / method:** Pasternak et al. (2009), *Magn. Reson. Med.*, https://doi.org/10.1002/mrm.22055 (free-water elimination); Hoy et al. (2014), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2014.09.053 (free-water DTI, the dipy `fwdti` implementation); Metzler-Baddeley et al. (2012), *NeuroImage* (periventricular CSF partial-volume in DTI). **Dataset:** the dipy-shipped Sherbrooke 3-shell single subject, fetched at runtime via `dipy.data.fetch_sherbrooke_3shell` / `read_sherbrooke_3shell` — real, public human diffusion MRI, b = 0/1000/2000/3500 s/mm².

**Genre:** reproduction (pin everything except the one lever; grade the reported number). Real data, no synthetic/planted truth.

### The un-cued lever

Periventricular white matter borders the ventricles and is heavily contaminated by **cerebrospinal-fluid (CSF) partial volume**. CSF is fast and isotropic (FA ≈ 0); a single diffusion tensor conflates it with the tissue, so the apparent FA is **deflated**. The recognised remedy is to model an explicit **free-water compartment** (free-water DTI, dipy `fwdti`) and report the *tissue* FA. The instruction names the deliverable (FA in periventricular white matter) and the data, and pins the reproducibility-critical preprocessing (brain mask, 1.25 mm FWHM smoothing, the exact CSF-seed / periventricular-region definition, shells b ≤ 2000) — but it **never** mentions free water, CSF partial volume, or a two-compartment model. A knowledgeable agent recognises the partial-volume confound in periventricular tissue and eliminates the free-water compartment; a naive agent fits a single tensor and reports the CSF-deflated FA.

### The trap (Step-0 validated, real data)

Pinned periventricular region (CSF seed grown 2 voxels, `0.8<MD<1.5`×10⁻³, `FA>0.25`; 1740 voxels; mean free-water fraction f = 0.39), model estimation on b ≤ 2000:

| fit | mean FA |
|---|---|
| **free-water-accounted (fwDTI, correct)** | **0.617** |
| single-tensor DTI, b ≤ 2000 (naive) | 0.527 |
| single-tensor DTI, b ≤ 1000 (naive, standard DTI) | 0.427 |
| single-tensor DTI, b ≤ 3500 (naive, all shells) | ~0.55 |

The gap between the free-water-accounted FA and any single-tensor variant is **≥ 0.09** (≈ +17% recovery of tissue anisotropy). The NLS/WLS estimator spread of the correct value is only ~0.006, so the reference is tight while every naive single-tensor value is well outside tolerance. CSF partial volume is what makes periventricular FA hard, which is exactly why the region is pinned; with the region and preprocessing pinned, the only material free choice left is whether to account for the free-water compartment = the lever. (Smoothing is a strong nuisance axis — without the pinned 1.25 mm smoothing the fwDTI estimator becomes unstable — so it is pinned.)

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) an FA fit produced a physically-plausible periventricular WM FA; (2) a periventricular white-matter region (voxel count or definition) was actually reported; (3) **the headline FA matches the free-water-accounted reference 0.615 ± 0.04** — a single-tensor fit (~0.53 or ~0.43) is outside tolerance. The tolerance passes the whole free-water family (NLS 0.617 / WLS 0.612) and fails every single-tensor variant with a ≥ 0.048 margin. The number is searched at any json depth (preferred field `fa_periventricular_wm`), skipping keys that name the naive/context/uncorrected value, with a findings.md fallback; no rubric, no score file.

**Offline discrimination (locked):** oracle output (free-water-accounted, 0.6173) → **3/3 PASS**; realistic naive output (single-tensor, 0.527, valid fit + region reported) → checks 1–2 PASS, check 3 **FAIL** → so the failure is the un-cued lever, not a format bug.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0** (locked locally). The ≥2-frontier-family gate (does GPT-5.x / Claude recognise the CSF partial-volume confound and free-water-correct unprompted, or default to single-tensor DTI FA?) is a maintainer step. Prior: single-tensor FA is the overwhelming default output of every DTI tutorial and pipeline, so reporting the CSF-deflated FA in a given ROI is the natural default an un-cued agent falls into — the trap has teeth.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy fetches the Sherbrooke 3-shell subject, ~1 download). A DTI fit plus a region-restricted fwDTI fit ≈ 60 s locally; timeouts agent 3600 s / verifier 900 s. Deps: dipy 1.12.1 + numpy/scipy/nibabel/h5py.
