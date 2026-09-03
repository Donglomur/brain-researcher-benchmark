## CATGEOM-001

**Proposal Title:** Reproduce the Haxby ventral-temporal category discriminability (representational geometry) — an un-cued same-run RDM-inflation trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Task-fMRI representational similarity analysis (RSA)

**Source paper:** Haxby et al. (2001), *Science* 293:2425, https://doi.org/10.1126/science.1063736 (dataset: `nilearn.datasets.fetch_haxby`, cached under `~/nilearn_data`; ships to fetch at runtime). Methodological basis: same-run noise correlations bias representational dissimilarity (Henriksson et al. 2015; Alink et al. 2015; Walther et al. 2016, *NeuroImage*, "Reliability of dissimilarity measures").

**Status: FULL runnable task, oracle + naive validated locally. Step-5 frontier calibration PENDING (maintainer).**

### What this task is

A faithful, mostly-numeric **reproduction** in the RSA genre (distinct from the decoding-accuracy tasks on this dataset): build the ventral-temporal representational dissimilarity matrix (RDM) for the eight Haxby object categories and report the **category discriminability index** = (mean between-category dissimilarity − mean within-category dissimilarity) / (their sum). The subject (3), mask (`mask_vt`), sample selection (drop `rest`), masker (`NiftiMasker`, `zscore_sample` + detrend), per-run pattern estimation, dissimilarity metric (`1 − Pearson correlation`), and the discriminability formula are all pinned. The **one thing left free is how acquisition runs enter the dissimilarities**, and it is decisive.

### The un-cued lever (PRIVATE — never named in `instruction.md`)

**Same-run vs cross-run dissimilarities (RDM diagonal / off-diagonal inflation).** Each category is estimated once per run. Two patterns from the *same* run share that run's structured (low-frequency / physiological) noise, so their correlation is spuriously high and their dissimilarity spuriously low. A within-category dissimilarity can only be formed *across* runs (a category appears once per run), but between-category dissimilarities can be read off **within-run** RDMs (different categories compared inside the same run) and averaged over runs — a common, tempting way to "average out run effects". Doing so collapses the between-category dissimilarity (~0.44) below the cross-run within-category dissimilarity (~0.90), so the discriminability index goes **strongly negative** — different categories appear *more* similar than repeats of the same category, which is impossible except as a shared-noise artifact. The correct, bias-free estimate computes **every** dissimilarity across *different* runs. The instruction never mentions runs-as-a-nuisance, cross-validation, same-run, leakage, or "artifact"; the task ID is neutral (CATGEOM, not SAMERUN).

### Step-0 result (validated on cached `haxby2001`, nilearn 0.13.1 / scikit-learn 1.8.0)

Subject 3, `mask_vt` (307 voxels), 8 categories × 12 runs, `1 − Pearson correlation` dissimilarity:

| run handling | discriminability index |
|---|---|
| **cross-run (CORRECT)** | **+0.056** |
| all pattern pairs (same-run + cross-run) | +0.032 |
| within-run RDM averaged (NAIVE) | −0.346 |

Gap **≈ 0.40** (a sign flip). The cross-run value is a small positive across subjects 1–5 (+0.017 … +0.056) while the within-run value is strongly negative on every subject (−0.35 … −0.51), so the lever is robust; subject 3 is pinned for a single reproducible number (its cross-run value is the furthest of the five from zero). The correct value is stable across `standardize` in {`zscore_sample`, `zscore`}. (Removing the per-run cocktail-blank mean — a non-default extra step outside the pinned `1 − Pearson correlation` recipe — raises both branches but the within-run branch stays the higher one; the verifier's window rejects it.)

### Hardening (2026-09) — tighten so the natural all-pairs RDM no longer passes

The original window (±0.13 around +0.056) admitted the **natural all-pairs RDM (+0.032)** — the most likely un-cued default, and precisely the answer that misses the lever. Fixing it required re-measuring the two families on the real streamed data (nilearn 0.13.1, subject 3, 12 runs):

| run handling | discriminability | family |
|---|---|---|
| cross-run pooled (CORRECT) | **+0.0563** | fully cross-run |
| cross-run per-run-pair averaged | **+0.0628** | fully cross-run |
| cross-run leave-one-run-out (cross-validated) | **+0.134** | fully cross-run |
| all-pairs full RDM (NAIVE, natural default) | **+0.0321** | same-run-contaminated |
| within-run RDMs averaged (NAIVE) | **−0.346** | same-run-contaminated |

The two families are cleanly separated by an **empty gap (+0.032 → +0.056)**: any method that lets same-run pairs into the between-category mean lands at +0.032 **or below** (the natural full RDM mixes in ~8% same-run pairs, whose shared within-run noise deflates the between-category dissimilarity), while any **fully-cross-run** method lands at +0.056 **or above**. So the graded band is now the asymmetric **[+0.044, +0.15]** — floor inside the gap, ceiling generous enough to admit even the leave-one-run-out cross-validated variant (+0.134). This confirms **within-run averaging is a plausible default** (averaging per-run RDMs is a real RSA habit, and it is the −0.346 trap) AND catches the even-more-plausible all-pairs default; no de-cuing of the instruction was needed (it never names runs-as-nuisance, cross-validation, same-run, or leakage).

### Verifier (2 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **discriminability reported** — a parseable index in [−1, 1] exists.
2. **fully-cross-run discriminability reproduced** — the reported index falls in the band **[+0.044, +0.15]**. Values are gathered at any depth from any JSON (discriminability/index/structure-keyed scalars, with within-run / per-run / naive / artifact / raw-dissimilarity / spread keys excluded) and from prose (numbers next to "discriminability"); `best` is the parsed value nearest the cross-run estimate. The band fails BOTH the natural all-pairs RDM (+0.032) and the within-run artifact (−0.346) and passes every fully-cross-run estimate (+0.056, +0.063, +0.134).

### Discrimination (re-validated on real streamed data)

| submission | reported discriminability | verdict |
|---|---|---|
| reference oracle (cross-run; also records the within-run value under a descriptive `*_within_run_artifact` key) | +0.0563 | **PASS** |
| cross-run per-run-pair averaged | +0.0628 | **PASS** |
| cross-run leave-one-run-out (cross-validated) | +0.134 | **PASS** (fair to a CV variant) |
| **all-pairs full RDM (same-run included, natural default)** | **+0.0321** | **FAIL** (now excluded) |
| partial/asymmetric all-pairs | +0.009 | **FAIL** |
| within-run RDM averaged (NAIVE) | −0.346 | **FAIL** |

Verifier robustness checked: a submission that reports BOTH the honest +0.056 and a within-run comparison (−0.346 under a `within_run`/`artifact` key) still passes, because the artifact value is excluded from the headline candidates; the honest value is what is graded. The reference oracle records its within-run contrast under `discriminability_within_run_artifact` (excluded by the `artifact` key filter), so its headline +0.0563 is what is graded.

### Distinctness from the shipped Haxby tasks

This is the first **RSA / representational-geometry** task on this dataset. The lever is the **same-run bias of dissimilarity estimates** (an estimator-bias / RDM-diagonal-inflation problem), which is a different statistical phenomenon from cross-validation fold choice (VTDECODE/DECODE), feature-selection circularity (OBJCAT), or a within-vs-cross-session classifier split. The deliverable is a representational discriminability index, not a decoding accuracy.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually read the between-category dissimilarities off within-run RDMs and report the negative artifact — is a maintainer step. (Note: nilearn/RSA-toolbox tutorials that use cross-validated distances would avoid the trap; the calibration will measure how often un-cued agents average per-run RDMs.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `haxby2001` for subject 3, ~250 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the +0.056 ground truth was measured with). Runtime is dominated by one `NiftiMasker.fit_transform` plus the pairwise pattern correlations (well under a minute). Data caveat: `fetch_haxby` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
