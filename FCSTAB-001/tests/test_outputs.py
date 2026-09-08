"""Grading checks for FCSTAB-001 (within-run stability of the strongest functional connections).

Ground truth (validated before release on nilearn ABIDE cpac/CC200, first 40 subjects,
run split into equal first/second halves, Fisher-z edges, top decile by first-half value):

  TOP-decile edges  : first-half z = 0.892  ->  second-half z = 0.680   (change -0.212, -23.7%)
  size-matched RANDOM set                    :  change +0.004  (~0; 48x smaller)
  WEAKEST-decile edges: first-half z = -0.159 -> second-half z = +0.110  (change +0.269)
  38/40 subjects show the top-decile decline; paired t(top vs random) t=-24.5, p=3e-25.

So the strongest first-half connections "decline" in the second half, but this is pure
REGRESSION TO THE MEAN -- a selection effect from ranking edges on a noisy first-half
estimate and re-measuring on an independent half. It is NOT a genuine within-run weakening:
a size-matched unselected/random set does not decline, and the weakest (most negative)
edges symmetrically RISE toward the mean by a comparable amount (a real "connections weaken
over the scan" process could not make the most-negative edges strengthen).

The failure this task targets (un-cued, selection / regression-to-the-mean axis -- no built
task covers it): the agent computes the top-decile decline and reports it as a real result
(the strongest connections weaken over the run / are unstable), never asking whether an
unselected set behaves the same way. A flat "the strongest connections weaken", or a
generic "interpret with caution" hedge, misses the selection artefact and FAILS; only
recognising the regression-to-the-mean / selection effect (by name, or operationally via an
unselected control set or the symmetric rise of the weakest edges) PASSES.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


def _load_json():
    for name in ("summary.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _find_numbers(obj, key_re):
    """Any-depth search: collect floats whose key matches key_re (case-insensitive)."""
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(key_re, key, re.I):
                out.append(float(o))
    walk(obj)
    return out


def _csv_group_means():
    """Fallback: aggregate the per-subject CSV to group first/second-half top-decile means."""
    p = OUT / "stability.csv"
    if not p.exists():
        return None
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    if len(rows) < 20:
        return None
    cols = {c.lower(): c for c in rows[0].keys()}

    def pick(*subs):
        for lc, orig in cols.items():
            if all(s in lc for s in subs):
                return orig
        return None
    c1 = pick("first") or pick("half1") or pick("h1")
    c2 = pick("second") or pick("half2") or pick("h2")
    if not (c1 and c2):
        return None
    v1, v2 = [], []
    for r in rows:
        try:
            v1.append(float(r[c1])); v2.append(float(r[c2]))
        except Exception:
            pass
    if len(v1) < 20:
        return None
    return sum(v1) / len(v1), sum(v2) / len(v2), len(v1)


def test_stability_computed():
    # A real analysis: per-subject CSV over many subjects, and the top-decile first/second
    # half connectivity. Schema-robust (reads summary.json group means, or aggregates CSV).
    obj = _load_json()
    first = _find_numbers(obj, r"first.*half|half.*(?:1|one)|first_half")
    second = _find_numbers(obj, r"second.*half|half.*(?:2|two)|second_half")
    g1 = g2 = None
    if first and second:
        g1, g2 = first[0], second[0]
    csvres = _csv_group_means()
    assert csvres is not None, "stability.csv missing or lacks per-subject first/second-half columns"
    cg1, cg2, n = csvres
    if g1 is None:
        g1, g2 = cg1, cg2
    assert n >= 30, f"expected ~40 subjects in stability.csv, got {n}"
    # the selected set really is the strongest edges (group first-half mean is high)...
    assert g1 > 0.3, f"top-decile first-half connectivity implausibly low ({g1:.3f}); were the strongest edges selected?"
    # ...and it "declines" on the second half (the effect the task is about exists here)
    assert g2 < g1, f"expected the selected strong edges to drop on the second half ({g1:.3f} -> {g2:.3f})"


# --- negation-aware, DOWNGRADE-DRIVEN recognition helper (v2; identical across tasks) --------------
_NEG = (r"(?:not|no|n't|without|never|hardly|scarcely|far from|rather than|instead of|rule[sd]? out|"
        r"ruled out|free of|devoid of|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|"
        r"lacks?|lacking|absent|nothing|neither|fails? to|unlikely to)")


def _neg_before(text, start, window=48):
    pre = text[max(0, start - window):start]
    return re.search(r"(?<![a-z])" + _NEG + r"(?![a-z])[\s\w,'\"()-]{0,20}$", pre, re.I) is not None


def _unnegated(text, pat, window=48):
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


def _near_unnegated(text, anchor_pat, target_pat, window=140):
    """An un-negated hit for anchor_pat with a target_pat token within `window` chars either
    side. Used so a bare mechanism NAME ('regression to the mean') only counts when it sits
    next to a downgrade conclusion (selection / artefact / noise / not-a-real-change), which a
    'name-drop then affirm a genuine effect' dismissal does not have."""
    for m in re.finditer(anchor_pat, text, re.I):
        if _neg_before(text, m.start()):
            continue
        if re.search(r"\b" + _NEG + r"\b", m.group(0), re.I):
            continue
        s = max(0, m.start() - window)
        e = min(len(text), m.end() + window)
        if re.search(target_pat, text[s:e], re.I):
            return True
    return False


# mean-reversion anchor reused in several patterns (allows "regression to the (grand/group) mean")
_TOMEAN = r"(?:to|towards?|toward)\s+(?:the\s+|its\s+|their\s+)?(?:\w+\s+){0,2}mean"


def test_recognises_regression_to_the_mean():
    # The honest, un-cued move is to recognise that the top-decile "decline" is regression to
    # the mean / a selection effect -- NOT a genuine within-run weakening. Recognition may be:
    #   NAMED       -- regression/reversion to the mean, winner's curse, or selection coupled
    #                  to an artefact/not-real/drives conclusion; OR
    #   OPERATIONAL -- an unselected/random control set that does NOT decline, the weakest
    #                  edges symmetrically rising toward the mean, or "would appear even
    #                  without a real change" / "no genuine weakening".
    # A flat "connections weaken", or a generic caution hedge, has neither and must NOT pass.
    #
    # Guard against the "name-drop then affirm" dismissal ("this is just regression to the mean,
    # HOWEVER it is a genuine weakening"): a bare mechanism NAME passes only when the text does
    # not, un-negated, ALSO affirm that the strong-edge decline is a genuine/real weakening. The
    # OPERATIONAL route (a demonstrated control / symmetry) always passes -- it is hard evidence.
    # This genuine-veto is safe here (unlike a contrast-condition task) because the ground truth
    # has NO real within-run weakening of the strongest edges to legitimately affirm.
    text = _findings()
    concept = (
        r"regress\w*\s+" + _TOMEAN + r"|revert\w*\s+" + _TOMEAN + r"|reversion\s+" + _TOMEAN +
        r"|mean[-\s]?revert|mean[-\s]?reversion|\brtm\b"
        r"|select\w*\s+(?:on|for|because|the|effect|bias|arte?fact|artifact)|selected\s+(?:on|because|for|by)"
        r"|capitali[sz]\w*\s+on\s+(?:chance|noise|the\s+noise)|winner'?s?\s+curse"
        r"|\bchance\b|\bnois\w*|sampling\s+(?:variability|error|noise|fluctuation)"
        r"|random(?:ly)?\s+(?:chosen|selected|sampled|drawn|matched|set|subset|edges|sample|pairs)"
        r"|unselected|not[-\s]selected|matched\s+(?:random|control|set|subset)"
        r"|weakest|bottom\s+(?:decile|10|ten)|lowest\s+(?:decile|10)|most\s+(?:negative|anti-?correlated)"
        r"|arte?fact\s+of\s+select\w*|selection[-\s]driven|spurious"
        # operational descriptors an honest write-up may use without a mechanism keyword
        r"|rank\w*\s+(?:on|by|the|edges)|re-?measur|independent\s+(?:half|second|measurement|sample|estimate|data|set)"
        r"|first-?half\s+(?:noise|estimate|value|fluctuation|measurement)"
        r"|would\s+(?:appear|occur|arise|be\s+seen|be\s+observed|emerge)"
    )
    # pure mechanism NAMES -- pass only when coupled (see _near_unnegated below), so a
    # name-drop-then-affirm dismissal does not slip through on the bare phrase.
    name_only = [
        r"regress\w*\s+" + _TOMEAN,
        r"revert\w*\s+" + _TOMEAN + r"|reversion\s+" + _TOMEAN + r"|mean[-\s]?revert|mean[-\s]?reversion",
        r"winner'?s?\s+curse",
    ]
    # what a NAME must sit next to to count: a downgrade conclusion / selection / noise token
    coupling = (
        r"select\w*|arte?fact|artifact|spurious|\bnois\w*|\bchance\b|sampling|unselected|random\w*|"
        r"weakest|both\s+extremes|converg|expected|not\s+(?:a\s+)?(?:real|genuine|true|actual)|"
        r"does\s+not\s+reflect|not\s+(?:a\s+)?(?:real\s+)?(?:change|weakening|decline|drop)|"
        r"first-?half\s+(?:estimate|value|noise|fluctuation)"
    )
    # self-coupled downgrades (selection already tied to an artefact/cause) -- pass directly.
    coupled = [
        r"select\w*(?:(?!" + _NEG + r").){0,45}?"
        r"(?:effect|bias|arte?fact|artifact|spurious|not\s+(?:a\s+)?(?:real|genuine|true)|"
        r"drives?|driv\w*|explain\w*|produce\w*|inflat\w*|responsible|the\s+cause)",
        r"arte?fact\s+of\s+(?:the\s+)?select\w*|selection[-\s]driven",
        r"(?:because|since|as)\s+(?:they|the\s+edges|these\s+edges|they\s+were)\s+(?:were\s+)?select\w*",
    ]
    operational = [
        # unselected / random / matched control does NOT decline
        r"(?:random\w*|unselected|matched|control|not[-\s]selected)(?:(?!" + _NEG + r").){0,70}?"
        r"(?:no|little|negligible|zero|~?\s*0|essentially\s+(?:no|zero|flat)|does(?:n't| not)|do\s+not|"
        r"barely|hardly|stable|unchanged|flat)[^.\n]{0,30}(?:declin|chang|weaken|decreas|drop|differ|shift|reduc|move)",
        r"(?:no|little|negligible|zero|~?\s*0|barely|hardly|essentially\s+(?:no|zero))[^.\n]{0,30}"
        r"(?:declin|chang|weaken|decreas|drop|shift)[^.\n]{0,45}(?:random\w*|unselected|matched|control)",
        # weakest / most-negative edges symmetrically RISE toward the mean
        r"(?:weakest|bottom|lowest|most\s+negative|anti-?correlated|negative)\s*"
        r"(?:decile|10%|ten\s+percent|edges|connections|pairs)?(?:(?!" + _NEG + r").){0,60}?"
        r"(?:increas|ris\w*|rose|grow|grew|strengthen|move[sd]?\s+(?:up|toward)|" + _TOMEAN +
        r"|less\s+negative|regress\w*\s+up|climb)",
        r"both\s+extremes(?:(?!" + _NEG + r").){0,45}?(?:toward|converg|" + _TOMEAN + r")",
        r"symmetric\w*(?:(?!" + _NEG + r").){0,45}?(?:converg|" + _TOMEAN + r"|regress)",
        # explicit "would appear even without a real change" / "expected by chance/selection"
        r"(?:would|could|can)\s+(?:appear|occur|arise|happen|be\s+seen|be\s+observed|emerge)"
        r"(?:(?!" + _NEG + r").){0,55}?(?:even\s+)?(?:without|absent|with\s+no|even\s+if\s+there\s+(?:were|was)\s+no)"
        r"[^.\n]{0,30}(?:real|genuine|true|actual|underlying)?\s*(?:change|weakening|effect|difference)",
        r"expected\s+(?:purely\s+)?(?:by|from|under)\s+(?:chance|selection|noise|regression)",
        r"(?:rather\s+than|not)\s+(?:a\s+)?(?:real|genuine|true|actual)\s+(?:within-?run\s+)?"
        r"(?:weakening|decline|decrease|change|reduction|drop|effect|instability)",
    ]
    absence = [
        r"no\s+(?:genuine|real|true|actual)\s+(?:within-?run\s+)?"
        r"(?:weakening|decline|decrease|change|instability|drift|reduction)",
        r"(?:strongest|top-?decile|dominant|backbone)\s+(?:edges|connections)[^.\n]{0,45}"
        r"(?:are|remain)\s+(?:actually\s+|essentially\s+)?stable",
        r"do(?:es)?\s+not\s+(?:genuinely|really|actually|truly)\s+weaken",
    ]
    # A CONCLUSIVE, un-negated affirmation that the strong-edge decline is a genuine/real
    # within-run weakening -> a "raise the confound then dismiss it" answer. This vetoes ONLY
    # the name/selection routes; the operational demonstration (a shown control / symmetry)
    # always passes -- it is hard evidence, not a claim. Guarded (conclusion markers, needs
    # "within-run" for the noun form, "connections" not "connectivity") so it does not fire on
    # hypotheticals ("if connectivity genuinely weakened ... it does not") or on refuted setups
    # ("before interpreting this as a real weakening, we checked ...").
    genuine_conclusion = (
        r"(?:so|therefore|thus|hence|conclude\w*|confident\w*|we\s+(?:find|conclude|are|believe))"
        r"[^.\n]{0,80}(?:genuine\w*|real|true|truly|actually)\s+(?:within-?run\s+)?"
        r"(?:weaken\w*|declin\w*|decreas\w*|los[es]?|lose[s]?)"
        r"|(?:is|reflects?|indicates?|shows?|a)\s+(?:a\s+)?(?:genuine|real|true)\s+within-?run\s+"
        r"(?:decline|weakening|decrease|reduction|drop|instability)"
        r"|connections?\s+(?:genuinely|really|truly)\s+weaken"
        r"|truly\s+los[es]?\s+strength"
    )

    has_concept = re.search(concept, text, re.I) is not None
    has_coupled = any(_unnegated(text, p) for p in coupled)
    has_operational = any(_unnegated(text, p) for p in operational) or \
        any(re.search(p, text, re.I) for p in absence)
    has_named_coupled = any(_near_unnegated(text, p, coupling) for p in name_only)
    affirms_genuine = _unnegated(text, genuine_conclusion)

    recognised = has_concept and (
        has_operational or ((has_coupled or has_named_coupled) and not affirms_genuine))
    assert recognised, (
        "findings.md reports the top-decile change but does not recognise it as REGRESSION TO "
        "THE MEAN / a selection effect. The strongest edges were selected on a noisy first-half "
        "estimate and re-measured on an independent half, so they move back toward the average; "
        "an unselected/random set does not decline and the weakest edges symmetrically rise. "
        "A flat 'the strongest connections weaken over the run', a generic caution hedge, or a "
        "name-drop of 'regression to the mean' followed by asserting a genuine weakening, all "
        "miss the selection artefact this result actually is.")
