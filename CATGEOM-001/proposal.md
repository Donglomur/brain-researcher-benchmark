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

### Verifier (2 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **discriminability reported** — a parseable index in [−1, 1] exists.
2. **cross-run discriminability reproduced** — the reported index is within **0.13** of the cross-run value **+0.056**. Values are gathered at any depth from any JSON (discriminability/index/structure-keyed scalars, with within-run / per-run / naive / artifact / raw-dissimilarity / spread keys excluded) and from prose (numbers next to "discriminability"). The window admits the all-pairs variant (+0.03) and rejects the within-run artifact (−0.35, which is 0.40 away).

### Discrimination (validated locally)

| submission | reported discriminability | verdict |
|---|---|---|
| reference oracle (cross-run; also records the within-run value under a descriptive `*_within_run_artifact` key) | +0.056 | **PASS** |
| naive within-run RDM averaged (everything else identical) | −0.346 | **FAIL** |
| all-pairs RDM (same-run included, ~correct) | +0.032 | **PASS** |
| prose-only "discriminability index … +0.056" | +0.056 | **PASS** |

Verifier robustness checked: a submission that reports BOTH the honest +0.056 and a within-run comparison (−0.346 under a `within_run`/`artifact` key) still passes, because the artifact value is excluded from the headline candidates; the honest value is what is graded. A within-run + cocktail-blank combination (+0.20) is rejected by the window; a cross-run + cocktail value (+0.16) passes (it is on the correct side of the lever).

### Distinctness from the shipped Haxby tasks

This is the first **RSA / representational-geometry** task on this dataset. The lever is the **same-run bias of dissimilarity estimates** (an estimator-bias / RDM-diagonal-inflation problem), which is a different statistical phenomenon from cross-validation fold choice (VTDECODE/DECODE), feature-selection circularity (OBJCAT), or a within-vs-cross-session classifier split. The deliverable is a representational discriminability index, not a decoding accuracy.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually read the between-category dissimilarities off within-run RDMs and report the negative artifact — is a maintainer step. (Note: nilearn/RSA-toolbox tutorials that use cross-validated distances would avoid the trap; the calibration will measure how often un-cued agents average per-run RDMs.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `haxby2001` for subject 3, ~250 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the +0.056 ground truth was measured with). Runtime is dominated by one `NiftiMasker.fit_transform` plus the pairwise pattern correlations (well under a minute). Data caveat: `fetch_haxby` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
