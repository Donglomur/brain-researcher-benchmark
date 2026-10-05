"""Source-run positives and coherent forgeries; never builds a bank or fetches data."""
import csv
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import load_reference, read_json, PIPELINE_ID, RECORD_STATUSES
from matrix_contract import validate_output_directory

FILES = ("experiment_targets.csv", "connectivity_matrix.csv", "matrix_support.csv",
         "source_strongest.csv", "self_projection.json", "run_metadata.json", "findings.md")


@pytest.fixture(scope="module")
def genuine():
    value = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not value:
        pytest.skip("requires genuine frozen-source REPAIR_ORACLE_OUTPUT; no invented bank")
    output, reference = Path(value), load_reference()
    assert len(reference["experiment_ids"]) == 498 and len(reference["target_ids"]) == 316
    assert len(reference["source_ids"]) == 157 and len(reference["stats"]["source_sha256"]) == 37
    validate_output_directory(output, reference)
    return output, reference


@pytest.fixture
def output_copy(genuine, tmp_path):
    original, reference = genuine
    for name in FILES: shutil.copyfile(original / name, tmp_path / name)
    return tmp_path, reference


def read_rows(path):
    with path.open(newline="") as stream: return list(csv.DictReader(stream))


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def rebuild_derived(output, rows=None, mode="equal"):
    """Recompute all public arithmetic from forged rows, independently of the bank.

Wrong weighting modes deliberately retain coherent matrix/argmax/headline files;
the scientific contract, not a disconnected summary, must reject them.
"""
    if rows is None: rows = read_rows(output / "experiment_targets.csv")
    experiments, targets, status_counts = {}, set(), {key: 0 for key in RECORD_STATUSES}
    values, projected, pixels = {}, {}, {}
    for row in rows:
        experiment, source, target = int(row["experiment_id"]), int(row["source_id"]), int(row["target_id"])
        assert experiment not in experiments or experiments[experiment] == source
        experiments[experiment] = source; targets.add(target)
        status_counts[row["record_status"]] += 1
        if row["record_status"] == "observed":
            key = source, target
            values.setdefault(key, []).append(float(row["projection_density"]))
            projected.setdefault(key, []).append(float(row["sum_projection_pixels"]))
            pixels.setdefault(key, []).append(float(row["sum_pixels"]))
    sources, targets = sorted(set(experiments.values())), sorted(targets)
    n_expected = {source: sum(value == source for value in experiments.values()) for source in sources}
    matrix_rows, support, strongest = [], [], []
    for source in sources:
        matrix = {"source_id": source}; vector = []
        for target in targets:
            key = source, target; n = len(values.get(key, []))
            value = math.fsum(values[key])/n if n else np.nan
            if mode == "pixel_weighted" and n: value = math.fsum(projected[key])/math.fsum(pixels[key])
            if mode == "expected_denominator" and n: value = math.fsum(values[key])/n_expected[source]
            if mode == "scale_matrix" and n: value *= 2
            matrix[str(target)] = float(value) if np.isfinite(value) else ""; vector.append(value)
            support.append(dict(source_id=source, target_id=target, n_observed=n, n_expected=n_expected[source]))
        vector = np.asarray(vector); missing = int(np.isnan(vector).sum())
        maximum = float(np.max(vector)) if not missing else None
        tied = [target for target, value in zip(targets, vector) if maximum is not None and abs(value-maximum) <= 1e-12]
        strongest.append(dict(source_id=source, status="incomplete" if missing else "complete",
            strongest_targets=json.dumps(tied), is_self_strongest="" if missing else int(source in tied),
            max_density="" if missing else maximum, n_missing_targets=missing, n_experiments=n_expected[source]))
        matrix_rows.append(matrix)
    eligible = [row for row in strongest if row["status"] == "complete"]
    n_self = sum(row["is_self_strongest"] for row in eligible)
    result = dict(status="ok", pipeline_id=PIPELINE_ID, n_experiments=len(experiments), n_target_structures=len(targets),
        n_source_regions=len(sources), n_eligible_sources=len(eligible), n_self_strongest=n_self,
        self_strongest_fraction=n_self/len(eligible) if eligible else None,
        n_zero_max_sources=sum(row["max_density"] == 0 for row in eligible),
        n_tied_max_sources=sum(len(json.loads(row["strongest_targets"])) > 1 for row in eligible), record_status_counts=status_counts)
    metadata = read_json(output / "run_metadata.json"); metadata.update(result)
    write_rows(output / "experiment_targets.csv", rows)
    write_rows(output / "connectivity_matrix.csv", matrix_rows)
    write_rows(output / "matrix_support.csv", support)
    write_rows(output / "source_strongest.csv", strongest)
    write_json(output / "self_projection.json", result); write_json(output / "run_metadata.json", metadata)


def test_genuine_source_outputs_pass(genuine):
    validate_output_directory(*genuine)


def test_public_template_matches_frozen_contract(genuine):
    _, reference = genuine
    assert read_json(Path(__file__).parents[1] / "environment/method_contract.json") == reference["stats"]["metadata_contract"]


def test_minimal_participant_metadata_from_public_template_passes(output_copy):
    output, reference = output_copy
    metadata = read_json(Path(__file__).parents[1] / "environment/method_contract.json")
    metadata.update(read_json(output / "self_projection.json"))
    write_json(output / "run_metadata.json", metadata)
    validate_output_directory(output, reference)


def test_reordered_rows_columns_ties_free_prose_and_extra_columns_pass(output_copy):
    output, reference = output_copy
    for name in FILES[:4]:
        rows = read_rows(output / name)[::-1]
        for row in rows:
            row["description"] = "extra"
            for key in ("experiment_id", "source_id", "target_id", "unionize_id", "n_observed", "n_expected", "n_missing_targets", "n_experiments"):
                if key in row and row[key]: row[key] = f"{int(row[key])}.0"
            if "strongest_targets" in row:
                row["strongest_targets"] = json.dumps(json.loads(row["strongest_targets"])[::-1])
            if "is_self_strongest" in row and row["is_self_strongest"]:
                row["is_self_strongest"] = "true" if str(row["is_self_strongest"]).lower() in ("true", "1") else "false"
        rows = [dict(reversed(list(row.items()))) for row in rows]
        write_rows(output / name, rows)
    (output / "findings.md").write_text("这是冻结图谱上的描述性汇总，不代表突触连接概率。\n")
    validate_output_directory(output, reference)


def test_independent_fsum_reaggregation_matches_source_outputs(output_copy):
    output, reference = output_copy; rebuild_derived(output)
    validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["duplicate", "drop_one", "foreign_target", "fractional_id", "wrong_unionize"])
def test_receipt_cartesian_membership_and_record_identity(output_copy, kind):
    output, reference = output_copy; rows = read_rows(output / "experiment_targets.csv")
    if kind == "duplicate": rows.append(rows[0].copy())
    elif kind == "drop_one": rows.pop()
    elif kind == "foreign_target": rows[0]["target_id"] = int(max(reference["target_ids"]))+100000
    elif kind == "fractional_id": rows[0]["experiment_id"] = float(rows[0]["experiment_id"])+.1
    else:
        present = next(row for row in rows if row["record_status"] != "api_absent")
        present["unionize_id"] = int(present["unionize_id"])+1000000000
    write_rows(output / "experiment_targets.csv", rows)
    with pytest.raises((AssertionError, ValueError)):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["scaled_measurements", "shifted_measurements", "source_alias", "target_shift", "missing_filled_zero", "drop_experiment", "raw_pixels_rescaled"])
def test_coherent_receipt_matrix_and_headline_forgeries_fail(output_copy, kind):
    output, reference = output_copy; rows = read_rows(output / "experiment_targets.csv")
    reason = "experiment density differs from raw source"
    if kind in ("scaled_measurements", "shifted_measurements"):
        for row in rows:
            if row["record_status"] == "observed":
                density = float(row["projection_density"])
                row["projection_density"] = density*.5 if kind == "scaled_measurements" else density+(1-density)*.01
                row["sum_projection_pixels"] = float(row["projection_density"])*float(row["sum_pixels"])
    elif kind == "source_alias":
        first = int(rows[0]["experiment_id"]); original = int(rows[0]["source_id"])
        alias = next(int(source) for source in reference["source_ids"] if source != original)
        for row in rows:
            if int(row["experiment_id"]) == first: row["source_id"] = alias
        reason = "experiment source mapping differs"
    elif kind == "target_shift":
        targets = list(map(int, reference["target_ids"])); shifted = dict(zip(targets, targets[1:]+targets[:1]))
        for row in rows: row["target_id"] = shifted[int(row["target_id"])]
        reason = "(record statuses|record IDs) differ from source"
    elif kind == "missing_filled_zero":
        missing = [row for row in rows if row["record_status"] == "api_absent"]
        assert missing, "real source must contain missing records for this control"
        for index, row in enumerate(missing):
            row.update(record_status="observed", unionize_id=9000000000+index,
                       projection_density=0., sum_projection_pixels=0., sum_pixels=1.)
        reason = "record statuses differ from source"
    elif kind == "drop_experiment":
        first = rows[0]["experiment_id"]; rows = [row for row in rows if row["experiment_id"] != first]
        reason = "Cartesian experiment/target membership"
    else:
        for row in rows:
            if row["record_status"] != "api_absent":
                row["sum_projection_pixels"] = float(row["sum_projection_pixels"])*2
                row["sum_pixels"] = float(row["sum_pixels"])*2
        reason = "experiment sum_projection_pixels differs from raw source"
    rebuild_derived(output, rows)
    with pytest.raises(AssertionError, match=reason): validate_output_directory(output, reference)


@pytest.mark.parametrize("mode", ["pixel_weighted", "expected_denominator", "scale_matrix"])
def test_wrong_aggregation_with_consistent_argmax_and_headline_fails(output_copy, mode):
    output, reference = output_copy; rebuild_derived(output, mode=mode)
    with pytest.raises(AssertionError, match="equal-experiment density means"):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["drop_source", "drop_target", "duplicate_source"])
def test_full_matrix_support_is_required(output_copy, kind):
    output, reference = output_copy; rows = read_rows(output / "connectivity_matrix.csv")
    if kind == "drop_source": rows.pop()
    elif kind == "duplicate_source": rows.append(rows[0].copy())
    else:
        target = str(reference["target_ids"][0])
        for row in rows: del row[target]
    write_rows(output / "connectivity_matrix.csv", rows)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["observed", "expected", "duplicate"])
def test_explicit_matrix_denominators_are_not_decorative(output_copy, kind):
    output, reference = output_copy; rows = read_rows(output / "matrix_support.csv")
    if kind == "duplicate": rows.append(rows[0].copy())
    else: rows[0][f"n_{kind}"] = int(rows[0][f"n_{kind}"])+1
    write_rows(output / "matrix_support.csv", rows)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


def test_fabricated_tie_and_derived_tie_count_fail(output_copy):
    output, reference = output_copy; rows = read_rows(output / "source_strongest.csv")
    row = next(row for row in rows if row["status"] == "complete" and len(json.loads(row["strongest_targets"])) < len(reference["target_ids"]))
    tied = json.loads(row["strongest_targets"]); was_tied = len(tied) > 1
    extra = next(int(target) for target in reference["target_ids"] if target not in tied)
    tied.append(extra); row["strongest_targets"] = json.dumps(tied)
    old_self = str(row["is_self_strongest"]).lower() in ("true", "1")
    row["is_self_strongest"] = int(int(row["source_id"]) in tied)
    write_rows(output / "source_strongest.csv", rows)
    for name in ("self_projection.json", "run_metadata.json"):
        result = read_json(output / name)
        result["n_tied_max_sources"] += int(not was_tied)
        result["n_self_strongest"] += row["is_self_strongest"]-int(old_self)
        result["self_strongest_fraction"] = result["n_self_strongest"]/result["n_eligible_sources"]
        write_json(output / name, result)
    with pytest.raises(AssertionError, match="strongest_targets"):
        validate_output_directory(output, reference)


def test_false_incomplete_exclusion_cannot_change_denominator(output_copy):
    output, reference = output_copy; rows = read_rows(output / "source_strongest.csv")
    row = next(row for row in rows if row["status"] == "complete")
    old_self = int(str(row["is_self_strongest"]).lower() in ("true", "1"))
    was_tied = len(json.loads(row["strongest_targets"])) > 1; was_zero = float(row["max_density"]) == 0
    row.update(status="incomplete", strongest_targets="[]", is_self_strongest="", max_density="", n_missing_targets=1)
    write_rows(output / "source_strongest.csv", rows)
    for name in ("self_projection.json", "run_metadata.json"):
        result = read_json(output / name)
        result["n_eligible_sources"] -= 1; result["n_self_strongest"] -= old_self
        result["n_tied_max_sources"] -= int(was_tied); result["n_zero_max_sources"] -= int(was_zero)
        result["self_strongest_fraction"] = result["n_self_strongest"]/result["n_eligible_sources"]
        write_json(output / name, result)
    with pytest.raises(AssertionError, match="status"): validate_output_directory(output, reference)


@pytest.mark.parametrize("key", ["n_eligible_sources", "n_experiments", "n_self_strongest", "self_strongest_fraction", "record_status_counts"])
def test_consistent_json_metadata_forgery_still_fails_recomputation(output_copy, key):
    output, reference = output_copy
    for name in ("self_projection.json", "run_metadata.json"):
        result = read_json(output / name)
        if key == "record_status_counts":
            result[key]["observed"] -= 1; result[key]["api_absent"] += 1
        else: result[key] += .01 if key == "self_strongest_fraction" else 1
        write_json(output / name, result)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


def test_source_hash_relabelling_fails(output_copy):
    output, reference = output_copy; metadata = read_json(output / "run_metadata.json")
    key = next(iter(metadata["source_sha256"])); metadata["source_sha256"][key] = "0"*64
    write_json(output / "run_metadata.json", metadata)
    with pytest.raises(AssertionError, match="source_sha256"): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_findings_required_without_keyword_gate(output_copy, kind):
    output, reference = output_copy
    if kind == "missing": (output / "findings.md").unlink()
    else: (output / "findings.md").write_text(" \n\t")
    with pytest.raises((AssertionError, FileNotFoundError)): validate_output_directory(output, reference)
