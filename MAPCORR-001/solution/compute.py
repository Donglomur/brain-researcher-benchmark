"""Reference (oracle) for MAPCORR-001 — spatial correspondence between two cortical maps.

Paper anchor: Alexander-Bloch et al. 2018, NeuroImage (10.1016/j.neuroimage.2018.05.070) — a
parametric test of the correlation between two brain maps is anticonservative because both maps
are spatially autocorrelated; the correct null is a spin test (rotating one map on the sphere,
preserving spatial autocorrelation). Gradient: Margulies et al. 2016, PNAS.

The task (un-cued) asks whether cortical thickness spatially corresponds to the second
functional-connectivity gradient. This reference computes the correlation — which is strongly
'significant' by the parametric test (r ~ -0.20, p ~ 0, treating 32k vertices as independent) —
and then VOLUNTEERS the check the task never asks: under a spin test (spatial-autocorrelation-
preserving null) the correlation is NOT significant (p ~ 0.3). So the apparent correspondence is
a spatial-autocorrelation artifact, not a real structure-function relationship.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "correspondence.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from scipy.stats import pearsonr
    from neuromaps.datasets import fetch_annotation
    from neuromaps import nulls, stats, images
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    map_a = fetch_annotation(source="hcps1200", desc="thickness", space="fsLR", den="32k")
    map_b = fetch_annotation(source="margulies2016", desc="fcgradient02", space="fsLR", den="32k")
except Exception as e:
    fail(f"could not fetch cortical maps (neuromaps/OSF): {e}")

da = images.load_data(map_a).astype(float)
db = images.load_data(map_b).astype(float)
m = np.isfinite(da) & np.isfinite(db) & (da != 0) & (db != 0)
n_vertices = int(m.sum())

r_par, p_par = pearsonr(da[m], db[m])

try:
    rot = nulls.alexander_bloch(map_a, atlas="fsLR", density="32k", n_perm=1000, seed=0)
    r_spin, p_spin = stats.compare_images(map_a, map_b, nulls=rot, metric="pearsonr")
except Exception as e:
    fail(f"spin-test null failed: {e}")

(OUT / "correspondence.json").write_text(json.dumps({
    "map_a": "cortical thickness (HCP S1200, fsLR 32k)",
    "map_b": "2nd functional connectivity gradient (Margulies 2016, fsLR 32k)",
    "n_vertices": n_vertices,
    "correlation_r": float(r_par),
    "p_parametric": float(p_par),
    "p_spin": float(p_spin),
    "spin_null_model": "Alexander-Bloch 2018 (spherical rotation, 1000 perms)",
    "significant_parametric": bool(p_par < 0.05),
    "significant_spin": bool(p_spin < 0.05),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "maps": ["HCP cortical thickness", "Margulies-2016 gradient 2"],
    "space": "fsLR 32k", "n_vertices": n_vertices,
    "method": "vertexwise Pearson correlation; parametric p AND Alexander-Bloch spin-test p (1000 rotations)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# MAPCORR-001 — spatial correspondence of two cortical maps

## The parametric correlation is strongly 'significant'
Across {n_vertices} cortical vertices (fsLR 32k), cortical thickness correlates with the second
functional-connectivity gradient at **r = {r_par:.3f}**, and the parametric test gives
**p = {p_par:.1e}** — apparently overwhelming evidence for a structure-function correspondence.

## But it does NOT survive a spatial null (the un-cued check)
The parametric p treats the {n_vertices} vertices as independent, which they are not — both maps
are strongly **spatially autocorrelated**, so the parametric test is anticonservative. Under a
**spin test** (Alexander-Bloch et al. 2018 — rotating one map on the sphere to preserve spatial
autocorrelation, 1000 rotations), the correlation is **not significant: p_spin = {p_spin:.3f}**.

## Conclusion
The apparent thickness–gradient correspondence is a **spatial-autocorrelation artifact**, not a
real structure-function relationship. A correlation between two brain maps must be tested against
a spatial-autocorrelation-preserving null (spin test); the parametric p (p = {p_par:.1e}) is
meaningless here. Reporting the correspondence as significant over-claims.
""")
print(f"OK: r={r_par:.3f} p_parametric={p_par:.1e} p_spin={p_spin:.3f} "
      f"(significant param={p_par < 0.05}, spin={p_spin < 0.05})")
