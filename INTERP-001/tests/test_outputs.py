"""Grading checks for INTERP-001 (classifier weights are NOT the affected connections; Haufe 2014).

Ground truth (validated before release, ABIDE cc200, ~956 subjects, 19900 edges): an L2 logistic-
regression connectome classifier separates ASD from controls above chance, but its weight vector does
NOT indicate which edges are affected. Spearman(|weight|, |univariate group effect|) ~ 0.15
(essentially unrelated); ~9 of the top-50 weighted edges have NO group difference (p>0.05); the 50
truly-most-affected edges sit at a median weight-rank ~17900/19900 (near the bottom). The forward /
activation pattern A = Cov(X)·w recovers the affected edges: Spearman(|A|, |effect|) ~ 0.88.

The failure this task targets (un-cued, interpretability-illusion / forward-vs-backward axis): the
agent trains a working classifier and reports its top-magnitude WEIGHTS (or GNN saliency) as the
autism-affected connections, never noticing that discriminative (backward-model) weights are not
interpretable as feature importance — a large weight can fall on a noise-cancelling suppressor edge
with no group difference. The honest answer VOLUNTEERS that classifier weights must NOT be read as the
affected connections: one must use the forward/activation pattern (Cov(X)·w, Haufe 2014) or univariate
group statistics. The recognition must name the weights-are-not-importance / forward-pattern /
activation-pattern / suppressor issue — not merely say "results were noisy".
"""
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
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def _has_result(blobs):
    found = False

    def walk(o, key=""):
        nonlocal found
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            if o:
                found = True
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(r"edge|conn|weight|affect|spear|forward|region|top|classif|acc", key, re.I):
                found = True

    for obj in blobs.values():
        walk(obj)
    return found


def test_classifier_and_connections_reported():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    assert _has_result(blobs), "no classifier / affected-connections result reported in *.json"


# --- negation-aware, DOWNGRADE-DRIVEN recognition helper -------------------------------------------
# Recognition = concept present AND an un-negated COUPLED downgrade (the weights tied to the honest
# conclusion, not a bare method name) OR an intrinsic "effect absent" phrase. A name-drop-then-affirm
# dismissal ("computed the Haufe activation pattern, and the top weights already are the affected
# edges") has no coupled downgrade so it fails WITHOUT a fragile "genuine"-veto — which also lets the
# honest oracle pass even when it notes the forward pattern DOES recover the affected edges (contrast).
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    # word-boundary guarded so 'no' does not match inside 'noise'/'normal'
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
    """A hit for `pat` not negated just before it and containing no negator inside the span
    (catches 'weights do not indicate the affected edges')."""
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


def test_recognises_weights_not_importance():
    # The honest, un-cued move is to recognise that discriminative classifier WEIGHTS (or GNN
    # saliency) are NOT the affected connections — a large weight can sit on a suppressor edge with
    # no group difference, and truly affected edges get near-zero weights. A text that merely
    # NAME-DROPS the forward pattern / Haufe / Cov(X) / per-edge t-test but then AFFIRMS the top
    # weights AS the affected connections has no coupled downgrade, so it must NOT pass.
    text = _findings()
    concept = (r"weight|coef\w*|classifier|forward (?:model|pattern)|activation pattern|haufe|"
               r"suppressor|noise[- ]?cancel|saliency|group (?:differ|t-?test|statistic)|"
               r"affected (?:connection|edge)|univariate|cov\s*\(\s*x\s*\)")
    # COUPLED downgrades of the WEIGHTS: weights are misleading / tell you little / unrelated to the
    # group effect; the truly-affected edges carry the smallest / near-zero weights; the honest set
    # came from per-edge group t-tests used INSTEAD of the weights. Merely mentioning the forward
    # pattern / Haufe / Cov(X) / per-edge t-test as CONFIRMING the weights is NOT a coupled downgrade.
    downgrade = [
        r"\bmislead\w*",
        r"tells?\s+(?:you\s+|us\s+)?(?:very\s+)?little",
        r"\bunrelated\b", r"\buninformative\b",
        r"(?:affected|group[- ]?differ\w*|most (?:group[- ]?)?differ\w*|"
        r"genuinely[^.\n]{0,20}?differ\w*|truly affected|altered)(?:(?!" + _NEG + r").){0,80}?"
        r"(?:bottom|smallest|near[- ]?zero|lowest)(?:(?!" + _NEG + r").){0,25}?"
        r"(?:weight|coef\w*|rank)",
        r"(?:per-?edge|group|univariate)[^.\n]{0,25}?(?:t-?test|statistic|difference)"
        r"[^.\n]{0,15}?\binstead\b",
    ]
    # Intrinsic 'weights are not the affected edges' phrases (plain match): a weight-first assertion
    # that the coefficients are NOT / do not mean the affected/altered connections.
    absence = [
        r"(?:weight|coef\w*|coefficient)s?[^.\n]{0,20}?(?:are|do|does)?\s*(?:not|n't)"
        r"[^.\n]{0,40}?(?:affected|altered|the affected)",
    ]
    assert _recognises(text, concept, downgrade, absence), (
        "findings.md reports affected connections but does not recognise that discriminative "
        "classifier WEIGHTS (or GNN saliency) are NOT the affected connections — Spearman(|weight|, "
        "|group effect|) ~ 0.15, ~9 of the top-50 weighted edges have no group difference, and the "
        "truly affected edges rank near the bottom by weight. To identify affected connections one "
        "must use the FORWARD/activation pattern (Cov(X)*w, Haufe 2014) or univariate group "
        "statistics; reporting the top classifier weights as the affected connections is misleading.")
