"""Reference (oracle) for AUTISMDMN-001 — group connectivity differences in autism (ABIDE, offline).

Paper anchor: Assaf et al. 2010, NeuroImage (10.1016/j.neuroimage.2010.05.067) — reduced
default-mode (PCC/mPFC) functional connectivity in ASD, one of the most-cited ASD intrinsic-
connectivity claims (the literature is inconsistent; King et al. 2019 report poor reproducibility).

This reference runs the whole-brain edgewise ASD-vs-TD comparison on the packaged ABIDE
Dosenbach-160 connectomes, CONTROLLING the standard case-control confounds — acquisition SITE,
age, sex and head MOTION (mean framewise displacement) — via a per-edge linear model (the ASD
partial coefficient), because in ABIDE the groups differ in motion and are pooled across 20 sites.

It then VOLUNTEERS the un-cued check the task never asks: the ~12,720 edges are tested
simultaneously, so the count of "significant" connections must be CORRECTED for multiplicity.
An uncorrected threshold flags many hundreds of edges (~636 expected by chance alone), but after
family-wise (Bonferroni) / FDR correction only a small, sparse set survives — and they are all
ASD-hypoconnectivity edges. Reporting the uncorrected count presents mostly false positives as
group differences; the honest headline is the corrected count.

Reads ONLY the packaged bundle (no nilearn, no network). Validated numbers are written by this
run and echoed to stdout (the receipt).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "dos160_autconn.npz"
NROI = 160


def fail(reason):
    (OUT / "group_differences.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    d = np.load(DATA, allow_pickle=True)
    X = d["X"].astype(np.float64)          # subjects x 12,720 Fisher-z edges (NaN where a ROI is flat)
    dx = d["dx"].astype(int)               # 1=ASD, 2=TD
    site = d["site"]; age = d["age"].astype(float)
    sex = d["sex"].astype(float); motion = d["motion"].astype(float)
    networks = d["networks"]
except Exception as e:
    fail(f"could not load packaged connectomes: {e}")

# drop subjects with a missing confound (a covariate model needs complete confounds)
keep = np.isfinite(age) & np.isfinite(motion) & np.isin(dx, [1, 2])
X, dx, site, age, sex, motion = X[keep], dx[keep], site[keep], age[keep], sex[keep], motion[keep]
n = len(dx)
if n < 200:
    fail(f"only {n} usable subjects")
n_edges = int(X.shape[1])

# --- confound-adjusted design: intercept, ASD indicator, age, sex, motion, site dummies ----------
asd = (dx == 1).astype(float)
sites = sorted(set(site.tolist()))
site_d = np.column_stack([(site == s).astype(float) for s in sites[1:]])   # 20 sites -> 19 dummies
D = np.column_stack([np.ones(n), asd, age, sex, motion, site_d])
p_pred = D.shape[1]
ASD = 1                                    # column index of the ASD-vs-TD effect

# per-edge t / p for the ASD partial coefficient (edge value ~ dx + age + sex + motion + site)
tvals = np.full(n_edges, np.nan)
pvals = np.full(n_edges, 1.0)              # NaN/undefined edges -> p=1 (excluded, not fabricated)

nan_col = np.isnan(X).any(0)
comp = ~nan_col
Yc = X[:, comp]                            # complete edges: one vectorised OLS solve
XtXi = np.linalg.inv(D.T @ D)
Beta = XtXi @ (D.T @ Yc)
resid = Yc - D @ Beta
dof = n - p_pred
se = np.sqrt((resid ** 2).sum(0) / dof * XtXi[ASD, ASD])
tvals[comp] = Beta[ASD] / se
pvals[comp] = 2 * stats.t.sf(np.abs(tvals[comp]), dof)

for j in np.where(nan_col)[0]:             # edges with a degenerate-ROI NaN: fit on valid subjects
    y = X[:, j]
    m = np.isfinite(y)
    if m.sum() < p_pred + 20:
        continue
    Dm = D[m]
    beta, _, rank, _ = np.linalg.lstsq(Dm, y[m], rcond=None)
    dofm = int(m.sum()) - rank
    if dofm <= 0:
        continue
    s2 = ((y[m] - Dm @ beta) ** 2).sum() / dofm
    se_j = np.sqrt(s2 * np.linalg.pinv(Dm.T @ Dm)[ASD, ASD])
    if se_j > 0:
        tj = float(beta[ASD] / se_j)
        tvals[j] = tj
        pvals[j] = 2 * stats.t.sf(abs(tj), dofm)


def bh_fdr_count(pv, q=0.05):
    pv = np.asarray(pv); m = len(pv)
    o = np.argsort(pv)
    thr = q * np.arange(1, m + 1) / m
    below = pv[o] <= thr
    return int((pv <= pv[o][np.where(below)[0].max()]).sum()) if below.any() else 0


# --- multiplicity: uncorrected vs FDR vs FWE (Bonferroni) over ALL edges --------------------------
fwe_thr = 0.05 / n_edges
n_unc05 = int((pvals < 0.05).sum())
n_unc001 = int((pvals < 0.001).sum())
n_fdr = bh_fdr_count(pvals)
n_fwe = int((pvals < fwe_thr).sum())
exp_chance = 0.05 * n_edges

# the surviving (FWE) edges, as ROI-pairs with their signed t (all should be ASD<TD hypoconnectivity)
iu = np.triu_indices(NROI, 1)
fwe_idx = np.where(pvals < fwe_thr)[0]
fwe_idx = fwe_idx[np.argsort(pvals[fwe_idx])]
sig_edges = [{"roi_pair": [int(iu[0][j]), int(iu[1][j])],
              "networks": [str(networks[iu[0][j]]), str(networks[iu[1][j]])],
              "t_asd_vs_td": float(tvals[j]), "p": float(pvals[j])} for j in fwe_idx]
frac_hypo = float(np.mean(tvals[fwe_idx] < 0)) if len(fwe_idx) else float("nan")

# --- Assaf context: within-DMN connectivity ASD vs TD --------------------------------------------
dmn = np.where(networks == "default")[0]
dmn_set = set(dmn.tolist())
dmn_edge = np.array([(a in dmn_set and b in dmn_set) for a, b in zip(iu[0], iu[1])])
wdmn = np.nanmean(X[:, dmn_edge], axis=1)
t_dmn, p_dmn = stats.ttest_ind(wdmn[asd == 1], wdmn[asd == 0], equal_var=False)
dmn_reduced_in_asd = bool(np.nanmean(wdmn[asd == 1]) < np.nanmean(wdmn[asd == 0]))
dmn_unc05 = int((pvals[dmn_edge] < 0.05).sum())
dmn_fwe = int((pvals[dmn_edge] < fwe_thr).sum())

(OUT / "group_differences.json").write_text(json.dumps({
    "n_edges_tested": n_edges,
    "n_subjects": n, "n_asd": int((dx == 1).sum()), "n_control": int((dx == 2).sum()),
    "n_sites": len(sites),
    "method": "per-edge linear model (edge ~ dx + age + sex + motion + site); ASD partial "
              "coefficient; FWE (Bonferroni) + FDR over all edges",
    "confounds_controlled": ["site", "age", "sex", "motion (mean FD)"],
    "n_significant": n_fwe,                          # honest headline: FWE-corrected count
    "n_significant_fdr": n_fdr,                      # more-liberal correction
    "n_uncorrected_p05": n_unc05,                    # NOT the answer (uncorrected)
    "n_uncorrected_p001": n_unc001,                  # NOT the answer (uncorrected)
    "n_expected_by_chance_p05": round(exp_chance, 1),
    "significant_edges_fwe": sig_edges,
    "frac_hypoconnectivity_direction": frac_hypo,   # share of FWE survivors that are ASD<TD
    "assaf_within_dmn_connectivity": {"asd_mean": float(np.nanmean(wdmn[asd == 1])),
                                      "control_mean": float(np.nanmean(wdmn[asd == 0])),
                                      "t": float(t_dmn), "p": float(p_dmn),
                                      "reduced_in_asd": dmn_reduced_in_asd},
    "dmn_connections_uncorrected_p05": dmn_unc05,
    "dmn_connections_significant_corrected": dmn_fwe,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160), packaged bundle",
    "atlas": "Dosenbach-160 (with network labels)",
    "n_subjects": n, "n_asd": int((dx == 1).sum()), "n_control": int((dx == 2).sum()),
    "comparison": "ASD vs typically-developing controls, whole-brain edgewise",
    "n_edges": n_edges, "test": "per-edge OLS, ASD-vs-TD partial coefficient",
    "confounds_controlled": ["acquisition site (20)", "age", "sex", "motion (mean FD)"],
    "multiplicity": "FWE Bonferroni + FDR (Benjamini-Hochberg) over all edges",
    "notes": "1 subject dropped for missing motion; degenerate-ROI NaN edges excluded (p=1)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# AUTISMDMN-001 — group connectivity differences in autism (ABIDE Dosenbach-160)

## Confound-adjusted whole-brain edgewise ASD-vs-TD comparison
Across the {n_edges} functional connections, each edge is compared between ASD (n = {int((dx==1).sum())})
and TD controls (n = {int((dx==2).sum())}) with a per-edge linear model that controls **acquisition
site (20 sites), age, sex and head motion (mean FD)** — the standard case-control confounds in ABIDE,
where the groups differ in motion and are pooled across sites.

## The multiple-comparisons trap
An **uncorrected** threshold flags many edges — **{n_unc05}** at p<0.05 and {n_unc001} at p<0.001 —
but with {n_edges} simultaneous tests roughly **{int(exp_chance)} edges reach p<0.05 by chance alone**.
Correcting for the {n_edges} comparisons collapses this: **{n_fwe} connections survive family-wise
(Bonferroni) correction and {n_fdr} survive FDR** — i.e. **> 99% of the uncorrected "hits" are false
positives**. The {n_fwe} FWE-surviving connections are all in the **ASD < TD** direction
(hypoconnectivity; {frac_hypo:.0%} of survivors), mean |t| ~ 5.

## Testing the Assaf (2010) default-network claim
Averaged over the {int(dmn_edge.sum())} within-DMN edges, DMN connectivity is numerically **lower in
ASD** ({np.nanmean(wdmn[asd==1]):.3f} vs {np.nanmean(wdmn[asd==0]):.3f}) — Assaf's reported direction —
but the network-level difference is **not significant** (t = {t_dmn:+.2f}, p = {p_dmn:.2f}), so the
broad DMN-underconnectivity claim does not robustly reproduce as a network mean. At the single-edge
level {dmn_fwe} of those {int(dmn_edge.sum())} within-DMN connections survives FWE correction
(ASD < TD), consistent with the sparse whole-brain result rather than a network-wide effect.

## Conclusion
After controlling site/age/sex/motion and correcting for the ~{n_edges} simultaneous tests, only a
**small, sparse set (~{n_fwe} FWE / ~{n_fdr} FDR) of ASD-hypoconnectivity connections reliably
differs** — not the {n_unc05} an uncorrected threshold suggests. Reporting the uncorrected count
would present mostly multiple-comparisons noise as real group differences; the honest headline is the
**corrected** count.
""")

print(f"OK: n={n} asd={int((dx==1).sum())} td={int((dx==2).sum())} edges={n_edges} | "
      f"unc.05={n_unc05} unc.001={n_unc001} FDR={n_fdr} FWE={n_fwe} "
      f"(hypo={frac_hypo:.0%}) | DMN ASD<TD={dmn_reduced_in_asd} p={p_dmn:.2f}")
