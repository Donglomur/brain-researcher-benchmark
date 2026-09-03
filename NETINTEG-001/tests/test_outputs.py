"""Grading checks for NETINTEG-001.

Ground truth (established before release on the nilearn ADHD-200 subset,
`fetch_adhd(n_subjects=40)`, Schaefer-2018 100/17 Pearson connectomes):

  Global efficiency is a binary-graph measure, so the correlation connectome must be
  thresholded/binarized first, and the thresholding CONVENTION determines the participant
  ranking. Per-participant efficiency vs. overall connectivity strength (mean positive edge):
    - fixed ABSOLUTE cutoff (r >= 0.3):        corr ~ +0.86  (efficiency IS overall strength)
    - DENSITY-MATCHED / proportional threshold: corr ~ -0.57  (confound removed)
  The two conventions give almost disjoint rankings (Spearman ~ -0.28; the top-8
  most-integrated sets overlap ~0/8). So "which participants are most integrated" is NOT a
  robust, single-answer ordering: under a fixed absolute threshold it degenerates into "who
  is most strongly correlated" (a density confound), and matching graph density across
  participants is required to compare integration fairly.

A good submission therefore (1) actually computes per-participant global efficiency, (2) checks
more than one thresholding convention/level rather than a single arbitrary threshold, and
(3) reports that the integration ranking is convention/density dependent (or controls density
and says why) -- instead of asserting one confident "most integrated" ordering from a single
absolute threshold. The tests below check those.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json", "ranking.json", "robustness.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def _efficiency_values():
    p = OUT / "efficiency.csv"
    if not p.exists():
        return []
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    if not rows:
        return []
    # locate the global-efficiency column
    def norm(s):
        return re.sub(r"[^a-z]", "", s.lower())
    col = None
    for c in rows[0].keys():
        n = norm(c)
        if "efficiency" in n or n in ("geff", "ge", "globaleff", "eglob"):
            col = c
            break
    if col is None:
        return []
    vals = []
    for r in rows:
        try:
            vals.append(float(r[col]))
        except (TypeError, ValueError):
            continue
    return vals


def test_efficiency_computed():
    vals = _efficiency_values()
    assert len(vals) >= 10, f"expected per-participant global efficiency for the cohort, got {len(vals)}"
    assert all(0.0 < v < 1.0 for v in vals), \
        "global efficiency values must lie in (0, 1) for a binary graph"
    # a real computation gives spread across participants, not a constant
    import statistics
    assert statistics.pstdev(vals) > 1e-4, \
        "global efficiency is identical across participants -- it was not actually computed per subject"


def test_ranking_present():
    # a participant ranking / most-integrated set must be reported somewhere
    found = False
    p = OUT / "ranking.json"
    if p.exists():
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            obj = None
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list) and len(cur) >= 3:
                found = True
                break
            if isinstance(cur, dict):
                stack.extend(cur.values())
    if not found:
        text = _text()
        # a ranking stated in prose / metadata: several participant ids or an explicit "most integrated"
        found = bool(re.search(r"most integrated|ranking|ranked|top[- ]?\d", text))
    assert found, "no participant ranking / most-integrated set was reported"


def test_examined_thresholding_choice():
    # Did the submission look at more than one thresholding convention/level before ranking,
    # rather than one arbitrary threshold? Accept a structured robustness report (>= 2 configs)
    # or a write-up that names more than one convention/level.
    for name in ("robustness.json", "run_metadata.json", "ranking.json"):
        try:
            obj = json.loads((OUT / name).read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list) and len(cur) >= 2 and any(isinstance(x, dict) for x in cur):
                # a list of >= 2 configuration/threshold dicts
                keys = " ".join(str(k).lower() for x in cur if isinstance(x, dict) for k in x)
                if re.search(r"thresh|densit|sparsit|cutoff|scheme|proportion|absolute", keys):
                    return
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    text = _text()
    # prose: either both conventions named, or an explicit multiple-density/threshold sweep
    both = re.search(r"proportional|density[- ]?match|fixed[- ]?densit", text) and \
        re.search(r"absolute (threshold|cutoff|correlation)|fixed (correlation|absolute)", text)
    sweep = re.search(r"(multiple|range of|several|different|varying|sweep|across)\s+"
                      r"[^.\n]{0,25}(threshold|densit|sparsit|cutoff)", text)
    assert both or sweep, (
        "submission thresholded the connectome one way only -- it did not check whether the "
        "integration ranking is robust to the thresholding convention (absolute cutoff vs "
        "density-matched/proportional) or to the threshold level")


def test_integration_ranking_not_overclaimed():
    # The warranted conclusion is that the integration ranking is convention/density dependent:
    # a fixed absolute threshold makes global efficiency track overall connectivity strength, so
    # the ranking must be reported as convention-dependent, OR density must be matched across
    # participants (and said so). A submission that just asserts a confident "these participants
    # are most integrated" from a single absolute threshold is overclaiming.
    text = _text()
    acknowledges = re.search(
        r"convention[- ]?dependent|depends on (the )?(threshold|densit|sparsit|convention|choice)"
        r"|not robust|n't robust|not (uniquely|robustly) (determined|defined|ordered)|not stable"
        r"|sensitive to (the )?(threshold|densit|sparsit|convention)"
        r"|confound\w*|driven by (the )?(overall |mean |raw )?(connectivity|correlation|strength|density)"
        r"|densit\w*[- ]?match\w*|proportional (threshold|sparsit)|match\w+ (the )?(graph )?densit"
        r"|fixed (graph )?densit", text)
    assert acknowledges, (
        "submission reports a confident integration ranking without noting that it is threshold-"
        "convention dependent -- under a fixed absolute cutoff, global efficiency is confounded "
        "by overall connectivity strength, and graph density must be matched across participants "
        "to compare integration; the ranking is not robust to this choice.")
