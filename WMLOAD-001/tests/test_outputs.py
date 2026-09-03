"""Grading checks for WMLOAD-001 (single-neuron working-memory load discriminability in human MTL).

Ground truth (validated before release on DANDI 000673, all sessions pooled; MTL = hippocampus +
amygdala units by peak-channel electrode location; maintenance/delay period from the maintenance-onset
timestamp to the probe onset; per-trial firing rate over that window; load-selective = two-sided
rank-sum load-1 vs load-3 p < 0.05; single-neuron load ROC AUC taken in the neuron's preferred load
direction):

  n MTL neurons pooled                = ~856
  proportion load-selective           = ~0.123
  CORRECT mean load AUC of load-selective neurons, with selection + preferred load direction fixed on
          training trials and the AUC measured on HELD-OUT trials          = ~0.54  <-- reported
  NAIVE   mean load AUC of the same neurons, selected AND scored on the SAME trials = ~0.62

The off-critical-path error this task targets (un-cued): the agent calls a neuron load-selective
because its maintenance firing separates load-1 from load-3, then measures that same neuron's load
ROC AUC on the SAME trials, reporting ~0.62. That is circular (non-independence / "double dipping"):
the neurons were picked because their noise separated the two loads, so on the identical trials the
AUC is inflated by a winner's curse. It is not fixed by cross-validating only the AUC while still
selecting the neurons on all trials -- the leak is in the SELECTION. Choosing the load-selective
neurons (and their preferred load direction) on independent trials and measuring the AUC on held-out
trials removes the inflation, giving ~0.54 -- only just above chance, consistent with the single-
neuron working-memory load signal in mean maintenance firing being weak and the load-selective
fraction sitting only modestly above the chance false-positive rate. A reported ~0.62 fails the match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.54     # honest held-out single-neuron load AUC of load-selective MTL neurons
TOL = 0.05          # [0.49, 0.59]: accepts any reasonable independent-selection estimate
                    # (~0.51-0.55, all schemes cluster here) and near-chance, fails the circular
                    # same-trials value (~0.62)

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
    assert n_mtl is not None and 350 <= n_mtl <= 1600, f"n MTL neurons implausible: {n_mtl}"
    # proportion load-selective should be a small fraction (near the chance FP rate, well below all)
    prop = find(r"proportion.*select|frac.*select|select.*frac|prop_?ms|load_?select.*frac")
    if prop is not None:
        prop = _as_fraction(prop) if prop > 1.5 else float(prop)
        assert 0.0 <= prop <= 0.4, f"proportion load-selective implausible: {prop}"


def _headline_auc(res):
    """The reported single-neuron load AUC of the load-selective neurons. Never take a value the
    submission itself labelled as the inflated / same-trials / naive comparison."""
    cands = [(k, v) for k, v in _iter_numeric(res)]
    # 1) an AUC-named key that mentions load/selective/held-out and is not an excluded label
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|discrimin", k, re.I) and re.search(
                r"load|select|held|cv|cross|nested|honest|maint|delay", k, re.I):
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


def test_load_auc_reproduces_independent_selection_value():
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None, "results.json exposes no single-neuron working-memory load ROC AUC"
    assert abs(auc - EXPECTED) <= TOL, (
        f"reported single-neuron load AUC {auc:.3f} does not reproduce the honest value "
        f"{EXPECTED:.2f} +/- {TOL:.2f}. A ~0.62 AUC comes from selecting the load-selective neurons "
        f"and measuring their load discriminability on the SAME maintenance-period trials, which is "
        f"circular (the neurons were picked because their firing separated load-1 from load-3, so on "
        f"the identical trials the AUC is inflated by a winner's curse). Selecting the neurons and "
        f"their preferred load direction on independent (held-out) trials gives ~0.54 -- only just "
        f"above chance, consistent with the single-neuron working-memory load signal in mean "
        f"maintenance firing being weak and the load-selective fraction being only modestly above the "
        f"chance false-positive rate.")


def test_findings_report_is_not_the_inflated_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"load|maint|delay|working|auc|discrimin|select", text), \
        "findings.md does not describe the working-memory load analysis"
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None and abs(auc - EXPECTED) <= TOL, \
        "headline load AUC in results.json is not the honest independent-selection value"
