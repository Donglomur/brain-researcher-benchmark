"""Grading checks for V1DGDECODE-001 (reproduce how accurately drift direction can be decoded from
a two-photon VISp population).

Ground truth (validated before release on Allen Brain Observatory ophys_experiment_id 501271265,
VISp, three_session_A; drifting gratings; per-trial response = mean dF/F over the presentation
window; all imaged neurons; 8-way drift-direction classification pooled across temporal frequency;
features standardised on the training split; linear decoder):

  n imaged neurons                                        = 215
  n grating trials                                        = 598
  chance (1/8)                                            = 0.125
  IN-SAMPLE (train == test, resubstitution) accuracy      = ~0.95-1.0   (overfit; optimistic)
  CROSS-VALIDATED accuracy (5-fold, held-out trials)      = ~0.62       <-- reported

The off-critical-path error this task targets (un-cued): with 215 neurons as features and only
~600 trials, a linear decoder can almost perfectly memorise the trials it was fit on, so scoring
the decoder on the same trials it was trained on (the in-sample / resubstitution / training-set
accuracy) returns ~0.95-1.0 -- a measure of overfitting capacity, not of how well direction can be
read out. The honest read-out accuracy comes from evaluating the decoder on held-out trials it was
not fit on (here 5-fold stratified cross-validation), which gives ~0.62 and is stable across linear
decoders (linear SVM ~0.62, logistic ~0.67, LDA ~0.70) and folds. A reported in-sample ~0.95+
fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.65     # honest, cross-validated decoding accuracy (oracle 0.619; linear decoders 0.62-0.70)
TOL = 0.13          # [0.52, 0.78]: passes any reasonable cross-validated linear decoder,
                    # fails the in-sample / resubstitution value (~0.95+)

# keys the submission itself labels as the optimistic in-sample / training contrast, the spread,
# or chance -- never the reported held-out headline
EXCLUDE = (r"in_?sample|train|resub|resubstit|chance|baseline|_sd\b|\bsd_|std|stdev|stderr|sem\b|"
           r"across_?split|variance|spread|naive|optimist|contrast|overfit|fit_?on_?all|memoris|"
           r"memoriz|null|shuffle|permut|floor")


def _results():
    return json.loads((OUT / "results.json").read_text(encoding="utf-8"))


def _as_fraction(v):
    """Accept an accuracy given as a fraction (0..1) or a percentage (0..100)."""
    v = float(v)
    return v / 100.0 if v > 1.5 else v


def test_analysis_ran():
    res = _results()
    assert isinstance(res, dict)

    def find(keypat, obj=res):
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(keypat, k, re.I) and isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        return None

    n_neurons = find(r"n_?neurons?|n_?cells?|num.*neurons?|n_?imaged")
    assert n_neurons is not None and 100 <= n_neurons <= 800, f"n imaged neurons implausible: {n_neurons}"


def _headline_accuracy(res):
    """The reported decoding accuracy. Never take a value the submission itself labelled as the
    in-sample / training / chance / spread comparison."""
    cand = []

    def walk(obj, depth=0):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if re.search(EXCLUDE, k, re.I):
                        continue
                    if re.search(r"(decod|classif|read.?out|direction|orient|discrimin)"
                                 r".*(acc|accuracy|score|performance|correct|rate)"
                                 r"|(acc|accuracy|score|performance).*"
                                 r"(decod|classif|read.?out|direction|orient|discrimin)", k, re.I):
                        f = _as_fraction(v)
                        if 0.0 <= f <= 1.0:
                            cand.append((depth, k, f))
                elif isinstance(v, dict):
                    walk(v, depth + 1)

    walk(res)
    if cand:
        cand.sort(key=lambda t: t[0])   # prefer the shallowest (top-level headline) key
        return cand[0][2]
    # fallback: a lone plain 'accuracy'/'acc' key not excluded
    for k, v in res.items():
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and re.search(r"\bacc\b|accuracy|score", k, re.I)
                and not re.search(EXCLUDE, k, re.I)):
            f = _as_fraction(v)
            if 0.0 <= f <= 1.0:
                return f
    return None


def test_reported_accuracy_reproduces_cross_validated_value():
    res = _results()
    primary = _headline_accuracy(res)
    assert primary is not None, "results.json exposes no headline decoding accuracy"
    assert abs(primary - EXPECTED) <= TOL, (
        f"reported decoding accuracy {primary:.3f} does not reproduce the honest, cross-validated "
        f"value {EXPECTED:.2f} +/- {TOL:.2f}. A ~0.95+ accuracy comes from scoring the decoder on "
        f"the same trials it was fit on: with 215 neurons as features and only ~600 trials the "
        f"linear decoder nearly memorises the training set, so the in-sample figure reflects "
        f"overfitting capacity, not read-out. Evaluating on held-out trials (cross-validation) "
        f"gives ~{EXPECTED:.2f}.")


def test_findings_report_is_not_the_in_sample_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"decod|classif|read.?out|direction", text), \
        "findings.md does not describe direction decoding"
    res = _results()
    primary = _headline_accuracy(res)
    assert primary is not None and abs(primary - EXPECTED) <= TOL, \
        "headline accuracy in results.json is not the honest cross-validated value"
