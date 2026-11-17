"""Owner-side real-data curation tables and full good-unit drift raster export.

This is a post-native construction component, never a sorter or accuracy grader.
The owner manifest and its expected digest must come from the assessment owner.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from collections import Counter
from itertools import combinations

TASK_ID = "PAPER-paper-method-add-008"
CONTRACT_SHA256 = "6350dbe7e3039ba9625ab4a5e28a31975b63cd8d2c09fbbb9c21ddd2eb0b10c6"
SOURCE_COMMIT = "d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1"
SORTERS = ("kilosort4", "spykingcircus2", "tridesclous2", "lupin")
BOMBCELL = ("good", "mua", "noise", "non_soma_good", "non_soma_mua")
UNITREFINE = ("sua", "mua", "noise")
ASSET = {
    "asset_id": "af795820-bc09-4494-9da8-d2aa9aad4724",
    "asset_path": "sub-A3702/sub-A3702_behavior+ecephys.nwb",
    "asset_bytes": 2007197177,
}
HOLDS = (
    "native_sorter_and_curation_execution_not_verified",
    "source_A3702_session_filename_to_asset_binding_requires_independent_audit",
    "source_batch_protocol_concatenation_and_path_defects_require_reviewed_repair",
    "tridesclous2A_protocol_to_curation_name_mapping_requires_native_audit",
    "common_analyzer_preprocessing_not_established_source_orders_differ",
    "external_dependency_defaults_models_licenses_and_exposure_require_audit",
    "drift_raster_is_not_a_numeric_drift_robustness_endpoint",
    "cross_sorter_spike_agreement_endpoint_not_frozen",
    "quality_labels_and_yield_are_not_spike_accuracy",
    "protected_packets_reference_controls_resources_and_scientific_qualification_open",
)


class ContractError(ValueError):
    """Input does not meet this component's frozen construction policy."""


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _keys(value, expected, location):
    _require(isinstance(value, dict) and set(value) == set(expected),
             f"{location}: expected exact keys {sorted(expected)}")


def _sha(value, location):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             f"{location}: expected lowercase SHA256")


def _text(value, location):
    _require(isinstance(value, str) and value.strip() == value and bool(value),
             f"{location}: expected nonempty trimmed string")


def _integer(value, location, minimum=0):
    _require(type(value) is int and value >= minimum, f"{location}: invalid integer")


def _finite(value, location, positive=False):
    _require(type(value) in (int, float) and math.isfinite(value)
             and (not positive or value > 0), f"{location}: invalid number")


def _seconds(frame, sampling_frequency_hz):
    try:
        value = frame / sampling_frequency_hz
    except OverflowError as error:
        raise ContractError("recording duration cannot be represented in seconds") from error
    _finite(value, "derived time_seconds")
    return value


def validate_manifest(manifest, expected_sha256):
    """Validate an independently frozen A3702 full-recording assessment manifest.

    The candidate must not choose this manifest or the expected digest. Hash
    binding detects changed declarations; it cannot authenticate native receipts.
    """
    _sha(expected_sha256, "expected_manifest_sha256")
    _require(canonical_digest(manifest) == expected_sha256, "owner manifest digest mismatch")
    _keys(manifest, ("schema_version", "task_id", "contract_sha256", "source_commit",
                     "evidence_kind", "recording", "curation", "runs"), "manifest")
    _require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
             "unsupported manifest schema")
    _require(manifest["task_id"] == TASK_ID and manifest["contract_sha256"] == CONTRACT_SHA256
             and manifest["source_commit"] == SOURCE_COMMIT, "task/source contract mismatch")
    _require(manifest["evidence_kind"] in ("generated_engineering_control", "owner_native_exports"),
             "unsupported evidence kind")
    rec = manifest["recording"]
    _keys(rec, (*ASSET, "content_sha256", "source_path_resolution_receipt_sha256",
                "electrical_series_path", "sampling_frequency_hz", "num_frames", "channel_ids"), "recording")
    for key, value in ASSET.items():
        _require(type(rec[key]) is type(value) and rec[key] == value, f"recording: wrong {key}")
    _require(rec["electrical_series_path"] == "acquisition/ElectricalSeries", "wrong ElectricalSeries")
    _sha(rec["content_sha256"], "recording.content_sha256")
    _sha(rec["source_path_resolution_receipt_sha256"], "source path resolution receipt")
    _finite(rec["sampling_frequency_hz"], "sampling_frequency_hz", positive=True)
    _integer(rec["num_frames"], "num_frames", minimum=1)
    _seconds(rec["num_frames"], rec["sampling_frequency_hz"])
    _require(isinstance(rec["channel_ids"], list) and bool(rec["channel_ids"]), "empty channel inventory")
    for channel in rec["channel_ids"]:
        _text(channel, "channel_id")
    _require(len(set(rec["channel_ids"])) == len(rec["channel_ids"]), "duplicate channels")
    curation = manifest["curation"]
    _keys(curation, ("spikeinterface_version", "bombcell_implementation_sha256",
                      "unitrefine_noise_model_sha256", "unitrefine_sua_mua_model_sha256",
                      "dependency_lock_sha256", "policy_sha256"), "curation")
    _text(curation["spikeinterface_version"], "spikeinterface_version")
    for key in curation:
        if key != "spikeinterface_version":
            _sha(curation[key], key)
    runs = manifest["runs"]
    _keys(runs, SORTERS, "runs")
    for sorter in SORTERS:
        run = runs[sorter]
        _keys(run, ("source_protocol_key", "sorter_version", "effective_parameters_sha256",
                    "native_artifact_sha256", "analyzer_preprocessing_order", "unit_spike_counts",
                    "runtime_seconds", "peak_memory_bytes"), sorter)
        protocol_sorter = "tridesclous2A" if sorter == "tridesclous2" else sorter
        _require(run["source_protocol_key"] == protocol_sorter + "_no_motion_correction",
                 f"{sorter}: source protocol mismatch")
        order = ["common_reference", "bandpass_filter"] if sorter == "kilosort4" else ["bandpass_filter", "common_reference"]
        _require(run["analyzer_preprocessing_order"] == order, f"{sorter}: source analyzer order mismatch")
        _text(run["sorter_version"], f"{sorter}.sorter_version")
        if sorter == "kilosort4" and manifest["evidence_kind"] == "owner_native_exports":
            _require(run["sorter_version"] == "4.1.2", "native Kilosort version must match source 4.1.2")
        for key in ("effective_parameters_sha256", "native_artifact_sha256"):
            _sha(run[key], f"{sorter}.{key}")
        _finite(run["runtime_seconds"], "runtime_seconds", positive=True)
        _integer(run["peak_memory_bytes"], "peak_memory_bytes", minimum=1)
        counts = run["unit_spike_counts"]
        _require(isinstance(counts, dict), "unit_spike_counts must be a mapping")
        for unit_id, count in counts.items():
            _text(unit_id, "unit_id")
            _integer(count, "unit spike count")
    return manifest


def evaluate_curation(manifest, exports, expected_sha256):
    """Reconstruct the pinned author's curation table from complete unit labels.

    Supplementary cross-tabs and paired count differences are descriptive only.
    No quality threshold is tuned and no sorter wins by returning more units.
    """
    validate_manifest(manifest, expected_sha256)
    _keys(exports, ("schema_version", "owner_manifest_sha256", "sorters"), "exports")
    _require(type(exports["schema_version"]) is int and exports["schema_version"] == 1,
             "unsupported export schema")
    _require(exports["owner_manifest_sha256"] == expected_sha256, "export manifest mismatch")
    _keys(exports["sorters"], SORTERS, "export sorters")
    summaries = {}
    for sorter in SORTERS:
        exported = exports["sorters"][sorter]
        _keys(exported, ("unit_rows", "slay_merge_groups", "native_artifact_sha256"), sorter)
        _require(exported["native_artifact_sha256"] == manifest["runs"][sorter]["native_artifact_sha256"],
                 f"{sorter}: native artifact mismatch")
        rows = exported["unit_rows"]
        _require(isinstance(rows, list), "unit_rows must be a list")
        seen = set()
        bomb, refine = Counter(), Counter()
        table = {b: {u: 0 for u in UNITREFINE} for b in BOMBCELL}
        for row in rows:
            _keys(row, ("unit_id", "bombcell_label", "unitrefine_label"), "unit row")
            unit_id, b, u = row["unit_id"], row["bombcell_label"], row["unitrefine_label"]
            _text(unit_id, "unit_id")
            _require(unit_id not in seen, f"{sorter}: duplicate unit")
            _require(isinstance(b, str) and b in BOMBCELL and isinstance(u, str) and u in UNITREFINE,
                     f"{sorter}: unknown curation label")
            seen.add(unit_id)
            bomb[b] += 1
            refine[u] += 1
            table[b][u] += 1
        expected_units = set(manifest["runs"][sorter]["unit_spike_counts"])
        _require(seen == expected_units, f"{sorter}: missing or unexpected units")
        groups = exported["slay_merge_groups"]
        _require(isinstance(groups, list), "slay_merge_groups must be a list")
        grouped = set()
        for group in groups:
            _require(isinstance(group, list) and len(group) >= 2, "merge group must contain at least two units")
            for unit_id in group:
                _text(unit_id, "merge unit_id")
                _require(unit_id in seen and unit_id not in grouped, "unknown or repeated merge unit")
                grouped.add(unit_id)
        total = len(rows)
        counts = {"total units": total, "bombcell good": bomb["good"] + bomb["non_soma_good"],
                  "unitrefine sua": refine["sua"], "bombcell mua": bomb["mua"] + bomb["non_soma_mua"],
                  "unitrefine mua": refine["mua"], "# slay merges": len(groups),
                  "bombcell noise": bomb["noise"], "unitrefine noise": refine["noise"]}
        summaries[sorter] = {
            "source_table": counts,
            "fractions_of_all_units": {key: value / total if total else None for key, value in counts.items()
                                       if key not in ("total units", "# slay merges")},
            "bombcell_distribution": {label: bomb[label] for label in BOMBCELL},
            "unitrefine_distribution": {label: refine[label] for label in UNITREFINE},
            "curation_label_cross_tab": table,
            "slay_units_in_proposed_groups": len(grouped),
            "declared_runtime_seconds": manifest["runs"][sorter]["runtime_seconds"],
            "declared_peak_memory_bytes": manifest["runs"][sorter]["peak_memory_bytes"],
        }
    differences = []
    for left, right in combinations(SORTERS, 2):
        differences.append({"left": left, "right": right,
                            "left_minus_right": {key: summaries[left]["source_table"][key] - summaries[right]["source_table"][key]
                                                 for key in summaries[left]["source_table"]}})
    return {"schema_version": 1, "task_id": TASK_ID, "owner_manifest_sha256": expected_sha256,
            "curation_exports_sha256": canonical_digest(exports), "evidence_kind": manifest["evidence_kind"],
            "sorters": summaries, "paired_descriptive_count_differences": differences,
            "scientific_qualified": False, "full_contract_complete": False,
            "native_reference_verified": False, "spike_accuracy_estimated": False,
            "holds": list(HOLDS)}


def export_good_unit_raster(manifest, exports, expected_sha256, source_csv, destination_csv):
    """Stream all Kilosort4 spikes; retain exactly Bombcell 'good' for the raster.

    CSV must cover every native Kilosort4 unit's declared spikes and be ordered
    by frame. No scatter decimation or numerical robustness claim is imposed.
    Caller discards destination on failure; the CLI stages output atomically.
    """
    evaluate_curation(manifest, exports, expected_sha256)
    reader = csv.DictReader(source_csv)
    fields = ["unit_id", "sample_index", "depth_um", "amplitude_uv"]
    _require(reader.fieldnames == fields, "raster CSV header mismatch")
    writer = csv.DictWriter(destination_csv, fieldnames=["unit_id", "sample_index", "time_seconds", "depth_um", "amplitude_uv"])
    writer.writeheader()
    counts = manifest["runs"]["kilosort4"]["unit_spike_counts"]
    good = {r["unit_id"] for r in exports["sorters"]["kilosort4"]["unit_rows"] if r["bombcell_label"] == "good"}
    seen, last_unit_frame = Counter(), {}
    previous_frame, total, retained = -1, 0, 0
    rec = manifest["recording"]
    for row in reader:
        _require(set(row) == set(fields) and all(isinstance(row[key], str) for key in fields), "malformed raster row")
        unit_id = row["unit_id"]
        _require(unit_id in counts, "raster unknown unit")
        _require(re.fullmatch(r"0|[1-9][0-9]*", row["sample_index"]) is not None, "raster invalid sample index")
        frame = int(row["sample_index"])
        _require(frame < rec["num_frames"] and frame >= previous_frame, "raster frame out of bounds/order")
        _require(frame > last_unit_frame.get(unit_id, -1), "duplicate unit spike frame")
        try:
            depth, amplitude = float(row["depth_um"]), float(row["amplitude_uv"])
        except ValueError as error:
            raise ContractError("raster nonnumeric location/amplitude") from error
        _finite(depth, "depth_um")
        _finite(amplitude, "amplitude_uv")
        seen[unit_id] += 1
        _require(seen[unit_id] <= counts[unit_id], "raster exceeds native spike inventory")
        last_unit_frame[unit_id], previous_frame = frame, frame
        total += 1
        if unit_id in good:
            writer.writerow({"unit_id": unit_id, "sample_index": frame,
                             "time_seconds": _seconds(frame, rec["sampling_frequency_hz"]),
                             "depth_um": depth, "amplitude_uv": amplitude})
            retained += 1
    _require(all(seen[unit_id] == n for unit_id, n in counts.items()), "raster omits native spikes")
    return {"source_sorter": "kilosort4", "source_bombcell_label": "good",
            "input_spikes": total, "retained_spikes": retained, "retained_units": len(good),
            "scatter_decimation_applied": False, "numeric_drift_robustness_computed": False}


def _load(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=unique_object,
                         parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"invalid JSON constant {value}")))


def _hashed_utf8_lines(binary_stream, digest):
    for line in binary_stream:
        digest.update(line)
        yield line.decode("utf-8")


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--curation-json", required=True, type=Path)
    parser.add_argument("--drift-spikes-csv", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest, exports = _load(args.owner_manifest), _load(args.curation_json)
    report = evaluate_curation(manifest, exports, args.expected_manifest_sha256)
    output = args.output_directory
    _require(not output.exists(), "output directory must not already exist")
    _require(output.parent.is_dir(), "output parent must exist")
    with tempfile.TemporaryDirectory(prefix=".curation-stage-", dir=output.parent) as tmp:
        stage = Path(tmp) / "result"
        stage.mkdir()
        raster_digest = hashlib.sha256()
        with args.drift_spikes_csv.open("rb") as source, (stage / "good_unit_raster.csv").open("w", newline="", encoding="utf-8") as dest:
            report["drift_raster"] = export_good_unit_raster(
                manifest, exports, args.expected_manifest_sha256,
                _hashed_utf8_lines(source, raster_digest), dest)
        report["input_raster_sha256"] = raster_digest.hexdigest()
        with (stage / "source_curation_table.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["sorter", *report["sorters"][SORTERS[0]]["source_table"]])
            writer.writeheader()
            for sorter in SORTERS:
                writer.writerow({"sorter": sorter, **report["sorters"][sorter]["source_table"]})
        report["output_artifacts_sha256"] = {
            name: _file_digest(stage / name)
            for name in ("good_unit_raster.csv", "source_curation_table.csv")}
        (stage / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        stage.rename(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
