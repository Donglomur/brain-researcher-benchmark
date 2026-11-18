"""Bind retained NEURAL-027 metadata to original source addresses; never load arrays.

This is operator preparation, not an evaluator plan, scientific split or public query.
Only standard-library JSON is read. Original typed metadata is retained unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

EXPORT_SHA256 = "f8a44b734dde0c5bc2e71825bcf108e7f6d1191f4503a7058ff92a805518220c"
INVENTORY_SHA256 = "d5f080ccaf7728877210efdb342ba55eb817577d1bef08444896bcbc332cc4fe"
SOURCE_NPY_SHA256 = "69756688e06fd60843b8aff988c2191f7719ec5a66d3660aee550a2ee2a26c56"
MAX_INPUT_BYTES = 1048576
MAX_OUTPUT_BYTES = 524288
SAFE_BEHAVIOR_FIELDS = ("ft_WallID", "ft_trInd", "ft_move", "ft_Pos", "ft_CorrSpc",
                        "Corridor_Length", "UniqWalls", "stim_id")
ROLES = ("neural", "transform", "behavior_container")


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def reject_constant(value):
    raise ValueError("JSON nonfinite literal is forbidden: " + value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def read_pinned_json(path, expected):
    with Path(path).open("rb") as handle:
        body = handle.read(MAX_INPUT_BYTES + 1)
    require(len(body) <= MAX_INPUT_BYTES, "input byte limit exceeded")
    require(hashlib.sha256(body).hexdigest() == expected, "input SHA256 mismatch")
    return json.loads(body, object_pairs_hook=unique_object, parse_constant=reject_constant)


def source_text(value, field, allow_empty=False):
    require(isinstance(value, dict) and set(value) == {"t", "v"}
            and value["t"] == "str" and isinstance(value["v"], str) and (value["v"] or allow_empty),
            field + ": expected original nonempty typed string; no coercion")
    text = value["v"]
    require("/" not in text and "\\" not in text and "\x00" not in text
            and text not in (".", ".."), field + ": unsafe source token")
    return text


def indexed_links(records, key):
    groups = {}
    for row in records:
        token = key(row)
        groups.setdefault(token, []).append(row["ordinal"])
    return [{"value": token, "record_ordinals": ordinals} for token, ordinals in groups.items()]


def bind_documents(export, inventory):
    """Pure metadata binding; CLI separately authenticates the complete source bytes.

    Generated tests use small documents here. It is not an admission API for arbitrary
    sources: only the CLI's exact accepted export and inventory are source-qualified.
    """
    roster = export["roster"]
    original = roster["records"]
    require(isinstance(original, list) and 0 < len(original) <= 512, "record count limit")
    require(roster["record_count"] == len(original), "record count mismatch")
    require(inventory["version"] == 2, "inventory version mismatch")
    files = inventory["files"]
    require(isinstance(files, list) and len(files) == inventory["count"] <= 512,
            "inventory count mismatch")
    by_id, by_name = {}, {}
    for asset in files:
        require(set(asset) == {"id", "name", "size", "download_url"}, "inventory fields")
        require(type(asset["id"]) is int and asset["id"] > 0 and
                type(asset["size"]) is int and asset["size"] >= 0, "inventory id/size")
        require(isinstance(asset["name"], str) and asset["name"], "inventory name")
        require(asset["id"] not in by_id and asset["name"] not in by_name,
                "duplicate inventory identity")
        by_id[asset["id"]] = asset
        by_name[asset["name"]] = asset
    group_map = {}
    for group in roster["groups"]:
        name = source_text(group["original_group"], "group")
        require(name not in group_map, "duplicate group")
        ids = group["record_ordinals"]
        require(isinstance(ids, list) and ids and all(type(x) is int for x in ids), "group ordinals")
        group_map[name] = ids
    flattened = [x for ids in group_map.values() for x in ids]
    require(flattened == list(range(len(original))), "groups must cover original source order exactly")
    records, asset_roles, asset_records = [], {}, {}
    seen_stems = {}
    for ordinal, row in enumerate(original):
        require(type(row["ordinal"]) is int and row["ordinal"] == ordinal, "original ordinal changed")
        group = source_text(row["source_group"], "source_group")
        require(group in group_map and ordinal in group_map[group], "group/ordinal mismatch")
        local = group_map[group].index(ordinal)
        require(row["source_pointer"] == ["group", row["source_group"], "index", local],
                "original pointer mismatch")
        require(row["phase_semantics"] is None and row["behavior_nested_key_verified"] is False,
                "unadmitted source qualification")
        fields = row["fields"]
        require(isinstance(fields, dict) and "stim_id" in fields, "missing original fields")
        mouse, date, block = (source_text(fields[k], k) for k in ("mname", "datexp", "blk"))
        stem = "_".join((mouse, date, block))
        require(row["candidate_session_stem"] == stem, "physical stem mismatch")
        stimulus_type = source_text(fields["stimtype"], "stimtype", allow_empty=True) if "stimtype" in fields else None
        behavior_key = stem if stimulus_type is None else stem + "_" + stimulus_type
        expected_names = {"neural": stem + "_neural_data.npy",
                          "transform": mouse + "_" + date + "_trans.npz",
                          "behavior_container": "Beh_" + group + ".npy"}
        asset_ids = {}
        for role, expected_name in expected_names.items():
            asset = row[role + "_asset"]
            require(isinstance(asset, dict) and asset.get("id") in by_id and
                    asset == by_id[asset["id"]] and asset["name"] == expected_name,
                    "source/inventory asset mismatch for " + role)
            aid = asset["id"]
            require(aid not in asset_roles or asset_roles[aid] == role, "cross-role asset alias")
            asset_roles[aid] = role
            asset_records.setdefault(aid, []).append(ordinal)
            asset_ids[role] = aid
        seen_stems.setdefault(stem, []).append(ordinal)
        records.append({
            "ordinal": ordinal,
            "binding_id": "original-record-" + str(ordinal).zfill(3),
            "source_pointer": copy.deepcopy(row["source_pointer"]),
            "source_group": copy.deepcopy(row["source_group"]),
            "group_local_ordinal": local,
            "original_fields": copy.deepcopy(fields),
            "original_group_metadata": copy.deepcopy(row["group_metadata"]),
            "source_record_json_sha256": digest(row),
            "literal_mname": mouse, "datexp": date, "blk": block,
            "original_identity_tuple": [copy.deepcopy(fields[k]) for k in ("mname", "datexp", "blk")],
            "physical_session_stem": stem,
            "stimtype_present": "stimtype" in fields,
            "behavior_lookup": {"container_asset_id": asset_ids["behavior_container"],
                                "key": behavior_key, "nested_key_verified": False,
                                "source_rule": "notebook:9087c6cc"},
            "asset_ids": asset_ids,
            "phase": None, "split": None, "prereward_eligible": None,
            "metadata_stim_id_is_behavior_mapping": None,
            "source_condition_frame_mask_verified": False,
        })
    duplicates = {stem: ids for stem, ids in seen_stems.items() if len(ids) > 1}
    require(roster["duplicate_session_stems"] == duplicates, "repeated stem roster mismatch")
    require(roster["existing_evaluator_plan_created"] is False and
            roster["scientific_phase_or_cohort_selected"] is False,
            "export already claims a scientific selection")
    for key in ("unmatched_neural_ordinals", "unmatched_behavior_container_ordinals",
                "unmatched_transform_ordinals"):
        require(roster[key] == [], "unresolved source asset join")
    associations = []
    for asset in files:
        aid = asset["id"]
        associations.append({**asset, "binding_role": asset_roles.get(aid),
                             "record_ordinals": asset_records.get(aid, []),
                             "payload_verified": False})
    role_summary = {}
    for role in ROLES:
        members = [a for a in associations if a["binding_role"] == role]
        role_summary[role] = {"unique_files": len(members), "bytes": sum(a["size"] for a in members)}
    joined = [a for a in associations if a["record_ordinals"]]
    unjoined = [a for a in associations if not a["record_ordinals"]]
    dependencies = {
        "literal_mname": indexed_links(records, lambda r: r["literal_mname"]),
        "physical_session_stem": indexed_links(records, lambda r: r["physical_session_stem"]),
        "neural_asset_id": indexed_links(records, lambda r: r["asset_ids"]["neural"]),
        "transform_asset_id": indexed_links(records, lambda r: r["asset_ids"]["transform"]),
        "behavior_container_asset_id": indexed_links(records, lambda r: r["asset_ids"]["behavior_container"]),
        "behavior_condition_address": indexed_links(
            records, lambda r: str(r["behavior_lookup"]["container_asset_id"]) + ":" + r["behavior_lookup"]["key"]),
        "group": [{"value": name, "record_ordinals": ids} for name, ids in group_map.items()],
        "biological_aliases_across_literal_names": "unknown",
        "record_count_is_independent_sample_count": False,
        "shared_container_is_shared_observation": "not established; storage dependency only",
    }
    return {
        "schema": "neural027-source-record-binding/v1", "task_id": "NEURAL-027",
        "qualification": "operator_metadata_preparation_only",
        "input_pins": {"accepted_export_sha256": EXPORT_SHA256, "inventory_sha256": INVENTORY_SHA256,
                       "original_metadata_npy_sha256": SOURCE_NPY_SHA256, "figshare_version": 2},
        "records": records, "dependencies": dependencies, "asset_inventory": associations,
        "storage": {"by_joined_role": role_summary,
                    "joined_original_files": {"count": len(joined), "bytes": sum(a["size"] for a in joined)},
                    "unjoined_original_files": {"count": len(unjoined), "bytes": sum(a["size"] for a in unjoined)},
                    "whole_inventory": {"count": len(files), "bytes": sum(a["size"] for a in files)},
                    "unjoined_assets_excluded_from_science": False,
                    "joined_assets_prove_scientific_sufficiency": False},
        "safe_export_field_sources": {
            "spks": {"asset_role": "neural", "key": "spks", "recipe": "concatenate neuron chunks on axis 0; equal frame axis required"},
            "iarea": {"asset_role": "transform", "key": "iarea", "recipe": "must align with original concatenated neuron axis"},
            **{key: {"asset_role": "behavior_container", "nested_key": "record.behavior_lookup.key", "field": key}
               for key in SAFE_BEHAVIOR_FIELDS}},
        "consumer_compatibility": {
            "implementation": "initial-evaluator-v1", "compatible": False,
            "five_field_plan_created": False, "safe_npz_created": False,
            "repeated_physical_stems": duplicates,
            "blocking_requirements": [
                "Represent every original record/condition without inventing mouse or physical-session aliases; current consumer rejects repeated stems.",
                "Verify original behavior key presence, condition frame support and behavior stim_id/UniqWalls/ft_WallID mapping; metadata stim_id is not a substitute.",
                "Resolve metadata/behavior descriptor relationship and field-specific nonfinite semantics without imputation or record loss.",
                "Establish row-level phase, prior reward history, biological identity and declared split before prereward attestation.",
                "Verify original neural/behavior/area payload equality, frame alignment and ft_Pos/Corridor_Length units before numeric safe export.",
            ],
            "condition_identity_is_sampling_unit": False,
            "current_consumer_demonstrated_split_leak": False,
            "no_identity_suffix_workaround": True,
        },
        "access_mode": "operator preparation only; neither native model understanding nor a tool-assisted model run",
    }


def write_new_json(path, value):
    body = canonical(value) + b"\n"
    require(len(body) <= MAX_OUTPUT_BYTES, "binding output byte limit exceeded")
    with Path(path).open("xb") as handle:
        handle.write(body)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    export = read_pinned_json(args.export, EXPORT_SHA256)
    inventory = read_pinned_json(args.inventory, INVENTORY_SHA256)
    require(export["source_sha256"] == SOURCE_NPY_SHA256, "original metadata source mismatch")
    binding = bind_documents(export, inventory)
    require(len(binding["records"]) == 142 and inventory["count"] == 297,
            "complete original source population required")
    pin = write_new_json(args.output, binding)
    print(json.dumps({"output": str(args.output), **pin, "records": 142,
                      "storage": binding["storage"], "consumer_compatible": False}, sort_keys=True))


if __name__ == "__main__":
    main()
