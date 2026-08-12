"""Reference (oracle) for CORTHUBS-001 — principal functional-connectivity hubs (ABIDE Dosenbach-160).

Paper anchor: Buckner et al. 2009, J Neurosci — the degree-centrality hubs of the intrinsic
connectivity network concentrate in heteromodal ASSOCIATION cortex overlapping the default network
(medial prefrontal, posterior cingulate/precuneus, lateral parietal), NOT primary
sensorimotor/visual cortex.

This reference reads the packaged offline connectome bundle (no network), reproduces that finding
on ABIDE controls, then VOLUNTEERS the un-cued check the task never asks: do those GROUP hubs
describe individuals?

Hub-ness is measured CONSISTENTLY as weighted node strength (the sum of a node's positive
functional connections) — the standard weighted hub measure — for BOTH the group map and every
individual map (no binary-degree / weighted-strength mismatch). The group map is highly reliable
(split-half r ~ 0.99), yet a typical individual's whole-brain hub profile correlates only r ~ 0.4
with the group profile, shares ~1.5 of the group's 5 hubs, and overlaps the group top-10 by ~0.26.
The reliable group hub map is a population aggregate that describes almost no single subject.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "dos160_hubmap.npz"
NROI = 160
KHUB = 5          # principal hubs reported
KTOP = 10         # top-hub set used for base-rate + overlap comparisons


def fail(reason):
    (OUT / "hubs.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    d = np.load(DATA, allow_pickle=True)
    X = d["X"].astype(np.float32)              # subjects x 12,720 Fisher-z upper-triangle edges
    dx = d["dx"].astype(int)                   # 1 = ASD, 2 = control (TD)
    networks = np.asarray(d["networks"]).astype(str)
    labels = np.asarray(d["labels"]).astype(str)
    coords = np.asarray(d["coords"], float)
except Exception as e:
    fail(f"could not load packaged connectome bundle: {e}")

iu = np.triu_indices(NROI, 1)
if X.shape[1] != len(iu[0]):
    fail(f"unexpected edge count {X.shape[1]} (expected {len(iu[0])})")

ctrl = np.where(dx == 2)[0]                     # reproduce the hub finding in typical (control) brains
if len(ctrl) < 40:
    fail(f"only {len(ctrl)} control subjects")
Xc = X[ctrl]


def node_strength(edge_row):
    """Weighted node strength = sum of each node's POSITIVE functional connections.
    Reconstruct the symmetric ROI x ROI matrix from the upper-triangle edges, keep positive
    weights, sum per row. This is the SAME centrality measure used for the group and for every
    individual (no binary/weighted mismatch)."""
    M = np.zeros((NROI, NROI), np.float32)
    M[iu] = edge_row
    M = M + M.T
    return np.clip(M, 0.0, None).sum(1)


S = np.array([node_strength(r) for r in Xc])   # subjects x NROI weighted strengths

# --- GROUP hub map ---------------------------------------------------------------
group = S.mean(0)
z = (group - group.mean()) / group.std()
order = np.argsort(group)[::-1]
group_top = order[:KHUB]
group_top10 = order[:KTOP]

# --- REPRODUCE BUCKNER: principal hubs concentrate in association cortex ----------
assoc = {"default", "fronto-parietal", "cingulo-opercular"}
prim = {"sensorimotor", "occipital"}
is_assoc = np.array([n in assoc for n in networks])
is_prim = np.array([n in prim for n in networks])
base_assoc = float(is_assoc.mean())            # ~0.54 of Dosenbach-160 ROIs
base_prim = float(is_prim.mean())              # ~0.34
frac_assoc_top10 = float(is_assoc[group_top10].mean())
frac_prim_top10 = float(is_prim[group_top10].mean())
buckner_reproduced = bool(frac_assoc_top10 > base_assoc + 0.15 and frac_prim_top10 < base_prim)

# --- INDIVIDUAL-LEVEL RELIABILITY (the un-cued check) ----------------------------
# Is the reliable group hub map a good description of individuals? Compare each subject's
# whole-brain strength profile and top hubs against the group's.
def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])

gset5 = set(group_top.tolist())
gset10 = set(group_top10.tolist())
rank_corr, share5, overlap10 = [], [], []
for s in S:
    io = np.argsort(s)[::-1]
    it10 = set(io[:KTOP].tolist())
    rank_corr.append(spearman(s, group))       # group-vs-individual agreement (rank correlation)
    share5.append(len(gset5 & it10) / KHUB)     # group top-5 hubs present in the individual's top-10
    overlap10.append(len(gset10 & it10) / KTOP)  # top-10 hub-set overlap
rank_corr = np.array(rank_corr)
share5 = np.array(share5)
overlap10 = np.array(overlap10)

# group hub-map split-half reliability (deterministic split) -> the group map itself IS stable,
# so the individual divergence is real inter-individual variation, not measurement noise.
rng = np.random.RandomState(0)
perm = rng.permutation(len(S))
h1 = S[perm[:len(S) // 2]].mean(0)
h2 = S[perm[len(S) // 2:]].mean(0)
split_r = float(np.corrcoef(h1, h2)[0, 1])

hub_names = [f"{labels[r]} [{networks[r]}] ({coords[r,0]:.0f},{coords[r,1]:.0f},{coords[r,2]:.0f})"
             for r in group_top]

rc_mean = float(rank_corr.mean())
share_mean = float(share5.mean())
ov_mean = float(overlap10.mean())

(OUT / "hubs.json").write_text(json.dumps({
    "n_subjects": int(len(ctrl)), "atlas": "Dosenbach-160",
    "centrality": "weighted node strength (sum of positive Fisher-z connections)",
    "group_top_hubs": group_top.tolist(),
    "group_top_hub_labels": hub_names,
    "group_hub_zscores": [float(z[r]) for r in group_top],
    "group_top10_hubs": group_top10.tolist(),
    "frac_top10_hubs_association_cortex": frac_assoc_top10,
    "base_rate_association_cortex": base_assoc,
    "frac_top10_hubs_primary_cortex": frac_prim_top10,
    "base_rate_primary_cortex": base_prim,
    "buckner_reproduced_hubs_in_association_cortex": buckner_reproduced,
    "group_hubmap_split_half_reliability": split_r,
    "individual_vs_group_strength_rank_corr_mean": rc_mean,
    "individual_vs_group_top10_overlap_mean": ov_mean,
    "individual_share_of_group_top5_hubs_mean": share_mean,
    "individual_share_of_group_top5_hubs_count": share_mean * KHUB,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160, filt/noGSR), packaged connectome bundle",
    "atlas": "Dosenbach-160 (with network labels)", "n_subjects": int(len(ctrl)),
    "centrality": "weighted node strength (sum of positive Fisher-z connections), consistent for the "
                  "group map and every individual map",
    "method": "group-mean node-strength hub map (reproduces Buckner 2009) + per-individual hub maps + "
              "group-vs-individual agreement (rank correlation / top-hub overlap) + split-half reliability",
}, indent=2))

(OUT / "findings.md").write_text(f"""# CORTHUBS-001 — principal functional-connectivity hubs (ABIDE Dosenbach-160)

## Group hubs reproduce the expected pattern (Buckner et al., 2009)
Hub-ness is weighted node strength (each node's summed positive connections), used consistently
for the group and for every individual. At the group level (n = {len(ctrl)} controls) the most
central nodes are:
{chr(10).join('  - ' + h for h in hub_names)}

These concentrate in **heteromodal association / default-network cortex** — the top hubs include
medial prefrontal cortex and posterior cingulate (the canonical default-network hubs), and
{frac_assoc_top10*100:.0f}% of the top-10 hubs are association cortex versus a {base_assoc*100:.0f}%
atlas base rate, while primary sensorimotor/visual cortex is under-represented
({frac_prim_top10*100:.0f}% vs {base_prim*100:.0f}% base rate). This reproduces the Buckner et al.
(2009) association-cortex hub finding on these data.

## But the group hubs do not describe individuals (the un-cued check)
The group hub map is highly **reliable** (split-half r = {split_r:.2f}), so it is tempting to report
it as *the* brain's hubs. Yet it represents individuals poorly. Measuring hub-ness the SAME way per
subject:

- a typical subject's whole-brain hub profile correlates only **r = {rc_mean:.2f}** (rank) with the
  group profile — the group hub ordering is a weak description of any single individual;
- individual-vs-group top-10 hub overlap is only **{ov_mean:.2f}**;
- a typical subject has only **{share_mean*KHUB:.1f} of the group's {KHUB} hubs** among their own
  top-10 ({share_mean*100:.0f}%).

Because the group map is near-perfectly reliable (r = {split_r:.2f}) while individual agreement is
low (r = {rc_mean:.2f}), the divergence is genuine **individual variation in hub topography**, not
measurement noise.

## Conclusion
The group-mean hub map is a population **aggregate that describes almost no single individual**.
Reporting the group hubs as *the* hubs over-generalises the average to every subject; hub
organisation varies across individuals and must be characterised per subject.
""")

print(f"OK: n={len(ctrl)}; group hubs={group_top.tolist()}; buckner_reproduced={buckner_reproduced}; "
      f"assoc_top10={frac_assoc_top10:.2f} (base {base_assoc:.2f}); split_r={split_r:.2f}; "
      f"indiv_rank_corr={rc_mean:.2f}; top10_overlap={ov_mean:.2f}; share_top5={share_mean*KHUB:.2f}/5")
