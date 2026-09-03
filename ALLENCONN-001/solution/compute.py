"""ALLENCONN-001 reference solution.

Descriptor: among the wild-type anterograde source regions of the Allen mouse mesoscale
connectome, what fraction have their STRONGEST projection to their OWN summary structure rather
than to a different structure? Built over the 316 summary structures, whole-structure
`projection_density`, source = primary injection structure mapped to its summary ancestor, entry =
mean projection_density over the experiments sharing that source.

The scientifically load-bearing choice (never named in the instruction): the Allen structure-
unionize records carry an `is_injection` flag. The `is_injection=True` rows are tracer signal
*inside the injection site*, which is saturated (median projection_density ~0.82) and is not a
projection to a target region. Because the injection site sits in the source's own summary
structure, leaving those saturated compartments in makes the SELF cell the largest entry of the
row for most sources -- an artifact -- so the naive fraction-with-self-strongest is ~0.62.
Reading projection signal only (is_injection=False) removes the saturated self compartment; the
source's own structure then still carries genuine local arborization but is the strongest target
for only ~0.36 of sources. So the honest self-strongest fraction is ~0.36, not ~0.62.
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
METRIC = "projection_density"

os.makedirs(OUT, exist_ok=True)


def fail(reason):
    for name, obj in (("run_metadata.json", {"status": "failed_precondition", "reason": reason}),
                      ("self_projection.json", {"status": "failed_precondition", "reason": reason})):
        with open(os.path.join(OUT, name), "w") as f:
            json.dump(obj, f, indent=2)
    with open(os.path.join(OUT, "findings.md"), "w") as f:
        f.write("# ALLENCONN-001\n\nfailed_precondition: %s\n" % reason)
    sys.stderr.write("failed_precondition: %s\n" % reason)
    sys.exit(1)


def self_strongest_fraction(mat):
    """fraction of source rows whose largest entry is the source's own structure (the diagonal)."""
    n = 0
    n_self = 0
    for s in mat.index:
        if s not in mat.columns:
            continue
        row = mat.loc[s]
        if row.notna().sum() < 2:
            continue
        n += 1
        selfv = row[s]
        if pd.notna(selfv) and selfv >= row.max() - 1e-12:
            n_self += 1
    return (n_self / n if n else float("nan")), n, n_self


def build_matrix(mcc, eids, summary_ids, eid2src, is_injection):
    kw = dict(structure_ids=summary_ids, hemisphere_ids=[HEMISPHERE_ID])
    if is_injection is not None:
        kw["is_injection"] = is_injection
    u = mcc.get_structure_unionizes(eids, **kw)
    u = u[[c for c in ("experiment_id", "structure_id", METRIC) if c in u.columns]].copy()
    u["src"] = u["experiment_id"].map(eid2src)
    u = u[u["src"].notna()]
    long = u.groupby(["src", "structure_id"])[METRIC].mean().reset_index()
    return long.pivot(index="src", columns="structure_id", values=METRIC)


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    mcc = MouseConnectivityCache(
        manifest_file=os.path.join(CACHE_DIR, "manifest.json"), resolution=100)

    exps = mcc.get_experiments(dataframe=False, cre=False)
    eids = sorted(e["id"] for e in exps)

    tree = mcc.get_structure_tree()
    summary = tree.get_structures_by_set_id([SUMMARY_SET_ID])
    summary_ids = [s["id"] for s in summary]
    acr = {s["id"]: s["acronym"] for s in summary}
    if len(summary_ids) != 316:
        fail("expected 316 summary structures, got %d" % len(summary_ids))

    sid2summary = {}
    for ssid in summary_ids:
        for d in tree.descendant_ids([ssid])[0]:
            sid2summary[d] = ssid
    eid2src = {e["id"]: sid2summary.get(e["primary_injection_structure"]) for e in exps}

    # projection signal only (exclude saturated injection-site compartments)
    mat = build_matrix(mcc, eids, summary_ids, eid2src, is_injection=False)
    frac_correct, n_src, n_self = self_strongest_fraction(mat)

    # naive contrast: leave the injection-site compartments in
    mat_naive = build_matrix(mcc, eids, summary_ids, eid2src, is_injection=None)
    frac_naive, _, _ = self_strongest_fraction(mat_naive)

    labeled = mat.rename(index=acr, columns=acr)
    labeled.to_csv(os.path.join(OUT, "connectivity_matrix.csv"))

    with open(os.path.join(OUT, "self_projection.json"), "w") as f:
        json.dump({
            "self_strongest_fraction": frac_correct,
            "n_source_regions": n_src,
            "n_self_strongest": n_self,
            "n_experiments": len(eids),
            "n_target_structures": int(mat.shape[1]),
            "metric": METRIC,
            "hemisphere_id": HEMISPHERE_ID,
            "injection_included_fraction": frac_naive,   # inflated contrast, for reference
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
            "matrix": "directed source-region x target-structure, mean projection_density over experiments per source region",
            "descriptor": "fraction of source regions whose strongest projection target (argmax over the 316 summary structures, self included) is the source's own structure",
            "injection_site_handling": "projection signal only (is_injection=False); saturated injection-site compartments excluded",
        }, f, indent=2)

    with open(os.path.join(OUT, "findings.md"), "w") as f:
        f.write(
            "# Self-referential strongest projections in the mouse mesoscale connectome (ALLENCONN-001)\n\n"
            "Across %d wild-type Allen anterograde experiments over the 316 summary structures, each "
            "source region's row of the directed source x target projection-strength matrix was taken "
            "(mean `projection_density` over the experiments sharing that source, whole structure / both "
            "hemispheres) and its strongest target (argmax over the 316 structures, including the source's "
            "own structure) identified.\n\n"
            "**%d of %d source regions (%.3f) have their strongest projection to their own structure.** "
            "Projection strength was read as projection signal only: the saturated tracer signal inside "
            "the injection site itself (median projection_density ~0.8) was excluded, because it is not a "
            "projection to a target region. If those injection-site compartments are left in, the source's "
            "own structure is spuriously the strongest target for %.3f of sources -- an artifact of the "
            "saturated injection bolus, not the anatomy.\n"
            % (len(eids), n_self, n_src, frac_correct, frac_naive))

    print("self_strongest_fraction=%.4f  (%d/%d)  naive(injection-in)=%.4f  n_exp=%d"
          % (frac_correct, n_self, n_src, frac_naive, len(eids)))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc()
        fail("Allen cache/unionize data could not be resolved: %s" % e)
