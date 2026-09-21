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

### PROOF-OF-WORK REWORK (this revision — un-cued judgment preserved)

The keyword-only recognition check (fabrication-vulnerable per the suite audit) is replaced by
a held-out per-voxel reference + three numeric pillars, WITHOUT cueing the free-water judgment
(the instruction still names only "the periventricular white-matter FA").

- **Held-out reference** (`tests/reference.npz`, sha256 `e6537380…fc07`, ~22 KB, committed,
  never shipped): the per-voxel FA map over the fixed 1740-voxel periventricular ROI for three
  model configs — free-water fwDTI 0.617, single-tensor DTI(b≤2000) 0.527, DTI(b≤1000) 0.427 —
  built by running the pinned pipeline on the real dipy Sherbrooke subject (numpy 2.1.3 /
  scipy 1.14.1 / dipy 1.12.1).
- **Neutral intermediate output** (new, un-cued): `fa_voxelwise.csv` — the per-voxel FA the
  standard pipeline already produces (columns `i,j,k,fa`).
- **Pillar 1** — the per-voxel FA table covers the real ROI (≥50 %), is non-constant, and
  correlates ≥0.80 with some real model config (a fabricated/constant/guessed table matches
  none).
- **Pillar 2** — the ROI mean recomputes to the reported FA and a physically real FA (range
  [0.43, 0.62] ±margin); a globally rescaled/fabricated map is caught.
- **Pillar 3** — the free-water / CSF partial-volume dependence graded as NUMBERS, with a
  negation-guarded CSF-deflation prose fallback (the honest single-tensor-that-flags-the-
  confound, or fwDTI-with-mechanism, path).

**Validation matrix (subprocess pytest per case):** honest (fwDTI + single-tensor context)
PASS · honest-prose (fwDTI + CSF-deflation mechanism, one number) PASS · no-table / constant /
fabricated-non-constant / fabricated-coords FAIL (pillar 1) · naive over-claim (real
single-tensor map + bare 0.527) FAIL (pillar 3 only; pillars 1–2 pass).

### Cost

`hard`. cpus 2, mem 8 GB, internet on (dipy fetches the Sherbrooke 3-shell subject, ~1 download). A DTI fit plus a region-restricted fwDTI fit ≈ 60 s locally; timeouts agent 3600 s / verifier 900 s. Deps: dipy 1.12.1 + numpy/scipy/nibabel/h5py.

### Second-pass fix (2026-09): the free-water sweep is now PER-VOXEL-BACKED + upper-ceiling fairness

The red-team confirmed pillar 3 was gameable: its prose fallback let a **naive single-tensor DTI
fit + a textbook CSF-deflation sentence** pass, and the numeric branch matched *guessable
reported scalars* (~0.62 / ~0.53) — the CORRECTED (free-water) model was never enforced to be
run. It also flagged an upper-band-ceiling **fairness false-negative** (an honest fwDTI, which
can run ~+10% high, could exceed the sanity range). Per SECOND_PASS_BRIEF §5 + the PVFA-specific
fairness note.

**What changed**
- New Required Output `fa_sweep.csv`: the per-voxel FA under each diffusion model evaluated
  (columns `i,j,k,model,fa`, ≥2 models). Instruction describes it neutrally as "the per-voxel FA
  under each diffusion model you evaluate" — it does **not** name free water, fwDTI, CSF partial
  volume, or which model is correct.
- Pillar 3 rewritten (`test_freewater_sweep_matches_reference`): each sweep group must be a REAL
  per-voxel fit — cover the ROI, non-constant, match ONE held-out config's FA pattern
  (r ≥ 0.80) AND its ROI-mean FA (≤ 0.08) — and the matched configs must include the
  **free-water-corrected model (`fwdti`)** plus ≥1 single-tensor, at distinct configs spanning
  ≥ 0.06. The prose fallback and reported-scalar `straddle` branch are removed.
- **Upper-ceiling fairness fix:** pillar 2's `RANGE_MARGIN` widened 0.06 → **0.10** (upper bound
  0.717) so an honest free-water FA at the top of the band passes; the sweep's `fwdti` mean-match
  tol is **0.08** (admits fwDTI ~+10% high, and stays below the 0.09 fwDTI-vs-single-tensor gap).
- `solution/compute.py` now writes `fa_sweep.csv` from the fwDTI and single-tensor fits it
  already computes.

**Why un-fabricable** (measured on the reference maps): a fabricated group matches no config's
pattern. A **rescaled/shifted** copy of one single-tensor fit is scale- and shift-invariant in r
→ best-correlates with the SAME single-tensor config → not a distinct config, and its shifted
ROI mean (0.617) no longer matches that config's mean (0.527, gap 0.09 > 0.08 tol) → a single fit
cannot be inflated into a fake `fwdti`. Faking `fwdti` requires actually estimating the
free-water compartment per voxel (a genuinely different spatial pattern; fwDTI self-corr 1.0 vs
single-tensor cross 0.898).

**Adversarial self-validation** (subprocess pytest, fixtures from the held-out per-model
reference maps):

| case | verdict | mechanism |
|---|---|---|
| honest (fwDTI headline + fwDTI/single-tensor per-voxel sweep) | **PASS** | all pillars |
| defensible: fwDTI + a different single-tensor (b=1000) | **PASS** | 2 distinct configs incl. fwdti |
| **fairness: honest fwDTI at the upper band edge (+9.7%, mean 0.677)** | **PASS** | wide upper margin; mean-match 0.06 < 0.08 |
| defensible: version-drift FA noise (r ≈ 0.90) | **PASS** | r ≥ 0.80 |
| attack A: fabricated sweep (random FA, right means) | **FAIL** | 0 configs matched |
| attack C: single-tensor only, two real single-tensor groups, no fwDTI | **FAIL** | corrected `fwdti` absent |
| attack C: sweep has 1 group | **FAIL** | < 2 groups |
| attack C: single-tensor + rescaled copy (mean→0.617) relabeled `fwdti` | **FAIL** | best-corr → single-tensor; mean 0.617≠0.527 |
| attack C: single-tensor + additively-shifted copy relabeled `fwdti` | **FAIL** | same (r shift-invariant) → single config |

The upper-band-edge honest case PASSES and every attack-C variant (guessed/rescaled/shifted
corrected value, and the naive single-tensor sweep omitting the correction) FAILS.

**Honest-limitations (blunt):**
- *Live-dipy not run.* dipy is not installed here and the sample download stalls, so the fixtures
  were synthesised from the committed held-out per-model reference maps. `compute.py` writes the
  sweep from the fwDTI and single-tensor fits it already computes; a maintainer must confirm on a
  live dipy run (no committed reference-build script exists — the maintainer should add one).
- *Mild cue (accepted 5(a)).* Requiring a per-model FA table cues that FA depends on the diffusion
  model. The retained teeth: the free-water-corrected model must be COMPUTED per-voxel, which a
  naive single-fit-plus-sentence, a guessed scalar, or a rescaled single-tensor copy cannot fake.
- *Tight attack margin.* The fwDTI-vs-single-tensor mean gap (0.09) barely exceeds the mean-match
  tol (0.08); this is the intended balance between admitting a high honest fwDTI and rejecting an
  inflated single-tensor. The per-voxel pattern match (r) is the primary gate, so the 0.01 mean
  margin is a secondary guard, not the sole defense.
