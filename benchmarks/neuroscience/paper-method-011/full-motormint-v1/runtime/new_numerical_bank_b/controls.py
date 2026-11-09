"""Tiny invented controls. Expected values do not call any other bank."""

import copy
import json
import math
import resource

from bank import evaluate


fixture_bytes = 0
calls = 0


def call(label, kind, payload, rejected=False):
    global fixture_bytes, calls
    fixture_bytes += len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    calls += 1
    try:
        result = evaluate(kind, payload)
    except (ValueError, KeyError, ArithmeticError) as exc:
        print(json.dumps({"control": label, "error_type": type(exc).__name__, "error": str(exc)}), flush=True)
        if not rejected:
            raise
        return None
    print(json.dumps({"control": label, "result": result}, allow_nan=False, sort_keys=True), flush=True)
    if rejected:
        raise AssertionError(label + " unexpectedly accepted")
    return result


def close(actual, expected, tolerance=2e-12):
    assert math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), (actual, expected)


geometry = {
    "neural_a": [[0], [1], [3]], "neural_b": [[0], [2], [6]],
    "muscle": [[0, 0, 0, 0, 0, 0, 0], [3, 0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0]],
    "phase": [0, 3, 7], "velocity": [0, 4, 0],
    "scales": {"muscle_sd": [1, 1, 1, 1, 1, 1, 1], "phase_sd": 1, "phase_period": 8, "velocity_sd": 1},
    "pair_policy": "unique_offdiagonal",
    "edges": {name: [0, 1, 1.5] for name in ("neural", "muscle", "kinematic", "partition")},
    "ordering_draws": [[0, 1, 0, 2], [0, 1, 1, 2], [0, 2, 1, 2], [1, 0, 0, 1]],
    "ordering_min_neural_difference": 0, "ordering_tie_policy": "include_as_disagreement",
}


def main():
    result = call("geometry_sqrt_circular_pairing_orientation", "cycle_geometry", geometry)
    assert result["pair_count"] == 3
    for key, expected in {"neural": 2, "partition": 4, "muscle": 2, "kinematic": (6 + math.sqrt(32)) / 3}.items():
        close(result["means"][key], expected)
    assert result["histograms"]["muscle"]["counts"] == [[0, 1], [1, 1]]
    assert result["histograms"]["partition"]["counts"] == [[1, 0], [0, 2]]
    assert result["histograms"]["kinematic"]["counts"] == [[0, 1], [1, 1]]
    assert all(item["outside"] == 0 for item in result["histograms"].values())
    assert result["ordering"]["muscle"]["discordant"] == 3
    assert result["ordering"]["partition"]["concordant"] == 3
    assert result["ordering"]["kinematic"]["concordant"] == 1
    assert all(item["neural_excluded"] == 1 for item in result["ordering"].values())

    threshold = copy.deepcopy(geometry)
    threshold["ordering_min_neural_difference"] = 0.5
    threshold_result = call("threshold_boundary_excluded", "cycle_geometry", threshold)
    assert threshold_result["ordering"]["muscle"]["eligible"] == 1
    assert threshold_result["ordering"]["muscle"]["neural_excluded"] == 3

    ties = copy.deepcopy(geometry)
    ties["muscle"][1][0] = ties["muscle"][2][0] = 1
    ties["ordering_draws"] = [[0, 1, 0, 2]]
    tied = call("ties_counted_as_disagreement", "cycle_geometry", ties)["ordering"]["muscle"]
    assert (tied["eligible"], tied["ties"], tied["discordant"], tied["concordance"]) == (1, 1, 0, 0)
    ties["ordering_tie_policy"] = "exclude"
    tied = call("ties_excluded", "cycle_geometry", ties)["ordering"]["muscle"]
    assert (tied["eligible"], tied["ties"], tied["concordance"]) == (0, 1, None)

    ordered = copy.deepcopy(geometry)
    ordered["pair_policy"] = "full_ordered_with_diagonal"
    ordered["ordering_draws"] = [[0, 0, 0, 1]]
    ordered_result = call("ordered_diagonal_outside", "cycle_geometry", ordered)
    assert ordered_result["pair_count"] == 9
    for key, mean in result["means"].items():
        close(ordered_result["means"][key], mean * 2 / 3)
    assert ordered_result["histograms"]["muscle"]["outside"] == 4
    assert ordered_result["ordering"]["muscle"]["concordant"] == 1

    scaled = copy.deepcopy(geometry)
    scaled["scales"]["muscle_sd"][0] = 3
    scaled["scales"]["phase_sd"] = scaled["scales"]["velocity_sd"] = 2
    scaled_result = call("supplied_scale_effects", "cycle_geometry", scaled)
    close(scaled_result["means"]["muscle"], 2 / 3)
    close(scaled_result["means"]["kinematic"], result["means"]["kinematic"] / 2)

    for label, mutate in [
        ("zero_mean_rejected", lambda p: p.update(neural_b=[[0], [0], [0]])),
        ("zero_sd_rejected", lambda p: p["scales"].update(phase_sd=0)),
        ("edge_duplication_rejected", lambda p: p["edges"].update(neural=[0, 1, 1])),
        ("draw_diagonal_rejected", lambda p: p.update(ordering_draws=[[0, 0, 0, 1]])),
        ("bad_neural_width_rejected", lambda p: p.update(neural_b=[[0, 0], [2, 0], [6, 0]])),
        ("nonfinite_input_rejected", lambda p: p.update(phase=[0, float("inf"), 7])),
    ]:
        invalid = copy.deepcopy(geometry)
        mutate(invalid)
        call(label, "cycle_geometry", invalid, rejected=True)

    paired_cases = [
        ("df1_t1", [0, 2], 1, 0.5),
        ("df1_t_half_complement", [-1, 3], 0.5, 1 - 2 * math.atan(0.5) / math.pi),
        ("df2", [0, 1, 2], math.sqrt(3), 1 - math.sqrt(3 / 5)),
        ("df3", [0, 0, 2, 2], math.sqrt(3), 0.5 - 1 / math.pi),
        ("df5", [0, 0, 0, 2, 2, 2], math.sqrt(5), 0.5 - 4 / (3 * math.pi)),
        ("df1_far_tail", [999, 1001], 1000, 2 * math.atan(0.001) / math.pi),
        ("negative_statistic", [0, -2], -1, 0.5),
        ("zero_mean", [-1, 1], 0, 1),
    ]
    for label, left, statistic, probability in paired_cases:
        payload = {"left": left, "right": [0] * len(left), "unit_ids": ["invented-" + str(i) for i in range(len(left))]}
        paired = call(label, "paired_test", payload)
        close(paired["t_statistic"], statistic)
        close(paired["two_sided_p"], probability)
        close(paired["standard_error"], paired["sample_sd"] / math.sqrt(paired["n"]))
    undefined = call("constant_difference_undefined", "paired_test", {"left": [2, 2], "right": [0, 0], "unit_ids": ["a", "b"]})
    assert undefined["t_statistic"] is None and undefined["two_sided_p"] is None
    assert undefined["undefined_reason"] == "zero_standard_error"
    call("duplicate_pair_identity_rejected", "paired_test", {"left": [1, 2], "right": [0, 0], "unit_ids": ["a", "a"]}, rejected=True)
    call("single_pair_rejected", "paired_test", {"left": [1], "right": [0], "unit_ids": ["a"]}, rejected=True)

    interval = call("linear_interval", "draw_interval", {"draws": [6, 0, 4, 2], "alpha": 0.5})
    assert interval["interval"] == [1.5, 4.5]
    assert call("single_draw_interval", "draw_interval", {"draws": [7], "alpha": 0.05})["interval"] == [7, 7]
    interval = call("undefined_draw_preserved", "draw_interval", {"draws": [0, None, 6], "alpha": 0.05})
    assert interval == {"draw_count": 3, "undefined_count": 1, "interval": None, "status": "undefined_draws"}
    call("empty_draws_rejected", "draw_interval", {"draws": [], "alpha": 0.05}, rejected=True)
    call("invalid_alpha_rejected", "draw_interval", {"draws": [1, 2], "alpha": 1}, rejected=True)
    print(json.dumps({"summary": "passed", "calls": calls, "cumulative_invented_payload_bytes": fixture_bytes,
                      "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)


if __name__ == "__main__":
    main()
