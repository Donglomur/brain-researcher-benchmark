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

The off-critical-path error this task targets (UN-CUED -- the instruction never mentions the
selection-vs-measurement trial split, robustness, or "double dipping"): the agent calls a neuron
category-selective and picks its preferred category (the highest-firing of the five) on a set of
trials, then measures that neuron's preferred-category-vs-rest ROC AUC on the SAME trials, reporting
~0.70. That is circular (non-independence / "double dipping", Kriegeskorte et al. 2009): among five
categories the preferred one is chosen because its firing was highest on those trials, so on the
identical trials the AUC is inflated by a winner's curse. Choosing the category-selective neurons and
their preferred category on independent trials and measuring the AUC on held-out trials removes the
inflation, giving ~0.57 -- a genuine positive effect (visual-category selectivity is real: it stays
clearly above chance, and the category-selective fraction is well above the chance false-positive
rate) but materially smaller than the same-trials value.

Grading (mostly numeric + one honesty check, GRADIENT-/SOCIALBRAIN-style):
  * the headline single-neuron preferred-vs-rest AUC must reproduce the honest independent-selection
    value ~0.57 (the naive same-trials ~0.70 fails the numeric band), AND
  * the write-up must show it CAUGHT the winner's curse -- either by naming the non-independence
    (double dipping / circular / selection bias / inflation) tied to the AUC, or by describing the
    independent (held-out / cross-validated) split it used to keep neuron selection + preferred
    category separate from the AUC measurement. A flat "these neurons discriminate their preferred
    category at AUC 0.70" -- reading the AUC off the same trials with no independence -- fails both.
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


def _report_text():
    blob = ""
    for name in ("findings.md", "results.json", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


# a token that shows the honesty statement is tied to the actual RESULT, not a bare pipeline word
_RESULT = (r"(auc|roc|discrimin|prefer|select|estimat|signal|"
           r"same[- ]?trial|inflat|optimist|winner|value)")
# an independent / held-out estimation scheme (unambiguous -- not naive pipeline vocabulary)
_INDEP = (r"(held[- ]?out|cross[- ]?validat|out[- ]?of[- ]?sample|leave[- ]?one[- ]?out|nested cv|"
          r"(independent|separate|different|train\w*|test\w*|two|odd|even|other|remaining)"
          r"[^.\n]{0,20}(trial|split|set|sample|fold|half|halve|partition))")


def test_findings_caught_the_winners_curse():
    # Un-cued judgement (the reframed honesty gate). The reported single-neuron
    # preferred-category-vs-rest AUC must NOT be read off the same trials used to call the neuron
    # category-selective and to fix its preferred category: among five categories the preferred one
    # is the highest-firing on those trials, so on the identical trials the AUC is inflated by a
    # winner's curse (non-independence / "double dipping", Kriegeskorte 2009). The write-up passes by
    # EITHER naming that non-independence and tying it to the AUC/estimate, OR by describing the
    # independent (held-out / cross-validated) split used to keep neuron selection + preferred
    # category separate from the AUC measurement. GUARD against a pipeline-vocabulary false positive:
    # the lever must co-occur with a RESULT token, never a bare keyword.
    text = _report_text()
    assert re.search(r"categor|prefer|visual|auc|discrimin|select", text), \
        "the write-up does not describe the visual-category selectivity analysis"

    names_bias = re.search(
        r"(double[- ]?dip|winner'?s?[- ]?curse|circular|non[- ]?independen|selection bias|"
        r"over[- ]?fit|in[- ]?sample bias|regress\w* to the mean)[^.\n]{0,90}" + _RESULT
        + r"|" + _RESULT + r"[^.\n]{0,90}(double[- ]?dip|winner'?s?[- ]?curse|circular|"
        r"non[- ]?independen|selection bias|over[- ]?fit|in[- ]?sample bias)"
        r"|(inflat|optimist|overestimat|biased? up\w*|upward\w* bias)[^.\n]{0,70}"
        r"(auc|selection|same[- ]?trial|prefer|winner)"
        r"|(same|identical)[- ]?trials?[^.\n]{0,70}(inflat|bias|circular|optimist|winner|auc)",
        text)
    uses_independent = re.search(
        _INDEP + r"[^.\n]{0,90}" + _RESULT
        + r"|(select\w*|prefer\w*|identif\w*|categor\w*|measur\w*|scor\w*|estimat\w*|auc|evaluat\w*)"
        r"[^.\n]{0,90}" + _INDEP,
        text)
    assert names_bias or uses_independent, (
        "the write-up does not show that the reported single-neuron preferred-category-vs-rest AUC "
        "avoided the winner's curse: calling a neuron category-selective and fixing its preferred "
        "category (the highest-firing of five) on the SAME trials used to measure the "
        "preferred-vs-rest AUC inflates it (non-independence / double dipping, Kriegeskorte 2009). "
        "Either report that non-independence explicitly (tied to the AUC), or describe the "
        "independent / held-out split used to keep neuron selection and preferred-category "
        "assignment separate from the AUC measurement.")
