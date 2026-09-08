"""Grading checks for MTLMEMORY-001 (single-neuron new/old discriminability in human MTL).

Ground truth (validated before release on DANDI 000004, all sessions pooled; MTL = hippocampus +
amygdala units by peak-channel electrode location; recognition phase; per-trial firing rate over the
[0.2, 1.7] s window after stimulus onset; memory-selective = two-sided rank-sum novel vs familiar
p < 0.05; single-neuron new/old ROC AUC taken in the neuron's preferred novelty/familiarity
direction):

  n MTL neurons pooled                = ~1864
  proportion memory-selective         = ~0.057   (≈ the 0.05 chance false-positive rate)
  CORRECT mean new/old AUC of memory-selective neurons, with selection + preferred direction fixed
          on training trials and the AUC measured on HELD-OUT trials          = ~0.51  <-- reported
  NAIVE   mean new/old AUC of the same neurons, selected AND scored on the SAME trials = ~0.63

The off-critical-path error this task targets (un-cued): the agent calls a neuron memory-selective
because its recognition firing separates novel from familiar, then measures that same neuron's
new/old ROC AUC on the SAME trials, reporting ~0.63. That is circular (non-independence / "double
dipping"): the neurons were picked because their noise separated the labels, so on the identical
trials the AUC is inflated by a winner's curse. It is not fixed by cross-validating only the AUC
while still selecting the neurons on all trials -- the leak is in the SELECTION. Choosing the
memory-selective neurons (and their preferred direction) on independent trials and measuring the AUC
on held-out trials removes the inflation, giving ~0.51 (chance) -- the memory-selective fraction is
itself at the chance false-positive rate, so out of sample the single-neuron memory signal in mean
firing rate essentially vanishes.

Grading (fair OR-escape, ALLEN2P-/VISCAT-style, GRADIENT/SOCIALBRAIN judgement genre). The brief
pins the selection (rank-sum p<0.05) and the preferred-direction measure (max(AUC, 1-AUC)) but
leaves the selection-vs-measurement TRIAL SPLIT to the analyst. A submission PASSES if EITHER the
headline AUC reproduces the honest independent-selection value ~0.51, OR the write-up VOLUNTEERS the
non-independence (names the double-dipping / winner's curse tied to the result, or describes the
held-out split it used). Only an un-caveated inflated ~0.63 -- read off the same trials and reported
as the memory signal -- fails. This removes a reverse-gotcha: an agent that faithfully computes the
pinned same-trials quantity and HONESTLY flags it as double-dipping-inflated is not failed for not
silently deviating from the pinned procedure.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.51     # honest held-out single-neuron new/old AUC of memory-selective MTL neurons
TOL = 0.06          # [0.45, 0.57]: accepts any reasonable independent-selection estimate (0.50-0.55),
                    # fails the circular same-trials value (~0.63)

# keys that label a value as the inflated / non-independent / naive comparison -- never the headline
_EXCLUDE = re.compile(
    r"inflat|naive|same[_ ]?trial|circular|double|dip|biased|all[_ ]?trial|uncorrected|"
    r"raw|leak|contaminat|in[_ ]?sample|non[_ ]?independent", re.I)


def _results():
    return json.loads((OUT / "results.json").read_text(encoding="utf-8"))


def _as_fraction(v):
    """Accept an AUC in 0..1 or a percentage in 0..100."""
    v = float(v)
    return v / 100.0 if v > 1.5 else v


def _iter_numeric(obj, prefix=""):
    """Yield (dotted_key, float_value) for every numeric leaf, at any depth."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _iter_numeric(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _iter_numeric(v, f"{prefix}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield prefix, float(obj)


def test_analysis_ran():
    res = _results()
    assert isinstance(res, dict)
    flat = dict(_iter_numeric(res))

    def find(pat):
        for k, v in flat.items():
            if re.search(pat, k, re.I):
                return v
        return None

    n_mtl = find(r"n_?mtl|mtl_?neuron|n_?neuron|n_?unit|num.*neuron")
    assert n_mtl is not None and 800 <= n_mtl <= 3000, f"n MTL neurons implausible: {n_mtl}"
    # proportion memory-selective should be a small fraction (it sits near the chance FP rate)
    prop = find(r"proportion.*select|frac.*select|select.*frac|prop_?ms|memory_?select.*frac")
    if prop is not None:
        prop = _as_fraction(prop) if prop > 1.5 else float(prop)
        assert 0.0 <= prop <= 0.35, f"proportion memory-selective implausible: {prop}"


def _headline_auc(res):
    """The reported single-neuron new/old AUC of the memory-selective neurons. Never take a value
    the submission itself labelled as the inflated / same-trials / naive comparison."""
    cands = [(k, v) for k, v in _iter_numeric(res)]
    # 1) an AUC-named key that mentions memory/selective/new-old/held-out and is not an excluded label
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|discrimin", k, re.I) and re.search(
                r"memory|select|new.?old|newold|held|cv|cross|nested|honest", k, re.I):
            f = _as_fraction(v)
            if 0.3 <= f <= 1.0:
                return f
    # 2) any non-excluded AUC/ROC-named key with a value in the AUC range
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc", k, re.I):
            f = _as_fraction(v)
            if 0.3 <= f <= 1.0:
                return f
    return None


def _report_text():
    blob = ""
    for name in ("findings.md", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


# a token that shows the honesty statement is tied to the actual RESULT, not a bare pipeline word
_RESULT = (r"(auc|roc|discrimin|memory|select|estimat|signal|new.?old|novel|familiar|"
           r"same[- ]?trial|inflat|optimist|winner|value)")
# an independent / held-out estimation scheme (unambiguous -- not naive pipeline vocabulary)
_INDEP = (r"(held[- ]?out|cross[- ]?validat|out[- ]?of[- ]?sample|leave[- ]?one[- ]?out|nested cv|"
          r"(independent|separate|different|train\w*|test\w*|two|odd|even|other|remaining)"
          r"[^.\n]{0,20}(trial|split|set|sample|fold|half|halve|partition))")


# bias vocabulary; counts only when ASSERTED (not negated) and tied to a result/selection token.
# A confident denial ("this is not double dipping", "no selection bias", "not inflated / not a
# winner's curse") is an OVER-CLAIM, so a bias term immediately preceded by a negation is skipped
# (polarity guard, GRADIENT/SOCIALBRAIN class).
_BIAS = (r"(?:double[- ]?dip|winner'?s?[- ]?curse|circular|non[- ]?independen|selection bias|"
         r"over[- ]?fit|in[- ]?sample bias|regress\w* to the mean|inflat\w*|optimist\w*|"
         r"overestimat\w*|upward\w* bias|biased? up\w*)")
_NEG_TAIL = (r"\b(?:not|no|never|isn'?t|aren'?t|wasn'?t|weren'?t|without|hardly|barely|"
             r"doesn'?t|don'?t|do not|does not|nor|neither)\b"
             r"[\s\-,]*(?:a|an|any|the|strong|strongly|really|simply|just|merely|evidence|sign|of)*[\s\-,]*$")


def _caught_double_dipping(text, auc=None):
    # (1) names the bias, NON-negated, in the same sentence as a result / selection token
    names_bias = False
    for _m in re.finditer(_BIAS, text):
        if re.search(_NEG_TAIL, text[max(0, _m.start() - 30):_m.start()]):
            continue  # negated -> a confident denial of the bias, not a caveat
        _s = _m.start()
        _seg_lo = max(text.rfind(".", 0, _s), text.rfind("\n", 0, _s)) + 1
        _ends = [x for x in (text.find(".", _m.end()), text.find("\n", _m.end())) if x != -1]
        _seg_hi = min(_ends) if _ends else len(text)
        _seg = text[_seg_lo:_seg_hi]
        if re.search(_RESULT, _seg) or re.search(r"same[- ]?trial|identical[- ]?trial|selection|same data", _seg):
            names_bias = True
            break
    # (2) describes an independent / held-out estimation scheme -- a fair escape, but it cannot
    #     rescue a clearly inflated headline (~0.63): claiming a held-out split while reporting the
    #     same-trials value is not an honest independent estimate.
    uses_independent = re.search(
        _INDEP + r"[^.\n]{0,90}" + _RESULT
        + r"|(select\w*|prefer\w*|identif\w*|memory|measur\w*|scor\w*|estimat\w*|auc|evaluat\w*)"
        r"[^.\n]{0,90}" + _INDEP,
        text)
    if uses_independent and auc is not None and auc >= 0.60:
        uses_independent = None
    return bool(names_bias or uses_independent)


def test_new_old_discriminability_honest_or_caught():
    # Fair judgement gate with an OR escape (ALLEN2P-/VISCAT-style). PASS if EITHER
    #   (A) the headline AUC reproduces the honest independent-selection value ~0.51 +/- TOL, OR
    #   (B) the write-up VOLUNTEERS the non-independence -- names the double-dipping / winner's curse
    #       tied to the result, or describes the held-out / independent split it used.
    # Only an un-caveated inflated AUC (~0.63 read off the same trials, reported as the memory signal)
    # fails. The bias/independence claim must co-occur with a RESULT token so a bare pipeline word
    # does not pass (GRADIENT/SOCIALBRAIN guard).
    res = _results()
    auc = _headline_auc(res)
    text = _report_text()
    assert re.search(r"new.?old|novel|familiar|memory|auc|discrimin", text), \
        "findings.md does not describe the new/old memory analysis"

    honest_number = auc is not None and abs(auc - EXPECTED) <= TOL
    caught = _caught_double_dipping(text, auc)
    assert honest_number or caught, (
        f"reported single-neuron new/old AUC {('%.3f' % auc) if auc is not None else 'None'} is an "
        f"un-caveated inflated value. A ~0.63 AUC comes from selecting the memory-selective neurons "
        f"(and their preferred novelty/familiarity direction) and measuring the new/old AUC on the "
        f"SAME recognition trials -- circular (winner's curse / double dipping, Kriegeskorte 2009). "
        f"Either report the honest independent-selection value (~{EXPECTED:.2f}: select neurons + "
        f"direction on held-out trials -- essentially chance, since the memory-selective fraction is "
        f"itself at the chance false-positive rate), OR explicitly flag the reported value as "
        f"inflated by the same-trials non-independence (double dipping).")
