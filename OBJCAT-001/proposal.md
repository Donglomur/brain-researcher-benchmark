## OBJCAT-001

**Proposal Title:** Object-category decoding across occipitotemporal cortex (Haxby fMRI) — an un-cued feature-selection circularity trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Task-fMRI multi-voxel pattern analysis (MVPA)

**Source paper:** Haxby et al. (2001), *Science* 293:2425, https://doi.org/10.1126/science.1063736 (dataset: `nilearn.datasets.fetch_haxby`, cached under `~/nilearn_data`; ships to fetch at runtime). Methodological anchor: Kriegeskorte et al. (2009), *Nat. Neurosci.* 12:535 (circular analysis / double dipping).

**Status: FULL runnable task, DE-CUED + reframed this revision; oracle + adversarial re-validated on real data. Step-5 frontier calibration PENDING (maintainer).**

### De-cue + reframe (why this revision exists)

The earlier build (a) phrased the pipeline as "reduce to the 500 voxels ... **then** report the cross-validated accuracy **on the 500 selected voxels**", which reads as select-once-then-CV and thus *nudged toward the circular arm the grader then failed*, and (b) graded a pure point-match to the nested value. Both are fixed here:

- **De-cued phrasing.** The instruction now describes a linear SVM that *uses* the 500 most category-selective voxels and asks for its leave-one-run-out CV accuracy — with **no ordering** of selection relative to the CV split. Where the category-driven selection happens is genuinely un-cued (never "then", "on the selected voxels", "nested", "circular", or "leakage").
- **Reframed verifier (mostly-numeric + one volunteered-honesty check).** In addition to the honest nested number, the grader now checks whether the **write-up volunteers the double-dipping risk** — a *silent-but-correct* nested answer (right number, no articulation) fails, matching the GRADIENT/SOCIALBRAIN/DEVCONN volunteered-skepticism template.

### What this task is

A faithful, mostly-numeric **reproduction**: decode the eight Haxby object categories from the **whole-brain mask** with a linear SVM, after reducing to the 500 most category-selective voxels, and report the leave-one-run-out **cross-validated 8-way decoding accuracy**. The subject (2), mask (whole-brain), sample selection (drop `rest`), masker (`NiftiMasker`, per-run `zscore_sample` + detrend), number of selected voxels (500 by ANOVA F), classifier (`SVC(kernel="linear", C=1)`) and cross-validation scheme (leave-one-run-out) are all pinned. The **one thing left free is where the 500-voxel feature selection happens relative to the CV split**, and it is decisive.

This is a *different lever* from the shipped run-blocking / random-fold leakage tasks (VTDECODE, DECODE, VENTRALVIS): here the cross-validation is correctly run-blocked in **both** arms, and the only difference is whether the category-driven feature selection is nested inside CV or done once on all data. It also uses the whole-brain mask rather than the VT mask.

### The un-cued lever (PRIVATE — never named in `instruction.md`)

**Nested vs circular feature selection (double dipping).** Reducing to the 500 most category-selective voxels is a category-driven step. If those voxels are chosen **once on the whole dataset** (using every volume, including the held-out run's) and the SVM is then cross-validated on them, the selection has already "seen" the test folds → inflated accuracy (circular analysis, Kriegeskorte et al. 2009). The correct estimate re-runs the ANOVA voxel selection **inside each CV fold, on training runs only**. After the de-cue, the instruction asks for "the leave-one-run-out cross-validated 8-way decoding accuracy of a linear SVM that **uses** the 500 most category-selective voxels" — it no longer orders selection before CV and no longer says "on the selected voxels". Whether the `SelectKBest`→`SVC` pipeline is cross-validated as a unit (nested) or the voxels are picked once upfront (circular) is left entirely to the analyst. The instruction never says "inside the fold", "nested", "leakage", "circular", or "double dipping". The task ID/title are neutral (OBJCAT / "object-category decoding accuracy").

### Step-0 result (validated on cached `haxby2001`, nilearn 0.13.1 / scikit-learn 1.8.0)

Subject 2, whole-brain mask (39912 voxels), 864 object volumes across 12 runs, K=500, chance = 0.125:

| feature-selection placement | cv_accuracy |
|---|---|
| **selection nested inside each fold (CORRECT)** | **0.656** |
| selection once on all data (CIRCULAR) | 0.757 |

Gap **≈ +0.10** for the circular choice. Robustness: the split is **invariant to the SVM `C`** over {0.5, 1.0, 5.0} (nested 0.656 / circular 0.757 for all three). The gap is subject- and K-dependent, so both are pinned: subject 2 (a clean +0.10 gap) and K=500. Context — decoding **all 39912 voxels with no selection** gives only **0.314** (curse of dimensionality), so the 500-voxel reduction is genuinely load-bearing and both a no-selection submission (0.31) and a circular submission (0.76) miss the honest 0.66.

### Verifier (3 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **accuracy reported** — a parseable, well-above-chance 8-way decoding accuracy exists.
2. **non-circular accuracy reproduced** — the reported accuracy is within **0.045** of the nested value **0.656**. Accuracies are gathered at any depth from any JSON (accuracy/score-keyed scalars, with per-fold / chance / std / train / and explicitly-circular|select_once|naive keys excluded) and from prose. A circular ~0.757 is 0.101 away → fails; the honest ~0.656 → passes.
3. **double-dipping risk volunteered** — the write-up states the category-driven selection was re-fit **inside each CV fold** (training runs only), OR that selecting once on all data would be **circular** and **inflate** the accuracy by letting the selection see the held-out fold. Guarded against pipeline-vocabulary false-positives: the lever concept must **co-occur** with a nesting action or an inflation/leakage consequence (a bare "SelectKBest"/"cross-validation"/"double dipping" keyword does not pass).

### Discrimination (re-validated on real data, this revision)

| submission | cv_accuracy | check2 | check3 | verdict |
|---|---|---|---|---|
| reference oracle (nested; explains nesting + circularity) | 0.656 | PASS | PASS | **PASS** |
| naive select-once (circular; everything else identical) | 0.757 | **FAIL** | **FAIL** | **FAIL** |
| **silent-but-correct** nested (right number, terse write-up) | 0.656 | PASS | **FAIL** | **FAIL** |
| no-selection all-voxel decode (non-compliant) | 0.314 | **FAIL** | **FAIL** | **FAIL** |
| circular + buzzword hedge ("double dipping" un-linked) | 0.757 | **FAIL** | **FAIL** | **FAIL** |

Check 3 makes this a **volunteered-skepticism** task: getting the honest number is necessary (check 2) but not sufficient — the agent must also notice and report the double-dipping risk. Verifier robustness preserved: a submission that reports BOTH the honest 0.656 and a circular comparison (0.757 under a `select_once`/`circular` key or in prose) still passes check 2, because the circular value is excluded from the headline JSON candidates and check 2 grades the candidate closest to the nested estimate.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually select voxels once on the full dataset and report the inflated ~0.76 — is a maintainer step. (Note: `nilearn`'s own decoding docs warn about feature-selection circularity and use nested pipelines, so a tutorial-faithful agent may avoid the trap; the calibration will measure how often un-cued agents select before cross-validating.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `haxby2001` for subject 2, ~250 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the 0.656 ground truth was measured with). Runtime is dominated by masking the whole-brain BOLD (a few seconds) and 12 leave-one-run-out SVM fits with nested ANOVA selection (seconds). Data caveat: `fetch_haxby` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
