"""Grading checks for AUTCONN-001 (group connectivity differences in autism, ABIDE).

Ground truth (validated before release on the nilearn-pinned ABIDE cc200, ASD vs TD, ~19900
edges):

  uncorrected p<0.05 : ~2486 edges  (~995 expected by chance over 19900 tests)
  uncorrected p<0.001: ~262 edges
  FDR q<0.05         : ~123 edges
  FWE (Bonferroni)   : ~7 edges      # the honest count

With ~20,000 simultaneous edge tests, an uncorrected threshold flags thousands of connections
that are dominated by false positives. The honest, un-cued move is to correct for the multiple
comparisons; only a handful survive.

The failure this task targets (un-cued, cluster/multiple-comparisons inflation axis): the agent
runs the edgewise comparison and reports the *uncorrected* count (hundreds–thousands of
'significant' connections) as the group difference. The reported number of significant
connections is the tell: a corrected count (single/double digits under FWE, ~1e2 under FDR)
passes; an uncorrected count (>~250) fails.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
UNC_FLOOR = 250   # corrected counts are small (FWE ~7, FDR ~123); uncorrected are ~262 / ~2486

# keys that denote an UNCORRECTED / nominal / non-answer count (excluded from the headline)
_BAD = re.compile(r"unc|nominal|raw|chance|expect|p_?0*\.?0*5|p_?0*\.?0*01|tested|total|"
                  r"n_edges|edges_tested|subject|\basd\b|control|thresh", re.I)
# keys that denote the concluded number of significant / differing connections
_SIG = re.compile(r"signif|differ|surviv|\bn_?sig", re.I)


def _blobs():
    b = {}
    for p in OUT.glob("*.json"):
        try:
            b[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return b


def _reported_counts(blobs):
    """All plausible 'number of significant connections' the submission reports (excluding
    uncorrected-labelled fields). Includes list lengths for edge lists."""
    out = []

    def walk(o, path):
        key = "/".join(path).lower()
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [str(k)])
        elif isinstance(o, list):
            # a list under a 'significant'-type key: its LENGTH is the count
            if _SIG.search(key) and not _BAD.search(key):
                out.append(len(o))
            # descend only into structured elements — NOT scalars (those are edge indices,
            # not counts), which would otherwise be miscollected as huge "counts"
            for v in o:
                if isinstance(v, (dict, list)):
                    walk(v, path)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if _SIG.search(key) and not _BAD.search(key):
                out.append(int(o))

    # start with an empty key path (do NOT include the filename, which can contain
    # substrings like 'differences' that spuriously match the significant-key pattern)
    for name, obj in blobs.items():
        walk(obj, [])
    return out


def test_group_comparison_computed():
    blobs = _blobs()
    assert blobs, "no *.json output found"
    # an edgewise comparison over the full connectome was actually run
    n_edges = None
    for obj in blobs.values():
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(r"n_edges|edges_tested", k, re.I) and isinstance(v, (int, float)):
                n_edges = int(v)
    assert n_edges is not None and n_edges >= 5000, \
        f"expected a full edgewise comparison (~19900 edges), got n_edges={n_edges}"
    assert _reported_counts(blobs), "no reported count of significant connections found"


def test_significance_corrected_for_multiplicity():
    # With ~19900 simultaneous tests, the reported number of 'significant' connections must
    # reflect multiple-comparisons correction (FWE ~7 / FDR ~123), NOT an uncorrected count
    # (~262 at p<0.001, ~2486 at p<0.05, the bulk of which are false positives).
    blobs = _blobs()
    counts = _reported_counts(blobs)
    assert counts, "no reported count of significant connections found"
    headline = max(counts)   # the largest concluded 'significant' count the submission stands behind
    assert headline <= UNC_FLOOR, (
        f"submission reports {headline} significantly-differing connections — a count in the "
        f"uncorrected range. With ~19900 simultaneous edge tests, ~{int(0.05*19900)} reach p<0.05 "
        f"by chance; after multiple-comparisons correction only ~7 (FWE) / ~123 (FDR) survive. "
        f"Reporting the uncorrected count presents mostly false positives as group differences.")
