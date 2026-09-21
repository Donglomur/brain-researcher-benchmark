"""Reusable proof-of-work helpers for LIFESPAN-001's grader (see PROOF_OF_WORK_SPEC.md).

A passing submission must be IMPOSSIBLE to produce without running the real connectome analysis
on the real packaged NKI region time series. The per-subject global connectivity is
partition-independent and pins the work tightly; system segregation is partition-dependent and
graded more loosely (cross-subject correlation), with the age relationships recomputed from the
submitted rows. Only numpy + stdlib.
"""
import csv
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np


def canon_id(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_reference(path):
    z = np.load(path, allow_pickle=True)
    ref = {
        "ids": [canon_id(x) for x in z["ref_ids"]],
        "age": np.asarray(z["ref_age"], float),
        "global": np.asarray(z["ref_global"], float),
        "within": np.asarray(z["ref_within"], float),
        "between": np.asarray(z["ref_between"], float),
        "segregation": np.asarray(z["ref_segregation"], float),
        "stats": json.loads(str(z["ref_stats"])),
    }
    ref["by_id"] = {i: {"age": a, "global": g, "seg": s, "within": w, "between": b}
                    for i, a, g, s, w, b in zip(ref["ids"], ref["age"], ref["global"],
                                                ref["segregation"], ref["within"], ref["between"])}
    return ref


def load_submitted(path):
    """{canon_id: {age, global, seg}} from connectome_summary.csv (tolerant columns)."""
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
    age_c = pick(("age",), exclude=("range",))
    glob_c = pick(("globalconnectivity", "globalfc", "overallconnectivity", "meanconnectivity",
                   "meanfc", "overallfc", "globalconn"), exclude=("within", "between", "segreg"))
    within_c = pick(("withinnetworkconnectivity", "withinnetwork", "withinnetworkfc", "within"),
                    exclude=("between", "segreg", "global"))
    between_c = pick(("betweennetworkconnectivity", "betweennetwork", "betweennetworkfc", "between"),
                     exclude=("within", "segreg", "global"))
    seg_c = pick(("systemsegregation", "segregation", "networksegregation", "segreg"))
    out = {}
    if id_c is None or glob_c is None:
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
        g = gf(glob_c)
        if g is None:
            continue
        out[cid] = {"age": gf(age_c), "global": g, "seg": gf(seg_c),
                    "within": gf(within_c), "between": gf(between_c)}
    return out


def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def check_subjects_and_values(sub, ref, st):
    """Pillar 1. coverage + non-constant + tight per-subject global match (partition-independent)
    + real per-subject age + looser cross-subject segregation correlation."""
    ref_ids = set(ref["ids"])
    matched = [i for i in ref["ids"] if i in sub]
    coverage = len(matched) / max(1, len(ref_ids))
    assert coverage >= st["COVER"], (
        f"connectome_summary.csv covers only {coverage:.0%} of the {len(ref_ids)} packaged NKI "
        f"subjects (need >= {st['COVER']:.0%}).")

    sub_g = [sub[i]["global"] for i in matched]
    ref_g = [ref["by_id"][i]["global"] for i in matched]
    assert statistics.pstdev(sub_g) > st["EPS"], \
        "submitted global connectivity is constant across subjects -- not computed per subject"
    rc = pearson(sub_g, ref_g)
    assert math.isfinite(rc) and rc >= st["GLOB_CORR_MIN"], (
        f"submitted per-subject global connectivity does not track the reference (cross-subject "
        f"r={rc:.3f} < {st['GLOB_CORR_MIN']}). Values were not computed from the real time series.")
    close = sum(1 for a, b in zip(sub_g, ref_g) if abs(a - b) <= st["GLOB_TOL"])
    assert close / len(matched) >= st["MATCH"], (
        f"only {close/len(matched):.0%} of subjects have global connectivity within {st['GLOB_TOL']} "
        f"of the reference (need >= {st['MATCH']:.0%}).")

    # real per-subject age is a hard fact
    if all(sub[i]["age"] is not None for i in matched):
        age_close = sum(1 for i in matched if abs(sub[i]["age"] - ref["by_id"][i]["age"]) <= st["AGE_TOL"])
        assert age_close / len(matched) >= st["COVER"], (
            "submitted per-subject ages do not match the real NKI phenotype ages.")

    # per-network within/between connectivity are MANDATORY (the neutral graph summary the
    # segregation is recomputed from). Partition-dependent, so graded by cross-subject correlation
    # (they track global at ~0.94/0.97, so a valid alternative partition stays well above the floor
    # while a mechanism-guess fabrication -- e.g. within=const, between rising with age -- fails).
    for name in ("within", "between"):
        assert all(sub[i].get(name) is not None for i in matched), (
            f"connectome_summary.csv is missing the per-subject {name}_network_connectivity column "
            f"for some subjects. Both within- and between-network connectivity are required: the "
            f"system segregation is recomputed from them, not read from a reported scalar.")
        sub_v = [sub[i][name] for i in matched]
        ref_v = [ref["by_id"][i][name] for i in matched]
        assert statistics.pstdev(sub_v) > st["EPS"], (
            f"submitted {name}-network connectivity is constant across subjects -- not per subject")
        rv = pearson(sub_v, ref_v)
        assert math.isfinite(rv) and rv >= st["WB_CORR_MIN"], (
            f"submitted per-subject {name}-network connectivity does not track the reference "
            f"(cross-subject r={rv:.3f} < {st['WB_CORR_MIN']}); the per-network mean connectivity "
            f"was not computed from the real connectomes.")

    # segregation: recomputed from within/between must track the reference (partition-dependent,
    # looser cross-subject correlation).
    seg_rec = [recompute_segregation(sub[i]["within"], sub[i]["between"]) for i in matched]
    assert all(s is not None and math.isfinite(s) for s in seg_rec), (
        "cannot recompute system segregation (within - between)/within from the submitted "
        "within/between-network connectivity columns.")
    assert statistics.pstdev(seg_rec) > st["EPS"], \
        "recomputed system segregation is constant across subjects -- not computed per subject"
    ref_s = [ref["by_id"][i]["seg"] for i in matched]
    rs = pearson(seg_rec, ref_s)
    assert math.isfinite(rs) and rs >= st["SEG_CORR_MIN"], (
        f"system segregation recomputed from the submitted within/between columns does not track "
        f"the reference (cross-subject r={rs:.3f} < {st['SEG_CORR_MIN']}).")

    # if a segregation column is also submitted, it must be internally consistent with within/between
    if all(sub[i]["seg"] is not None for i in matched):
        bad = sum(1 for i, s in zip(matched, seg_rec) if abs(sub[i]["seg"] - s) > 0.05)
        assert bad <= 0.1 * len(matched), (
            f"the submitted system_segregation column is inconsistent with (within - between)/within "
            f"for {bad}/{len(matched)} subjects; it must be the segregation of the reported networks.")
    return matched


def recompute_segregation(within, between):
    """System segregation (Chan et al. 2014) = (within - between) / within, from a subject's mean
    within-network and between-network positive-edge connectivity."""
    if within is None or between is None:
        return None
    try:
        w = float(within); b = float(between)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(w) and math.isfinite(b)) or w == 0:
        return None
    return (w - b) / w


def recompute_segregation_age_r(sub, matched, ref):
    """Recompute the segregation-vs-age Pearson r FROM the submitted per-subject within/between
    columns and the real per-subject age (reference phenotype keyed by id). This is the un-guessable
    gate: an agent that omits the network columns (or fabricates them without the real per-subject
    network structure) cannot reproduce the declining segregation-with-age relationship."""
    ages, segs = [], []
    for i in matched:
        seg = recompute_segregation(sub[i].get("within"), sub[i].get("between"))
        a = ref["by_id"][i]["age"]
        if seg is not None and math.isfinite(seg) and a is not None and math.isfinite(a):
            ages.append(a); segs.append(seg)
    if len(segs) < 20:
        return float("nan"), 0
    return pearson(segs, ages), len(segs)


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
