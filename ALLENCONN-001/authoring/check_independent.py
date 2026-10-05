"""Source-keyed independent stdlib aggregation; never imports the oracle.

Use independently parsed official records, dictionary grouping and math.fsum,
not the oracle's dense masked NumPy summation. This checks computational lineage,
not a biological interpretation or the truth of inferred regional connections.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def mean_or_undefined(values):
    return math.fsum(values) / len(values) if values else math.nan


def source_summary_ancestor(primary, tree, target_ids):
    path = [int(item) for item in tree[primary]["structure_id_path"].split("/") if item]
    if not path or path[-1] != primary or len(path) != len(set(path)):
        raise ValueError("invalid source hierarchy")
    for node in reversed(path):
        if node in target_ids:
            return node
    raise ValueError("source has no target-set ancestor")


def independent_descriptors(source_ids, target_ids, values):
    records = []
    for source in source_ids:
        row = [values[source, target] for target in target_ids]
        if not all(math.isfinite(value) for value in row):
            records.append((source, None, [], None))
        else:
            maximum = max(row)
            ties = [target for target, value in zip(target_ids, row) if abs(value - maximum) <= 1e-12]
            records.append((source, maximum, ties, source in ties))
    return records


def check(output_dir, data_dir, report_path):
    output_dir, data_dir = Path(output_dir), Path(data_dir)
    manifest = json.loads((data_dir / "source_manifest.json").read_text())
    assert manifest["snapshot_id"] == "allen-connectivity-20261001"
    roles = defaultdict(list)
    for entry in manifest["files"]:
        path = data_dir / entry["path"]
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assert digest == entry["sha256"] and path.stat().st_size == entry["size_bytes"]
        document = json.loads(path.read_text())
        assert document["success"] and document["num_rows"] == len(document["msg"])
        roles[entry["role"]].extend(document["msg"])
    tree = {int(row["id"]): row for row in roles["structures"]}
    target_ids = sorted(sid for sid, row in tree.items()
                        if any(int(group["id"]) == 167587189 for group in row["structure_sets"]))
    exps = []
    for experiment in roles["experiments"]:
        line = experiment.get("transgenic_line")
        line_name = line.get("name") if line else None
        if not line_name:
            exps.append(experiment)
    exps.sort(key=lambda item: item["data_set_id"])
    experiment_ids = [int(item["data_set_id"]) for item in exps]
    source_by_experiment = {int(item["data_set_id"]): source_summary_ancestor(int(item["structure_id"]), tree, set(target_ids))
                            for item in exps}
    source_ids = sorted(set(source_by_experiment.values()))
    assert len(experiment_ids) == len(set(experiment_ids)) == 498 and len(target_ids) == 316
    raw = {}; row_ids = set()
    for record in roles["projection_page"]:
        key = int(record["section_data_set_id"]), int(record["structure_id"])
        assert key[0] in source_by_experiment and key[1] in target_ids
        assert record["is_injection"] is False and record["hemisphere_id"] == 3
        assert key not in raw and record["id"] not in row_ids
        raw[key] = record; row_ids.add(record["id"])
    with np.load(output_dir / "analysis_arrays.npz", allow_pickle=False) as archive:
        retained = {name: archive[name] for name in archive.files}
    for name, expected in [("experiment_ids", experiment_ids), ("target_ids", target_ids), ("source_ids", source_ids),
                           ("experiment_source_ids", [source_by_experiment[e] for e in experiment_ids])]:
        np.testing.assert_array_equal(retained[name], expected)
    grouped = defaultdict(list); expected_counts = defaultdict(int)
    statuses = {"observed": 0, "api_absent": 0, "zero_domain": 0}
    max_ratio_error = 0.0
    for i, experiment in enumerate(experiment_ids):
        source = source_by_experiment[experiment]
        expected_counts[source] += 1
        for j, target in enumerate(target_ids):
            record = raw.get((experiment, target))
            if record is None:
                status = "api_absent"
                assert retained["unionize_id"][i, j] == -1
                assert all(math.isnan(retained[field][i, j]) for field in ("density", "sum_projection_pixels", "sum_pixels"))
            else:
                density, numerator, denominator = [float(record[field]) for field in
                                                   ("projection_density", "sum_projection_pixels", "sum_pixels")]
                assert all(math.isfinite(value) for value in (density, numerator, denominator))
                assert 0 <= density <= 1 and 0 <= numerator <= denominator
                assert retained["unionize_id"][i, j] == record["id"]
                for name, expected in [("density", density), ("sum_projection_pixels", numerator), ("sum_pixels", denominator)]:
                    assert retained[name][i, j] == expected
                if denominator == 0:
                    status = "zero_domain"
                else:
                    status = "observed"
                    max_ratio_error = max(max_ratio_error, abs(density - numerator / denominator))
                    assert abs(density - numerator / denominator) <= 1e-12 + 1e-9 * abs(numerator / denominator)
                    grouped[source, target].append(density)
            statuses[status] += 1
            assert retained["record_status"][i, j] == status
    means = {(source, target): mean_or_undefined(grouped[source, target])
             for source in source_ids for target in target_ids}
    matrix = np.asarray([[means[source, target] for target in target_ids] for source in source_ids])
    counts = np.asarray([[len(grouped[source, target]) for target in target_ids] for source in source_ids])
    expected = np.asarray([[expected_counts[source]] * len(target_ids) for source in source_ids])
    np.testing.assert_allclose(retained["matrix"], matrix, atol=1e-12, rtol=1e-9, equal_nan=True)
    np.testing.assert_array_equal(retained["n_observed"], counts)
    np.testing.assert_array_equal(retained["n_expected"], expected)
    descriptors = independent_descriptors(source_ids, target_ids, means)
    eligible = [row for row in descriptors if row[1] is not None]
    n_self = sum(int(row[3]) for row in eligible)
    result = json.loads((output_dir / "self_projection.json").read_text())
    assert result["n_eligible_sources"] == len(eligible) and result["n_self_strongest"] == n_self
    assert result["self_strongest_fraction"] == n_self / len(eligible)
    assert result["record_status_counts"] == statuses
    assert result["n_zero_max_sources"] == sum(row[1] == 0 for row in eligible)
    assert result["n_tied_max_sources"] == sum(len(row[2]) > 1 for row in eligible)
    import csv
    with (output_dir / "source_strongest.csv").open(newline="") as stream:
        submitted = {int(row["source_id"]): row for row in csv.DictReader(stream)}
    assert set(submitted) == set(source_ids)
    for source, maximum, ties, self_max in descriptors:
        row = submitted[source]
        assert set(json.loads(row["strongest_targets"])) == set(ties)
        assert row["status"] == ("complete" if maximum is not None else "incomplete")
        if maximum is not None:
            assert abs(float(row["max_density"]) - maximum) <= 1e-12 + 1e-9 * abs(maximum)
            assert row["is_self_strongest"].lower() == str(self_max).lower()
    finite = np.isfinite(matrix)
    report = {"status": "passed", "n_source_files": len(manifest["files"]),
              "n_experiments": len(experiment_ids), "n_target_structures": len(target_ids),
              "n_source_regions": len(source_ids), "record_status_counts": statuses,
              "max_abs_raw_density_ratio_error": max_ratio_error,
              "max_abs_matrix_diff": float(np.max(np.abs(matrix[finite] - retained["matrix"][finite]))) if finite.any() else None,
              "n_eligible_sources": len(eligible), "n_self_strongest": n_self,
              "self_strongest_fraction": n_self / len(eligible),
              "implementation": "independent raw JSON parsing, reverse-path mapping, keyed groups, stdlib math.fsum; no oracle import",
              "limit": "computational source/aggregation agreement, not biological validation of a regional connectivity model"}
    Path(report_path).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/allen"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    check(args.output_dir, args.data_dir, args.report)
