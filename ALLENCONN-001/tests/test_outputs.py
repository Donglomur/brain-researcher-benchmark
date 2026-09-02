"""Grading checks for ALLENCONN-001 (mouse mesoscale projection-connectome density).

Ground truth (established before release on the Allen Mouse Connectivity Atlas via
allensdk MouseConnectivityCache, 498 wild-type experiments, the 316 summary structures,
whole-structure `projection_density`, strong-connection threshold 0.1):

  strong-connection fraction, injection-site signal EXCLUDED  : 0.0234   (1162 / 49612)
  strong-connection fraction, injection-site signal INCLUDED  : ~0.045 - 0.050

The Allen structure-unionize records carry an `is_injection` flag. Records with
is_injection=True describe tracer signal *inside the injection site*, which is saturated
(median projection_density ~0.82 vs ~0.0001 for genuine projection targets, ~7000x) and is
not a projection to a target region. Counting those compartments as connections roughly
DOUBLES the strong-connection fraction (0.0234 -> ~0.05). The projection density in genuine
target regions almost never exceeds 0.1, so the saturated injection compartments dominate
the "strong" count when they are not excluded. A correct connectome measures projection
signal only (is_injection=False); a naive one leaves the injection-site compartments in and
over-reports the density. The split-half gap between the two is stable (~0.024).

The reported fraction is graded numerically: the injection-masked value 0.0234 passes; the
injection-included ~0.05 fails. (The instruction never mentions the injection flag; whether
the analysis excludes the saturated injection compartments is left to the analyst.)
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.0234   # injection-masked strong-connection fraction
TOL = 0.008         # fails the injection-included ~0.045-0.050 by a wide margin


def _json_frac_candidates():
    """Every number under a key mentioning 'frac' in any JSON the run wrote (any depth)."""
    cands = []

    def walk(obj, key=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, str(k))
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            if "frac" in key.lower():
                v = float(obj)
                if v > 1.0:      # a percentage written as e.g. 2.34
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
    """Fraction-like numbers in the prose write-up: percentages and decimals."""
    cands = []
    p = OUT / "findings.md"
    if not p.exists():
        return cands
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"(?<!\d)(\d+(?:\.\d+)?)\s*%", text):    # "2.3%" -> 0.023
        cands.append(float(m.group(1)) / 100.0)
    for m in re.finditer(r"(?<!\d)0?\.\d+", text):               # standalone decimals like 0.0234
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
    # projection densities are fractions in [0, 1]; a genuine connectome matrix has many
    # cells, is sparse, and is not all-zero.
    assert len(vals) >= 1000, f"connectivity_matrix.csv has too few numeric cells ({len(vals)})"
    assert all(-1e-6 <= v <= 1.0 + 1e-6 for v in vals), "matrix holds values outside [0,1] (not projection densities)"
    frac_pos = sum(v > 1e-9 for v in vals) / len(vals)
    assert frac_pos > 0.05, "matrix is essentially all-zero"
    strong = sum(v > 0.1 for v in vals) / len(vals)
    assert strong < 0.4, f"matrix is implausibly dense ({strong:.3f} of cells strong)"


def test_strong_fraction_reproduces():
    """The reported strong-connection fraction matches the injection-masked value."""
    cands = _json_frac_candidates()
    if not cands:
        cands = _findings_candidates()
    else:
        cands += _findings_candidates()   # allow the prose value too, but json 'frac' is primary
    assert cands, "no strong-connection fraction found in strong_fraction.json / findings.md"
    best = min(cands, key=lambda c: abs(c - EXPECTED))
    assert abs(best - EXPECTED) < TOL, (
        f"reported strong-connection fraction {best:.4f} is not the injection-masked value "
        f"{EXPECTED:.4f} (tol {TOL}). The injection-site compartments (is_injection=True) are "
        f"saturated and must be excluded; leaving them in roughly doubles the fraction to ~0.05.")
