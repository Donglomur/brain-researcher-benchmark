"""Reusable proof-of-work helpers for GRADIENT-001 (macroscale principal gradient).

A passing submission must be impossible to produce without actually computing the per-subject
diffusion-map gradients on the real ds000228 / Schaefer-400/7 connectomes. The held-out reference
(tests/reference.npz, kept out of the container) stores the group-gradient leading-3 loadings (400
parcels) and the discriminating robustness numbers (cross-subject reproducibility after vs before
alignment; 7-network differentiability; the apex networks observed across defensible analytic
choices). The per-parcel loadings are graded by a ROTATION/SIGN-INVARIANT subspace overlap, which
is stable (>= 0.94) across the exact band-pass / subsample choices that flip the apex identity, so
it is robust to a defensible pipeline yet impossible for a fabricated gradient to hit.

R2 hedge: the graded conclusion is a RIGOR verdict scoped to this cohort and these analytic choices
-- the grader never forces a universal "identity unstable" claim, only that a robustness check was
run and the discriminating numbers are the real ones.
"""
import csv
import json
import os
import re
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(os.environ.get("GRADIENT_REFERENCE",
                               str(Path(__file__).resolve().parent / "reference.npz")))
NETWORKS = ["Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default"]


def load_reference():
    d = np.load(REF_PATH, allow_pickle=False)
    return {"group_g": np.asarray(d["ref_group_g"], float),
            "nets": [str(x) for x in d["ref_nets"]],
            "stats": json.loads(str(d["ref_stats"]))}


def canon_net(label):
    s = re.sub(r"[^a-z]", "", str(label).lower())
    for key, code in (("default", "Default"), ("limbic", "Limbic"), ("dors", "DorsAttn"),
                      ("sal", "SalVentAttn"), ("vent", "SalVentAttn"), ("vis", "Vis"),
                      ("som", "SomMot"), ("motor", "SomMot"), ("cont", "Cont"), ("frontopar", "Cont")):
        if key in s:
            return code
    return "NA"


def subspace_overlap(A, B):
    """Mean canonical correlation of the column spaces of A and B (rotation + sign invariant)."""
    A = np.asarray(A, float); B = np.asarray(B, float)
    Qa, _ = np.linalg.qr(A - A.mean(0))
    Qb, _ = np.linalg.qr(B - B.mean(0))
    s = np.linalg.svd(Qa.T @ Qb, compute_uv=False)
    return float(np.mean(np.clip(s, 0.0, 1.0)))


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_group_gradient():
    """Return (G 400x3, nets list) from group_gradient.csv, ordered by parcel_index if present."""
    p = OUT / "group_gradient.csv"
    assert p.exists(), "missing required output group_gradient.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "group_gradient.csv has no data rows"
    hdr = list(rows[0].keys())

    def col(*cands):
        for c in cands:
            for h in hdr:
                if _norm(h) == c:
                    return h
        for h in hdr:
            if any(c in _norm(h) for c in cands):
                return h
        return None

    ci = col("parcelindex", "parcel", "index", "roi")
    cn = col("network", "net", "yeo")
    c1, c2, c3 = col("g1", "gradient1", "grad1"), col("g2", "gradient2", "grad2"), col("g3", "gradient3", "grad3")
    assert c1 and c2 and c3, f"group_gradient.csv must have g1,g2,g3 columns (columns: {hdr})"
    recs = []
    for r in rows:
        try:
            g = [float(r[c1]), float(r[c2]), float(r[c3])]
        except (TypeError, ValueError):
            continue
        idx = None
        if ci is not None:
            try:
                idx = int(float(r[ci]))
            except (TypeError, ValueError):
                idx = None
        net = canon_net(r[cn]) if cn is not None else "NA"
        recs.append((idx, net, g))
    if all(x[0] is not None for x in recs):
        recs.sort(key=lambda x: x[0])
    G = np.array([x[2] for x in recs], float)
    nets = [x[1] for x in recs]
    return G, nets


def between_within(G, nets):
    """7-network differentiability in the leading gradient plane (g1-g2)."""
    g12 = G[:, :2]
    nets = np.asarray(nets)
    present = [n for n in NETWORKS if (nets == n).sum() >= 2]
    if len(present) < 5:
        return 0.0
    cent = np.array([g12[nets == n].mean(0) for n in present])
    between = float(np.var(cent, 0).sum())
    within = float(np.mean([g12[nets == n].var(0).sum() for n in present]))
    return between / within if within else 0.0


def network_means_from_rows(G, nets):
    nets = np.asarray(nets)
    return {n: [float(G[nets == n, j].mean()) for j in range(3)]
            for n in NETWORKS if (nets == n).sum() >= 1}


def load_json(name):
    p = OUT / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def find_number(obj, key_re):
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(key_re, key, re.I):
                out.append(float(o))
    walk(obj)
    return out


def written_blob():
    blob = ""
    for name in ("findings.md", "run_metadata.json", "robustness.json", "consistency.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def count_configs():
    """Number of distinct analysis configurations the submission reports (structured lists)."""
    best = 0
    for name in ("robustness.json", "run_metadata.json"):
        obj = load_json(name)
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list) and any(isinstance(x, dict) for x in cur):
                best = max(best, len([x for x in cur if isinstance(x, dict)]))
                for x in cur:
                    stack.append(x)
            elif isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return best


def distinct_apex_networks():
    """Distinct apex/anchor networks reported across configs (structured or prose)."""
    nets = set()
    for name in ("robustness.json", "run_metadata.json"):
        obj = load_json(name)

        def walk(o, key=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, str(k))
            elif isinstance(o, list):
                for v in o:
                    walk(v, key)
            elif isinstance(o, str) and re.search(r"apex|anchor|top|peak|dominant", key, re.I):
                c = canon_net(o)
                if c != "NA":
                    nets.add(c)
        walk(obj)
    return nets
