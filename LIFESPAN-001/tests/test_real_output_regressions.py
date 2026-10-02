"""Real-output metamorphic and mutation checks; original-source truth is replayed.

These authoring checks are not part of the participant's single grading test.
Every mutation must change real output and retain the untouched original tree.
"""
import csv
import json
import os
from pathlib import Path

import numpy as np
import pytest

from fixture_support import artifact_copy
import proof_of_work as grader


def edit_json(root, name, change):
    path = root / name
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value, allow_nan=False))


def edit_csv(root, name, change):
    path = root / name
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    change(rows)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def edit_arrays(root, change):
    path = root / "connectome_primitives.npz"
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    change(arrays)
    np.savez_compressed(path, **arrays)


def reorder_axes(a):
    s, r = len(a["subject_id"]), len(a["roi_index"])
    t = int(a["subject_frame_offsets"][1])
    sp, rp = np.arange(s)[::-1], np.arange(r)[::-1]
    ep = np.arange(len(a["edge_roi_index"]))[::-1]
    a["subject_id"] = a["subject_id"][sp]
    a["roi_timeseries"] = a["roi_timeseries"].reshape(s,t,r)[sp, ::-1, :][:,:,rp].reshape(s*t,r)
    a["frame_index"] = a["frame_index"].reshape(s,t)[sp, ::-1].reshape(s*t)
    a["parcel_status"] = a["parcel_status"][np.ix_(sp,rp)]
    for key in ("raw_r", "fisher_z", "edge_valid"):
        a[key] = a[key][np.ix_(sp,ep)]
    a["edge_roi_index"] = a["edge_roi_index"][ep, ::-1]
    for key in ("group_features", "group_valid"):
        a[key] = a[key][np.ix_(rp,rp)]
    offsets, vertices = a["vertex_offsets"], a["vertex_index"]
    blocks = [vertices[offsets[j]:offsets[j+1]][::-1] for j in rp]
    a["vertex_offsets"] = np.r_[0,np.cumsum([len(block) for block in blocks])]
    a["vertex_index"] = np.concatenate(blocks)
    a["roi_index"] = a["roi_index"][rp]


def relabel(root):
    transform = lambda label: "network/" + label + "/renamed"
    edit_csv(root, "roi_partition.csv", lambda rows: [row.update(network_id=transform(row["network_id"]))
             for row in rows if row["network_id"]])
    edit_json(root, "partition.json", lambda value: [row.update(network_id=transform(row["network_id"]))
              for row in value["clusters"]])


POSITIVE_CASES = ("axis_permutation", "cluster_renaming", "csv_row_order", "float64_means",
                  "neighbor_means", "numeric_masks", "metadata_extras", "six_decimal_summaries")


def positive(root, case):
    if case == "axis_permutation": edit_arrays(root, reorder_axes)
    elif case == "cluster_renaming": relabel(root)
    elif case == "csv_row_order":
        for name in ("cohort.csv", "parcels.csv", "roi_partition.csv", "connectome_summary.csv"):
            edit_csv(root, name, lambda rows: rows.reverse())
    elif case == "float64_means":
        edit_arrays(root, lambda a: a.update(roi_timeseries=a["roi_timeseries"].astype(np.float64)))
    elif case == "neighbor_means":
        def change(a):
            q = a["roi_timeseries"].astype(np.float32)
            next_q = np.nextafter(q, np.float32(np.inf))
            a["roi_timeseries"] = np.where(np.isfinite(next_q), next_q, q).astype(np.float64)
        edit_arrays(root, change)
    elif case == "numeric_masks":
        edit_arrays(root, lambda a: a.update(edge_valid=a["edge_valid"].astype(np.int8),
                                           group_valid=a["group_valid"].astype(np.float64)))
    elif case == "metadata_extras":
        def change(value):
            value["software_versions"] = {"alternative": "truthful implementation description"}
            value["warnings"] = ["Optional descriptive diagnostic wording."]
            value["source_files"].reverse()
            value["source_observed"]["subjects"].reverse()
            value["source_observed"]["extra_timing_note"] = "Header units are unspecified."
            value["additional_measurement"] = 123.0
        edit_json(root, "run_metadata.json", change)
    else:
        assert case == "six_decimal_summaries"
        keys = ("global_fisher_sum", "global_connectivity", "within_positive_sum", "between_positive_sum",
                "within_network_connectivity", "between_network_connectivity", "system_segregation")
        edit_csv(root, "connectome_summary.csv", lambda rows: [row.update({k:format(float(row[k]), ".6f")
                 for k in keys if row[k] != ""}) for row in rows])


NEGATIVE_CASES = ("missing_subject", "duplicate_subject", "source_age", "source_hash", "parcel_label",
                  "source_vertex", "mean_error", "raw_r", "fisher_z", "group_diagonal", "group_mean",
                  "edge_mask", "parcel_status", "partition_assignment", "pair_denominator", "summary_value",
                  "endpoint_r", "endpoint_p", "ci_order", "pilot_status", "timing_unit", "missing_source",
                  "failure_marker", "nonfinite_json", "empty_findings", "missing_artifact")


def negative(root, case):
    if case in ("missing_subject", "duplicate_subject", "source_age", "source_hash"):
        def change(rows):
            if case == "missing_subject": rows.pop()
            elif case == "duplicate_subject": rows[-1]["subject_id"] = rows[0]["subject_id"]
            elif case == "source_age": rows[0]["age_source"] = str(float(rows[0]["age_source"])+1)
            else: rows[0]["left_sha256"] = "0"*64
        edit_csv(root, "cohort.csv", change)
    elif case == "parcel_label":
        edit_csv(root, "parcels.csv", lambda rows: rows[0].update(label_name="not_source_label"))
    elif case in ("source_vertex", "mean_error", "raw_r", "fisher_z", "group_diagonal", "group_mean", "edge_mask", "parcel_status"):
        def change(a):
            if case == "source_vertex": a["vertex_index"][0] = 1_000_000
            elif case == "mean_error": a["roi_timeseries"][0,0] += np.float32(100)
            elif case in ("raw_r", "fisher_z"):
                i,j = np.argwhere(a["edge_valid"])[0]
                a[case][i,j] += 0.05
            elif case == "group_diagonal": a["group_features"][0,0] = 0.5
            elif case == "group_mean":
                ij = np.argwhere(a["group_valid"] & ~np.eye(len(a["roi_index"]),dtype=bool))[0]
                a["group_features"][tuple(ij)] += 0.05
            elif case == "edge_mask": a["edge_valid"][0,0] = not a["edge_valid"][0,0]
            else: a["parcel_status"][0,0] = "invalid"
        edit_arrays(root, change)
    elif case == "partition_assignment":
        def change(rows):
            different = next(row["network_id"] for row in rows if row["network_id"] != rows[0]["network_id"])
            rows[0]["network_id"] = different
        edit_csv(root, "roi_partition.csv", change)
    elif case in ("pair_denominator", "summary_value"):
        key = "n_within_edges" if case == "pair_denominator" else "global_connectivity"
        edit_csv(root, "connectome_summary.csv", lambda rows: rows[0].update({key:str(float(rows[0][key])+1)}))
    elif case in ("endpoint_r", "endpoint_p", "ci_order", "pilot_status"):
        def change(value):
            if case == "pilot_status": value["status"] = "resource_pilot"; return
            e = value["overall_connectivity_vs_age"]
            assert e["status"] == "ok", "Actual endpoint undefined; control must be reviewed, not silently skipped"
            if case == "endpoint_r": e["pearson_r"] = 0.9 if e["pearson_r"] < 0.5 else -0.9
            elif case == "endpoint_p": e["p"] = 0 if e["p"] > 0.5 else 1
            else: e["ci95"] = [1,-1]
        edit_json(root, "results.json", change)
    elif case in ("timing_unit", "missing_source"):
        def change(value):
            if case == "timing_unit": value["source_observed"]["header_timing_unit"] = "seconds"
            else: value["source_files"].pop()
        edit_json(root, "run_metadata.json", change)
    elif case == "failure_marker": (root / "failure_report.json").write_text("")
    elif case == "nonfinite_json":
        path = root / "results.json"
        path.write_text(path.read_text().replace("{", '{"nonfinite_extra":NaN,',1))
    elif case == "empty_findings": (root / "findings.md").write_text(" \n")
    else:
        assert case == "missing_artifact"
        (root / "results.json").unlink()


@pytest.mark.parametrize("case", POSITIVE_CASES)
def test_real_equivalent_evidence(case, source_reference):
    original = Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    with artifact_copy(original) as output:
        positive(output, case)
        grader.validate(output, source_reference)


@pytest.mark.parametrize("case", NEGATIVE_CASES)
def test_real_changed_evidence_rejected(case, source_reference):
    original = Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    with artifact_copy(original) as output:
        negative(output, case)
        with pytest.raises((ValueError, KeyError, FileNotFoundError)):
            grader.validate(output, source_reference)
