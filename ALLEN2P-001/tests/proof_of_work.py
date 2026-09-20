"""Reusable proof-of-work helpers for ALLEN2P-001 (orientation-/direction-selective fraction
of a two-photon VISp field). See PROOF_OF_WORK_SPEC.md.

A passing submission must be impossible to produce without computing the REAL per-neuron OSI/DSI
of the pinned experiment's imaged neurons. A held-out reference (tests/reference.npz, kept out of
the container) stores, per pinned cell_specimen_id, both the SAME-TRIALS OSI/DSI (the winner's-curse
inflated procedure the brief pins) and the HELD-OUT OSI/DSI (preferred condition chosen on one set
of trials, OSI/DSI measured on the disjoint set). A submission's per-neuron OSI/DSI must match one
of these two references (a fabricated table cannot reproduce which neurons are tuned), and its
reported selective fraction must recompute from its own table.
"""
import csv
import json
import math
import os
import re
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(os.environ.get("ALLEN2P_REFERENCE",
                               str(Path(__file__).resolve().parent / "reference.npz")))


def load_reference():
    d = np.load(REF_PATH, allow_pickle=False)
    st = json.loads(str(d["ref_stats"]))
    thr = float(st["threshold"])
    osi_same = np.asarray(d["ref_osi_same"], float)
    dsi_same = np.asarray(d["ref_dsi_same"], float)
    osi_ho = np.asarray(d["ref_osi_ho"], float)
    dsi_ho = np.asarray(d["ref_dsi_ho"], float)
    sel_same = (np.nan_to_num(osi_same, nan=-9) > thr) | (np.nan_to_num(dsi_same, nan=-9) > thr)
    sel_ho = (np.nan_to_num(osi_ho, nan=-9) > thr) | (np.nan_to_num(dsi_ho, nan=-9) > thr)
    return {
        "cell_ids": [str(c) for c in d["ref_cell_ids"]],
        "osi_same": osi_same, "dsi_same": dsi_same,
        "osi_ho": osi_ho, "dsi_ho": dsi_ho,
        "sel_same": sel_same, "sel_ho": sel_ho,
        "stats": st,
    }


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _canon_id(x):
    return re.sub(r"\D", "", str(x)).lstrip("0") or "0"


def load_results():
    p = OUT / "results.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_per_neuron():
    """Return dict cell_id(canon) -> {'osi':float|nan, 'dsi':float|nan, 'sel':int|None}."""
    p = OUT / "per_neuron.csv"
    assert p.exists(), "missing required output per_neuron.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "per_neuron.csv has no data rows"
    hdr = list(rows[0].keys())
    idc = next((h for h in hdr if any(t in _norm(h) for t in ("cellspecimen", "cellid", "specimen"))
                or _norm(h) == "id" or _norm(h) == "cell"), None)
    if idc is None:
        idc = hdr[0]

    def pick(metric):
        # prefer an EXACT 'osi'/'dsi' column, then one NOT labelled same-trials/naive, then any
        exact = [h for h in hdr if _norm(h) == metric]
        if exact:
            return exact[0]
        prefixed = [h for h in hdr if _norm(h).startswith(metric)]
        clean = [h for h in prefixed if not re.search(r"same|naive|nohold|circular", _norm(h))]
        if clean:
            return clean[0]
        if prefixed:
            return prefixed[0]
        anym = [h for h in hdr if metric in _norm(h)]
        return anym[0] if anym else None

    osic, dsic = pick("osi"), pick("dsi")
    selc = next((h for h in hdr if _norm(h) == "selective"), None) or \
        next((h for h in hdr if "select" in _norm(h) and not re.search(r"same|naive", _norm(h))), None) or \
        next((h for h in hdr if "select" in _norm(h)), None)
    assert osic and dsic, f"per_neuron.csv must have osi and dsi columns (columns: {hdr})"

    def fnum(v):
        try:
            f = float(v)
            return f if math.isfinite(f) else float("nan")
        except (TypeError, ValueError):
            return float("nan")

    out = {}
    for r in rows:
        cid = _canon_id(r.get(idc, ""))
        sel = None
        if selc is not None:
            sv = _norm(r.get(selc, ""))
            sel = 1 if sv in ("1", "true", "yes", "y", "t") else (0 if sv in ("0", "false", "no", "n", "f", "") else None)
        out[cid] = {"osi": fnum(r.get(osic)), "dsi": fnum(r.get(dsic)), "sel": sel,
                    "osi_col": osic, "dsi_col": dsic}
    return out


def coverage(sub_map, ref_ids):
    ref_canon = {_canon_id(i) for i in ref_ids}
    hit = sum(1 for i in ref_canon if i in sub_map)
    return hit / len(ref_canon)


def _rank(a):
    a = np.asarray(a, float)
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(len(a), dtype=float)
    return ranks


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 8:
        return 0.0
    ra, rb = _rank(a[m]), _rank(b[m])
    if np.std(ra) < 1e-9 or np.std(rb) < 1e-9:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _aligned(sub_map, ref_ids, ref_vals, key):
    """Return (sub_vec, ref_vec) aligned over matched cell ids."""
    sv, rv = [], []
    for i, cid in enumerate(ref_ids):
        c = _canon_id(cid)
        if c in sub_map:
            sv.append(sub_map[c][key]); rv.append(ref_vals[i])
    return np.asarray(sv, float), np.asarray(rv, float)


def best_reference_match(sub_map, REF):
    """Match the submitted per-neuron OSI+DSI against BOTH the same-trials and held-out
    references; return (which, osi_rho, dsi_rho, sel_agreement) for the better-matching one."""
    ids = REF["cell_ids"]
    results = {}
    for which, osir, dsir, selr in (("same_trials", REF["osi_same"], REF["dsi_same"], REF["sel_same"]),
                                    ("held_out", REF["osi_ho"], REF["dsi_ho"], REF["sel_ho"])):
        so, ro = _aligned(sub_map, ids, osir, "osi")
        sd, rd = _aligned(sub_map, ids, dsir, "dsi")
        orho = spearman(so, ro)
        drho = spearman(sd, rd)
        # selective-flag agreement (over neurons where the submission gives a flag)
        agree = _sel_agreement(sub_map, ids, selr)
        results[which] = (0.5 * (orho + drho), orho, drho, agree)
    which = max(results, key=lambda k: results[k][0])
    return which, results[which]


def _sel_agreement(sub_map, ref_ids, ref_sel):
    n = ok = 0
    for i, cid in enumerate(ref_ids):
        c = _canon_id(cid)
        if c in sub_map and sub_map[c]["sel"] is not None:
            n += 1
            if int(sub_map[c]["sel"]) == int(ref_sel[i]):
                ok += 1
    return ok / n if n else None


def table_selective_fraction(sub_map, n_total):
    """Fraction of table rows flagged selective, over the imaged-neuron count."""
    flags = [v["sel"] for v in sub_map.values() if v["sel"] is not None]
    if not flags or not n_total:
        return None
    return sum(flags) / n_total


def headline_fraction(res):
    """Reported selective fraction (0..1), never a value the submission labelled same-trials/sd."""
    excl = re.compile(r"same_?trial|no_?hold|persplit|per_?split|_sd\b|sd_|std|sem|across_?split|"
                      r"naive|inflat|circular|double|winner|biased|variance|spread", re.I)
    if not isinstance(res, dict):
        return None
    for k, v in res.items():
        if (isinstance(v, (int, float)) and not isinstance(v, bool) and not excl.search(k)
                and re.search(r"(select|osi|dsi).*frac|frac.*(select|osi|dsi)|selective_?fraction",
                              k, re.I)):
            return float(v) / 100.0 if v > 1.5 else float(v)
    v = res.get("selective_fraction")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) / 100.0 if v > 1.5 else float(v)
    return None


def same_trials_fraction(res):
    if isinstance(res, dict):
        for k, v in res.items():
            if (isinstance(v, (int, float)) and not isinstance(v, bool)
                    and re.search(r"same_?trial|no_?hold", k, re.I)):
                return float(v) / 100.0 if v > 1.5 else float(v)
    return None


# --- volunteered winner's-curse / double-dipping detector (secondary judgement, DEVCONN-style) --
_LEVER = re.compile(
    r"held[\s-]?out|cross[\s-]?validat|double[\s-]?dipp|winner'?s?[\s-]?curse|circular|"
    r"selection[\s-]?bias|select\w*[\s-]?bias|same[\s-]?(set of )?trials|same[\s-]?data|"
    r"same set of trials|non[\s-]?independent|independent (set of )?trials|disjoint trials|"
    r"re[\s-]?used the same|regression to the mean", re.I)
_RESULT = re.compile(
    r"inflat|over[\s-]?estimat|overestimat|exagger|artificially|spurious|too high|"
    r"bias\w* (high|up|upward|toward)|upward|winner|lower|drops?|fall|reduc|shrink|"
    r"honest\w*|unbiased|\b0\.(4[5-9]|5[0-9]|6[0-6])\b", re.I)


def volunteers_selection_bias(text):
    levers = [m.start() for m in _LEVER.finditer(text)]
    results = [m.start() for m in _RESULT.finditer(text)]
    for li in levers:
        for ri in results:
            if abs(li - ri) <= 200:
                return True
    return False


def all_prose():
    blob = ""
    for name in ("findings.md", "run_metadata.json", "results.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()
