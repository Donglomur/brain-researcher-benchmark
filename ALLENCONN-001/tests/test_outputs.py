"""Grading checks for ALLENCONN-001 (self-referential strongest projections in the mouse mesoscale
connectome).

Ground truth (established before release on the real streamed Allen Mouse Connectivity Atlas via
allensdk MouseConnectivityCache, 498 wild-type experiments, 316 summary structures, whole-structure
`projection_density`, source = primary injection structure mapped to its summary ancestor, entry =
mean projection_density over the experiments sharing that source; descriptor = fraction of source
regions whose STRONGEST target -- argmax over the 316 structures, the source's own structure
included -- is the source's own structure):

  self-strongest fraction, injection signal EXCLUDED (is_injection=False) : 0.357   (56/157)  <- honest
  self-strongest fraction, injection signal INCLUDED (default)           : 0.624   (98/157)  <- naive
  stable across aggregation: mean-over-experiments 0.357 / median 0.350; injection-in 0.624 / 0.643

The Allen structure-unionize records carry an `is_injection` flag. Records with is_injection=True
describe tracer signal INSIDE the injection site, which is saturated (median projection_density
~0.82) and is not a projection to a target region. Because the injection sits in the source's OWN
summary structure, leaving those saturated compartments in makes the self (diagonal) cell the
largest entry of the row for most sources, so the naive self-strongest fraction is ~0.62 -- an
artifact of the injection bolus. Reading projection signal only (is_injection=False) removes the
saturated self compartment; the source's own structure is then the strongest target for only ~0.36
of sources. The instruction never mentions the injection flag, saturation, masking, or self-loops;
whether the analysis excludes the saturated injection compartment is left to the analyst.

Why this descriptor (hardening 2026-09): the earlier "strong-connection density" descriptor had a
single lever -- inject-mask via `is_injection=False`, which is the standard, documented unionize
query and therefore too in-prior on its own. A measured second independent numeric lever does not
exist for that descriptor (self-loop exclusion moves the density by 0.0017 < the 0.0026 split-half
noise; the metric projection_density->normalized_projection_volume and the ipsi/contra/whole
hemisphere are strong but genuinely contested choices that must stay pinned). This descriptor is a
per-source ARGMAX statistic -- not the standard connectivity-matrix-density workflow -- so the
inject-mask reflex is less automatic, AND the artifact is dramatic and self-concentrated (the
saturated injection bolus sits on the diagonal), giving a large, robust naive/honest separation
(0.62 vs 0.36). The reported fraction is graded numerically: the injection-masked ~0.357 passes;
the injection-included ~0.62 fails.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.357        # injection-masked self-strongest fraction (used to pick the headline)
BAND_LO, BAND_HI = 0.28, 0.44   # passes 0.35-0.36 (mean/median); fails the naive ~0.62 and the
                                # normalized-projection-volume ~0.23 (a pinned-metric violation)

# a value the submission itself labels as the injection-included / naive contrast is never the
# reported honest headline
_EXCL = re.compile(r"injection_?incl|incl_?injection|naive|inflat|contrast|no_?mask|unmask|"
                   r"with_?injection|raw|contaminat|default", re.I)
_KEY = re.compile(r"self.*(frac|strong)|strong.*self|self_?strong|frac.*self", re.I)


def _json_frac_candidates():
    """Every fraction-like number under a self-strongest key in any JSON the run wrote (any depth),
    excluding the labelled injection-included / naive contrast."""
    cands = []

    def walk(obj, key=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, str(k))
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            if _KEY.search(key) and not _EXCL.search(key):
                v = float(obj)
                if v > 1.0:      # a percentage written as e.g. 35.7
                    v = v / 100.0
                if 0.0 <= v <= 1.0:
                    cands.append(v)

    for jf in sorted(OUT.glob("*.json")):
        try:
            walk(json.loads(jf.read_text(encoding="utf-8")))
        except Exception:
            continue
    return cands


def _findings_candidates():
    """Fraction-like numbers stated next to a 'strongest ... self / own' phrase in the prose."""
    cands = []
    p = OUT / "findings.md"
    if not p.exists():
        return cands
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"(?<!\d)(\d+(?:\.\d+)?)\s*%", text):
        cands.append(float(m.group(1)) / 100.0)
    for m in re.finditer(r"(?<!\d)0?\.\d+", text):
        v = float(m.group(0))
        if 0.0 <= v <= 1.0:
            cands.append(v)
    return cands


def test_matrix_computed():
    """A real directed projection-strength matrix was built (not fabricated numbers)."""
    import csv

    path = OUT / "connectivity_matrix.csv"
    assert path.exists(), "connectivity_matrix.csv missing"
    vals = []
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f):
            for cell in row:
                try:
                    vals.append(float(cell))
                except (ValueError, TypeError):
                    continue
    assert len(vals) >= 1000, f"connectivity_matrix.csv has too few numeric cells ({len(vals)})"
    assert all(-1e-6 <= v <= 1.0 + 1e-6 for v in vals), \
        "matrix holds values outside [0,1] (not projection densities)"
    frac_pos = sum(v > 1e-9 for v in vals) / len(vals)
    assert frac_pos > 0.05, "matrix is essentially all-zero"
    strong = sum(v > 0.1 for v in vals) / len(vals)
    assert strong < 0.4, f"matrix is implausibly dense ({strong:.3f} of cells strong)"


def test_self_strongest_fraction_reproduces():
    """The reported self-strongest fraction matches the injection-masked value, not the
    injection-included artifact (~0.62)."""
    cands = _json_frac_candidates()
    if not cands:
        cands = _findings_candidates()
    else:
        cands += _findings_candidates()
    assert cands, "no self-strongest-projection fraction found in self_projection.json / findings.md"
    best = min(cands, key=lambda c: abs(c - EXPECTED))
    assert BAND_LO <= best <= BAND_HI, (
        f"reported self-strongest fraction {best:.4f} is not the injection-masked value "
        f"(~{EXPECTED:.3f}; band [{BAND_LO}, {BAND_HI}]). Parsed values: "
        f"{sorted(set(round(c, 3) for c in cands))}. A value near 0.62 counts the saturated "
        f"injection-site compartment (is_injection=True) as a projection: because the injection sits "
        f"in the source's own structure, the self (diagonal) cell is spuriously the strongest target. "
        f"Excluding the injection compartment (is_injection=False) gives ~0.36.")
