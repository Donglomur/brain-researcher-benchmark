"""Reusable proof-of-work helpers for FCSTAB-001 (see PROOF_OF_WORK_SPEC.md).

A passing submission must be impossible to produce without running the real four-selection
analysis on the real baked cohort: the per-subject forward/reverse Fisher-z changes must be
the REAL numbers for the pinned subjects, the group summaries must recompute from those rows,
and the discriminating selection-scheme means must match the held-out reference.
"""
import csv
import json
import os
import re
import statistics
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(os.environ.get("FCSTAB_REFERENCE",
                               str(Path(__file__).resolve().parent / "reference.npz")))


def canon_id(s):
    return re.sub(r"\D", "", str(s)).lstrip("0")


def load_reference():
    d = np.load(REF_PATH, allow_pickle=False)
    ref = {k: d[k] for k in d.files if k != "ref_stats"}
    ref["ids"] = [canon_id(x) for x in d["ref_ids"]]
    ref["stats"] = json.loads(str(d["ref_stats"]))
    return ref


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _match_col(header, includes, excludes=(), fallbacks=()):
    """Return the first column whose normalised name contains ALL `includes` tokens and none
    of `excludes`; else try each (includes, excludes) pair in `fallbacks`."""
    norm = {c: _norm(c) for c in header}
    for c, n in norm.items():
        if all(t in n for t in includes) and not any(t in n for t in excludes):
            return c
    for inc, exc in fallbacks:
        for c, n in norm.items():
            if all(t in n for t in inc) and not any(t in n for t in exc):
                return c
    return None


def load_submitted():
    """Load stability.csv into (header, rows). Raises AssertionError if absent/empty."""
    p = OUT / "stability.csv"
    assert p.exists(), f"missing required output {p}"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "stability.csv has no data rows"
    return list(rows[0].keys()), rows


# canonical column resolvers (tolerant to reasonable renamings) -----------------------------
COLSPEC = {
    "id":          (["subject"], [], [(["subid"], []), (["id"], ["nedges", "edges"])]),
    "forward_first":  (["forward", "first"], [], [(["first", "half"], ["reverse", "second"])]),
    "forward_second": (["forward", "second"], [], [(["second", "half"], ["reverse", "first"])]),
    "forward_delta":  (["forward", "delta"], [],
                       [(["forward", "change"], []), (["forward", "diff"], []),
                        (["topdecile", "delta"], ["reverse"]), (["top", "change"], ["reverse"])]),
    "reverse_delta":  (["reverse", "delta"], [],
                       [(["reverse", "change"], []), (["reverse", "diff"], []),
                        (["reversehalf", "delta"], []), (["secondhalfselect"], [])]),
    "independent_delta": (["independent", "delta"], [],
                          [(["independent", "change"], []), (["loso", "delta"], []),
                           (["loso", "change"], []), (["indep", "delta"], []),
                           (["crossfit", "delta"], []), (["heldout", "delta"], [])]),
    "random_delta":   (["random", "delta"], [],
                       [(["random", "change"], []), (["random", "diff"], []),
                        (["control", "delta"], ["independent"])]),
}


def resolve_columns(header):
    return {k: _match_col(header, inc, exc, fb) for k, (inc, exc, fb) in COLSPEC.items()}


def submitted_map(rows, col):
    """{canon_id: float} for a resolved column (skips non-numeric)."""
    out = {}
    idc = resolve_columns(rows[0].keys())["id"]
    for r in rows:
        try:
            out[canon_id(r[idc])] = float(r[col])
        except (TypeError, ValueError, KeyError):
            continue
    return out


def coverage(sub_map, ref_ids):
    hit = sum(1 for i in ref_ids if i in sub_map)
    return hit / len(ref_ids)


def real_id_fraction(sub_map, ref_ids):
    """fraction of SUBMITTED ids that are real (in ref_ids) -- guards against padded fake ids."""
    if not sub_map:
        return 0.0
    refset = set(ref_ids)
    return sum(1 for i in sub_map if i in refset) / len(sub_map)


def nonconstant(sub_map, eps):
    vals = list(sub_map.values())
    return len(vals) >= 3 and statistics.pstdev(vals) > eps


def per_subject_match(sub_map, ref_ids, ref_vals, val_tol):
    """fraction of matched subjects whose |submitted - reference| <= val_tol."""
    ref = {i: float(v) for i, v in zip(ref_ids, ref_vals)}
    matched = [i for i in ref_ids if i in sub_map]
    if not matched:
        return 0.0, 0
    ok = sum(1 for i in matched if abs(sub_map[i] - ref[i]) <= val_tol)
    return ok / len(matched), len(matched)


def group_mean(sub_map):
    vals = list(sub_map.values())
    return sum(vals) / len(vals) if vals else float("nan")


def reported_scheme_means(summary):
    """Pull the reported per-scheme delta means from summary.json (schema-tolerant)."""
    out = {}
    sch = summary.get("selection_schemes", summary)
    if isinstance(sch, dict):
        for name in ("forward", "reverse", "independent", "random"):
            v = sch.get(name)
            if isinstance(v, dict):
                for key in ("delta_mean", "mean", "change", "delta"):
                    if isinstance(v.get(key), (int, float)):
                        out[name] = float(v[key]); break
    return out
