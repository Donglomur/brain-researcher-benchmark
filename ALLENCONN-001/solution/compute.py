"""Projection-only Allen atlas descriptor on a frozen official API snapshot.

Missing records are not zeros. Source assignment is a primary-site label, not an
unmixing model. Importing this module performs no download, aggregation, or writes.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

PIPELINE_ID = "allen-projection-summary-v2"
DATASET_ID = "allen-mouse-connectivity-api-v2"
SNAPSHOT_ID = "allen-connectivity-20261001"
SUMMARY_SET_ID = 167587189
NUM_ATOL, NUM_RTOL, TIE_ATOL = 1e-12, 1e-9, 1e-12
RAW_FIELDS = ["experiment_id", "source_id", "target_id", "record_status", "unionize_id",
              "projection_density", "sum_projection_pixels", "sum_pixels"]
SUPPORT_FIELDS = ["source_id", "target_id", "n_observed", "n_expected"]
STRONGEST_FIELDS = ["source_id", "status", "strongest_targets", "is_self_strongest",
                    "max_density", "n_missing_targets", "n_experiments"]


def metadata_contract(manifest):
    """Pure public input/method template: never includes computed answers."""
    return {
        "pipeline_id": PIPELINE_ID, "dataset_id": DATASET_ID,
        "snapshot_id": SNAPSHOT_ID, "acquired_at_utc": manifest["acquired_at_utc"],
        "api_base": manifest["api_base"],
        "snapshot_kind": "locally_frozen_official_API_responses_not_an_official_release",
        "source_sha256": {item["path"]: item["sha256"] for item in manifest["files"]},
        "source_size_bytes": {item["path"]: item["size_bytes"] for item in manifest["files"]},
        "cohort": {"table": "ApiConnectivity", "selection": "SDK_cre_false",
                   "transgenic_line_rule": "false_after_name_simplification",
                   "experiment_id_field": "data_set_id", "primary_structure_field": "structure_id"},
        "structures": {"graph_id": 1, "summary_set_id": SUMMARY_SET_ID,
                       "source_mapping": "deepest_summary_member_in_structure_id_path_including_self",
                       "unmapped_policy": "fail", "target_set": "all_members_including_nested_structures"},
        "unionizes": {"table": "ProjectionStructureUnionize", "hemisphere_id": 3,
                      "is_injection": False, "include_descendants": False,
                      "metric": "projection_density", "density_identity": "sum_projection_pixels/sum_pixels",
                      "duplicate_key_policy": "fail"},
        "missingness": {"api_absent": "no_record_no_zero_imputation",
                        "zero_domain": "present_sum_pixels_zero_excluded_from_mean",
                        "observed": "present_finite_positive_domain",
                        "matrix_undefined": "no_observed_experiments_for_source_target",
                        "source_eligible": "all_target_means_finite"},
        "aggregation": {"experiment_weight": "equal_among_observed_per_source_target",
                        "pool_pixels_across_experiments": False,
                        "hemisphere_aggregation": "use_API_hemisphere_3_not_mean_of_1_and_2",
                        "source_weight_in_fraction": "equal_among_eligible_sources"},
        "argmax": {"report": "all_maximizing_targets", "absolute_tie_tolerance": TIE_ATOL,
                   "relative_tie_tolerance": 0.0, "self_counts_if_tied": True,
                   "all_zero_complete_row": "all_targets_tied_including_self",
                   "incomplete_row": "unidentified_not_in_fraction_denominator"},
        "tolerances": {"raw_atol": NUM_ATOL, "raw_rtol": NUM_RTOL,
                       "matrix_atol": NUM_ATOL, "matrix_rtol": NUM_RTOL,
                       "summary_atol": 1e-9},
        "undefined_serialization": {"csv": "blank", "json": None},
    }


def as_id(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("source identifier is not numeric")
    if not math.isfinite(value) or value < 0 or value != int(value):
        raise ValueError("source identifier is not a nonnegative integer")
    return int(value)


def read_sources(data_dir):
    data_dir = Path(data_dir).resolve()
    manifest = json.loads((data_dir / "source_manifest.json").read_text())
    if manifest["snapshot_id"] != SNAPSHOT_ID:
        raise ValueError("wrong frozen source snapshot")
    documents, seen = {}, set()
    for entry in manifest["files"]:
        relative = Path(entry["path"]); path = (data_dir / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(data_dir) or str(relative) in seen:
            raise ValueError("duplicate or out-of-directory source path")
        seen.add(str(relative))
        if entry["role"] not in {"experiments", "structures", "projection_page"}:
            raise ValueError("unexpected raw source role")
        if path.stat().st_size != entry["size_bytes"]:
            raise ValueError("raw source size mismatch")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != entry["sha256"]:
            raise ValueError("raw source SHA256 mismatch")
        document = json.loads(path.read_text())
        if document.get("success") is not True or not isinstance(document.get("msg"), list):
            raise ValueError("failed or malformed official API response")
        if document.get("num_rows") != len(document["msg"]):
            raise ValueError("API page row-count mismatch")
        documents.setdefault(entry["role"], []).append(document["msg"])
    if len(documents.get("experiments", [])) != 1 or len(documents.get("structures", [])) != 1:
        raise ValueError("require one complete experiment and one complete structure response")
    if not documents.get("projection_page"):
        raise ValueError("projection source pages absent")
    return documents, manifest


def structure_path(record):
    raw = record["structure_id_path"]
    path = [as_id(int(part)) for part in raw.strip("/").split("/")] if isinstance(raw, str) else [as_id(i) for i in raw]
    if not path or path[-1] != as_id(record["id"]) or len(path) != len(set(path)):
        raise ValueError("malformed/cyclic structure path")
    return path


def select_cohort(experiments, structures):
    tree = {as_id(s["id"]): s for s in structures}
    if len(tree) != len(structures) or any(s["graph_id"] != 1 for s in structures):
        raise ValueError("invalid graph-1 structure identities")
    targets = sorted(sid for sid, node in tree.items()
                     if SUMMARY_SET_ID in [as_id(item["id"]) for item in node["structure_sets"]])
    if not targets:
        raise ValueError("summary set is empty")
    target_set = set(targets)
    selected, source_by_id, seen = {}, {}, set()
    for experiment in experiments:
        eid = as_id(experiment["data_set_id"])
        if eid in seen:
            raise ValueError("duplicate experiment identity")
        seen.add(eid)
        line = experiment.get("transgenic_line")
        if line:
            line = line["name"]
        if line:
            continue
        primary = as_id(experiment["structure_id"])
        if primary not in tree:
            raise ValueError("primary injection structure absent from frozen tree")
        path = structure_path(tree[primary])
        if any(sid not in tree for sid in path):
            raise ValueError("incomplete source hierarchy")
        candidates = [sid for sid in path if sid in target_set]
        if not candidates:
            raise ValueError("primary injection structure has no summary ancestor")
        selected[eid] = experiment
        source_by_id[eid] = candidates[-1]
    experiment_ids = sorted(selected)
    return (np.asarray(experiment_ids, dtype=np.int64),
            np.asarray([source_by_id[eid] for eid in experiment_ids], dtype=np.int64),
            np.asarray(targets, dtype=np.int64), tree)


def parse_unionizes(experiment_ids, experiment_source_ids, target_ids, records):
    e_lookup = {int(e): i for i, e in enumerate(experiment_ids)}
    t_lookup = {int(t): i for i, t in enumerate(target_ids)}
    shape = len(experiment_ids), len(target_ids)
    arrays = {"experiment_ids": experiment_ids, "experiment_source_ids": experiment_source_ids,
              "target_ids": target_ids, "source_ids": np.unique(experiment_source_ids),
              "record_status": np.full(shape, "api_absent", dtype="U12"),
              "unionize_id": np.full(shape, -1, dtype=np.int64),
              "density": np.full(shape, np.nan), "sum_projection_pixels": np.full(shape, np.nan),
              "sum_pixels": np.full(shape, np.nan)}
    seen_keys, seen_ids = set(), set()
    for row in records:
        eid, tid, rid = map(as_id, (row["section_data_set_id"], row["structure_id"], row["id"]))
        if (eid not in e_lookup or tid not in t_lookup or row["hemisphere_id"] != 3
                or row["is_injection"] is not False):
            raise ValueError("projection record outside the frozen projection-only domain")
        if (eid, tid) in seen_keys or rid in seen_ids:
            raise ValueError("duplicate unionize record ID or experiment-target key")
        seen_keys.add((eid, tid)); seen_ids.add(rid)
        density, numerator, denominator = [row[name] for name in
                                          ("projection_density", "sum_projection_pixels", "sum_pixels")]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in (density, numerator, denominator)):
            raise ValueError("nonfinite raw unionize field")
        if not 0 <= density <= 1 or not 0 <= numerator <= denominator:
            raise ValueError("invalid unionize pixel/density domain")
        if denominator > 0 and not np.isclose(density, numerator / denominator, atol=NUM_ATOL, rtol=NUM_RTOL):
            raise ValueError("raw projection density disagrees with its numerator/denominator")
        i, j = e_lookup[eid], t_lookup[tid]
        arrays["record_status"][i, j] = "observed" if denominator > 0 else "zero_domain"
        arrays["unionize_id"][i, j] = rid
        arrays["density"][i, j] = density
        arrays["sum_projection_pixels"][i, j] = numerator
        arrays["sum_pixels"][i, j] = denominator
    return arrays


def load_inputs(data_dir):
    documents, manifest = read_sources(data_dir)
    exps, sources, targets, tree = select_cohort(documents["experiments"][0], documents["structures"][0])
    if len(exps) != 498 or len(targets) != 316:
        raise ValueError("frozen cohort/summary membership differs from the public snapshot")
    records = (row for page in documents["projection_page"] for row in page)
    arrays = parse_unionizes(exps, sources, targets, records)
    return arrays, metadata_contract(manifest), tree


def aggregate(arrays):
    sources, targets = arrays["source_ids"], arrays["target_ids"]
    shape = len(sources), len(targets)
    matrix = np.full(shape, np.nan)
    n_observed = np.zeros(shape, dtype=np.int64); n_expected = np.zeros(shape, dtype=np.int64)
    for index, source in enumerate(sources):
        selected = arrays["experiment_source_ids"] == source
        observed = arrays["record_status"][selected] == "observed"
        n_observed[index] = observed.sum(axis=0)
        n_expected[index] = int(np.sum(selected))
        sums = np.where(observed, arrays["density"][selected], 0.0).sum(axis=0)
        np.divide(sums, n_observed[index], out=matrix[index], where=n_observed[index] > 0)
    return matrix, n_observed, n_expected


def describe(arrays):
    matrix, targets = arrays["matrix"], arrays["target_ids"]
    rows, n_self, n_eligible, n_zero, n_tied = [], 0, 0, 0, 0
    for index, source in enumerate(arrays["source_ids"]):
        row = matrix[index]
        missing = int(np.sum(~np.isfinite(row)))
        strongest, self_max, maximum = [], None, None
        if missing == 0:
            maximum = float(row.max())
            strongest = targets[(maximum - row) <= TIE_ATOL].astype(int).tolist()
            self_max = int(source) in strongest
            n_eligible += 1; n_self += int(self_max); n_zero += int(maximum == 0); n_tied += int(len(strongest) > 1)
        rows.append({"source_id": int(source), "status": "complete" if missing == 0 else "incomplete",
                     "strongest_targets": strongest, "is_self_strongest": self_max,
                     "max_density": maximum, "n_missing_targets": missing,
                     "n_experiments": int(np.sum(arrays["experiment_source_ids"] == source))})
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, "n_experiments": len(arrays["experiment_ids"]),
              "n_target_structures": len(targets), "n_source_regions": len(arrays["source_ids"]),
              "n_eligible_sources": n_eligible, "n_self_strongest": n_self,
              "self_strongest_fraction": n_self / n_eligible if n_eligible else None,
              "n_zero_max_sources": n_zero, "n_tied_max_sources": n_tied,
              "record_status_counts": {status: int(np.sum(arrays["record_status"] == status))
                                      for status in ("observed", "api_absent", "zero_domain")}}
    return result, rows


def csv_value(value):
    if value is None or isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return ""
    return value.item() if isinstance(value, np.generic) else value


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in row.items()})


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_outputs(output_dir, arrays, contract, tree):
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    result, strongest_rows = describe(arrays)
    if not result["n_eligible_sources"]:
        raise ValueError("no source has complete target support; full-target fraction is unidentified")
    def raw_rows():
        for i, experiment in enumerate(arrays["experiment_ids"]):
            for j, target in enumerate(arrays["target_ids"]):
                absent = arrays["record_status"][i, j] == "api_absent"
                yield dict(zip(RAW_FIELDS, [experiment, arrays["experiment_source_ids"][i], target,
                    arrays["record_status"][i, j], None if absent else arrays["unionize_id"][i, j],
                    arrays["density"][i, j], arrays["sum_projection_pixels"][i, j], arrays["sum_pixels"][i, j]]))
    write_csv(output_dir / "experiment_targets.csv", RAW_FIELDS, raw_rows())
    with (output_dir / "connectivity_matrix.csv").open("w", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["source_id", *arrays["target_ids"].tolist()])
        for source, row in zip(arrays["source_ids"], arrays["matrix"]):
            writer.writerow([int(source), *[csv_value(value) for value in row]])
    support_rows = (dict(zip(SUPPORT_FIELDS, [source, target, arrays["n_observed"][i, j], arrays["n_expected"][i, j]]))
                    for i, source in enumerate(arrays["source_ids"]) for j, target in enumerate(arrays["target_ids"]))
    write_csv(output_dir / "matrix_support.csv", SUPPORT_FIELDS, support_rows)
    write_csv(output_dir / "source_strongest.csv", STRONGEST_FIELDS,
              ({**row, "strongest_targets": json.dumps(row["strongest_targets"])} for row in strongest_rows))
    metadata = {**contract, **result}
    write_json(output_dir / "self_projection.json", result); write_json(output_dir / "run_metadata.json", metadata)
    arrays["metadata_json"] = np.asarray(json.dumps(metadata, allow_nan=False))
    np.savez_compressed(output_dir / "analysis_arrays.npz", **arrays)
    incomplete = result["n_source_regions"] - result["n_eligible_sources"]
    nested = [(int(t), [sid for sid in structure_path(tree[int(t)])[:-1] if sid in set(arrays["target_ids"].tolist())])
              for t in arrays["target_ids"]]
    nested = [(t, ancestors) for t, ancestors in nested if ancestors]
    text = (f"# Projection-only atlas descriptor\n\n"
            f"{result['n_self_strongest']} of {result['n_eligible_sources']} eligible source regions "
            f"({result['self_strongest_fraction']:.9f}) have their own summary structure among the maximum mean-density targets. "
            f"There are {result['n_source_regions']} total source regions and {incomplete} incomplete rows.\n\n"
            f"Input support: {result['n_experiments']} non-transgenic-line experiments, "
            f"{result['n_target_structures']} targets; record statuses {json.dumps(result['record_status_counts'])}. "
            "Absent records are not zero. Each cell is an equal-experiment mean over available projection-only observations; "
            "the support table exposes target-dependent denominators.\n\n"
            f"{result['n_tied_max_sources']} sources have multiple maximizing targets; "
            f"{result['n_zero_max_sources']} have zero maximum. Tied self counts do not demonstrate preference. "
            f"Nested target memberships (child, ancestors): {nested}.\n\n"
            "This bilateral segmented-pixel-density descriptor is not synapse count, total projected signal, or the paper's "
            "injection-unmixed regional connection model. Primary-site grouping does not unmix injections spanning several structures. "
            "The modern frozen API cohort/target set differs from Oh et al. (2014)'s published cohort and parcellation. "
            "No injection-inclusive contrast or causal artifact attribution is inferred.\n")
    (output_dir / "findings.md").write_text(text)
    return result


def run(output_dir, data_dir):
    arrays, contract, tree = load_inputs(data_dir)
    arrays["matrix"], arrays["n_observed"], arrays["n_expected"] = aggregate(arrays)
    result = write_outputs(output_dir, arrays, contract, tree)
    print(json.dumps(result, allow_nan=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=os.environ.get("ALLEN_DATA_DIR", "/app/data/allen"))
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    args = parser.parse_args()
    try:
        run(args.output_dir, args.data_dir)
    except Exception as exc:
        output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
        failure = {"status": "failed_precondition", "pipeline_id": PIPELINE_ID, "reason": str(exc)}
        write_json(output / "self_projection.json", failure); write_json(output / "run_metadata.json", failure)
        (output / "findings.md").write_text("# Failed precondition\n\n" + str(exc) + "\n")
        raise


if __name__ == "__main__":
    main()
