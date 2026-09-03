"""Grading checks for NETINTEG-001.

Ground truth (established before release on the nilearn ADHD-200 subset,
`fetch_adhd(n_subjects=40)`, Schaefer-2018 100/17 Pearson connectomes):

  Global efficiency is a binary-graph measure, so the correlation connectome must be
  thresholded/binarized first, and the thresholding CONVENTION determines the participant
  ranking. Per-participant efficiency vs. overall connectivity strength (mean positive edge):
    - fixed ABSOLUTE cutoff (r >= 0.3):        corr ~ +0.86  (efficiency IS overall strength)
    - DENSITY-MATCHED / proportional threshold: corr ~ -0.57  (confound removed)
  The two conventions give almost DISJOINT rankings (Spearman ~ -0.28; the top-8
  most-integrated sets overlap 0/8). So "which participants are most integrated" is NOT a
  robust, single-answer ordering: under a fixed absolute threshold it degenerates into "who
  is most strongly correlated" (a density confound), and matching graph density across
  participants is required to compare integration fairly.

A good submission therefore (1) actually computes per-participant global efficiency,
(2) reports a participant ranking, (3) engages with the thresholding convention rather than
a single arbitrary absolute cutoff, and -- the numeric teeth -- (4) the participant ranking it
reports as "most integrated" is the DENSITY-MATCHED one, NOT the absolute/strength-confounded
one. Check 4 is a top-k CONTRAST against two ground-truth sets (below): the reported
top-integrated set must be closer to the density-matched set than to the absolute set. This
cannot be passed by hedging in prose while reporting a single absolute-threshold ranking.

The two release ground-truth top-8 sets (participant ids, leading zeros stripped). They were
computed on the pinned data and are essentially DISJOINT (top-8 overlap 0/8). Grading is a
CONTRAST (closer to density-matched than to absolute), not exact identity, so it is robust to
the exact density/cutoff and to preprocessing: in the Step-0 probe EVERY density-matched
variant (5 densities x 2 preprocessings) overlapped DM_TOP by >= DM and > ABS, while every
absolute cutoff and the pure strength ranking did the reverse.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

# density-matched (proportional) top-8 most integrated -- the principled, confound-controlled set
DM_TOP = {"27018", "3699991", "1679142", "4164316", "4134561", "27037", "23008", "1418396"}
# absolute-cutoff top-8 -- what an un-cued analyst who thresholds absolutely reports; it is
# really the overall-connectivity-strength ranking (efficiency vs strength r ~ +0.86)
ABS_TOP = {"23012", "3994098", "9744150", "3902469", "1562298", "10128", "1019436", "1552181"}


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json", "ranking.json", "robustness.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def _load(name):
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _canon_id(s):
    return re.sub(r"\D", "", str(s)).lstrip("0")


def _efficiency_values():
    p = OUT / "efficiency.csv"
    if not p.exists():
        return []
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    if not rows:
        return []

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
    obj = _load("ranking.json")
    if obj is not None:
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
        found = bool(re.search(r"most integrated|ranking|ranked|top[- ]?\d", text))
    assert found, "no participant ranking / most-integrated set was reported"


def test_examined_thresholding_choice():
    # Did the submission engage with the thresholding convention rather than a single arbitrary
    # absolute cutoff? Accept a structured robustness report (>= 2 configs), a write-up naming
    # more than one convention/level or a density sweep, OR an explicit density-matched /
    # proportional thresholding method (the principled choice -- a submission that simply does
    # the right thing should not be failed here; the numeric teeth are in check 4).
    for name in ("robustness.json", "run_metadata.json", "ranking.json"):
        obj = _load(name)
        if obj is None:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list) and len(cur) >= 2 and any(isinstance(x, dict) for x in cur):
                keys = " ".join(str(k).lower() for x in cur if isinstance(x, dict) for k in x)
                if re.search(r"thresh|densit|sparsit|cutoff|scheme|proportion|absolute", keys):
                    return
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    text = _text()
    both = re.search(r"proportional|density[- ]?match|fixed[- ]?densit", text) and \
        re.search(r"absolute (threshold|cutoff|correlation)|fixed (correlation|absolute)", text)
    sweep = re.search(r"(multiple|range of|several|different|varying|sweep|across)\s+"
                      r"[^.\n]{0,25}(threshold|densit|sparsit|cutoff)", text)
    density_matched = re.search(r"proportional (threshold|sparsit|weight|)|density[- ]?match\w*|"
                                r"match\w+ (the )?(graph )?densit|(fixed|equal|same|common) (graph )?densit|"
                                r"edge densit|top \d+\s?%|top \d+ percent|"
                                r"\d+\s?%\s+(of )?(the )?(strongest |top )?edges|"
                                r"(keep|kept|retain\w*|select\w*)[^.\n]{0,25}%[^.\n]{0,15}edges", text)
    assert both or sweep or density_matched, (
        "submission thresholded the connectome one way only -- it did not engage with the "
        "thresholding convention (absolute cutoff vs density-matched/proportional) or the "
        "threshold level")


# ---------------------------------------------------------------------------------------------
# check 4: the numeric top-k contrast (the hedge-defeating teeth)
# ---------------------------------------------------------------------------------------------
def _reported_top_set(k=8):
    """The participant set the submission reports as MOST integrated, canonicalised.

    Priority: (1) an explicit top/most-integrated set key that is NOT the absolute-threshold
    one; (2) a full most-to-least ordering (take the first k); (3) efficiency.csv sorted by the
    efficiency column, descending. Returns a set of up to k canonical ids, or None.
    """
    EXCLUDE = r"absolute|abs\b|_abs|strength|\braw\b|unmatched|fixed|uncorrected"

    def _lists_from(obj, path=""):
        """Yield (path, list-of-scalars) for every list of scalars in the json."""
        out = []
        if isinstance(obj, dict):
            for kk, vv in obj.items():
                out.extend(_lists_from(vv, path + "/" + str(kk).lower()))
        elif isinstance(obj, list):
            if obj and all(not isinstance(x, (dict, list)) for x in obj):
                out.append((path, obj))
            else:
                for x in obj:
                    out.extend(_lists_from(x, path))
        return out

    candidates = []  # (priority, path, list)
    for name in ("ranking.json", "run_metadata.json", "results.json"):
        obj = _load(name)
        if obj is None:
            continue
        for path, lst in _lists_from(obj):
            ids = [_canon_id(x) for x in lst if _canon_id(x)]
            if len(ids) < 3:
                continue
            is_excluded = re.search(EXCLUDE, path) is not None
            is_topset = re.search(r"(top|most)[^/]*integrat|top[_ ]?\d|top[_ ]?integ|"
                                  r"most[_ ]?integ", path) is not None
            is_ordering = re.search(r"rank|order|integrat|most.*least|efficien", path) is not None
            if is_topset and not is_excluded:
                candidates.append((0, path, ids))
            elif is_ordering and not is_excluded:
                candidates.append((1, path, ids))
    if candidates:
        candidates.sort(key=lambda t: (t[0], len(t[2])))  # prefer an explicit small top-set
        return set(candidates[0][2][:k])

    # fallback: efficiency.csv sorted by efficiency, descending
    p = OUT / "efficiency.csv"
    if p.exists():
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        if rows:
            def norm(s):
                return re.sub(r"[^a-z]", "", s.lower())
            eff_col = pid_col = None
            for c in rows[0].keys():
                n = norm(c)
                if eff_col is None and ("efficiency" in n or n in ("geff", "ge", "globaleff", "eglob")):
                    eff_col = c
                if pid_col is None and ("participant" in n or "subject" in n or n in ("id", "sub", "pid")):
                    pid_col = c
            if pid_col is None:
                pid_col = list(rows[0].keys())[0]
            if eff_col is not None:
                try:
                    ranked = sorted(rows, key=lambda r: float(r[eff_col]), reverse=True)
                    ids = [_canon_id(r[pid_col]) for r in ranked if _canon_id(r[pid_col])]
                    if len(ids) >= 3:
                        return set(ids[:k])
                except (TypeError, ValueError):
                    pass
    return None


def _confound_contrast_reported():
    """Route B (preprocessing-robust fallback): the submission numerically reports the
    efficiency<->overall-strength confound under BOTH conventions with the correct sign
    contrast -- strongly positive under an absolute/fixed threshold, and weak/negative under a
    density-matched/proportional one. This is the confound signature the task is about and is
    robust to preprocessing (reproduced on a 2nd cohort at release). A hedge that never
    computed both conventions has neither number, so this does not open a loophole.
    """
    abs_corrs, dm_corrs = [], []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for kk, vv in obj.items():
                walk(vv, path + "/" + str(kk).lower())
        elif isinstance(obj, list):
            for x in obj:
                walk(x, path)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            v = float(obj)
            if -1.01 <= v <= 1.01 and re.search(r"corr|strength|confound|r_|_r\b|pearson", path):
                if re.search(r"absolute|abs\b|_abs|fixed|cutoff", path):
                    abs_corrs.append(v)
                elif re.search(r"proportion|densit|match", path):
                    dm_corrs.append(v)

    for name in ("robustness.json", "run_metadata.json", "ranking.json", "results.json"):
        obj = _load(name)
        if obj is not None:
            walk(obj)
    return abs_corrs and dm_corrs and max(abs_corrs) >= 0.4 and min(dm_corrs) <= 0.2


def test_reported_ranking_is_density_matched_not_absolute():
    # NUMERIC TOP-K CONTRAST. The warranted "most integrated" ranking is the density-matched
    # one; a fixed absolute threshold makes global efficiency track overall connectivity
    # strength, so an absolute ranking is the confounded (wrong) answer. The set the submission
    # reports as most integrated must be closer to the density-matched ground truth than to the
    # absolute one. Robust to the exact density/cutoff and to preprocessing (Step-0 validated).
    top = _reported_top_set()
    assert top, "could not locate a reported most-integrated participant set to grade"
    dm = len(top & DM_TOP)
    ab = len(top & ABS_TOP)
    ok = (dm >= 2 and dm > ab) or _confound_contrast_reported()
    assert ok, (
        f"the reported most-integrated ranking matches the ABSOLUTE-threshold convention "
        f"(overlap with the absolute/strength-confounded top-8 = {ab}/8) rather than the "
        f"density-matched one (overlap = {dm}/8). Under a fixed absolute cutoff, global "
        f"efficiency is confounded by overall connectivity strength; graph density must be "
        f"matched across participants to compare integration, which yields a nearly disjoint "
        f"ranking. The submission reported the confounded ordering as the answer.")
