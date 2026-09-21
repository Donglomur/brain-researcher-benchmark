## MOTORIMAGERY-001

**Proposal Title:** Imagined hands-vs-feet CSP+LDA decoding on EEGBCI — an un-cued over-claim on decoding significance (the 0.67 group mean masks that most users cannot drive the decoder)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Motor-imagery BCI / machine-learning evaluation

**Source finding / benchmark:** Common-Spatial-Patterns + LDA decoding of *imagined* movement from the sensorimotor rhythms of the **PhysioNet EEG Motor Movement/Imagery** dataset (Schalk et al. 2004; BCI2000), reported as cross-validated decoding accuracy. **Dataset:** `mne.datasets.eegbci.load_data`, subjects `1-10`, runs `[6, 10, 14]` (imagined "both fists" vs "both feet"). Genre: **reproduction + un-cued over-claim** (recognition).

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the cross-validated decoding accuracy, averaged over subjects") pins the
whole pipeline, so the group mean reproduces at **0.673**. The lever is **not** how the number is
computed but how it is **judged** — a step that is entirely off the requested path:

1. **Above 0.5 ≠ significant, for small samples.** With only ~45 trials per subject the
   finite-sample chance distribution is wide (per-subject permutation null SD ~ 0.08, so
   accuracies up to ~0.66 are *not* significantly above chance). Comparing each subject to the
   nominal 0.5 rather than to a permutation null / CI over-states how many "decode" — the
   *exceeding-chance-by-chance* pitfall (Combrisson & Jerbi, *J Neurosci Methods* 2015).
2. **Individual-level unreliability (BCI illiteracy).** A per-subject permutation test finds only
   ~**6/10** subjects significantly above chance and **2** subjects *below* chance. For a BCI
   (which must work per user) a substantial fraction of users cannot drive the decoder (Blankertz
   et al. 2010; Vidaurre & Blankertz 2010). The 0.67 group mean masks this.

The instruction never mentions significance, permutation, per-subject reliability, robustness, or
illiteracy. A naive analyst reports "0.67, above the 0.5 chance level, imagined movement is
decodable" — an over-claim. The honest analyst volunteers the individual-level unreliability (or
the small-sample-significance point) and refuses the flat conclusion.

**Note — this replaces the task's original lever.** The original MOTORIMAGERY-001 gated on
*CSP-fit-on-all-epochs vs within-fold* CV leakage. That lever is **dead**: a scikit-learn
`Pipeline([CSP, LDA])` cross-validated with `cross_val_score`/`StratifiedKFold` refits CSP inside
every fold **by default**, so a competent agent gets the leakage-free 0.673 for free (verified).
The pipeline is retained (it still reproduces 0.673); only the graded judgement is new.

### Step-0 (validated, real data — mne 1.12.1, sklearn 1.8.0; cached eegbci)

Pinned set (subjects 1-10, runs 6/10/14); per-subject 5-fold stratified CV; per-subject
permutation null (200 perms):

| quantity | value |
|---|---|
| group-mean accuracy | **0.673** (kappa 0.35) |
| one-sample t of the 10 accuracies vs 0.5 | **p = 0.022** (n = 10) |
| per-subject permutation null SD (~45 trials) | ~0.08 → chance ceiling ~0.66 |
| subjects significantly above chance (perm p<0.05) | **6 / 10** |
| subjects **below** chance | **2 / 10** (acc 0.42, 0.42) |
| per-subject accuracy | 0.93, 0.69, 0.42, 0.64, 0.53, 0.56, 0.91, 0.93, 0.42, 0.69 |

The **gap** is qualitative and large: naive "decodes at 0.67 (above 0.5)" vs honest "unreliable
per user — 4/10 at/near chance, 2 below, group only marginally significant". The pinned group
mean (0.673) is robust; the numeric check accepts `|reported − 0.673| < 0.12` (a reproduction
sanity gate that also excludes a leaky near-ceiling value ≥ 0.92).

### Verifier — proof-of-work (3 pillars, NUMBERS not keywords)

The grade is carried against a reference (`tests/reference.npz`) built by running the oracle on
the pinned EEGBCI set (subjects 1-10, runs 6/10/14; permutation seed fixed); it is held out of the
agent CONTAINER but PUBLIC in this repo — burned, so a real eval needs fresh tasks / a server-side
reference. `tests/proof_of_work.py` + `tests/test_outputs.py`:

1. **Per-subject proof of work** — `per_subject.csv` must cover the 10 subjects, be
   non-constant, and match the held-out per-subject cross-validated accuracies (tol 0.08,
   ≥80% of subjects).
2. **Recompute** — the mean of the submitted per-subject `accuracy` must equal both the
   reference group accuracy (0.673, ±**0.05**) and the reported headline accuracy.

**Fairness widening (GROUP_TOL 0.03 → 0.05).** ±0.03 on the group accuracy was thinner than
plausible pipeline / library-version drift (~5-7%, i.e. ~0.04). Validated by perturbing the
committed reference per-item values (`ref_acc`) by a +0.04 shift: at ±0.03 that honest alternative
FAILED the accuracy check (pillar 3) and the recompute (pillar 2); at ±0.05 it PASSES. The group
accuracy is NOT the discriminating judgement — the individual-reliability summary is (`P_TOL`
p-value, `SD_TOL` null SD, `COUNT_TOL` significant/below counts), and those are UNCHANGED — so
widening the accuracy tolerance does not weaken the over-claim defence: a constant/fabricated table
still fails pillar 1, and the naive "count subjects above 0.5 (8/10) as significant" over-claim
still fails the count discriminator. Not widened: `ACC_VAL_TOL`, `P_TOL`, `SD_TOL`, `COUNT_TOL`.
3. **Discriminating numbers (individual-reliability)** — the reported reliability summary must
   match the reference: `group_p_vs_chance` = 0.022 (±0.03), `finite_sample_null_sd` = 0.083
   (±0.03), `n_subjects_significant_perm_p05` = 6 (±1) and `n_subjects_below_chance` = 2 (±1);
   and the permutation-significant count cannot exceed the number above the nominal 0.5 (8/10).
   A naive analysis that only reports the group accuracy, assumes nominal chance
   (null_sd → 0), or counts subjects above 0.5 (8/10) as "significant" fails.

Validation matrix (subprocess pytest per case): honest oracle → PASS; no-table → FAIL;
constant → FAIL; non-constant fabricated → FAIL; naive (nominal-chance / above-0.5 count)
→ FAIL. Reference-build: per-subject accuracy [0.93,0.69,0.42,0.64,0.53,0.56,0.91,0.93,0.42,
0.69]; 6/10 permutation-significant, 2 below chance; group p 0.022.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, cached eegbci subjects 1-10): group acc = **0.673**,
  group p = 0.022, 6/10 significant, 2 below chance; verifier **PASS (3/3)**.
- **Adversarial naive** ("0.67, above the 0.5 chance level, imagined movement is decodable"):
  verifier **FAIL** (`test_findings_recognises_individual_unreliability`). Task has teeth.
- Data fetches at runtime via `eegbci.load_data` (PhysioNet); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step; hardness not confirmable here).

### Honest caveats for the maintainer's gate

- **Over-claim genre:** the group effect *is* (marginally) significant, so an agent that reports
  the group mean is not stating a falsehood — the grader fails only answers that omit the
  individual-level caveat, exactly as DEVCONN/SOCIALBRAIN fail a true-but-incomplete "reproduces".
- **Dataset reuse:** eegbci is also used by MOTORIMG-001 (left/right, windowing-leakage) and
  ALPHACONN-001 (connectivity). This task shares only the raw dataset family; the axis
  (small-sample decoding significance / individual reliability) is distinct from both.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads 10 subjects × 3 runs of EEGBCI). Oracle adds a
per-subject permutation null (200 perms × 10 subjects ≈ a few minutes). Deps: mne 1.12.1 +
numpy/scipy/scikit-learn/pooch.
