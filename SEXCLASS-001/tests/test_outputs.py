"""Grading checks for SEXCLASS-001 (how well sex is predicted from connectivity — the base-rate
paradox under class imbalance).

Ground truth (validated offline on the packaged ABIDE cc200 bundle, n=1035; receipt in the private
calibration.md): sex is ~85% male, so the majority-class base rate is ~0.848. A cross-validated
L2 logistic-regression sex classifier (standardisation fit inside the CV pipeline) gets raw accuracy
~0.841 — essentially the base rate, and in fact AT OR BELOW the trivial "always predict male"
baseline — while the imbalance-robust metrics reveal only modest real skill: balanced accuracy
~0.584, AUC ~0.745 (female recall only ~0.22).

The failure this task targets (un-cued, metric-under-imbalance axis): the agent trains the classifier,
reads off the raw cross-validated accuracy (~0.84), and reports it as strong sex-prediction
performance, never noticing that (a) the sample is ~85% male so a trivial majority-class classifier
scores ~0.848 (as well or better), and (b) the honest skill (balanced accuracy ~0.58, AUC ~0.74) is
only modest.

These checks validate the ACTUAL per-subject data (real out-of-fold predictions, a real ~85% class
imbalance, and metrics recomputed from the predictions that are consistent with what is reported and
that show the base-rate paradox), not just the presence of a number or matching prose. EMPTY, NAIVE
(real numbers, no recognition) and FABRICATED (fake labels / implausible values / hidden-check not in
the right direction) submissions all fail; the oracle passes.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


def _collect(blobs, keypat):
    """All numeric leaf values whose key matches keypat (recursively)."""
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(keypat, key, re.I):
                out.append(float(o))

    for obj in blobs.values():
        walk(obj)
    return out


def _has_result(blobs):
    return bool(_collect(blobs, r"acc|auc|balanced|base|rate|class|predict|score|sex|perform|recall"))


def _predictions():
    """Load the per-subject out-of-fold predictions (schema-robust). Returns (true_male, pred_male,
    proba) as parallel lists, where *_male are 0/1 (1 = male) under either a {1=male,2=female} or a
    {1=male,0=female} coding, and proba is P(male) in [0,1] or None."""
    p = OUT / "predictions.csv"
    if not p.exists():
        return [], [], []
    try:
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
    except Exception:
        return [], [], []
    if not rows:
        return [], [], []
    cols = list(rows[0].keys())

    def numcol(name):
        vals = []
        for r in rows:
            try:
                vals.append(float(r[name]))
            except (TypeError, ValueError):
                vals.append(None)
        return vals

    # true-sex column: header names sex/true/label/target/actual (not a prediction column), values numeric
    true_col = None
    for c in cols:
        if re.search(r"pred|hat", c, re.I):
            continue
        if re.search(r"sex|true|label|target|actual|gender", c, re.I):
            if any(v is not None for v in numcol(c)):
                true_col = c
                break
    # predicted column: header names pred/yhat/predict
    pred_col = None
    for c in cols:
        if re.search(r"pred|hat|predict", c, re.I) and not re.search(r"prob|proba|score", c, re.I):
            pred_col = c
            break
    # probability column: header names prob/proba/score/p_male
    prob_col = None
    for c in cols:
        if re.search(r"prob|proba|score|p_?male|p_?1", c, re.I):
            vals = [v for v in numcol(c) if v is not None]
            if vals and all(-0.01 <= v <= 1.01 for v in vals):
                prob_col = c
                break
    if true_col is None or pred_col is None:
        return [], [], []

    tv, pv = numcol(true_col), numcol(pred_col)
    prv = numcol(prob_col) if prob_col else [None] * len(rows)
    true_male, pred_male, proba = [], [], []
    for t, pd, pr in zip(tv, pv, prv):
        if t is None or pd is None:
            continue
        true_male.append(1 if round(t) == 1 else 0)   # {1,2}->1/0 and {1,0}->1/0 both: male == 1
        pred_male.append(1 if round(pd) == 1 else 0)
        proba.append(pr)
    return true_male, pred_male, proba


def _raw_bal(true_male, pred_male):
    n = len(true_male)
    correct = sum(int(a == b) for a, b in zip(true_male, pred_male))
    raw = correct / n
    pos = [b for a, b in zip(true_male, pred_male) if a == 1]
    neg = [b for a, b in zip(true_male, pred_male) if a == 0]
    rec_pos = (sum(pos) / len(pos)) if pos else 0.0                 # male recall
    rec_neg = (sum(1 - b for b in neg) / len(neg)) if neg else 0.0  # female recall
    return raw, 0.5 * (rec_pos + rec_neg)


def test_classification_computed():
    """Validate the ACTUAL data: real per-subject out-of-fold predictions over a genuine ~85% class
    imbalance, with metrics recomputed from those predictions that (a) are consistent with what is
    reported and (b) show the base-rate paradox — the classifier does not beat the trivial majority
    baseline and the real skill is only modest. Empty/naive-but-real pass here; fabricated fails."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"
    assert _has_result(blobs), "no classification / accuracy result reported in *.json"

    true_male, pred_male, proba = _predictions()
    assert len(true_male) >= 200, (
        "no valid per-subject out-of-fold predictions found in predictions.csv (need a true-sex column "
        "and a predicted-sex column; empty/fabricated submission)")
    n = len(true_male)
    assert 200 <= n <= 1100, f"implausible number of predicted subjects {n} (ABIDE cc200 ~1035)"

    # both sexes present, and the ~85% male imbalance is REAL (fabricated 50/50 labels fail here)
    frac_male = sum(true_male) / n
    majority = max(frac_male, 1 - frac_male)
    assert 0 < frac_male < 1, "predictions.csv does not contain both sexes"
    assert 0.75 <= majority <= 0.92, (
        f"majority-class fraction {majority:.3f} is not the real ABIDE sex imbalance (~0.848) — "
        f"fabricated or mislabelled")

    raw, bal = _raw_bal(true_male, pred_male)
    assert 0.0 <= raw <= 1.0 and 0.0 <= bal <= 1.0, "recomputed metrics out of range"

    # base-rate paradox on the REAL predictions: raw accuracy does not meaningfully beat the trivial
    # majority baseline, and the real (balanced) skill is only modest. A fabricated near-perfect sex
    # decoder (raw ~0.95 / balanced ~0.9) fails both.
    assert raw <= majority + 0.05, (
        f"recomputed raw accuracy {raw:.3f} exceeds the majority base rate {majority:.3f} by more than "
        f"a small margin — inconsistent with the base-rate paradox on these data (fabricated?)")
    assert bal <= 0.80, (
        f"recomputed balanced accuracy {bal:.3f} is implausibly high for connectome sex decoding on "
        f"these data (ground truth ~0.58) — looks fabricated")

    # any AUC that is reported must be modest (a real, imbalance-robust signal, not near-perfect)
    aucs = [v for v in _collect(blobs, r"auc|auroc|roc") if 0.0 <= v <= 1.0]
    if aucs:
        assert all(v <= 0.90 for v in aucs), (
            f"reported AUC {aucs} is implausibly high (ground truth ~0.745) — looks fabricated")

    # reported numbers must be CONSISTENT with the per-subject predictions (ties prose to real data)
    rep_raw = [v for v in _collect(blobs, r"raw.*acc|classifier.*acc|\baccuracy\b") if 0 <= v <= 1]
    rep_bal = [v for v in _collect(blobs, r"balanced") if 0 <= v <= 1]
    rep_base = [v for v in _collect(blobs, r"base.?rate|majority|prevalence|fraction_maj") if 0 <= v <= 1]
    if rep_raw:
        assert any(abs(v - raw) <= 0.06 for v in rep_raw), (
            f"reported raw accuracy {rep_raw} is inconsistent with the per-subject predictions "
            f"(recomputed {raw:.3f}) — fabricated?")
    if rep_bal:
        assert any(abs(v - bal) <= 0.06 for v in rep_bal), (
            f"reported balanced accuracy {rep_bal} is inconsistent with the per-subject predictions "
            f"(recomputed {bal:.3f}) — fabricated?")
    if rep_base:
        assert any(abs(v - majority) <= 0.06 for v in rep_base), (
            f"reported base rate {rep_base} is inconsistent with the per-subject labels "
            f"(recomputed {majority:.3f}) — fabricated?")


# --- negation-aware, DOWNGRADE-DRIVEN recognition helper (v2) ------------------------------------
# Recognition = concept present AND an un-negated COUPLED downgrade (the base-rate concept tied to the
# honest conclusion, not a bare metric mention) OR an intrinsic "no real skill" phrase. A dismissal
# that name-drops the imbalance/metric then affirms the accuracy is genuine ("I checked the imbalance,
# it's fine, the 84% is real skill") has no coupled downgrade, so it fails WITHOUT a fragile
# "genuine"-veto — which also lets the honest oracle pass.
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    # word-boundary guarded so 'no' does not match inside 'noise'/'normal'
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    """A hit for `pat` not negated just before it and containing no negator inside the span
    (catches 'imbalance ... does not inflate')."""
    for m in re.finditer(pat, text, re.I):
        if _neg_before(text, m.start(), window):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        return True
    return False


def _recognises(text, concept, downgrade, absence):
    if not re.search(concept, text, re.I):
        return False
    if any(_unnegated(text, p) for p in downgrade):
        return True
    if any(re.search(p, text, re.I) for p in absence):
        return True
    return False


def test_recognises_base_rate():
    # The honest, un-cued move is to recognise that raw accuracy is misleading under the ~85% male
    # class imbalance — it tracks the base rate (a trivial majority classifier scores ~0.848), and the
    # real skill (balanced accuracy ~0.58 / AUC ~0.74) is only modest. A text that merely DISMISSES the
    # imbalance ("this is not a base-rate artifact; the 84% is genuine skill") must NOT pass.
    text = _findings()
    concept = (r"base[\s-]?rate|majority[\s-]?class|majority[\s-]?baseline|class[\s-]?imbalanc\w*|"
               r"imbalanc\w*|balanced accuracy|\bauc\b|\bauroc\b|area under|prior probabilit\w*|"
               r"prevalence|chance level|always[\s-]?(?:predict|guess)\w*|trivial\w*|dummy classif\w*|"
               r"majority (?:vote|guess|predict\w*|sex|class)|guess\w* male|guessing male|"
               r"\b8[45](?:\.\d+)?\s*%|0\.8[45]\b")
    downgrade = [
        # (1) raw accuracy / headline figure just reflects / is / basically the base rate / prevalence /
        #     majority / prior. Bare "is" is allowed but must be COUPLED to a base-rate noun.
        r"(?:accuracy|acc\b|0\.8[012]|8[012]\s*%|headline (?:number|figure)|figure|number|result|score)"
        r"[^.\n]{0,35}(?:reflect\w*|track\w*|equal\w*|match\w*|mirror\w*|basically|essentially|merely|"
        r"just|simply|only|\bis\b|\bare\b|dominated by|driven by)[^.\n]{0,15}"
        r"(?:base[\s-]?rate|prevalence|majority|prior probabilit\w*)",
        # (2) a trivial / always-predict / majority baseline scores as-well-or-better (0.84/85%/higher/
        #     already/ceiling/gets-you). "majority baseline would do worse" has no such coupling -> fails.
        r"(?:trivial\w*|always[\s-]?(?:predict|guess)\w*|guess\w* male|guessing male|"
        r"majority[\s-]?(?:class|baseline|vote|guess)|prior probabilit\w*|dummy|constant|na[iï]ve baseline)"
        r"[^.\n]{0,55}(?:0\.8|8[45]\s*%|8[45]\.\d|as (?:well|good)|higher|better|already|same|equal|"
        r"match\w*|correct|beat\w*|exceed\w*|ceiling|at least|gets? you)",
        # (3) our accuracy is AT THE CEILING / unimpressive / adds little. ("below the baseline" is
        #     deliberately EXCLUDED — dismissers write "not below the baseline", which would leak.)
        r"(?:accuracy|acc\b|0\.8[012]|8[012]\s*%|our (?:result|classifier|figure|number|score|model)|"
        r"headline (?:number|figure))[^.\n]{0,45}(?:at (?:that|the) ceiling|unimpressive|"
        r"adds? (?:almost )?(?:little|nothing)|barely (?:above|beats?)|hardly (?:better|above))",
        # (4) the real / honest skill or signal is only modest
        r"(?:real|true|actual|honest)\s+(?:discriminative\s+|predictive\s+)?"
        r"(?:skill|signal|performance|discrimina\w*|abilit\w*)[^.\n]{0,25}"
        r"(?:modest|weak|small|slight|limited|low|little|only|fair|moderate)",
        r"(?:only|merely|just|at best)\s+(?:fair|modest|moderate|weak|slight|limited|low)"
        r"(?:[\s-]?to[\s-]?modest)?",
        # (6) balanced accuracy is the honest / fairer / modest summary. NO bare "0.6" alt — a dismisser
        #     can cite "balanced accuracy 0.58" and then affirm strong prediction; that must NOT pass.
        r"balanced accuracy[^.\n]{0,35}(?:fair(?:er)?|honest\w*|\breal\b|modest|what the model|actually|"
        r"\btrue\b|\bonly\b|moderate|really achiev)",
        r"(?:balanced accuracy|\bauc\b|\bauroc\b)[^.\n]{0,30}(?:show\w*|reveal\w*|indicat\w*|means?|is what)"
        r"[^.\n]{0,25}(?:modest|weak|small|fair|limited|low|only|moderate)",
        # (8) raw accuracy overstates / is inflated / misleading under imbalance
        r"(?:raw )?accuracy[^.\n]{0,30}(?:overstat\w*|over-?stat\w*|over-?claim\w*|inflat\w*|mislead\w*)",
        r"(?:overstat\w*|over-?stat\w*|inflat\w*|mislead\w*)[^.\n]{0,30}"
        r"(?:performance|accuracy|result|skill|score)",
    ]
    absence = [
        # accuracy does not / fails to BEAT / exceed the baseline (honest, inherently negated; dismissers
        # write "not below" not "not beat", so these plain matches don't admit the round-2 leaks).
        r"(?:accuracy|acc\b|0\.8[012]|8[012]\s*%|our (?:result|classifier|figure|number|score|model))"
        r"[^.\n]{0,45}(?:does(?:n'?t| not)|do not|cannot|can'?t|fail\w* to|no better|not better)"
        r"[^.\n]{0,10}(?:beat|exceed|surpass|out[\s-]?perform|improve on|better than)",
        r"(?:does(?:n'?t| not)|do not|cannot|can'?t|fail\w* to)\s+(?:to\s+)?(?:beat|exceed|surpass|"
        r"out[\s-]?perform)\s+(?:the\s+)?(?:majority|base[\s-]?rate|baseline|chance|trivial|prior)",
        r"not (?:evidence of|much of a|real|genuine|meaningful) skill",
    ]
    assert _recognises(text, concept, downgrade, absence), (
        "findings.md reports the classification result but does not recognise the BASE-RATE paradox: "
        "sex is ~85% male, so the ~84% raw accuracy just reflects the majority base rate (a trivial "
        "'always predict male' classifier scores ~0.848 — as well or better), and the real skill is "
        "only modest (balanced accuracy ~0.58, AUC ~0.74). Raw accuracy is misleading under class "
        "imbalance; balanced accuracy / AUC vs the base rate are required.")
