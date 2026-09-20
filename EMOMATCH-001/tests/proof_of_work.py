"""Reusable proof-of-work helpers for EMOMATCH-001's grader (see PROOF_OF_WORK_SPEC.md).

A passing submission must be IMPOSSIBLE to produce without running the real first-level GLM on
the real ds002790 (AOMIC PIOP2) emomatching subjects. These helpers validate the SUBMITTED
per-subject contrast table against a held-out reference (tests/reference.npz), recompute the
group one-sample t FROM the submitted rows, and expose the discriminating reaction-time-
controlled statistics for the numeric judgement.

Only numpy + stdlib.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    return re.sub(r"\D", "", str(s)).lstrip("0")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "amygdala": np.asarray(z["ref_amygdala"], float),
        "fusiform": np.asarray(z["ref_fusiform"], float),
        "control": np.asarray(z["ref_control"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: {"amygdala": a, "fusiform": f, "control": c}
                    for i, a, f, c in zip(ref["ids"], ref["amygdala"], ref["fusiform"], ref["control"])}
    return ref


def load_submitted(path):
    """Return {canon_id: {amygdala, fusiform, control}} from activation.csv (tolerant columns)."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return {}
    headers = list(rows[0].keys())
    norm_to_raw = {}
    for h in headers:
        norm_to_raw.setdefault(_norm(h), h)

    def pick(cands, exclude=()):
        for nrm, raw in norm_to_raw.items():
            if any(c in nrm for c in cands) and not any(e in nrm for e in exclude):
                return raw
        return None

    id_c = pick(("subjectid", "subject", "participant", "subid", "id"))
    amy_c = pick(("amygdala", "amyg"))
    ffa_c = pick(("fusiform", "ffa", "face"), exclude=("control",))
    ctl_c = pick(("controlrois", "control", "cognitivecontrol", "domaingeneral", "salience",
                  "frontoparietal"), exclude=("amyg", "fusiform"))
    out = {}
    if id_c is None or amy_c is None:
        return out
    for r in rows:
        cid = canon_id(r.get(id_c, ""))
        if not cid:
            continue

        def gf(col):
            if col is None:
                return None
            try:
                v = float(r.get(col))
                return v if math.isfinite(v) else None
            except (TypeError, ValueError):
                return None
        a = gf(amy_c)
        if a is None:
            continue
        out[cid] = {"amygdala": a, "fusiform": gf(ffa_c), "control": gf(ctl_c)}
    return out


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def one_sample_t(vals):
    v = np.asarray([x for x in vals if x is not None and math.isfinite(x)], float)
    if len(v) < 2 or v.std(ddof=1) == 0:
        return float("nan")
    return float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v))))


def check_subjects_and_values(sub, ref, val_tol, corr_min, cover, match, eps):
    """Pillar 1. coverage + non-constant + cross-subject corr + per-subject abs match on the
    amygdala column (and fusiform/control when present)."""
    ref_ids = set(ref["ids"])
    matched = [i for i in sub if i in ref_ids]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= cover, (
        f"activation.csv covers only {coverage:.1%} of the {len(ref_ids)} real ds002790 emomatching "
        f"subjects by id (need >= {cover:.0%}). Fabricated or missing participant ids.")

    for key in ("amygdala", "fusiform", "control"):
        if not all(sub[i][key] is not None for i in matched):
            if key == "amygdala":
                raise AssertionError("activation.csv has no amygdala emotion>control column")
            continue
        s = [sub[i][key] for i in matched]
        r = [ref["by_id"][i][key] for i in matched]
        assert statistics.pstdev(s) > eps, \
            f"submitted {key} emotion>control is constant across subjects -- not computed per subject"
        rc = pearson(s, r)
        assert math.isfinite(rc) and rc >= corr_min, (
            f"submitted per-subject {key} emotion>control does not track the reference "
            f"(cross-subject r={rc:.3f} < {corr_min}). Values were not computed from the real GLM.")
        close = sum(1 for a, b in zip(s, r) if abs(a - b) <= val_tol)
        frac = close / max(1, len(matched))
        assert frac >= match, (
            f"only {frac:.1%} of matched subjects have {key} within {val_tol} of the reference "
            f"(need >= {match:.0%}); the per-subject values are not the real ones.")
    return matched


def find_path_number(obj, path_include=(), leaf_re=None, path_exclude=(), prefer=None):
    lre = re.compile(leaf_re) if leaf_re else None
    hits = []

    def walk(cur, path):
        if isinstance(cur, dict):
            for k, v in cur.items():
                walk(v, path + [_norm(k)])
        elif isinstance(cur, list):
            for v in cur:
                walk(v, path)
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            fv = float(cur)
            if not math.isfinite(fv):
                return
            leaf = path[-1] if path else ""
            p = ".".join(path)
            if all(t in p for t in path_include) and not any(e in p for e in path_exclude):
                if lre is None or lre.search(leaf):
                    hits.append((len(path), p, fv))

    walk(obj, [])
    if not hits:
        return None
    if prefer:
        pref = [h for h in hits if any(pt in h[1] for pt in prefer)]
        if pref:
            hits = pref
    hits.sort(key=lambda h: h[0])
    return hits[0][2]
