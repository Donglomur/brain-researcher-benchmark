"""Schema/source-identity mechanics, not measurements on the Allen release."""
import copy
import csv
import json
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import (number, integer, optional_number, optional_integer, boolean,
    optional_boolean, read_json, load_experiment_targets, load_matrix, load_support,
    load_strongest, validate_receipt_arrays, match_contract)
from matrix_contract import validate_experiment_targets, validate_matrix
from test_matrix import mechanics_fixture, matrix_rows, support_rows


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def receipt_rows(ref):
    return {(int(e), int(t)): (int(ref["experiment_source_ids"][i]), str(ref["record_status"][i, j]),
            int(ref["unionize_id"][i, j]), ref["density"][i, j], ref["sum_projection_pixels"][i, j], ref["sum_pixels"][i, j])
            for i, e in enumerate(ref["experiment_ids"]) for j, t in enumerate(ref["target_ids"])}


def receipt_csv_rows(ref):
    result = []
    for (experiment, target), values in receipt_rows(ref).items():
        source, status, unionize, density, projected, pixels = values
        result.append(dict(experiment_id=experiment, source_id=source, target_id=target, record_status=status,
            unionize_id="" if unionize == -1 else unionize, projection_density="" if np.isnan(density) else density,
            sum_projection_pixels="" if np.isnan(projected) else projected, sum_pixels="" if np.isnan(pixels) else pixels))
    return result


@pytest.mark.parametrize("value", [True, False, "NaN", "Inf", "-Inf"])
def test_nonfinite_or_boolean_measurement_rejected(value):
    with pytest.raises((AssertionError, ValueError)): number(value)


@pytest.mark.parametrize("value", [-1, .1, "2.5"])
def test_ids_not_rounded_or_negative(value):
    with pytest.raises(AssertionError): integer(value)


def test_reasonable_ids_and_missing_tokens():
    assert integer("123.0") == integer("1.23e2") == 123
    for value in ("", " NA ", "null", None):
        assert np.isnan(optional_number(value)) and optional_integer(value) == -1 and optional_boolean(value) is None
    for value in (True, "true", "1", "1.0"): assert boolean(value)
    for value in (False, "false", "0", "0.0"): assert not boolean(value)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '[]'])
def test_strict_json(tmp_path, text):
    path = tmp_path / "data.json"; path.write_text(text)
    with pytest.raises((AssertionError, ValueError)): read_json(path)


def test_extra_metadata_is_allowed_but_fixed_contract_cannot_change():
    match_contract({"flag": False, "x": 1., "extra": "description"}, {"flag": False, "x": 1})
    with pytest.raises(AssertionError): match_contract({"flag": 0}, {"flag": False})


def test_order_free_receipt_and_extra_columns(tmp_path):
    ref = mechanics_fixture(); rows = receipt_csv_rows(ref)[::-1]
    for row in rows:
        row["experiment_id"] = f'{row["experiment_id"]}.0'; row["description"] = "extra"
    path = tmp_path / "receipt.csv"; write_csv(path, rows)
    validate_experiment_targets(load_experiment_targets(path), ref)


@pytest.mark.parametrize("kind", ["duplicate", "unknown_status", "fractional_id", "nan_density"])
def test_receipt_parser_rejects_malformed_values(tmp_path, kind):
    rows = receipt_csv_rows(mechanics_fixture())
    if kind == "duplicate": rows.append(rows[0].copy())
    elif kind == "unknown_status": rows[0]["record_status"] = "imputed"
    elif kind == "fractional_id": rows[0]["target_id"] = .1
    else: rows[0]["projection_density"] = "NaN"
    path = tmp_path / "receipt.csv"; write_csv(path, rows)
    with pytest.raises((AssertionError, ValueError)): load_experiment_targets(path)


@pytest.mark.parametrize("kind", ["drop", "foreign_experiment", "source_alias", "wrong_status", "wrong_unionize", "wrong_density", "wrong_pixels"])
def test_receipt_is_bound_to_source_not_only_result(kind):
    ref = mechanics_fixture(); rows = receipt_rows(ref); key = (1001, 10)
    values = list(rows[key])
    if kind == "drop": del rows[key]
    elif kind == "foreign_experiment": rows[(9000, 10)] = rows.pop(key)
    elif kind == "source_alias": values[0] = 20
    elif kind == "wrong_status": values[1] = "zero_domain"
    elif kind == "wrong_unionize": values[2] += 999
    elif kind == "wrong_density": values[3] *= 2
    else: values[5] *= 2
    if kind not in ("drop", "foreign_experiment"): rows[key] = tuple(values)
    with pytest.raises(AssertionError): validate_experiment_targets(rows, ref)


@pytest.mark.parametrize("kind", ["missing_filled_zero", "observed_missing", "observed_zero_domain", "negative_measurement"])
def test_status_semantics_do_not_conflate_absence_with_zero(kind):
    ref = mechanics_fixture()
    if kind == "missing_filled_zero": ref["density"][1, 1] = 0
    elif kind == "observed_missing": ref["density"][0, 0] = np.nan
    elif kind == "observed_zero_domain": ref["sum_pixels"][0, 0] = 0
    else: ref["density"][0, 0] = -.1
    with pytest.raises(AssertionError): validate_receipt_arrays(ref)


def test_wide_matrix_target_order_numeric_ids_and_extra_columns(tmp_path):
    ref = mechanics_fixture(); rows = []
    for source, values in reversed(list(matrix_rows(ref).items())):
        rows.append({"description": "extra", **{f"{target}.0": "NA" if np.isnan(value) else value
            for target, value in reversed(list(values.items()))}, "source_id": source})
    path = tmp_path / "matrix.csv"; write_csv(path, rows)
    validate_matrix(load_matrix(path, ref["target_ids"]), support_rows(ref), ref, ref)


@pytest.mark.parametrize("kind", ["missing", "foreign", "numeric_alias_duplicate"])
def test_matrix_target_support_is_exact(tmp_path, kind):
    row = {"source_id": 10, "10": .1, "20": .2, "30": .3}
    if kind == "missing": del row["30"]
    elif kind == "foreign": row["40"] = row.pop("30")
    else: row["10.0"] = .1
    path = tmp_path / "matrix.csv"; write_csv(path, [row])
    with pytest.raises(AssertionError): load_matrix(path, [10, 20, 30])


def test_tie_list_order_free_but_no_duplicates(tmp_path):
    row = dict(source_id=20, status="complete", strongest_targets="[30,10,20]", is_self_strongest="true",
               max_density=0., n_missing_targets=0, n_experiments=1)
    path = tmp_path / "strongest.csv"; write_csv(path, [row])
    assert load_strongest(path)[20]["strongest_targets"] == {10, 20, 30}
    row["strongest_targets"] = "[20,20]"; write_csv(path, [row])
    with pytest.raises(AssertionError, match="duplicate tied target"): load_strongest(path)


@pytest.mark.parametrize("kind", ["density_above_one", "numerator_above_denominator", "ratio_disagrees", "zero_domain_positive_numerator"])
def test_raw_physical_domain_and_ratio_checks(kind):
    ref = mechanics_fixture()
    if kind == "density_above_one": ref["density"][0, 0] = 1.01
    elif kind == "numerator_above_denominator": ref["sum_projection_pixels"][0, 0] = 11.
    elif kind == "ratio_disagrees": ref["sum_projection_pixels"][0, 0] *= .9
    else: ref["sum_projection_pixels"][3, 1] = 1e-20
    with pytest.raises(AssertionError): validate_receipt_arrays(ref)


def test_opposing_accepted_field_errors_cannot_violate_pixel_ratio():
    ref = mechanics_fixture(); rows = receipt_rows(ref)
    values = list(rows[(1001, 10)])
    values[3] = .2+1.8e-10
    values[4] = 2.-1.8e-9
    assert np.isclose(values[3], ref["density"][0, 0], atol=1e-12, rtol=1e-9)
    assert np.isclose(values[4], ref["sum_projection_pixels"][0, 0], atol=1e-12, rtol=1e-9)
    rows[(1001, 10)] = tuple(values)
    with pytest.raises(AssertionError, match="pixel ratio"):
        validate_experiment_targets(rows, ref)


def test_physically_consistent_small_rounding_is_accepted():
    ref = mechanics_fixture(); rows = receipt_rows(ref)
    values = list(rows[(1001, 10)])
    values[3] += 5e-11; values[4] = values[3]*values[5]
    rows[(1001, 10)] = tuple(values)
    validate_experiment_targets(rows, ref)
