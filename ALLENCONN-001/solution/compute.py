"""ALLENCONN-001 reference solution.

Builds the directed source-region x target-structure projection-strength matrix for the
wild-type Allen mouse anterograde experiments over the 316 summary structures, and reports
the fraction of region-pairs whose projection density exceeds 0.1.

The one scientifically load-bearing choice: the Allen structure-unionize records carry an
`is_injection` flag. Records with is_injection=True describe tracer signal *inside the
injection site*, which is saturated (median projection_density ~0.8) and is not a
projection to a target region; they must be excluded when measuring connectivity. This
reference reads projection signal only (is_injection=False).
"""
import json
import os
import sys
import traceback

import numpy as np
import pandas as pd
from allensdk.core.mouse_connectivity_cache import MouseConnectivityCache

OUT = os.environ.get("OUTPUT_DIR", "/app/output")
CACHE_DIR = os.environ.get("ALLEN_CACHE_DIR", "/app/allen_cache")
SUMMARY_SET_ID = 167587189   # "Mouse Connectivity - Summary" (the 316 summary structures)
HEMISPHERE_ID = 3            # both hemispheres (whole-structure projection density)
THRESHOLD = 0.1
METRIC = "projection_density"

os.makedirs(OUT, exist_ok=True)


def fail(reason):
    for name, obj in (("run_metadata.json", {"status": "failed_precondition", "reason": reason}),
                      ("strong_fraction.json", {"status": "failed_precondition", "reason": reason})):
        with open(os.path.join(OUT, name), "w") as f:
            json.dump(obj, f, indent=2)
    with open(os.path.join(OUT, "findings.md"), "w") as f:
        f.write("# ALLENCONN-001\n\nfailed_precondition: %s\n" % reason)
    sys.stderr.write("failed_precondition: %s\n" % reason)
    sys.exit(1)


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    mcc = MouseConnectivityCache(
        manifest_file=os.path.join(CACHE_DIR, "manifest.json"), resolution=100)

    # wild-type (non-transgenic) injection experiments
    exps = mcc.get_experiments(dataframe=False, cre=False)
    eids = sorted(e["id"] for e in exps)

    # the 316 summary structures
    tree = mcc.get_structure_tree()
    summary = tree.get_structures_by_set_id([SUMMARY_SET_ID])
    summary_ids = [s["id"] for s in summary]
    acr = {s["id"]: s["acronym"] for s in summary}
    if len(summary_ids) != 316:
        fail("expected 316 summary structures, got %d" % len(summary_ids))

    # map each injection structure onto its summary-structure ancestor
    sid2summary = {}
    for ssid in summary_ids:
        for d in tree.descendant_ids([ssid])[0]:
            sid2summary[d] = ssid
    eid2src = {e["id"]: sid2summary.get(e["primary_injection_structure"]) for e in exps}

    # projection signal only (exclude injection-site compartments), whole-structure hemisphere
    u = mcc.get_structure_unionizes(
        eids, structure_ids=summary_ids, is_injection=False, hemisphere_ids=[HEMISPHERE_ID])
    u = u[[c for c in ("experiment_id", "structure_id", METRIC) if c in u.columns]].copy()
    u["src"] = u["experiment_id"].map(eid2src)
    u = u[u["src"].notna()]

    # directed source-region x target-structure matrix: mean over experiments per source region
    long = u.groupby(["src", "structure_id"])[METRIC].mean().reset_index()
    mat = long.pivot(index="src", columns="structure_id", values=METRIC)

    vals = mat.values
    finite = vals[~np.isnan(vals)]
    n_strong = int((finite > THRESHOLD).sum())
    n_pairs = int(finite.size)
    strong_fraction = float(n_strong / n_pairs)

    # write the matrix with acronym labels
    labeled = mat.rename(index=acr, columns=acr)
    labeled.to_csv(os.path.join(OUT, "connectivity_matrix.csv"))

    with open(os.path.join(OUT, "strong_fraction.json"), "w") as f:
        json.dump({
            "strong_fraction": strong_fraction,
            "threshold": THRESHOLD,
            "n_region_pairs": n_pairs,
            "n_strong_pairs": n_strong,
            "n_experiments": len(eids),
            "n_source_regions": int(mat.shape[0]),
            "n_target_structures": int(mat.shape[1]),
        }, f, indent=2)

    with open(os.path.join(OUT, "run_metadata.json"), "w") as f:
        json.dump({
            "status": "ok",
            "dataset": "Allen Mouse Brain Connectivity Atlas (allensdk MouseConnectivityCache)",
            "source_paper": "Oh et al. 2014, Nature (10.1038/nature13186)",
            "n_experiments": len(eids),
            "cohort": "wild-type (cre=False)",
            "structure_set_id": SUMMARY_SET_ID,
            "n_summary_structures": len(summary_ids),
            "metric": METRIC,
            "hemisphere_id": HEMISPHERE_ID,
            "threshold": THRESHOLD,
            "matrix": "directed source-region x target-structure, mean projection_density over experiments per source region",
            "injection_site_handling": "projection signal only (is_injection=False); injection-site compartments excluded",
        }, f, indent=2)

    with open(os.path.join(OUT, "findings.md"), "w") as f:
        f.write(
            "# Mesoscale projection-connectome density (ALLENCONN-001)\n\n"
            "Across %d wild-type Allen anterograde experiments, over the 316 summary "
            "structures, the directed source-region x target-structure projection-strength "
            "matrix (%d region-pairs) has a strong-connection fraction of "
            "**%.4f** at a projection-density threshold of %.1f "
            "(%d of %d pairs above threshold).\n\n"
            "Projection strength was read from the structure-unionize records as "
            "`projection_density` for the whole structure (both hemispheres). Signal inside "
            "the injection site itself was excluded (it is saturated, median projection "
            "density ~0.8, and does not represent a projection to a target region); counting "
            "it would roughly double the reported fraction. The mouse mesoscale connectome is "
            "therefore sparse at this threshold: only about %.1f%% of possible region-pairs "
            "carry strong projection signal.\n"
            % (len(eids), n_pairs, strong_fraction, THRESHOLD, n_strong, n_pairs,
               100.0 * strong_fraction))

    print("strong_fraction=%.4f  (%d/%d)  n_exp=%d  n_src=%d"
          % (strong_fraction, n_strong, n_pairs, len(eids), mat.shape[0]))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc()
        fail("Allen cache/unionize data could not be resolved: %s" % e)
