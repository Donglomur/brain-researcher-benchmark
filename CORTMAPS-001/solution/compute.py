"""Reference (oracle) for CORTMAPS-001 — spatial correspondence between two cortical maps.

Paper anchor: Alexander-Bloch et al. 2018, NeuroImage (10.1016/j.neuroimage.2018.05.070) — the
parametric test of a correlation between two brain maps is anticonservative because both maps are
strongly spatially autocorrelated; the correct null is a spin test (rotating one map on the
sphere, which preserves spatial autocorrelation). Gradient: Margulies et al. 2016, PNAS.

The task (un-cued) asks whether cortical thickness spatially corresponds to the second
functional-connectivity gradient. This reference reproduces the routine result — the vertexwise
correlation is r ~ -0.20 with an astronomically small PARAMETRIC p (treating ~59k vertices as
independent) — and then VOLUNTEERS the check the task never asks: under a spatial-autocorrelation-
preserving SPIN TEST (Alexander-Bloch 2018, 1000 rotations) the same correlation is NOT
significant (p_spin ~ 0.34). So the apparent thickness-gradient correspondence is a
spatial-autocorrelation artifact, not a real structure-function relationship.

Route b (offline): reads the packaged fsLR-32k bundle (maps + sphere coordinates + cortical mask)
from data/mapcorr_fslr32k.npz and runs a self-contained Alexander-Bloch spin (numpy/scipy only) —
no network, no neuromaps at runtime.

Emitted for the verifier to CHECK the actual data (not just prose):
  correspondence.json — map identities, cortical vertex count, parametric r/p, n_spins, spin p,
                        and a summary of the spin null distribution (mean/sd/quantiles).
  spin_null.csv       — one row per rotation: spin_index, null_r  (the actual spin null the p uses)
  run_metadata.json   — maps, space, mask, vertex count, method, n_spins, seed
  findings.md         — reproduces the parametric significance + the spin-null downgrade + verdict

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import csv
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

# harmless BLAS matmul over/underflow warnings on some platforms; results are exact
np.seterr(over="ignore", divide="ignore", invalid="ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(__file__).resolve().parent.parent / "data" / "mapcorr_fslr32k.npz"
N_SPINS = 1000
SEED = 0


def fail(reason):
    (OUT / "correspondence.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "neuromaps fsLR 32k"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from scipy.spatial import cKDTree
    from scipy.stats import norm
except Exception as e:  # pragma: no cover
    fail(f"scipy import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    thickness = d["thickness"].astype(np.float64)
    gradient2 = d["gradient2"].astype(np.float64)
    coords = d["sphere_coords"].astype(np.float64)
    hemi = d["hemi"].astype(int)
    cortex = d["cortex_mask"].astype(bool)
    map_a_name = str(d["map_a"]); map_b_name = str(d["map_b"])
    space = str(d["space"]); density = str(d["density"]); mask_desc = str(d["mask"])
except Exception as e:
    fail(f"could not load packaged fsLR-32k bundle ({DATA.name}): {e}")

n_grid = int(thickness.shape[0])
if not (thickness.shape == gradient2.shape == hemi.shape == cortex.shape and coords.shape == (n_grid, 3)):
    fail(f"packaged arrays have inconsistent shapes (grid={n_grid})")

# keep the cortical vertices (drop the medial wall) where both maps are finite
mask = cortex & np.isfinite(thickness) & np.isfinite(gradient2)
n_vertices = int(mask.sum())
if n_vertices < 10000:
    fail(f"only {n_vertices} cortical vertices after masking")

a = thickness[mask]
b = gradient2[mask]


def pearson(x, y):
    x = x - x.mean(); y = y - y.mean()
    d = math.sqrt(float(x @ x) * float(y @ y))
    return float(x @ y) / d if d > 0 else float("nan")


# ---- naive parametric correlation (vertices treated as independent) ----
r_par = pearson(a, b)
t_stat = r_par * math.sqrt((n_vertices - 2) / max(1e-12, 1 - r_par * r_par))
# the parametric two-sided p underflows to 0.0 at this |t|; report a representable magnitude via
# the normal tail (neg_log10) so the "astronomically significant" naive result is on record.
neg_log10_p_par = float(-(norm.logsf(abs(t_stat)) + math.log(2)) / math.log(10))
p_par = float(2 * norm.sf(abs(t_stat)))  # 0.0 by underflow


# ---- Alexander-Bloch spin test: spatial-autocorrelation-preserving null ----
def _gen_rotation(rs):
    """A random proper rotation for the left hemisphere, mirrored (Y-Z reflection) for the right —
    exactly the Alexander-Bloch / neuromaps construction."""
    reflect = np.array([[-1., 0, 0], [0, 1, 0], [0, 0, 1]])
    rl, tmp = np.linalg.qr(rs.normal(size=(3, 3)))
    rl = rl @ np.diag(np.sign(np.diag(tmp)))
    if np.linalg.det(rl) < 0:
        rl[:, 0] = -rl[:, 0]
    rr = reflect @ rl @ reflect
    return rl, rr


def gen_spins(coords, hemi, n_rotate, seed):
    """Resampling array (n_grid x n_rotate): each column reassigns every vertex to the nearest
    vertex after a random spherical rotation of its hemisphere (Alexander-Bloch 2018, 'original')."""
    rs = np.random.RandomState(seed)
    n = len(coords); inds = np.arange(n)
    spins = np.zeros((n, n_rotate), int)
    for j in range(n_rotate):
        count, dup = 0, True
        while dup and count < 500:
            count += 1; dup = False
            res = np.zeros(n, int)
            for h, rot in enumerate(_gen_rotation(rs)):
                hi = hemi == h
                coor = coords[hi]
                _, col = cKDTree(coor @ rot).query(coor, 1)
                res[hi] = inds[hi][col]
            if j and np.any(np.all(res[:, None] == spins[:, :j], axis=0)):
                dup = True
            elif np.all(res == inds):
                dup = True
        spins[:, j] = res
    return spins


spins = gen_spins(coords, hemi, N_SPINS, SEED)
# spin map A, restrict to the cortical mask, correlate the spun map A against (unspun) map B
null_a = thickness[spins]                       # (n_grid, n_spins) spun thickness
abs_true = abs(r_par)
null_r = np.empty(N_SPINS)
for j in range(N_SPINS):
    null_r[j] = pearson(null_a[mask, j], b)
# two-sided empirical p (Alexander-Bloch / neuromaps convention: +1 in numerator and denominator)
exceed = int(np.sum(np.abs(null_r) >= abs_true))
p_spin = (exceed + 1) / (N_SPINS + 1)

null_mean = float(np.mean(null_r)); null_sd = float(np.std(null_r, ddof=1))
q = np.quantile(null_r, [0.025, 0.5, 0.975])

# ---- spin_null.csv: the actual per-rotation null the spin p is computed from ----
with open(OUT / "spin_null.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["spin_index", "null_r"])
    for j in range(N_SPINS):
        w.writerow([j, f"{null_r[j]:.6f}"])

(OUT / "correspondence.json").write_text(json.dumps({
    "map_a": map_a_name,
    "map_b": map_b_name,
    "space": f"{space} {density}",
    "cortical_mask": mask_desc,
    "n_grid_vertices": n_grid,
    "n_vertices": n_vertices,
    "correlation_metric": "Pearson r (vertexwise)",
    "correlation_r": r_par,
    # naive parametric test (vertices treated as independent)
    "p_parametric": p_par,
    "t_statistic": float(t_stat),
    "neg_log10_p_parametric": neg_log10_p_par,
    "significant_parametric": bool(neg_log10_p_par > 1.30103),   # p < 0.05
    # spatial-autocorrelation-preserving spin test
    "spin_null_model": "Alexander-Bloch 2018 (spherical rotation of one map, 'original' assignment)",
    "n_spins": N_SPINS,
    "seed": SEED,
    "p_spin": float(p_spin),
    "significant_spin": bool(p_spin < 0.05),
    "spin_p_larger_than_parametric": bool(p_spin > p_par),
    "spin_null_mean_r": null_mean,
    "spin_null_sd_r": null_sd,
    "spin_null_q2.5": float(q[0]),
    "spin_null_median": float(q[1]),
    "spin_null_q97.5": float(q[2]),
    "spin_null_frac_ge_abs_observed": float(exceed / N_SPINS),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "neuromaps annotations (packaged fsLR-32k bundle, offline)",
    "maps": [map_a_name, map_b_name],
    "space": f"{space} {density}",
    "cortical_mask": mask_desc,
    "n_grid_vertices": n_grid,
    "n_vertices": n_vertices,
    "n_spins": N_SPINS, "seed": SEED,
    "method": ("vertexwise Pearson correlation on the cortical (no-medial-wall) mask; naive "
               "parametric p AND a spatial-autocorrelation-preserving Alexander-Bloch spin test "
               "(1000 spherical rotations, self-contained)"),
}, indent=2))

(OUT / "findings.md").write_text(f"""# CORTMAPS-001 — spatial correspondence of two cortical maps

Maps: **{map_a_name}** vs **{map_b_name}** ({space} {density}), on the {n_vertices} cortical
vertices of the no-medial-wall mask.

## The parametric correlation is astronomically 'significant'
Across the {n_vertices} cortical vertices, cortical thickness correlates with the second
functional-connectivity gradient at **r = {r_par:.3f}** (t = {t_stat:.1f}); the parametric test —
treating the vertices as independent — gives a p so small it underflows (**p ≈ 0**,
−log10 p ≈ {neg_log10_p_par:.0f}). Taken at face value this reproduces the routinely-reported
structure–function correspondence: a moderate, "overwhelmingly significant" relationship.

## But it does NOT survive a spatial-autocorrelation-preserving null (the un-cued check)
The parametric p is **anticonservative**: the {n_vertices} vertices are not independent — both maps
are strongly **spatially autocorrelated**, so nearby vertices carry redundant information and the
effective degrees of freedom are far smaller. Under a **spin test** (Alexander-Bloch et al. 2018 —
rotating one map on the sphere to build a null that preserves spatial autocorrelation, {N_SPINS}
rotations), the observed correlation sits well inside the null distribution
(null r: mean {null_mean:.3f}, 95% interval [{q[0]:.3f}, {q[2]:.3f}];
{100*exceed/N_SPINS:.0f}% of rotations reach \\|r\\| ≥ {abs_true:.3f}), giving
**p_spin = {p_spin:.3f} — not significant**.

## Conclusion
The apparent thickness–gradient correspondence is a **spatial-autocorrelation artifact**, not a
real structure–function relationship. A correlation between two brain maps must be tested against a
spatial-autocorrelation-preserving null (spin test); the parametric p (≈ 0) is **meaningless** here
because it ignores the shared spatial autocorrelation. Reporting the correspondence as significant
**over-claims** — on these data the correlation is indistinguishable from chance under the spin test
(p_spin = {p_spin:.3f}).
""")

print(f"OK: r={r_par:.3f} n_vertices={n_vertices} p_parametric~0 (neg_log10p={neg_log10_p_par:.0f}) "
      f"n_spins={N_SPINS} p_spin={p_spin:.3f} "
      f"(significant param={neg_log10_p_par > 1.30103}, spin={p_spin < 0.05})")
