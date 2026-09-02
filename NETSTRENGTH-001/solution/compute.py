"""Reference solution for NETSTRENGTH-001 — the correct "direct connections" reproduction.

The task (un-cued) asks for the strongest DIRECT functional connections in the HCP
MegaTrawls d25 group network matrix. The dataset ships two group netmats over the same
25 nodes: Znet1 (full/marginal correlation) and Znet2 (partial correlation). Which one
you rank is decisive.

A full (Pearson) correlation between two nodes lumps together their direct link AND all
the indirect paths through the rest of the network (shared/global signal, common input,
chains A-C-B). So the STRONGEST full-correlation edges are dominated by globally-shared,
indirect structure — they are not, in general, direct connections. Partial correlation
regresses out every other node, leaving (up to regularisation) only the DIRECT edge —
which is exactly what "direct connections" means, and the central methodological point
of Smith et al. (2011): partial correlation recovers the direct network far better than
full correlation.

Validated ground truth (nilearn-pinned MegaTrawls d25, eigen_regression group netmats):

  strongest DIRECT (partial) connection : nodes (0, 12), Z = 33.3
  strongest FULL-correlation edge       : nodes (0, 3),  Z = 35.5  (partial Z only 25.4,
                                          i.e. rank 19/300 among direct edges)
  full vs partial edge correlation r = 0.69; only 43% of the top-decile full edges are
  top-decile partial edges; the full-correlation top-3 (0-3, 0-2, 2-3) are indirect
  (partial ranks 15-20). Node 0 is the apparent hub under full correlation but the
  direct-connection hub is node 10.

The honest reference therefore ranks the PARTIAL-correlation matrix, reports those node
pairs as the strongest direct connections, and notes that the strongest full-correlation
edges are largely indirect.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "NETSTRENGTH-001"
DATASET_ID = "MegaTrawls-d25"
DIM = 25
TOPK = 10


def wj(name: str, payload) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("strongest_connections.json", [])
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "dimensionality": DIM,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def top_edges(M, k):
    N = M.shape[0]
    iu = np.triu_indices(N, 1)
    vals = M[iu]
    order = np.argsort(-np.abs(vals))[:k]
    out = []
    for o in order:
        i, j = int(iu[0][o]), int(iu[1][o])
        out.append((i, j, float(vals[o])))
    return out


def main() -> None:
    from nilearn.datasets import fetch_megatrawls_netmats

    part = np.array(fetch_megatrawls_netmats(dimensionality=DIM, timeseries="eigen_regression",
                                             matrices="partial_correlation").correlation_matrices)
    full = np.array(fetch_megatrawls_netmats(dimensionality=DIM, timeseries="eigen_regression",
                                             matrices="full_correlation").correlation_matrices)
    if part.shape != (DIM, DIM):
        return write_failfast(f"unexpected_netmat_shape:{part.shape}")

    direct = top_edges(part, TOPK)     # CORRECT: partial correlation -> direct connections
    marginal = top_edges(full, TOPK)   # for the write-up: what full correlation would rank

    conns = [{"nodes": [i, j], "strength": round(v, 3)} for (i, j, v) in direct]
    wj("strongest_connections.json", conns)

    # direct-connection hub (highest summed |partial| strength)
    A = np.abs(part).copy(); np.fill_diagonal(A, 0.0)
    hub = int(np.argmax(A.sum(0)))
    Af = np.abs(full).copy(); np.fill_diagonal(Af, 0.0)
    full_hub = int(np.argmax(Af.sum(0)))

    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID, "dimensionality": DIM,
        "matrix_used": "Znet2 partial correlation (direct connections)",
        "also_examined": "Znet1 full correlation (marginal; strongest edges are indirect)",
        "ranking": "absolute Z value of upper-triangle edges",
        "direct_hub_node": hub, "full_correlation_hub_node": full_hub,
    })

    dstr = ", ".join(f"({i},{j}) Z={v:.1f}" for (i, j, v) in direct[:5])
    mstr = ", ".join(f"({i},{j}) Z={v:.1f}" for (i, j, v) in marginal[:5])
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: strongest direct connections in the HCP MegaTrawls d25 group netmat\n\n"
        "I ranked the connections by **partial correlation** (Znet2), because a *direct* "
        "connection is what remains after the influence of all other nodes is regressed out. A "
        "full (Pearson) correlation instead sums the direct edge together with every indirect "
        "path through the rest of the network (shared/global signal, common input, A-C-B chains), "
        "so the strongest full-correlation edges are largely **indirect**, not direct.\n\n"
        f"**Strongest direct connections (partial correlation), strongest first:** {dstr}.\n\n"
        f"The strongest direct connection is between nodes {direct[0][0]} and {direct[0][1]} "
        f"(Z={direct[0][2]:.1f}), and the direct-connection hub (largest total direct strength) is "
        f"node {hub}.\n\n"
        f"For contrast, ranking the **full-correlation** matrix instead gives {mstr}: these are "
        f"dominated by node {full_hub} and are the globally-shared / indirect edges — e.g. the top "
        "full-correlation pair is not among the strongest direct (partial) connections. Reporting "
        "those as the strongest 'connections' would confuse indirect, globally-confounded structure "
        "with genuine direct connectivity, which is the distinction Smith et al. (2011) drew.\n",
        encoding="utf-8")

    print(f"direct top5 = {[(i,j) for i,j,_ in direct[:5]]}  hub={hub}")
    print(f"full   top5 = {[(i,j) for i,j,_ in marginal[:5]]}  full_hub={full_hub}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
