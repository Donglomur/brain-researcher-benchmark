"""Grading checks for NETSTRENGTH-001 (strongest DIRECT connections in the HCP group netmat).

Ground truth (validated before release on the nilearn-pinned MegaTrawls d25 group netmats,
eigen_regression; node indices are 0-based over the 25 group-ICA components):

  Strongest DIRECT connections = the top edges of the PARTIAL-correlation matrix (Znet2).
  Top-10 partial (direct) edges:
    (0,12) (8,9) (0,1) (10,14) (10,15) (1,8) (6,14) (10,23) (5,13) (0,8)

  The naive answer ranks the FULL/Pearson-correlation matrix (Znet1). Its top-10 edges are
    (0,3) (0,2) (2,3) (0,12) (2,4) (4,7) (0,4) (5,13) (2,14) (19,23)
  Only (0,12) and (5,13) are shared. The full-correlation-only top edges
    (0,2) (0,3) (0,4) (2,3) (2,4) (2,14) (4,7) (19,23)
  are INDIRECT / globally-confounded paths: e.g. (0,3) is the single strongest full edge
  (Z=35.5) but only rank 19/300 in partial (Z=25.4), and (0,4) is a top-7 full edge (Z=-29)
  yet essentially a zero direct connection (partial Z=+0.08, dead last). corr(full,partial)
  over edges = 0.69; only 43% of top-decile full edges are top-decile partial. Node 0 is the
  apparent hub under full correlation; the direct-connection hub is node 10.

So a submission that ranks the full-correlation matrix reports indirect edges and FAILS;
one that ranks partial correlation reports the direct connections and PASSES. The
instruction names both matrices but never says which to use, nor that full-correlation
strongest edges are indirect.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
DIM = 25

# Direct-connection ground truth (0-based), as frozenset pairs.
PARTIAL_TOP10 = {frozenset(e) for e in
                 [(0, 12), (8, 9), (0, 1), (10, 14), (10, 15), (1, 8), (6, 14), (10, 23), (5, 13), (0, 8)]}
# Edges that are strong in FULL correlation but NOT among the direct (partial) top edges:
# the signature of ranking the wrong (marginal) matrix.
FULL_ONLY = {frozenset(e) for e in
             [(0, 2), (0, 3), (0, 4), (2, 3), (2, 4), (2, 14), (4, 7), (19, 23)]}
# Direct edges that a full-correlation ranking does NOT surface in its top-10:
PARTIAL_ONLY = {frozenset(e) for e in
                [(0, 1), (0, 8), (1, 8), (6, 14), (8, 9), (10, 14), (10, 15), (10, 23)]}

_NODE_KEY = re.compile(r"node|source|target|\bfrom\b|\bto\b|comp|roi|region|^i$|^j$|^a$|^b$|idx|index", re.I)
_PAIR_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:[-–—]|,|and|&|to|vs\.?|with|\+)\s*(\d{1,2})(?![\d.])", re.I)


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _collect_json_pairs(obj, pairs):
    if isinstance(obj, dict):
        node_ints = []
        for k, v in obj.items():
            if _is_int(v) and _NODE_KEY.search(str(k)):
                node_ints.append(v)
            if isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_int(x) for x in v):
                pairs.append((v[0], v[1]))
        if len(node_ints) == 2:
            pairs.append((node_ints[0], node_ints[1]))
        for v in obj.values():
            _collect_json_pairs(v, pairs)
    elif isinstance(obj, (list, tuple)):
        if len(obj) == 2 and all(_is_int(x) for x in obj):
            pairs.append((obj[0], obj[1]))
        for v in obj:
            _collect_json_pairs(v, pairs)


def _reported_pairs():
    """All node-index pairs the submission reports, from any JSON structure and from prose."""
    raw = []
    for p in sorted(OUT.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        _collect_json_pairs(obj, raw)
    prose = ""
    for name in ("findings.md", "strongest_connections.json", "run_metadata.json"):
        fp = OUT / name
        if fp.exists():
            prose += "\n" + fp.read_text(encoding="utf-8")
    for m in _PAIR_RE.finditer(prose):
        raw.append((int(m.group(1)), int(m.group(2))))
    return raw


def _pairset(raw, offset):
    s = set()
    for a, b in raw:
        a2, b2 = a + offset, b + offset
        if 0 <= a2 < DIM and 0 <= b2 < DIM and a2 != b2:
            s.add(frozenset((a2, b2)))
    return s


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        fp = OUT / name
        if fp.exists():
            blob += "\n" + fp.read_text(encoding="utf-8")
    return blob.lower()


def test_strongest_connections_are_direct_not_marginal():
    # The reported strongest connections must match the PARTIAL-correlation (direct) edges,
    # not the FULL-correlation (marginal/indirect) edges. We accept 0-based or 1-based node
    # numbering (whichever interpretation is more consistent with a real edge set).
    raw = _reported_pairs()
    assert raw, "no node-index connection pairs could be parsed from the submission"
    best = None
    for offset in (0, -1):
        s = _pairset(raw, offset)
        p_only = len(s & PARTIAL_ONLY)
        f_only = len(s & FULL_ONLY)
        if best is None or (p_only - f_only) > (best[0] - best[1]):
            best = (p_only, f_only)
    p_only, f_only = best
    # A partial-ranked answer is dominated by direct-only edges; a full-ranked answer is
    # dominated by the full-only (indirect) edges. Requiring direct-only edges to be present
    # AND to outnumber the indirect ones also rejects a dump of the entire matrix.
    assert p_only >= 2 and p_only > f_only + 1, (
        f"the reported strongest connections are not the direct (partial-correlation) edges: "
        f"matched {p_only} direct-only edges vs {f_only} full-correlation-only (indirect) edges. "
        f"The strongest full-correlation edges (e.g. 0-3, 0-2, 2-3) are indirect, globally-confounded "
        f"paths; the strongest DIRECT connections are the top partial-correlation edges "
        f"(0-12, 8-9, 0-1, 10-14, 10-15, ...).")


def test_writeup_distinguishes_direct_from_indirect():
    # The write-up must justify the direct connections via partial correlation / by removing
    # the influence of other nodes, or explicitly flag that full-correlation strongest edges
    # are indirect -- not merely list the largest correlation-matrix entries.
    text = _text()
    justified = re.search(
        r"partial[- ]?correlation|partial corr|precision matrix|inverse cov"
        r"|regress\w*\s+out|controll?ing for|conditioning on|remov\w*[^.\n]{0,30}(shared|global|common|indirect|other)"
        r"|indirect|confound|globally[- ]shared|mediat", text)
    assert justified, (
        "findings/run_metadata do not explain the connections as DIRECT (partial-correlation / "
        "influence of other nodes removed) or note that full-correlation strongest edges are "
        "indirect -- a ranking of raw full-correlation entries does not identify direct connections.")
