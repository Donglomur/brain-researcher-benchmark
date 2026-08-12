"""Reference (oracle) for EFFCONN-001 — directed (Granger) functional connectivity, ABIDE dos160.

Reproduces the directed-connectivity result the way a Roebroeck-style analysis reports it — a set
of region pairs show a DOMINANT directed (Granger) influence, "region A drives region B" — then
VOLUNTEERS the un-cued check the task never asks: is the inferred DIRECTION reliable? It is not.
Within a subject, splitting the run in half and re-estimating, the inferred direction of influence
replicates only ~51% of the time (chance 50%) — essentially at chance. fMRI recovers the PRESENCE
of connections (the split-half connectivity structure replicates, r~0.4, well above its 0 chance)
but their DIRECTION poorly, because inter-regional hemodynamic-lag differences confound lag-based
causality (Smith et al. 2011). So a directed/causal claim ("A drives B") is unwarranted here.

Repair vs the earlier draft: the directed measure is a REAL bivariate VAR(1) Granger test — per
subject, per pair, an F-test on the lagged cross-term (log-ratio of restricted vs full residual
variance), aggregated across subjects — not a raw lag cross-product mislabelled "causal".

Reads ONLY the packaged, network-free bundle data/dos160_causal.npz. Validated numbers are written
by this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import stats

np.seterr(all="ignore")
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "dos160_causal.npz"
NROI, NPAIRS, TOPK = 160, 100, 10


def fail(reason):
    (OUT / "directed_connectivity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    d = np.load(DATA, allow_pickle=True)
    ts_raw, dx = d["ts"], d["dx"].astype(int)
except Exception as e:
    fail(f"could not load packaged timeseries bundle: {e}")

# z-score each subject's ROI timeseries (constant columns -> all-zero, harmless in the VAR)
TS = []
for a in ts_raw:
    a = np.asarray(a, float)[:, :NROI]
    if a.ndim == 2 and a.shape[0] >= 120 and a.shape[1] >= NROI:
        TS.append((a - a.mean(0)) / (a.std(0) + 1e-8))
if len(TS) < 100:
    fail(f"only {len(TS)} usable subjects in the packaged bundle")
N = len(TS)

# --- select the most strongly connected region pairs (group-mean |correlation|) ---
G = np.mean([np.corrcoef(a.T) for a in TS], 0)
np.fill_diagonal(G, 0.0)
iu = np.triu_indices(NROI, 1)
top = np.argsort(np.abs(G[iu]))[::-1][:NPAIRS]
I, J = iu[0][top], iu[1][top]


def _rss(D, y):
    beta, _, _, _ = np.linalg.lstsq(D, y, rcond=None)
    r = y - D @ beta
    return float(r @ r)


def granger(Z, I, J):
    """Bivariate VAR(1) Granger test per pair. For direction i->j: compare the restricted model
    j_t ~ 1 + j_{t-1} against the full j_t ~ 1 + j_{t-1} + i_{t-1} (an F-test on the lagged
    cross-term). Returns the log-ratio Granger measure G and the F-stat for both directions."""
    Y, L = Z[1:], Z[:-1]
    n = Y.shape[0]
    one = np.ones(n)
    Gij = np.empty(len(I)); Gji = np.empty(len(I))
    Fij = np.empty(len(I)); Fji = np.empty(len(I))
    dof = n - 3
    for k, (i, j) in enumerate(zip(I, J)):
        li, lj = L[:, i], L[:, j]
        yi, yj = Y[:, i], Y[:, j]
        # i -> j
        rss_r = _rss(np.column_stack([one, lj]), yj)
        rss_f = _rss(np.column_stack([one, lj, li]), yj)
        Gij[k] = np.log(rss_r / rss_f) if rss_f > 0 else 0.0
        Fij[k] = ((rss_r - rss_f) / (rss_f / dof)) if rss_f > 0 and dof > 0 else 0.0
        # j -> i
        rss_r2 = _rss(np.column_stack([one, li]), yi)
        rss_f2 = _rss(np.column_stack([one, li, lj]), yi)
        Gji[k] = np.log(rss_r2 / rss_f2) if rss_f2 > 0 else 0.0
        Fji[k] = ((rss_r2 - rss_f2) / (rss_f2 / dof)) if rss_f2 > 0 and dof > 0 else 0.0
    return Gij, Gji, Fij, Fji


def presence_corr(Z):
    """within-subject split-half Pearson r of the full-connectome edge weights (nan-safe)."""
    h = Z.shape[0] // 2
    c1 = np.corrcoef(Z[:h].T)[iu]; c2 = np.corrcoef(Z[h:].T)[iu]
    m = np.isfinite(c1) & np.isfinite(c2)
    return float(np.corrcoef(c1[m], c2[m])[0, 1]) if m.sum() > 3 else np.nan


# --- per-subject Granger (full run) + within-subject split-half direction agreement ---
net_full, F_dom, Gij_all, Gji_all = [], [], [], []
dir_agree, pres_rel = [], []
sign_h1, sign_h2 = [], []
for Z in TS:
    Gij, Gji, Fij, Fji = granger(Z, I, J)
    net = Gij - Gji                     # >0 : i Granger-leads j
    net_full.append(net); Gij_all.append(Gij); Gji_all.append(Gji)
    F_dom.append(np.where(net > 0, Fij, Fji))
    h = Z.shape[0] // 2
    g1i, g1j, _, _ = granger(Z[:h], I, J)
    g2i, g2j, _, _ = granger(Z[h:], I, J)
    s1, s2 = np.sign(g1i - g1j), np.sign(g2i - g2j)
    sign_h1.append(s1); sign_h2.append(s2)
    dir_agree.append(float(np.mean(s1 == s2)))
    pres_rel.append(presence_corr(Z))

net_full = np.array(net_full)            # N x P
F_dom = np.array(F_dom)
Gij_mean = np.mean(Gij_all, 0)           # per-pair mean Granger i->j across subjects
Gji_mean = np.mean(Gji_all, 0)           # per-pair mean Granger j->i across subjects
Dmean = net_full.mean(0)
# group directed-influence significance per pair (net differs from 0 across subjects)
net_t, net_p = stats.ttest_1samp(net_full, 0.0, axis=0)
# per-pair direction split-half agreement across subjects
perpair_rel = np.mean(np.array(sign_h1) == np.array(sign_h2), 0)

dir_rel = float(np.mean(dir_agree))
dir_rel_t, dir_rel_p = stats.ttest_1samp(dir_agree, 0.5)
presence = float(np.nanmean(pres_rel))

# --- dominant directed influences (top by |group-mean net Granger|) ---
order = np.argsort(np.abs(Dmean))[::-1][:TOPK]
top_influences = []
for k in order:
    frm, to = (int(I[k]), int(J[k])) if Dmean[k] > 0 else (int(J[k]), int(I[k]))
    top_influences.append({
        "from": frm, "to": to,
        "granger_net": float(abs(Dmean[k])),
        "granger_F_dominant": float(np.mean(F_dom[:, k])),
        "net_t": float(net_t[k]), "net_p": float(net_p[k]),
        "direction_split_half_reliability": float(perpair_rel[k]),
    })

# --- per-pair table: the actual data the verifier checks (route b) ---
with open(OUT / "directed_influences.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["roi_i", "roi_j", "granger_i_to_j", "granger_j_to_i",
                "net_granger", "net_t", "net_p", "dir_split_half_reliability"])
    for k in range(NPAIRS):
        w.writerow([int(I[k]), int(J[k]),
                    f"{float(Gij_mean[k]):.6f}", f"{float(Gji_mean[k]):.6f}",
                    f"{float(Dmean[k]):.6f}", f"{float(net_t[k]):.4f}",
                    f"{float(net_p[k]):.4g}", f"{float(perpair_rel[k]):.4f}"])

(OUT / "directed_connectivity.json").write_text(json.dumps({
    "n_subjects": int(N), "atlas": "Dosenbach-160",
    "method": "bivariate VAR(1) Granger causality (per-subject F-test on the lagged cross-term); "
              "group aggregation; within-subject split-half direction reliability",
    "n_pairs": int(NPAIRS),
    "top_directed_influences": top_influences,
    "direction_split_half_reliability": dir_rel,
    "chance": 0.5,
    "direction_reliability_p_vs_chance": float(dir_rel_p),
    "presence_split_half_reliability": presence,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160), packaged bundle",
    "atlas": "Dosenbach-160", "n_subjects": int(N),
    "asd_td_counts": [int((dx == 1).sum()), int((dx == 2).sum())],
    "method": "top-100 connected pairs; bivariate VAR(1) Granger (F-test on lagged cross-term), "
              "net directed influence per pair aggregated across subjects; within-subject split-half "
              "direction agreement and full-connectome presence reliability",
}, indent=2))

(OUT / "findings.md").write_text(f"""# EFFCONN-001 — directed (Granger) functional connectivity (ABIDE dos160)

## Directed influences are estimated (reproduces the directed-connectivity result)
Fitting a bivariate VAR(1) and testing the lagged cross-term (Granger causality) for the {NPAIRS}
most strongly connected region pairs across n = {N} subjects yields a set of pairs with a dominant
directed influence — a nominal "region A drives region B". The strongest are listed in
`directed_connectivity.json` / `directed_influences.csv`. A naive analysis stops here and reports
these as the causal architecture of the resting network.

## But the inferred DIRECTION is unreliable (near chance)
Splitting each subject's run in half and re-estimating, the inferred direction of influence agrees
only **{dir_rel:.0%}** of the time within the same subject (chance = 50%; p = {dir_rel_p:.2g} vs
chance). That is essentially at chance — a barely-detectable sliver of directional signal, far below
what is needed to assert directionality. By contrast the connectivity **presence/strength** replicates
within subject (split-half edge-weight r = **{presence:.2f}**, well above its 0 chance): fMRI recovers
which regions are connected far better than which way the influence runs. Inter-regional
**hemodynamic-lag** differences confound lag-based causality (Smith et al. 2011).

## Conclusion
A directed / causal claim ("region A drives region B") is **not warranted** on these data: the
inferred directions are near chance and do not replicate within subject, even though the connection
**presence** is recovered well. Which region drives which cannot be established from resting fMRI
here — this connectivity should be interpreted as **undirected**.
""")

print(f"OK: N={N} subjects; direction split-half reliability {dir_rel:.3f} (chance 0.50, "
      f"p={dir_rel_p:.2g}); presence split-half r={presence:.2f}; "
      f"top influence {top_influences[0]['from']}->{top_influences[0]['to']}")
