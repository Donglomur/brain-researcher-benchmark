"""Grading checks for WEIGHTMAPS-001 (classifier weights are NOT the affected connections; Haufe 2014).

Ground truth (validated; receipt in the private calibration.md — ABIDE cc200, 1035 subjects, 19900
edges): a nested-CV L2 logistic-regression connectome classifier separates ASD from controls above
chance (mean AUC ~0.75), but its weight vector does NOT indicate which edges are affected.
Spearman(|weight|, |univariate group effect|) ~ 0.17 (essentially unrelated); ~14 of the top-50
weighted edges have NO group difference (p>0.05); the 50 truly-most-affected edges sit at a median
weight-rank ~17884/19900 (near the bottom; only ~3 are in the top-50 by weight). The Haufe FORWARD /
activation pattern A = Cov(X)*w recovers the affected edges: Spearman(|A|, |effect|) ~ 0.96 (~41 of the
50 truly-affected edges in its top-50).

The failure this task targets (un-cued, interpretability-illusion / forward-vs-backward axis): the
agent trains a working classifier and reports its top-magnitude WEIGHTS (or GNN saliency) as the
autism-affected connections, never noticing that discriminative (backward-model) weights are not
interpretable as feature importance — a large weight can fall on a noise-cancelling suppressor edge
with no group difference. The honest answer VOLUNTEERS that classifier weights must NOT be read as the
affected connections: one must use the forward/activation pattern (Cov(X)*w, Haufe 2014) or univariate
group statistics.

These checks validate the actual DATA (real cc200 ROI-pair edges, a plausible classifier AUC, subject
count, and — where the recovery numbers are reported — that the FORWARD pattern genuinely recovers the
affected edges while the raw WEIGHTS do not, i.e. the hidden check points the right way), not just the
presence of a number or matching prose. EMPTY, NAIVE (real numbers, no recognition) and FABRICATED
(fake edges / implausible values / hidden-check reversed) submissions all fail; the oracle passes.
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
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


def _walk_num(o, keypat, out, key=""):
    if isinstance(o, dict):
        for k, v in o.items():
            _walk_num(v, keypat, out, str(k))
    elif isinstance(o, list):
        for v in o:
            _walk_num(v, keypat, out, key)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        if re.search(keypat, key, re.I):
            out.append(float(o))


def _top_connections(blobs):
    """Find a reported list of top connections (each an ROI-pair with an associated number)."""
    found = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            if re.search(r"top|connection|edge|pair|affect|differ", key, re.I) and o and isinstance(o[0], dict):
                found.append(o)
            for v in o:
                walk(v, key)

    for obj in blobs.values():
        walk(obj)
    return found[0] if found else []


def test_connections_computed():
    """Validate the actual data: real cc200 ROI-pair edges with an associated value, a sane subject
    count, a plausible classifier AUC (if reported), and — where the recovery numbers are present —
    that the FORWARD pattern genuinely recovers the affected edges while the raw WEIGHTS do not (the
    hidden check points the right way). Empty/fabricated (fake pairs, implausible values, reversed
    check) fails."""
    blobs = _blobs()
    assert blobs, "no *.json output found (empty submission)"

    conns = _top_connections(blobs)
    assert conns, "no top affected/connection list reported in *.json"
    # each connection is an ROI pair in the cc200 range [0,199] with an associated numeric value
    good = 0
    for c in conns:
        idxs = []
        for v in c.values():
            if isinstance(v, list):
                idxs += [x for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
        nums = [v for v in c.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        pair_ok = len(idxs) >= 2 and all(0 <= int(x) <= 199 for x in idxs[:2])
        val_ok = any(0.01 <= abs(x) <= 5 for x in nums)   # a plausible edge-level value (t / forward / weight)
        if pair_ok and val_ok:
            good += 1
    assert good >= max(3, len(conns) // 2), (
        f"top connections are not valid cc200 ROI-pairs with plausible values ({good}/{len(conns)})")

    ns = []
    _walk_num(blobs, r"n_?subj|n_?sample|\bn\b", ns)
    if ns:
        assert any(200 <= int(v) <= 1100 for v in ns), f"implausible n_subjects {ns}"

    # a reported classifier performance must be at/above chance and not impossible
    aucs = []
    _walk_num(blobs, r"\bauc\b|roc[_ ]?auc|mean_auc", aucs)
    if aucs:
        assert any(0.5 <= v <= 1.0 for v in aucs), f"implausible classifier AUC {aucs}"

    # --- the hidden check must point the right way (only enforced if the recovery numbers are given) ---
    # Spearman of the BACKWARD weights vs the true per-edge group effect (should be LOW ~0.17) ...
    w_sp = [v for v in _spearman(blobs, r"weight|coef|backward")]
    # ... vs the FORWARD / Haufe activation pattern vs the same group effect (should be HIGH ~0.96)
    f_sp = [v for v in _spearman(blobs, r"forward|activation|haufe")]
    if f_sp:
        assert max(f_sp) >= 0.5, (
            f"a forward/activation-pattern recovery is claimed ({f_sp}) but it does not recover the "
            f"affected edges (Spearman < 0.5) — the corrected readout is not real")
    if w_sp:
        assert min(w_sp) < 0.5, (
            f"the raw classifier weights are reported as correlated with the group effect ({w_sp}) — "
            f"but the whole point is that discriminative weights are uninformative (Spearman ~0.17)")
    if w_sp and f_sp:
        assert max(f_sp) > max(w_sp), (
            "the forward pattern does not beat the raw weights at recovering the affected edges — the "
            "backward-vs-forward hidden check is reversed (fabricated?)")

    # overlap-with-true-affected numbers, if reported, must also favour the forward pattern
    w_ov = []
    f_ov = []
    _walk_num(blobs, r"overlap.*(weight|coef)|(weight|coef).*overlap", w_ov)
    _walk_num(blobs, r"overlap.*(forward|activation|haufe)|(forward|activation|haufe).*overlap", f_ov)
    if w_ov and f_ov:
        assert max(f_ov) > max(w_ov), (
            "forward-pattern overlap with the truly-affected edges is not greater than the raw-weight "
            "overlap — the hidden check is reversed (fabricated?)")


def _spearman(blobs, side):
    """Collect Spearman/correlation values whose key ties a `side` (weight/forward) to the group
    effect. Weight-side keys must NOT also name the forward pattern, and vice versa."""
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            k = key.lower()
            if not re.search(r"spearman|corr|rho", k):
                return
            if side == r"weight|coef|backward":
                hit = re.search(side, k) and not re.search(r"forward|activation|haufe", k)
            else:
                hit = re.search(side, k) and not re.search(r"weight|coef|backward", k)
            if hit and -1.0001 <= o <= 1.0001:
                out.append(float(o))

    for obj in blobs.values():
        walk(obj)
    return out


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
        "|group effect|) ~ 0.17, ~14 of the top-50 weighted edges have no group difference, and the "
        "truly affected edges rank near the bottom by weight. To identify affected connections one "
        "must use the FORWARD/activation pattern (Cov(X)*w, Haufe 2014) or univariate group "
        "statistics; reporting the top classifier weights as the affected connections is misleading.")
