"""Mechanical fixtures only; these must never become a scientific bank."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


oracle = load_module("allen_oracle_numerics", TASK / "solution/compute.py")
independent = load_module("allen_independent_numerics", TASK / "authoring/check_independent.py")


def node(sid, path, summary=False):
    return {"id": sid, "graph_id": 1, "structure_id_path": path,
            "structure_sets": [{"id": 167587189}] if summary else []}


def record(eid, target, numerator, denominator, rid):
    return {"id": rid, "section_data_set_id": eid, "structure_id": target,
            "hemisphere_id": 3, "is_injection": False,
            "projection_density": numerator / denominator if denominator else 0.0,
            "sum_projection_pixels": numerator, "sum_pixels": denominator}


def parse(records):
    return oracle.parse_unionizes(np.asarray([1, 2, 3]), np.asarray([10, 10, 20]),
                                  np.asarray([10, 20]), records)


def support_fixture():
    arrays = parse([record(1, 10, 1, 10, 1), record(2, 10, 90, 100, 2),
                    record(2, 20, 4, 10, 3), record(3, 10, 0, 0, 4), record(3, 20, 9, 10, 5)])
    arrays["matrix"], arrays["n_observed"], arrays["n_expected"] = oracle.aggregate(arrays)
    return arrays


def test_deepest_summary_ancestor_is_not_dependent_on_tree_iteration_order():
    nodes = [node(997, "/997/"), node(10, "/997/10/", True), node(11, "/997/10/11/", True),
             node(12, "/997/10/11/12/"), node(20, "/997/20/", True)]
    exps = [{"data_set_id": 2, "structure_id": 12, "transgenic_line": None},
            {"data_set_id": 1, "structure_id": 10, "transgenic_line": None},
            {"data_set_id": 3, "structure_id": 20, "transgenic_line": {"name": "Cre"}}]
    ids, sources, targets, tree = oracle.select_cohort(exps, nodes[::-1])
    np.testing.assert_array_equal(ids, [1, 2]); np.testing.assert_array_equal(sources, [10, 11])
    np.testing.assert_array_equal(targets, [10, 11, 20])
    assert independent.source_summary_ancestor(12, tree, set(targets)) == 11


def test_unmapped_primary_is_not_silently_dropped():
    nodes = [node(997, "/997/"), node(10, "/997/10/", True)]
    with pytest.raises(ValueError, match="no summary ancestor"):
        oracle.select_cohort([{"data_set_id": 1, "structure_id": 997, "transgenic_line": None}], nodes)


def test_missing_is_not_zero_and_zero_domain_is_not_an_observed_density():
    arrays = support_fixture()
    assert arrays["record_status"][0, 1] == "api_absent" and math.isnan(arrays["density"][0, 1])
    assert arrays["record_status"][2, 0] == "zero_domain" and arrays["density"][2, 0] == 0
    assert arrays["matrix"][0, 1] == 0.4 and math.isnan(arrays["matrix"][1, 0])
    np.testing.assert_array_equal(arrays["n_observed"], [[2, 1], [0, 1]])
    np.testing.assert_array_equal(arrays["n_expected"], [[2, 2], [1, 1]])


def test_equal_experiment_average_is_not_a_pixel_pooled_density():
    arrays = support_fixture()
    assert arrays["matrix"][0, 0] == 0.5
    assert arrays["matrix"][0, 0] != 91 / 110
    assert independent.mean_or_undefined([0.1, 0.9]) == arrays["matrix"][0, 0]
    assert math.isnan(independent.mean_or_undefined([]))


def test_incomplete_source_is_retained_but_not_in_headline_denominator():
    arrays = support_fixture(); result, rows = oracle.describe(arrays)
    assert result["n_source_regions"] == 2 and result["n_eligible_sources"] == 1
    assert result["n_self_strongest"] == 1 and result["self_strongest_fraction"] == 1
    assert rows[1]["status"] == "incomplete" and rows[1]["strongest_targets"] == []
    assert rows[1]["is_self_strongest"] is None and rows[1]["max_density"] is None


def test_legitimate_zero_row_has_all_targets_tied_without_an_extra_strength_gate():
    arrays = support_fixture(); arrays["matrix"][:] = 0
    result, rows = oracle.describe(arrays)
    assert result["n_zero_max_sources"] == 2 and result["n_tied_max_sources"] == 2
    assert result["self_strongest_fraction"] == 1
    assert all(row["strongest_targets"] == [10, 20] for row in rows)


def test_tie_tolerance_and_independent_set_computation():
    arrays = support_fixture(); arrays["matrix"] = np.array([[0.5, 0.5 + 0.5e-12], [0.1, 0.2]])
    result, rows = oracle.describe(arrays)
    assert rows[0]["strongest_targets"] == [10, 20] and rows[0]["is_self_strongest"]
    keyed = {(source, target): arrays["matrix"][i, j]
             for i, source in enumerate([10, 20]) for j, target in enumerate([10, 20])}
    actual = independent.independent_descriptors([10, 20], [10, 20], keyed)
    assert actual[0][2] == [10, 20]


@pytest.mark.parametrize("mutation", ["duplicate_key", "duplicate_id", "injection", "hemisphere", "foreign_target"])
def test_invalid_unionize_identity_or_domain_fails(mutation):
    first = record(1, 10, 1, 10, 1); other = record(2, 10, 1, 10, 2)
    if mutation == "duplicate_key": other["section_data_set_id"] = 1
    if mutation == "duplicate_id": other["id"] = 1
    if mutation == "injection": other["is_injection"] = True
    if mutation == "hemisphere": other["hemisphere_id"] = 1
    if mutation == "foreign_target": other["structure_id"] = 999
    with pytest.raises(ValueError): parse([first, other])


@pytest.mark.parametrize("value", [math.nan, math.inf, -0.1, 1.1, 0.6])
def test_invalid_or_inconsistent_density_fails(value):
    row = record(1, 10, 5, 10, 1); row["projection_density"] = value
    with pytest.raises(ValueError): parse([row])


def test_source_rounding_budget_is_not_bitwise_equality():
    row = record(1, 10, 5, 10, 1); row["projection_density"] += 1e-15
    assert parse([row])["record_status"][0, 0] == "observed"


def test_undefined_serialization_is_blank_not_zero_or_nonstandard_json():
    assert oracle.csv_value(math.nan) == "" and oracle.csv_value(None) == ""
    assert oracle.csv_value(0.0) == 0.0
