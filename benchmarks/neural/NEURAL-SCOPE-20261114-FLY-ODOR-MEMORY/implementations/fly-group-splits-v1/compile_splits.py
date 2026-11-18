"""Compile complete, identity-resolved fly splits; never infer animal identity.

The CLI authenticates the exact existing native descriptor map. The parsed
function is also usable for generated software controls, not authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

TASK_ID = "NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY"
PLAN_BYTES = 3419523
PLAN_SHA256 = "7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c"
FILES = 42
TRIALS = 1345
GENOTYPES = {"VT062617", "52G12"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_RESOLUTION_BYTES = 65536
MAX_OUTPUT_BYTES = 1048576


class Refused(ValueError):
    """The identity or complete-support contract was not established."""


def require(ok, reason):
    if not ok:
        raise Refused(reason)


def exact_keys(value, keys, reason):
    require(type(value) is dict and set(value) == set(keys), reason)


def identifier(value, reason):
    require(type(value) is str and 0 < len(value) <= 256 and
            not any(ord(c) < 32 or ord(c) == 127 for c in value), reason)
    return value


def digest(value, reason):
    require(type(value) is str and SHA256.fullmatch(value) is not None, reason)
    return value


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(value):
    raise Refused("nonfinite_json_constant")


def read_bound_json(path, maximum, expected_sha256, exact_bytes=None):
    """Read one regular non-symlink operand and authenticate before parsing."""
    digest(expected_sha256, "invalid_expected_digest")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode), "regular_file_required")
        require(info.st_size <= maximum, "operand_size_limit")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            body = handle.read(maximum + 1)
        require(len(body) <= maximum, "operand_size_limit")
        if exact_bytes is not None:
            require(len(body) == exact_bytes, "descriptor_extent")
        require(hashlib.sha256(body).hexdigest() == expected_sha256,
                "operand_digest_mismatch")
        return json.loads(body, object_pairs_hook=strict_pairs,
                          parse_constant=reject_constant)
    finally:
        os.close(fd)


def compile_splits(plan, resolution, *, resolution_sha256):
    """Pure metadata compiler; callers must authenticate both operands first.

    No inferred identity or label is supplied here. A reviewed resolution is a
    necessary external operand; digest shape/consistency is not its scientific
    validation. Every trial of each mapped native file inherits its fly group.
    """
    digest(resolution_sha256, "resolution_digest")
    require(type(plan) is dict and type(plan.get("files")) is list,
            "descriptor_files")
    original = plan["files"]
    require(len(original) == FILES, "complete_42_file_support")
    source_by_id = {}
    for item in original:
        require(type(item) is dict, "descriptor_file_object")
        member = identifier(item.get("archive_member_id"), "descriptor_member")
        require(member not in source_by_id, "duplicate_descriptor_member")
        lookup = item.get("official_lookup_index")
        require(type(lookup) is int and lookup >= 0, "descriptor_lookup_index")
        identifier(item.get("population_label"), "descriptor_population")
        count = item.get("trial_count")
        require(type(count) is int and 0 < count <= TRIALS, "trial_count")
        trials = item.get("trials")
        require(type(trials) is list and len(trials) == count,
                "complete_file_trial_support")
        require(all(type(row) is dict and
                    type(row.get("trial_index_zero_based")) is int and
                    row["trial_index_zero_based"] == index
                    for index, row in enumerate(trials)),
                "original_contiguous_trial_order")
        source_by_id[member] = item
    require(sum(item["trial_count"] for item in original) == TRIALS,
            "complete_1345_trial_support")

    exact_keys(resolution, {
        "schema", "task_id", "base_plan_sha256", "identity_status",
        "identity_review_sha256", "files", "record_50_51_resolution"},
        "resolution_fields")
    require(resolution["schema"] == "fly-odor-identity-resolution/v1" and
            resolution["task_id"] == TASK_ID, "resolution_task_schema")
    require(resolution["base_plan_sha256"] == PLAN_SHA256,
            "resolution_descriptor_binding")
    require(resolution["identity_status"] == "reviewed_resolved",
            "unresolved_biological_identity")
    digest(resolution["identity_review_sha256"], "identity_review_digest")
    assignments = resolution["files"]
    require(type(assignments) is list and len(assignments) == FILES,
            "complete_identity_assignments")
    assigned, fly_genotype, population_genotype = {}, {}, {}
    for row in assignments:
        exact_keys(row, {"archive_member_id", "official_lookup_index",
                         "source_population_label", "fly_id", "genotype",
                         "identity_evidence_sha256"}, "identity_assignment_fields")
        member = identifier(row["archive_member_id"], "assignment_member")
        require(member in source_by_id and member not in assigned,
                "identity_assignment_coverage")
        source = source_by_id[member]
        require(type(row["official_lookup_index"]) is int and
                row["official_lookup_index"] == source["official_lookup_index"] and
                row["source_population_label"] == source["population_label"],
                "source_assignment_join")
        fly = identifier(row["fly_id"], "biological_fly_id")
        genotype = row["genotype"]
        require(type(genotype) is str and genotype in GENOTYPES, "genotype")
        digest(row["identity_evidence_sha256"], "assignment_evidence_digest")
        require(fly not in fly_genotype or fly_genotype[fly] == genotype,
                "fly_spans_genotypes")
        require(source["population_label"] not in population_genotype or
                population_genotype[source["population_label"]] == genotype,
                "source_population_spans_genotypes")
        fly_genotype[fly] = genotype
        population_genotype[source["population_label"]] = genotype
        assigned[member] = row
    require(set(assigned) == set(source_by_id), "complete_identity_assignments")
    require(set(fly_genotype.values()) == GENOTYPES, "both_genotypes_required")

    alias = resolution["record_50_51_resolution"]
    exact_keys(alias, {"decision", "evidence_sha256", "record_50_members",
                       "record_51_members"}, "alias_resolution_fields")
    require(alias["decision"] in ("same_animal", "different_animals"),
            "unresolved_50_51_identity")
    digest(alias["evidence_sha256"], "alias_evidence_digest")
    # Source record labels 50/51 are NOT assumed to be lookup-table indices.
    # Their relationship to native members is another explicit reviewed join.
    by_alias = []
    for key in ("record_50_members", "record_51_members"):
        members = alias[key]
        require(type(members) is list and 0 < len(members) <= FILES and
                all(type(member) is str for member in members) and
                len(members) == len(set(members)) and
                all(member in assigned for member in members),
                "alias_member_join")
        by_alias.append({assigned[member]["fly_id"] for member in members})
    members_50, members_51 = by_alias
    require(len(members_50) == len(members_51) == 1,
            "explicit_50_and_51_identity_required")
    same = members_50 == members_51
    require(same == (alias["decision"] == "same_animal"),
            "alias_decision_assignment_mismatch")

    groups = {fly: sorted(member for member, row in assigned.items()
                          if row["fly_id"] == fly)
              for fly in sorted(fly_genotype)}
    folds = []
    for genotype in sorted(GENOTYPES):
        flies = sorted(fly for fly in groups if fly_genotype[fly] == genotype)
        require(len(flies) >= 3, "insufficient_flies_for_nested_grouping")
        for held in flies:
            train = [fly for fly in flies if fly != held]
            folds.append({
                "genotype": genotype,
                "test_fly": held,
                "outer_training_flies": train,
                "test_members": groups[held],
                "outer_training_members": sorted(member for fly in train
                                                 for member in groups[fly]),
                "inner_folds": [
                    {"validation_fly": valid,
                     "training_flies": [fly for fly in train if fly != valid],
                     "validation_members": groups[valid],
                     "training_members": sorted(member for fly in train
                                                if fly != valid
                                                for member in groups[fly])}
                    for valid in train]})
    # Census stays complete: no target, event, quality or condition filtering.
    census = [
        {"archive_member_id": member,
         "official_lookup_index": source_by_id[member]["official_lookup_index"],
         "source_population_label": source_by_id[member]["population_label"],
         "fly_id": assigned[member]["fly_id"],
         "genotype": assigned[member]["genotype"],
         "trial_index_start_inclusive": 0,
         "trial_index_stop_exclusive": source_by_id[member]["trial_count"]}
        for member in sorted(source_by_id)]
    return {
        "schema": "fly-odor-complete-grouped-splits/v1", "task_id": TASK_ID,
        "base_plan_sha256": PLAN_SHA256,
        "identity_resolution_sha256": resolution_sha256,
        "identity_review_sha256": resolution["identity_review_sha256"],
        "record_50_51_resolution": dict(alias),
        "source_files": FILES, "source_trials": TRIALS,
        "biological_flies": len(groups),
        "source_population_to_genotype": population_genotype,
        "file_census": census, "outer_folds": folds,
        "scope": "Metadata-only outer and inner leave-one-fly-out grouping within genotype; all native trials retained.",
        "target_or_episode_eligibility_created": False,
        "identity_independently_proved_by_this_program": False,
        "scientific_admission": False,
    }


def write_new_private(path, value):
    body = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(body) <= MAX_OUTPUT_BYTES, "output_size_limit")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-plan", required=True)
    parser.add_argument("--identity-resolution", required=True)
    parser.add_argument("--identity-resolution-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        plan = read_bound_json(args.base_plan, PLAN_BYTES, PLAN_SHA256, PLAN_BYTES)
        resolution = read_bound_json(args.identity_resolution, MAX_RESOLUTION_BYTES,
                                     args.identity_resolution_sha256)
        result = compile_splits(plan, resolution,
                                resolution_sha256=args.identity_resolution_sha256)
        info = write_new_private(args.output, result)
    except (Refused, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(2, "fly-group-splits refused: " + str(exc) + "\n")
    print(json.dumps({"status": "metadata_compiled", **info,
                      "scientific_admission": False}, sort_keys=True))


if __name__ == "__main__":
    main()
