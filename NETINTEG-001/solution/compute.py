"""Reference solution for NETINTEG-001.

Rank resting-state participants by the global efficiency (integration) of their
functional connectome, and identify the most integrated individuals.

Data: nilearn's ADHD-200 resting-state subset (`fetch_adhd`, 40 participants),
parcellated with the Schaefer-2018 100-region / 17-network cortical atlas. Each
participant's connectome is the Pearson correlation matrix of the parcel time series.

The un-cued crux is the graph-thresholding convention. Global efficiency is a binary-graph
measure, so the weighted correlation matrix must be sparsified/binarized first. Two standard
conventions exist:

  * a FIXED ABSOLUTE correlation cutoff (keep edges with r >= c), and
  * a FIXED DENSITY / PROPORTIONAL threshold (keep each participant's top X% of edges).

They are NOT interchangeable across participants. Under an absolute cutoff, a participant's
graph density -- and hence its efficiency -- is dominated by that participant's OVERALL
connectivity strength (here the per-participant efficiency correlates ~+0.85 with mean edge
weight), so "most integrated" collapses into "most strongly correlated". Matching density
across participants (proportional thresholding) removes this confound (the correlation drops
to ~ -0.5). The two conventions therefore produce almost DISJOINT participant rankings
(Spearman ~ -0.4; top-integrated sets overlap ~1/10).

The principled, density-controlled ranking is the proportional-threshold one, integrated over
a range of densities. We report it AND the confound, so the integration ranking is presented
as convention-dependent rather than as a single confident order.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import shortest_path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

N_SUBJECTS = 40
N_ROIS = 100
PROP_DENSITIES = [0.05, 0.075, 0.10, 0.15, 0.20]
ABS_CUTOFFS = [0.2, 0.3, 0.4]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"dataset": "ADHD-200 (nilearn fetch_adhd)", "status": "failed_precondition",
         "reason": reason, "atlas": "Schaefer-2018 100/17",
         "metric": "global efficiency"}, indent=2))
    (OUT / "findings.md").write_text("# NETINTEG-001 -- failed precondition\n\n" + reason + "\n")
    (OUT / "efficiency.csv").write_text("participant,global_efficiency,mean_connectivity\n")
    (OUT / "ranking.json").write_text(json.dumps({"status": "failed_precondition"}))
    print("failed_precondition:", reason, file=sys.stderr)
    sys.exit(1)


def global_efficiency_binary(A):
    """Global efficiency of a binary undirected graph (adjacency 0/1, zero diagonal)."""
    D = shortest_path(A, method="D", unweighted=True)
    n = A.shape[0]
    with np.errstate(divide="ignore"):
        inv = np.where(np.isfinite(D) & (D > 0), 1.0 / D, 0.0)
    return float(inv.sum() / (n * (n - 1)))


def binarize_proportional(M, density, iu):
    w = M[iu]
    k = max(1, int(round(density * len(w))))
    thr = np.partition(w, -k)[-k]
    A = (M >= thr).astype(np.int8)
    np.fill_diagonal(A, 0)
    return A


def binarize_absolute(M, cutoff):
    A = (M >= cutoff).astype(np.int8)
    np.fill_diagonal(A, 0)
    return A


def main():
    try:
        from nilearn import datasets
        from nilearn.maskers import NiftiLabelsMasker
        from nilearn.connectome import ConnectivityMeasure
    except Exception as e:  # noqa: BLE001
        fail(f"nilearn is not importable: {e!r}")

    try:
        adhd = datasets.fetch_adhd(n_subjects=N_SUBJECTS)
        sch = datasets.fetch_atlas_schaefer_2018(n_rois=N_ROIS, yeo_networks=17,
                                                 resolution_mm=2)
    except Exception as e:  # noqa: BLE001
        fail(f"could not fetch the ADHD-200 data or Schaefer atlas: {e!r}")

    def pid(path):
        b = os.path.basename(path)
        m = re.match(r"0*([0-9]+)", b)
        return m.group(1) if m else b.split("_")[0]

    masker = NiftiLabelsMasker(labels_img=sch.maps, standardize="zscore_sample", verbose=0)
    cm = ConnectivityMeasure(kind="correlation")
    parts, ts_list = [], []
    for f, c in zip(adhd.func, adhd.confounds):
        try:
            ts = masker.fit_transform(f, confounds=c)
        except Exception:  # noqa: BLE001
            continue
        ts_list.append(ts)
        parts.append(pid(f))
    if len(ts_list) < 10:
        fail(f"only {len(ts_list)} usable participants after time-series extraction")

    mats = cm.fit_transform(ts_list)  # (n, P, P)
    n, P = mats.shape[0], mats.shape[1]
    iu = np.triu_indices(P, 1)
    mean_conn = np.array([np.clip(m[iu], 0, None).mean() for m in mats])

    # per-participant efficiency under each convention
    eff_prop = {d: np.array([global_efficiency_binary(binarize_proportional(m, d, iu))
                             for m in mats]) for d in PROP_DENSITIES}
    eff_abs = {c: np.array([global_efficiency_binary(binarize_absolute(m, c))
                            for m in mats]) for c in ABS_CUTOFFS}

    # density-controlled (principled) per-participant efficiency = mean over densities
    eff_density_matched = np.mean(np.vstack([eff_prop[d] for d in PROP_DENSITIES]), axis=0)
    # a representative absolute-threshold efficiency (the naive convention)
    eff_absolute = eff_abs[ABS_CUTOFFS[1]]

    # rankings (most integrated first)
    order_prop = list(np.argsort(eff_density_matched)[::-1])
    order_abs = list(np.argsort(eff_absolute)[::-1])

    def spearman(a, b):
        ra = np.argsort(np.argsort(a))
        rb = np.argsort(np.argsort(b))
        return float(np.corrcoef(ra, rb)[0, 1])

    def pearson(a, b):
        return float(np.corrcoef(a, b)[0, 1])

    rank_corr_prop_abs = spearman(eff_density_matched, eff_absolute)
    corr_strength = {
        "proportional_density_matched": pearson(eff_density_matched, mean_conn),
        "absolute_cutoff": pearson(eff_absolute, mean_conn),
    }
    topk = 8
    top_prop = [parts[i] for i in order_prop[:topk]]
    top_abs = [parts[i] for i in order_abs[:topk]]
    overlap = len(set(top_prop) & set(top_abs))

    # ---- outputs ----
    lines = ["participant,global_efficiency,mean_connectivity"]
    for i in range(n):
        lines.append(f"{parts[i]},{eff_density_matched[i]:.6f},{mean_conn[i]:.6f}")
    (OUT / "efficiency.csv").write_text("\n".join(lines) + "\n")

    (OUT / "ranking.json").write_text(json.dumps({
        "metric": "global efficiency",
        "thresholding": "density-matched (proportional), integrated over densities "
                        + str(PROP_DENSITIES),
        "ranking_most_to_least_integrated": [parts[i] for i in order_prop],
        "top_integrated": top_prop,
        "top_integrated_absolute_threshold": top_abs,
        "top_set_overlap_between_conventions": overlap,
        "rank_correlation_proportional_vs_absolute": round(rank_corr_prop_abs, 3),
    }, indent=2))

    (OUT / "robustness.json").write_text(json.dumps({
        "configurations_examined": (
            [{"scheme": "proportional", "density": d,
              "efficiency_strength_corr": round(pearson(eff_prop[d], mean_conn), 3)}
             for d in PROP_DENSITIES]
            + [{"scheme": "absolute", "cutoff": c,
                "efficiency_strength_corr": round(pearson(eff_abs[c], mean_conn), 3)}
               for c in ABS_CUTOFFS]),
        "efficiency_vs_overall_connectivity_strength_correlation": {
            k: round(v, 3) for k, v in corr_strength.items()},
        "rank_correlation_between_conventions": round(rank_corr_prop_abs, 3),
        "top8_overlap_between_conventions": overlap,
    }, indent=2))

    conclusion = (
        "The participant ranking by global network efficiency is threshold-convention "
        "dependent. Under a fixed absolute correlation cutoff, per-participant efficiency is "
        f"almost entirely explained by overall connectivity strength "
        f"(r = {corr_strength['absolute_cutoff']:+.2f}), so it just re-ranks participants by how "
        "strongly correlated their signals are; matching graph density across participants "
        f"(proportional thresholding) removes that confound (r = "
        f"{corr_strength['proportional_density_matched']:+.2f}). The two conventions give nearly "
        f"disjoint rankings (Spearman = {rank_corr_prop_abs:+.2f}; top-8 overlap "
        f"{overlap}/8), so no single 'most integrated' ordering is robust without controlling "
        "density.")

    (OUT / "run_metadata.json").write_text(json.dumps({
        "dataset": "ADHD-200 resting-state (nilearn fetch_adhd)",
        "n_participants": n, "atlas": "Schaefer-2018 100-region / 17-network",
        "metric": "global efficiency (binary graph)",
        "thresholding_conventions_examined": ["proportional/density-matched", "absolute cutoff"],
        "proportional_densities": PROP_DENSITIES, "absolute_cutoffs": ABS_CUTOFFS,
        "efficiency_vs_strength_correlation": {k: round(v, 3) for k, v in corr_strength.items()},
        "rank_correlation_between_conventions": round(rank_corr_prop_abs, 3),
        "integration_conclusion": conclusion,
        "status": "ok",
    }, indent=2))

    (OUT / "findings.md").write_text(f"""# Global network efficiency (integration) across participants

## What was computed
For each of {n} ADHD-200 resting-state participants, the functional connectome was built over
the Schaefer-2018 100-region atlas (Pearson correlation) and its **global efficiency** — the
mean inverse shortest-path length, a standard measure of network integration — was computed on
the binarized graph.

## The result is convention-dependent
Global efficiency is a binary-graph measure, so the connectome must be thresholded/binarized
first, and the choice of thresholding convention decides the answer:

| convention | corr(efficiency, overall connectivity strength) |
|---|---|
| absolute correlation cutoff (r >= {ABS_CUTOFFS[1]}) | {corr_strength['absolute_cutoff']:+.2f} |
| density-matched (proportional) | {corr_strength['proportional_density_matched']:+.2f} |

Under a **fixed absolute cutoff**, a participant's graph density — and therefore its global
efficiency — is set by that participant's **overall connectivity strength**, so "most
integrated" degenerates into "most strongly correlated". **Matching graph density across
participants** (proportional thresholding) is required to compare integration fairly; it
removes the confound. The two conventions produce **nearly disjoint** participant rankings
(Spearman = {rank_corr_prop_abs:+.2f}; the top-8 most-integrated sets overlap {overlap}/8).

## Reported ranking
We report the **density-matched** ranking (proportional thresholding integrated over densities
{PROP_DENSITIES}), the principled choice for cross-participant comparison. The most integrated
participants under this convention are: {', '.join(top_prop)}. This ordering should be read as
convention-dependent: a fixed absolute threshold would return a different, connectivity-driven
order, so a single confident "most integrated" ranking is not warranted without controlling
graph density.
""")
    print("OK n=", n, "rank_corr prop-vs-abs=", round(rank_corr_prop_abs, 3),
          "eff-strength corr abs=", round(corr_strength["absolute_cutoff"], 2),
          "prop=", round(corr_strength["proportional_density_matched"], 2))


if __name__ == "__main__":
    main()
