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
firing rate essentially vanishes. A reported ~0.63 fails the numeric match.
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


def test_new_old_auc_reproduces_independent_selection_value():
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None, "results.json exposes no single-neuron new/old ROC AUC"
    assert abs(auc - EXPECTED) <= TOL, (
        f"reported single-neuron new/old AUC {auc:.3f} does not reproduce the honest value "
        f"{EXPECTED:.2f} +/- {TOL:.2f}. A ~0.63 AUC comes from selecting the memory-selective "
        f"neurons and measuring their new/old discriminability on the SAME recognition trials, which "
        f"is circular (the neurons were picked because their firing separated novel from familiar, "
        f"so on the identical trials the AUC is inflated by a winner's curse). Selecting the neurons "
        f"and their preferred direction on independent (held-out) trials gives ~0.51 -- essentially "
        f"chance, consistent with the memory-selective fraction being at the chance false-positive "
        f"rate.")


def test_findings_report_is_not_the_inflated_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"new.?old|novel|familiar|memory|auc|discrimin", text), \
        "findings.md does not describe the new/old memory analysis"
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None and abs(auc - EXPECTED) <= TOL, \
        "headline new/old AUC in results.json is not the honest independent-selection value"
