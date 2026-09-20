"""Proof-of-work grading for TIMEDECODE-001 (single-trial MEG modality decoding, MNE sample).

Templates: QSMDIPOLE-001 (held-out reference + tight tolerance) + FCSTAB-001 (per-item table +
recompute + discriminating numbers). See PROOF_OF_WORK_SPEC.md.

Held-out reference (tests/reference.npz), built by running solution/compute.py on the real MNE
`sample` data (gradiometers; -0.2..0.5 s epochs, baseline (None,0), grad reject 4000e-13,
decim=2; each 0.05-0.45 s post-stimulus time sample of every trial is one example; StandardScaler
+ logistic regression; 5 folds; auditory {1,2} vs visual {3,4}). Re-validated across every
defensible choice:

  folds grouped BY TRIAL (leakage-free)   SGKF5=0.666 SGKF10=0.683 GKF5=0.689 GKF10=0.689 LOGO=0.688
  ordinary random k-fold over pooled samples   SKF5=0.791 SKF10=0.792 KF5=0.789   <- inflated

Each trial contributes many autocorrelated time samples sharing one modality label. Splitting the
pooled (trial x time) samples with a random k-fold puts samples from the same trial in both train
and test, inflating the accuracy to ~0.79; keeping every trial wholly on one side of the split
(StratifiedGroupKFold / GroupKFold / LeaveOneGroupOut by trial) gives the honest ~0.67. The
instruction pins only the fold COUNT (5); the fold-construction scheme is left to judgement.

The single headline is made non-guessable by the per-fold breakdown: the honest trial-grouped
folds all sit in the ~0.65-0.69 band, far below the ~0.79 random-k-fold folds. A submission whose
per-fold accuracies sit in the inflated band, or whose headline is not the recomputed trial-grouped
value, fails.

Three pillars (all required):
  1. per-fold table present, non-constant, folds in the trial-grouped (leakage-free) band
  2. the reported headline recomputes from the per-fold rows AND lands in the accept window
  3. the reported headline is the trial-grouped value, materially below the random-k-fold value
"""
from proof_of_work import (
    OUT, load_reference, load_results, headline_accuracy, reported_leaky, load_per_fold,
    nonconstant, findings_text,
)

REF = load_reference()
ST = REF["stats"]
ACCEPT_LO = ST["ACCEPT_LO"]
ACCEPT_HI = ST["ACCEPT_HI"]
HONEST = ST["honest_accuracy"]
GROUPED_MAX = ST["grouped_max"]
LEAKY_MIN = ST["leaky_min"]
LEAKY = ST["leaky_accuracy"]
RECOMPUTE_TOL = ST["MEAN_RECOMPUTE_TOL"]
GAP_MIN = ST["GAP_MIN"]
MIN_FOLDS = int(ST["MIN_FOLDS"])
CHANCE = ST["chance"]
EPS = ST["EPS"]
N_T = int(ST["n_t"])
N_TRIALS = int(ST["n_trials"])
N_SAMPLES_TOTAL = int(ST["n_samples_total"])
# per-fold discriminator between the grouped band (<=0.689) and the leaky band (>=0.789)
PERFOLD_MAX = round(0.5 * (GROUPED_MAX + LEAKY_MIN), 4)


# =============================================================================================
# Pillar 1 -- the per-fold breakdown is a real trial-grouped one (leakage-free band)
# =============================================================================================
def test_per_fold_table_is_trial_grouped_band():
    accs, nss, nts = load_per_fold()
    assert len(accs) >= MIN_FOLDS, (
        f"per-fold table has only {len(accs)} folds; the instruction fixes the fold count at "
        f"{MIN_FOLDS}. A shorter table is not the real per-fold breakdown.")
    assert nonconstant(accs, EPS), "per-fold accuracies are constant across folds -- looks fabricated"
    assert (accs > CHANCE).mean() >= 0.8, "most folds are at/below chance (0.5) -- not a real decoder"
    below = float((accs <= PERFOLD_MAX).mean())
    assert below >= 0.8, (
        f"only {below:.0%} of the per-fold accuracies are in the trial-grouped (leakage-free) band "
        f"(<= {PERFOLD_MAX}); the rest sit in the inflated random-k-fold band (~{LEAKY:.2f}). The "
        f"pooled (trial x time) samples must be split with the folds grouped by trial, so that "
        f"held-out samples come only from unseen trials.")
    # structural signature of trial grouping when trial counts are reported
    if nts is not None and nss is not None:
        import math as _m
        ok = [i for i in range(min(len(nts), len(nss)))
              if _m.isfinite(nts[i]) and _m.isfinite(nss[i]) and nts[i] > 0
              and abs(nss[i] - nts[i] * N_T) <= max(2 * N_T, 0.15 * nss[i])]
        assert len(ok) >= 0.6 * len(nts), (
            "the reported per-fold test-sample counts are not consistent with whole trials held out "
            f"(n_test_samples ~= n_test_trials x {N_T}); the folds do not appear to be trial-grouped")


# =============================================================================================
# Pillar 2 -- the headline recomputes from the per-fold rows and lands in the accept window
# =============================================================================================
def test_headline_recomputes_and_in_band():
    res = load_results()
    acc = headline_accuracy(res)
    assert acc is not None, "no cross-validated accuracy reported in decoding_results.json"
    assert int(res.get("n_classes", 0)) == 2 or len(res.get("classes", [])) == 2, \
        "must be a two-class (auditory vs visual) decoding problem"
    accs, _, _ = load_per_fold()
    recomputed = float(accs.mean())
    assert abs(recomputed - acc) <= RECOMPUTE_TOL, (
        f"the reported accuracy {acc:.3f} is not the mean of the submitted per-fold rows "
        f"({recomputed:.3f}); the headline must be recomputable from the per-fold breakdown")
    assert ACCEPT_LO <= acc <= ACCEPT_HI, (
        f"reported cross-validated accuracy {acc:.3f} is outside the trial-grouped accept window "
        f"[{ACCEPT_LO}, {ACCEPT_HI}]. A value near {LEAKY:.3f} is the random-k-fold artifact (same-"
        f"trial samples leak across the split); a value near chance is not a real decoder.")


# =============================================================================================
# Pillar 2b -- the pipeline was actually run: epoch / pooled-sample counts match the reference
# =============================================================================================
def test_sample_counts_match_reference():
    """The number of trials surviving the pinned artifact rejection (288), the pooled
    (trial x time) sample count (8640), and the per-fold test-sample total must be the REAL
    ones -- a fabricator who did not build the epochs cannot know them."""
    res = load_results()
    n_trials = res.get("n_trials")
    n_total = res.get("n_samples_total")
    assert isinstance(n_trials, (int, float)) and abs(int(n_trials) - N_TRIALS) <= 5, (
        f"reported n_trials={n_trials} is not the number of epochs surviving the pinned "
        f"grad=4000e-13 rejection (~{N_TRIALS}); the epochs were not built as specified")
    assert isinstance(n_total, (int, float)) and abs(int(n_total) - N_SAMPLES_TOTAL) <= 0.05 * N_SAMPLES_TOTAL, (
        f"reported n_samples_total={n_total} is not the real pooled (trial x time) sample count "
        f"(~{N_SAMPLES_TOTAL}); the pooled samples were not built as specified")
    accs, nss, _ = load_per_fold()
    if nss is not None:
        tot = sum(v for v in nss if v == v)
        assert abs(tot - N_SAMPLES_TOTAL) <= 0.06 * N_SAMPLES_TOTAL, (
            f"the per-fold n_test_samples sum to {tot:.0f}, not the ~{N_SAMPLES_TOTAL} pooled samples "
            f"(each sample should be tested exactly once across the folds)")


# =============================================================================================
# Pillar 3 -- the reported number is the trial-grouped value, not the leaky one
# =============================================================================================
def test_reported_accuracy_is_trial_grouped():
    res = load_results()
    acc = headline_accuracy(res)
    assert acc is not None, "no accuracy reported"
    assert acc <= LEAKY - GAP_MIN, (
        f"reported accuracy {acc:.3f} is not materially below the random-k-fold value "
        f"(~{LEAKY:.3f}); a trial-grouped (leakage-free) estimate must be under it by >= {GAP_MIN}")
    for lk in reported_leaky(res):
        if lk > CHANCE + 0.1:
            assert abs(lk - LEAKY) <= 0.06, (
                f"the submission reports a random-k-fold accuracy {lk:.3f} that does not match the "
                f"real leaky value (~{LEAKY:.3f}); the contrast appears fabricated")


# --- secondary prose guard (numbers above carry the grade) -----------------------------------
def test_findings_report_decoding():
    text = findings_text()
    assert text, "findings.md is missing or empty"
    import re
    assert re.search(r"accuracy|decod", text), "findings.md does not state a decoding accuracy"
