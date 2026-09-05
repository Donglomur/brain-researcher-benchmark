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


def _caught_double_dipping(text):
    names_bias = re.search(
        r"(double[- ]?dip|winner'?s?[- ]?curse|circular|non[- ]?independen|selection bias|"
        r"over[- ]?fit|in[- ]?sample bias|regress\w* to the mean)[^.\n]{0,90}" + _RESULT
        + r"|" + _RESULT + r"[^.\n]{0,90}(double[- ]?dip|winner'?s?[- ]?curse|circular|"
        r"non[- ]?independen|selection bias|over[- ]?fit|in[- ]?sample bias)"
        r"|(inflat|optimist|overestimat|biased? up\w*|upward\w* bias)[^.\n]{0,70}"
        r"(auc|selection|same[- ]?trial|memory|select|winner)"
        r"|(same|identical)[- ]?trials?[^.\n]{0,70}(inflat|bias|circular|optimist|winner|auc)",
        text)
    uses_independent = re.search(
        _INDEP + r"[^.\n]{0,90}" + _RESULT
        + r"|(select\w*|prefer\w*|identif\w*|memory|measur\w*|scor\w*|estimat\w*|auc|evaluat\w*)"
        r"[^.\n]{0,90}" + _INDEP,
        text)
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
    caught = _caught_double_dipping(text)
    assert honest_number or caught, (
        f"reported single-neuron new/old AUC {('%.3f' % auc) if auc is not None else 'None'} is an "
        f"un-caveated inflated value. A ~0.63 AUC comes from selecting the memory-selective neurons "
        f"(and their preferred novelty/familiarity direction) and measuring the new/old AUC on the "
        f"SAME recognition trials -- circular (winner's curse / double dipping, Kriegeskorte 2009). "
        f"Either report the honest independent-selection value (~{EXPECTED:.2f}: select neurons + "
        f"direction on held-out trials -- essentially chance, since the memory-selective fraction is "
        f"itself at the chance false-positive rate), OR explicitly flag the reported value as "
        f"inflated by the same-trials non-independence (double dipping).")
