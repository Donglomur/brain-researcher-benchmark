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

### Verifier — PROOF OF WORK (`tests/test_outputs.py` + `tests/proof_of_work.py`)

Rebuilt to the proof-of-work contract (`PROOF_OF_WORK_SPEC.md`): a passing submission must be
impossible to produce without running the real nested leave-one-run-out decoding on the real
subject. A **held-out reference** (`tests/reference.npz`, built by running `solution/compute.py`
and kept out of the container) stores the per-run held-out accuracies of the NESTED pipeline keyed
by acquisition run, plus the discriminating nested (0.656) vs circular select-once (0.757) numbers.
The single headline is made non-guessable by the required **per-fold breakdown** (`per_fold.csv`).
Three pillars, all required:

1. **per-fold table matches the held-out reference** — the submitted per-run held-out accuracies
   are the REAL nested values (keyed by held-out run; within-tol fraction ≥ 0.7 OR correlation
   ≥ 0.8), non-constant. A fabricated table or a circular pipeline's per-run numbers do not match.
2. **headline recomputes** — reported `cv_accuracy` = mean of the submitted per-fold rows AND the
   nested reference **0.656** (± 0.06). (A circular run that reports 0.656 but submits its own
   ~0.757 per-fold rows fails the recompute.)
3. **nested, not circular** — the reported accuracy is materially below the circular value
   (~0.757) by ≥ 0.05; any circular contrast the submission reports must itself be the real ~0.757.
   A secondary prose guard requires the write-up to describe the evaluation.

### Discrimination — validated locally via SUBPROCESS pytest (uvx, container-matched)

| submission | verdict | why |
|---|---|---|
| reference oracle (nested; per_fold.csv + cv_accuracy 0.656) | **PASS** | all checks |
| no per_fold.csv | **FAIL** | pillar 1 (+2) |
| constant per-fold table (all = 0.656) | **FAIL** | pillar 1 non-constant guard |
| non-constant fabricated table (right mean 0.656, wrong per-fold) | **FAIL** | pillar 1 |
| naive random-fold table + cv_accuracy 0.757 | **FAIL** | pillars 2, 3 |
| **realistic circular** select-once (real per-run values, cv_accuracy 0.757) | **FAIL** | pillars 1, 2, 3 |

The realistic circular adversary — a genuine select-once pipeline with its true per-run held-out
accuracies — is the strongest attack and is rejected on all three pillars: its per-run numbers do
not match the nested reference, and its 0.757 headline fails the nested match.

### Reference provenance / packaging

- **Held-out reference** `tests/reference.npz` from `solution/compute.py` on Haxby subject-2
  (nilearn 0.13.1 / scikit-learn 1.8.0): `ref_run_ids` = runs 0–11, `ref_fold_acc` = nested
  per-run held-out accuracies, `ref_stats.nested_accuracy` = 0.6562,
  `ref_stats.circular_accuracy` = 0.7569. Never ships to the container.
- **Pinned inputs:** Haxby **subject 2**, whole-brain `mask`, drop `rest`, per-run masker,
  `SelectKBest(f_classif, k=500)`, `SVC(linear, C=1)`, leave-one-run-out. Deterministic dataset,
  so the per-run numbers reproduce exactly on the pinned stack.
- **Packaging follow-up (maintainer):** raw subject fetch ~300 MB (> 90 MB bake threshold), so
  runtime fetch + `allow_internet=true` are kept; baking the derived whole-brain masked series
  to set `allow_internet=false` is a cheap follow-up.

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally. The ≥2-frontier-family (k≥3, hand-rescored) gate — that un-cued frontier agents actually select voxels once on the full dataset and report the inflated ~0.76 — is a maintainer step. (Note: `nilearn`'s own decoding docs warn about feature-selection circularity and use nested pipelines, so a tutorial-faithful agent may avoid the trap; the calibration will measure how often un-cued agents select before cross-validating.)

### Cost / data caveat

`hard`. cpus 2, mem 8 GB, internet on (fetches `haxby2001` for subject 2, ~250 MB, at runtime; timeouts 3600 s). Deps: nilearn 0.13.1 + scikit-learn 1.8.0 + scipy/pandas/nibabel/numpy (pinned in the Dockerfile to the versions the 0.656 ground truth was measured with). Runtime is dominated by masking the whole-brain BOLD (a few seconds) and 12 leave-one-run-out SVM fits with nested ANOVA selection (seconds). Data caveat: `fetch_haxby` pulls from a public mirror; on rare mirror hiccups the fetch can time out and should be retried (an infra artifact, not a task FAIL).
