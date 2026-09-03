"""Grading checks for EVBOUND-001 (population decoding of cognitive boundaries in human MTL).

Ground truth (validated before release on DANDI 000207, all 19 sessions; per-session MTL population =
hippocampus + amygdala units by electrode location; encoding phase; per-clip firing rate over the
[0.0, 1.5] s window after the cut; standardized features; L2 logistic regression; repeated stratified
5-fold CV; ROC AUC of boundary (soft/hard) vs no-boundary from held-out decision scores; mean over
sessions):

  CORRECT mean CV decoding AUC, all neurons / neuron selection kept INSIDE the CV   = ~0.60  <-- reported
  LEAKY   mean CV decoding AUC, boundary-informative neurons chosen on ALL clips then CV = ~0.70

The off-critical-path error this task targets (un-cued): the agent ranks/selects "the neurons that
carry a boundary signal" on the FULL set of clips and then cross-validates a decoder restricted to
those neurons. The held-out folds were already used to choose the features, so the cross-validated AUC
is inflated by selection leakage (Kriegeskorte et al. 2009, "selection outside the CV loop"). Decoding
from all MTL neurons, or performing the neuron selection within each training fold, removes the leak
and gives ~0.60 -- clearly above chance (0.5), a genuine population boundary signal, but materially
smaller than the ~0.70 obtained when the neurons are chosen on the same clips used to test the
decoder. A reported ~0.70 fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.60     # honest cross-validated population decoding AUC (selection kept inside the CV)
TOL = 0.05          # [0.55, 0.65]: accepts any leak-free CV estimate (~0.59-0.61) and fails the
                    # selection-leakage value (~0.69-0.70) as well as a chance/null result (~0.50)

# keys that label a value as the leaky / naive comparison -- never the headline
_EXCLUDE = re.compile(
    r"leak|naive|inflat|biased|double|dip|selection[_ ]?outside|outside[_ ]?cv|non[_ ]?nested|"
    r"contaminat|circular|same[_ ]?clip|all[_ ]?clip|uncorrected|optimistic|overfit", re.I)


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

    n_sess = find(r"n_?sess|num.*sess|sessions")
    assert n_sess is not None and 8 <= n_sess <= 40, f"n sessions implausible: {n_sess}"


def _headline_auc(res):
    """The reported mean cross-validated boundary-vs-no-boundary population decoding AUC. Never take a
    value the submission itself labelled as the leaky / selection-outside-CV / naive one, and never a
    per-session entry from a list."""
    # 1) a scalar (non-list) AUC/decod-named key that is not excluded and is in the AUC range
    def scalar_leaves(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield from scalar_leaves(v, f"{prefix}.{k}" if prefix else str(k))
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            yield prefix, float(obj)
        # deliberately do NOT descend into lists (per-session arrays are not the headline)

    cands = list(scalar_leaves(res))
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|decod|discrimin|accuracy|score", k, re.I) and re.search(
                r"boundary|decod|auc|roc|cross|cv|held", k, re.I):
            f = _as_fraction(v)
            if 0.3 <= f <= 1.0:
                return f
    # 2) any non-excluded AUC/decoding-named scalar in range
    for k, v in cands:
        if _EXCLUDE.search(k):
            continue
        if re.search(r"auc|roc|decod", k, re.I):
            f = _as_fraction(v)
            if 0.3 <= f <= 1.0:
                return f
    return None


def test_decoding_auc_reproduces_leak_free_value():
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None, "results.json exposes no cross-validated boundary decoding ROC AUC"
    assert abs(auc - EXPECTED) <= TOL, (
        f"reported boundary decoding AUC {auc:.3f} does not reproduce the leak-free value "
        f"{EXPECTED:.2f} +/- {TOL:.2f}. A ~0.70 AUC comes from ranking/selecting the "
        f"boundary-informative neurons on the FULL set of clips and then cross-validating a decoder "
        f"restricted to them: the held-out folds were already used to pick the features, so the AUC "
        f"is inflated by selection leakage. Decoding from all MTL neurons, or selecting neurons "
        f"within each training fold, gives ~0.60 -- clearly above chance (a genuine population "
        f"boundary signal) but materially smaller than the leaky estimate.")


def test_findings_report_is_not_the_leaky_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"boundary|decod|auc|population|discrimin", text), \
        "findings.md does not describe the boundary population-decoding analysis"
    res = _results()
    auc = _headline_auc(res)
    assert auc is not None and abs(auc - EXPECTED) <= TOL, \
        "headline decoding AUC in results.json is not the leak-free value"
