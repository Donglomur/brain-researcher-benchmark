"""Narrow normal-checkout import/selector/schema check; invented operands only."""
import copy
import json
from pathlib import Path
import sys

# The original programme uses top-level runtime and scientific packages.
sys.path.insert(0, str(Path(__file__).resolve().parent / "programme"))
from scientific import allen
from scientific import allen_source_selector as selector
from scientific.allen_selector_contract import amended_outputs
from scientific.json_extent import layout_bytes
from scientific.technical_support.contracts import ALLEN
import numpy as np


def main():
    checks = []
    jobs = allen.schedule()
    assert len(jobs) == 52 and len(ALLEN) == 4
    assert {j["specimen"] for j in jobs} == set(ALLEN)
    for specimen in ALLEN:
        rows = [j for j in jobs if j["specimen"] == specimen]
        assert len(rows) == 13
        assert len([j for j in rows if j["budget"] == "high"]) == 2
        assert sorted(j["seed"] for j in rows if j["algorithm"] == "GA" and
                      j["budget"] == "low") == list(range(10))
    checks.append("complete source schedule")
    assert selector.PRODUCTS == (
        "full_voltage", "soft_DTW", "spike_count", "spike_times",
        "spike_amplitudes", "best_final_hof_lineage", "resource_trajectory")
    assert selector.CONDITIONS == ("A_R", "B_R", "A_I", "B_I")
    checks.append("seven products and four conditions")
    assert selector.plain_rank([3.0, 1.0, 2.0], [0, 1, 2]) == ([1, 2, 0], [1])
    checks.append("three-value pure ranking")

    # This invented minimal layout tests relocation/import composition only.
    # It is not the real original J11 plan or a runtime admission.
    products = []
    for name in selector.PRODUCTS:
        layout = {"kind": "array", "minimum_count": 52, "maximum_count": 52,
                  "items": {"kind": "object", "fields": {"retained": {"kind": "null"}}}}
        products.append({"artifact_id": name, "format": "json",
                         "extent": {"kind": "upper_bound", "bytes": layout_bytes(layout) + 1,
                                    "derivation": {"layout": layout}}})
    old = copy.deepcopy(products)
    amended = amended_outputs(products, max_candidates=2000,
                              max_path_bytes=256, max_job_id_bytes=128)
    assert products == old and len(amended) == 7
    for row in amended:
        layout = row["extent"]["derivation"]["layout"]
        assert layout["minimum_count"] == layout["maximum_count"] == 52
        fields = layout["items"]["fields"]
        assert fields["retained"] == {"kind": "null"}
        assert "source_selector_join" in fields
        assert ("source_selection" in fields) == (row["artifact_id"] == "best_final_hof_lineage")
        assert row["extent"]["bytes"] == layout_bytes(layout) + 1
    checks.append("closed schema amendment and preserved input")
    print(json.dumps({"kind": "invented_checkout_check", "checks": checks,
                      "numpy_version": np.__version__, "scientific_result": False,
                      "native_execution": False}, sort_keys=True))


if __name__ == "__main__":
    main()
