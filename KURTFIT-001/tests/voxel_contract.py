"""Validate each declared cap against its own source-derived reference map."""
import numpy as np

from proof_of_work import (
    PRIMARY_CAP, MAP_TOL, ARITHMETIC_TOL, PIPELINE_ID, integer, number,
    read_json, match_contract, cap_values, load_maps, ordered_values,
)


def validate_maps(output, reference):
    primary = ordered_values(load_maps(output / "mk_voxelwise.csv"), reference)
    groups = load_maps(output / "mk_sweep.csv", sweep=True)
    assert len(groups) >= 2 and PRIMARY_CAP in groups, "at least two caps including 2000 are required"
    aligned = {}
    for cap, values in groups.items():
        aligned[cap] = ordered_values(values, reference)
        assert np.max(np.abs(aligned[cap] - reference["maps"][cap])) <= MAP_TOL, (
            f"voxel MK values differ from the declared cap {cap} reference")
    assert np.max(np.abs(primary - reference["maps"][PRIMARY_CAP])) <= MAP_TOL, (
        "primary map must use the declared 2000 cap")
    assert np.max(np.abs(primary - aligned[PRIMARY_CAP])) <= ARITHMETIC_TOL, (
        "primary map and 2000 sweep map disagree")
    return primary, aligned


def validate_results(output, reference, primary, groups):
    result = read_json(output / "dki_results.json")
    assert result["status"] == "ok", "a completed analysis must report status ok"
    assert result["pipeline_id"] == PIPELINE_ID
    assert integer(result["n_wm_voxels"]) == len(reference["keys"])
    assert integer(result["b_max_used"]) == PRIMARY_CAP
    assert abs(number(result["mean_kurtosis_wm"]) - primary.mean()) <= ARITHMETIC_TOL, (
        "primary mean does not recompute from its voxel table")
    means = cap_values(result["mean_kurtosis_wm_by_bcap"])
    assert set(means) == set(groups), "reported cap means must match the submitted sweep"
    for cap, values in groups.items():
        assert abs(means[cap] - values.mean()) <= ARITHMETIC_TOL, f"cap {cap} mean does not recompute"
    measured_means = [values.mean() for values in groups.values()]
    spread = max(measured_means) - min(measured_means)
    assert abs(number(result["mk_shell_cap_spread"]) - spread) <= ARITHMETIC_TOL, (
        "spread must recompute over the submitted caps")
    expected_shells = reference["stats"]["metadata_contract"]["shell_subsets"][str(PRIMARY_CAP)]["shells"]
    match_contract(result["shells_used"], expected_shells, "shells_used")
