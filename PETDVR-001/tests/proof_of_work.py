"""Reusable proof-of-work helpers for the PET reproduction tasks (PETDVR / PETREF / PETVT).

Each task ships a held-out reference (tests/reference.npz, built from the oracle
solution/compute.py on the real OpenNeuro TACs, never shipped to the agent's container).
The submitted per-scan / per-subject table (the neutral per-item deliverable BOTH a naive
and an honest analysis produce) is validated against that reference by REAL id: coverage,
non-constant, and per-item value match. Because the naive lever (all-frames Logan / SUVR
ratio / wrong blood input) changes the per-item value itself, matching the per-item table
to the held-out honest reference closes fabrication AND the naive shortcut without cueing
the lever in the instruction (the QSMDIPOLE held-out-reference model). The cohort headline
is then recomputed FROM the submitted rows and cross-checked against the reference and the
reported JSON.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    d = {
        "ids": [str(x) for x in z["ref_ids"]],
        "values": np.asarray(z["ref_values"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    for k in ("ref_naive", "ref_R1", "ref_k2"):
        if k in z.files:
            d[k.replace("ref_", "")] = np.asarray(z[k], float)
    return d


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def read_rows(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    return rows, (list(rows[0].keys()) if rows else [])


def pick_col(headers, cands, exclude=()):
    """First header whose normalised name contains any candidate token and no exclude token.
    Exact-normalised matches are preferred over substring matches."""
    nmap = [(h, norm(h)) for h in headers]
    for h, n in nmap:
        if n in cands and not any(e in n for e in exclude):
            return h
    for h, n in nmap:
        if any(c in n for c in cands) and not any(e in n for e in exclude):
            return h
    return None


def ref_key_tokens(ref_id):
    """A reference id like 'sub-01|ses-baseline|highbinding' -> ['sub01','sesbaseline','highbinding']."""
    return [norm(p) for p in str(ref_id).split("|") if p != ""]


def build_submitted_map(rows, headers, id_col_groups, val_col, region_alias=None):
    """Return {ref_id_norm_key: value} keyed the same way reference ids normalise.

    id_col_groups: ordered list of candidate-token tuples, one per id component (subject,
    then session, then region/target), matching the '|' components of the reference ids.
    A component with no matching column contributes '' (so a table without a session column
    still matches single-component ids). region_alias maps a submitted region label to the
    reference token (e.g. 'leftputamen'->'putamen') via substring.
    """
    id_cols = []
    for group, exclude in id_col_groups:
        id_cols.append(pick_col(headers, group, exclude))
    out = {}
    for r in rows:
        parts = []
        for c in id_cols:
            if c is None:
                parts.append("")
                continue
            raw = norm(r.get(c, ""))
            if region_alias:
                for token, ref_tok in region_alias.items():
                    if token in raw:
                        raw = ref_tok
                        break
            parts.append(raw)
        key = "".join(parts)
        try:
            v = float(r.get(val_col, ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            out[key] = v
    return out


def norm_ref_ids(ref_ids):
    """Map each reference id to its normalised concatenated key."""
    return {rid: "".join(ref_key_tokens(rid)) for rid in ref_ids}


def match_items(submitted_map, ref_ids, ref_values, subset_tokens=None):
    """Return list of (ref_id, submitted_value, ref_value) for reference items present in the
    submitted table. subset_tokens (e.g. 'highbinding') restricts to matching ref ids."""
    nmap = norm_ref_ids(ref_ids)
    out = []
    for rid, rv in zip(ref_ids, ref_values):
        if subset_tokens and subset_tokens not in norm(rid):
            continue
        key = nmap[rid]
        if key in submitted_map:
            out.append((rid, submitted_map[key], float(rv)))
    return out


def within(sub, ref, tol_rel, tol_abs):
    return abs(sub - ref) <= max(tol_abs, tol_rel * abs(ref))


def find_number(obj, key_patterns, exclude=None):
    exc = [re.compile(e) for e in (exclude or [])]
    pats = [re.compile(p) for p in key_patterns]
    stack = [obj]
    while stack:
        cur = stack.pop(0)
        if isinstance(cur, dict):
            for k, v in cur.items():
                nk = norm(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if any(p.search(nk) for p in pats) and not any(e.search(nk) for e in exc):
                        fv = float(v)
                        if math.isfinite(fv):
                            return fv
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None
