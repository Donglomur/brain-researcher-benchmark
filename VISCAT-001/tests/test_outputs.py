"""Grading checks for VISCAT-001 (single-neuron visual-category selectivity in human MTL).

Ground truth (validated before release on DANDI 000004, all sessions pooled; MTL = hippocampus +
amygdala units by peak-channel electrode location; recognition phase; per-trial firing rate over the
[0.2, 1.7] s window after stimulus onset; category-selective = Kruskal-Wallis across the five visual
categories p < 0.05; single-neuron preferred-category-vs-rest ROC AUC with the preferred category
taken as the highest-firing category):

  n MTL neurons pooled                 = ~1864
  proportion category-selective        = ~0.167   (well above the 0.05 chance false-positive rate)
  CORRECT mean preferred-vs-rest AUC of category-selective neurons, with neuron selection + preferred
          category fixed on training trials and the AUC measured on HELD-OUT trials     = ~0.57  <-- reported
  NAIVE   mean preferred-vs-rest AUC of the same neurons, selected AND scored on the SAME trials = ~0.70

The off-critical-path error this task targets (un-cued): the agent calls a neuron category-selective
and picks its preferred category (the highest-firing of the five) on a set of trials, then measures
that neuron's preferred-category-vs-rest ROC AUC on the SAME trials, reporting ~0.70. That is circular
(non-independence / "double dipping"): among five categories the preferred one is chosen because its
firing was highest on those trials, so on the identical trials the AUC is inflated by a winner's
curse. Choosing the category-selective neurons and their preferred category on independent trials and
measuring the AUC on held-out trials removes the inflation, giving ~0.57 -- a genuine positive effect
(visual-category selectivity is real: it stays clearly above chance, and the category-selective
fraction is well above the chance false-positive rate) but materially smaller than the same-trials
value. A reported ~0.70 fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.575    # honest held-out single-neuron preferred-vs-rest AUC of category-selective cells
TOL = 0.05          # [0.525, 0.625]: accepts any reasonable independent-selection estimate
                    # (~0.57-0.60), fails the circular same-trials value (~0.65-0.70)

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
    # proportion category-selective should be a modest fraction (well above chance, well below all)
    prop = find(r"proportion.*select|frac.*select|select.*frac|prop_?sel|categor.*select.*frac")
    if prop is not None:
        prop = _as_fraction(prop) if prop > 1.5 else float(prop)
        assert 0.03 <= prop <= 0.6, f"proportion category-selective implausible: {prop}"


def _headline_auc(res):
    """The reported single-neuron preferred-category-vs-rest AUC of the category-selective neurons.
    Never take a value the submission itself labelled as the inflated / same-trials / naive one."""
    cands = [(k, v) for k, v in _iter_numeric(res)]
    # 1) an AUC-named key that mentions category/selective/preferred/held-out and is not excluded
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|discrimin", k, re.I) and re.search(
                r"categor|select|prefer|pref|held|cv|cross|nested|honest", k, re.I):
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


def test_pref_vs_rest_auc_reproduces_independent_selection_value():
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None, "results.json exposes no single-neuron preferred-category-vs-rest ROC AUC"
    assert abs(auc - EXPECTED) <= TOL, (
        f"reported single-neuron preferred-category-vs-rest AUC {auc:.3f} does not reproduce the "
        f"honest value {EXPECTED:.2f} +/- {TOL:.2f}. A ~0.70 AUC comes from calling a neuron "
        f"category-selective and picking its preferred category (highest-firing of the five) on a set "
        f"of trials and then measuring the preferred-vs-rest AUC on those SAME trials, which is "
        f"circular (the preferred category was chosen because its firing was highest, so on the "
        f"identical trials the AUC is inflated by a winner's curse over the five categories). "
        f"Choosing the neurons and their preferred category on independent (held-out) trials gives "
        f"~0.57 -- still clearly above chance (visual-category selectivity is a genuine single-neuron "
        f"effect) but materially smaller than the same-trials estimate.")


def test_findings_report_is_not_the_inflated_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"categor|prefer|visual|auc|discrimin|select", text), \
        "findings.md does not describe the visual-category selectivity analysis"
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None and abs(auc - EXPECTED) <= TOL, \
        "headline preferred-category-vs-rest AUC in results.json is not the honest independent-selection value"
