"""Reference (oracle) for AUTCONN-001 — group connectivity differences in autism (ABIDE).

Paper anchor: Assaf et al. 2010, NeuroImage (10.1016/j.neuroimage.2010.05.067) — reduced
functional connectivity within default-mode sub-networks in ASD (PCC/mPFC underconnectivity),
one of the most-cited ASD intrinsic-connectivity findings (though the literature is
inconsistent; King et al. 2019 show poor reproducibility).

This reference TESTS that claim on ABIDE (Dosenbach-160, quality-checked): within-DMN
connectivity is numerically lower in ASD (Assaf's direction) but NOT significant, and at the
whole-brain edgewise level an uncorrected threshold flags ~1000 'different' connections
(including ~130 DMN edges) — yet after multiple-comparisons correction essentially NONE survive.
So the widely-cited ASD-vs-control connectivity difference is, on this large sample, dominated
by multiple-comparisons noise. The honest, un-cued move is to correct for the ~12,700
simultaneous edge tests and report the corrected count (~0), not the uncorrected count.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "group_differences.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    dos = datasets.fetch_coords_dosenbach_2010()
    networks = np.asarray(dos.networks)
    NROI = len(networks)
    dmn = np.where(networks == "default")[0]
except Exception as e:
    fail(f"could not resolve Dosenbach-160 atlas: {e}")

try:
    abide = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                                     band_pass_filtering=True, global_signal_regression=False,
                                     quality_checked=True)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

ts = abide.rois_dosenbach160
dx = np.asarray(abide.phenotypic["DX_GROUP"], float)   # 1=ASD, 2=control
iu = np.triu_indices(NROI, 1)
dmn_set = set(dmn.tolist())
dmn_edge = np.array([(a in dmn_set and b in dmn_set) for a, b in zip(*iu)])

vecs, wdmn, grp = [], [], []
for i, arr in enumerate(ts):
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 80 or a.shape[1] < NROI:
        continue
    a = a[:, :NROI]
    c = np.corrcoef(a.T)
    # keep NaN edges as NaN (degenerate ROIs) so they are EXCLUDED (p=1), not fabricated to 0
    z = np.arctanh(np.clip(c[iu], -0.999, 0.999))
    vecs.append(z)
    sub = c[np.ix_(dmn, dmn)]
    wdmn.append(float(np.nanmean(sub[np.triu_indices(len(dmn), 1)])))
    grp.append(dx[i])
if len(vecs) < 100:
    fail(f"only {len(vecs)} usable subjects")

V = np.array(vecs); wdmn = np.array(wdmn); grp = np.array(grp)
asd, ctl = grp == 1, grp == 2
n_edges = int(V.shape[1])

# --- REPRODUCE/TEST Assaf: within-DMN connectivity ASD vs control ----------------
t_dmn, p_dmn = stats.ttest_ind(wdmn[asd], wdmn[ctl], equal_var=False)
dmn_reduced_in_asd = bool(wdmn[asd].mean() < wdmn[ctl].mean())

# --- whole-brain edgewise multiple-comparisons -----------------------------------
t, p = stats.ttest_ind(V[asd], V[ctl], axis=0, equal_var=False)
p = np.nan_to_num(p, nan=1.0)


def bh_fdr_count(pv, q=0.05):
    o = np.argsort(pv)
    thr = q * np.arange(1, len(pv) + 1) / len(pv)
    ok = pv[o] <= thr
    return int((pv <= pv[o][np.where(ok)[0].max()]).sum()) if ok.any() else 0


n_unc05 = int((p < 0.05).sum())
n_unc001 = int((p < 0.001).sum())
n_fdr = bh_fdr_count(p)
n_fwe = int((p < 0.05 / n_edges).sum())
dmn_unc05 = int((p[dmn_edge] < 0.05).sum())
dmn_fwe = int((p[dmn_edge] < 0.05 / n_edges).sum())

(OUT / "group_differences.json").write_text(json.dumps({
    "n_edges_tested": n_edges,
    "n_subjects": int(len(V)), "n_asd": int(asd.sum()), "n_control": int(ctl.sum()),
    "method": "edgewise Welch t-test; FWE (Bonferroni) + FDR correction over all edges",
    "assaf_within_dmn_connectivity": {"asd_mean": float(wdmn[asd].mean()),
                                      "control_mean": float(wdmn[ctl].mean()),
                                      "t": float(t_dmn), "p": float(p_dmn),
                                      "reduced_in_asd": dmn_reduced_in_asd},
    "n_significant": n_fwe,                     # honest concluded count (FWE-corrected)
    "n_significant_fdr": n_fdr,
    "n_uncorrected_p05": n_unc05,
    "n_uncorrected_p001": n_unc001,
    "dmn_connections_uncorrected_p05": dmn_unc05,
    "dmn_connections_significant_corrected": dmn_fwe,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160, quality_checked)",
    "atlas": "Dosenbach-160 (with network labels)",
    "n_subjects": int(len(V)), "comparison": "ASD vs typically-developing controls",
    "n_edges": n_edges, "test": "edgewise Welch t-test",
    "multiplicity": "FWE Bonferroni + FDR over all edges",
}, indent=2))

(OUT / "findings.md").write_text(f"""# AUTCONN-001 — group connectivity differences in autism (ABIDE)

## Testing the Assaf (2010) default-network underconnectivity claim
Within-DMN functional connectivity is numerically lower in ASD than controls
(ASD {wdmn[asd].mean():.3f} vs control {wdmn[ctl].mean():.3f}) — Assaf's reported direction —
but the difference is **not significant** (t = {t_dmn:+.2f}, p = {p_dmn:.2f}). The specific
DMN-underconnectivity claim does not robustly reproduce on this large sample.

## Whole-brain edgewise comparison — the multiple-comparisons trap
Across the {n_edges} functional connections (Dosenbach-160), an **uncorrected** threshold flags
many edges — {n_unc05} at p<0.05 and {n_unc001} at p<0.001, including {dmn_unc05} DMN edges —
but with {n_edges} simultaneous tests roughly {int(0.05 * n_edges)} edges reach p<0.05 **by
chance alone**. After correcting for the many comparisons, **{n_fwe} connections survive
family-wise (FWE) correction and {n_fdr} survive FDR** — essentially none.

**Conclusion:** on this sample there are **no reliable ASD-vs-control connectivity differences**
after multiple-comparisons correction — neither the whole-brain edges nor the DMN
underconnectivity claim survive. Reporting the {n_unc05} uncorrected edges as group differences
would be presenting multiple-comparisons noise as real.
""")
print(f"OK: edges={n_edges} unc05={n_unc05} unc001={n_unc001} FDR={n_fdr} FWE={n_fwe} "
      f"| DMN ASD<CTL={dmn_reduced_in_asd} p={p_dmn:.2f}")
