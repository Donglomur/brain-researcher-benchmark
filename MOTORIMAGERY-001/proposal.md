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

### Verifier (3 plain checks, recognition-style)

`tests/test_outputs.py`: (1) a two-class decoding with a valid above-chance group accuracy that
reproduces the pinned value (`|acc − 0.673| < 0.12`); (2) findings.md reports that accuracy; (3)
**guarded recognition** — findings.md must link a reliability-NEGATIVE judgement (at/near/below
chance, not significant, unreliable, illiteracy, cannot drive) to the **individual/per-subject/
per-user** level, OR recognise that a permutation/finite-sample null is needed and above-0.5
over-states significance. Co-occurrence guarded so a flat "above chance / decodable" conclusion
(the naive read) fails; "above chance" is deliberately excluded from the NEG set; the numeric IND
token is `N/10`, not "10 subjects", so the naive "averaged across the 10 subjects" cannot trip it.

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
