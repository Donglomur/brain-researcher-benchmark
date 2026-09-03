## MOVIESYNC-001

**Proposal Title:** Inter-subject correlation of the movie-evoked visual-cortex response — a clean reproduction / easy control (estimator-agnostic)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Naturalistic fMRI / Inter-subject correlation

**Source paper (landscape):** Hasson et al. (2004), *Science* 303:1634 (inter-subject correlation); Richardson et al. (2018), *Nature Communications* 9:1027 (`development_fmri`, OpenNeuro ds000228); Nastase et al. (2019), *SCAN* (ISC estimator taxonomy). Anchor for the `naturalistic fMRI` / `functional connectivity` topics.

**Status: EASY CONTROL — full runnable task, grader fixed and re-validated on real data.**

### What this task is

A faithful **reproduction / easy control**: on the pinned `development_fmri` cohort (Pixar *Partly Cloudy*), extract the three MSDL visual-cortex regions with the pinned masker/confound/band-pass recipe and report the **inter-subject correlation (ISC)** of the movie response. It has calibration value — a competent agent recovers an above-chance visual ISC — and is not forced to be hard.

### Fairness fix (why this revision exists)

The previous grader pinned the dataset, atlas, region set, nuisance regression and band-pass but **left the ISC estimator unnamed**, then failed any leave-one-out estimate (~0.365) as an "inflated artifact," accepting only the pairwise value (~0.152). That is a **fairness bug**: leave-one-out ISC (correlate each participant with the mean of the others) is a completely standard, widely used estimator (Hasson 2004 used exactly this template approach; BrainIAK and most naturalistic-fMRI toolboxes default to it). Nastase et al. 2019 catalog both pairwise and leave-one-out as legitimate — leave-one-out is simply larger because it correlates against a higher-SNR template, not wrong. Failing a scientifically-correct leave-one-out answer violates the fairness contract.

**Resolution (widen the band + make the deliverable unambiguous):**
- `instruction.md` now states explicitly that **either** estimator (pairwise or leave-one-out) is acceptable, and asks the submission to name which it used in `run_metadata.json`. There is no hidden trap.
- The grader accepts any legitimate above-chance visual-cortex ISC in the band **[0.05, 0.60]** — which contains both the pairwise (0.152) and leave-one-out (0.365) estimates and reasonable variants of either — and only fails a wrong quantity.

### Ground truth (re-validated on real data, this revision)

nilearn 0.13.1, `fetch_development_fmri(n_subjects=40)`, MSDL atlas, `NiftiMapsMasker(standardize="zscore_sample", low_pass=0.1, high_pass=0.01, t_r=2.0)`, confound-cleaned, mean over `["Vis","Striate","Occ post"]`:

| estimator | visual-cortex ISC |
|---|---|
| pairwise (mean r over subject pairs) | **0.152** |
| leave-one-out (subject vs mean of others) | **0.365** |
| chance | ~0.0 |

### Verifier (2 plain checks; both must pass)

1. **`test_isc_reported`** — a parseable inter-subject correlation was produced, and it is above chance (`max > 0.03`).
2. **`test_isc_is_a_valid_visual_estimate`** — at least one reported ISC candidate lies in the valid visual-cortex band `[0.05, 0.60]`. Schema-robust (walks every JSON at any depth plus prose), estimator-agnostic (per-region and leave-one-out values are no longer excluded), and rejects only a wrong quantity.

### Discrimination (re-validated on real data)

| answer | test 1 | test 2 | verdict |
|---|---|---|---|
| pairwise ISC 0.152 (reference) | pass | pass | **PASS** |
| leave-one-out ISC 0.365 (previously failed — the fairness bug) | pass | pass | **PASS** |
| chance / wrong-region ISC 0.012 | **fail** | **fail** | **FAIL** |
| degenerate near-unity 0.98 (self-correlation / undropped-diagonal bug) | pass | **fail** | **FAIL** |

Both defensible correct answers now pass; a wrong quantity fails on both ends of the band.

### Cost

`hard` resource envelope inherited (cpus 2, mem 8 GB, internet on to fetch ds000228 + MSDL; timeouts 3600 s), but scientifically an easy control — the masker extraction over 40 subjects dominates runtime (~a few minutes); the ISC itself is trivial.
