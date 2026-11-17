"""Trusted source/state freezing and paired P0 plan validation.

No candidate code is imported or executed by these helpers. File hashes bind
selected bytes, not scientific truth, rights, storage quotas or contamination.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

from contract import PEOPLE, CELLS, require

REPRESENTATION = "float32-le-c-order-62x301-v1"
MODES = ("frozen_program", "case_adaptive")
REFERENCE_NAMES = ("prior_only", "order_only", "premarker", "permutation",
                   "validated_competent_EEG_reference")
HOLDS = ("authentic_exact_source_intake", "all32_identity_and_complete_class_coverage",
         "raw_marker_and_channel_schema", "known_bad_channel_policy",
         "source_target_privacy_and_contamination", "matched_resource_budget",
         "native_reference_and_null_controls", "independent_scoring_replication",
         "qualified_process_isolation", "scientific_interpretation_review",
         "prefix_identifiability_and_order_controls", "behavioral_diagnostics",
         "historical_software_terms")
CANONICAL_SHA256 = "1f8038574d9193933f1a081dc449a08f25d23ae6ece69972d561e70a039be3a8"


def strict_json(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def bad(value):
        raise ValueError("nonfinite JSON constant")
    value = json.loads(body, object_pairs_hook=pairs, parse_constant=bad)
    def check(x):
        if isinstance(x, float):
            require(math.isfinite(x), "nonfinite JSON exponent")
        elif isinstance(x, dict):
            for v in x.values(): check(v)
        elif isinstance(x, list):
            for v in x: check(v)
    check(value)
    return value


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha(value):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "SHA256 required")
    return value


def positive(value, name, *, zero=False):
    require(type(value) is int and value >= (0 if zero else 1), name)
    return value


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value
            and not any(ord(c) < 32 for c in value), "relative path required")
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value
            and all(x not in (".", "..", "") for x in path.parts), "canonical relative path")
    return path


def ordinary(root, relative_name):
    root = Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "ordinary absolute root")
    path = root
    for part in relative(relative_name).parts:
        path = path / part
        require(not path.is_symlink(), "symlink forbidden")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            "ordinary single-link file required")
    return path, info


def read_member(root, member, maximum):
    require(set(member) == {"path", "bytes", "sha256"}, "exact member pin fields")
    positive(member["bytes"], "member extent", zero=True)
    require(member["bytes"] <= maximum, "member exceeds selected bound")
    sha(member["sha256"])
    path, before = ordinary(root, member["path"])
    require(before.st_size == member["bytes"], "member size mismatch")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "file changed before open")
        pieces, total = [], 0
        while True:
            data = os.read(fd, min(2**20, maximum + 1 - total))
            if not data:
                break
            total += len(data)
            require(total <= maximum, "member grew beyond bound")
            pieces.append(data)
        after = os.fstat(fd)
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "member mutated during read")
        body = b"".join(pieces)
        require(len(body) == member["bytes"] and hashlib.sha256(body).hexdigest() == member["sha256"], "member digest mismatch")
        return body
    finally:
        os.close(fd)


def write_new(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists() and not path.is_symlink(), "refusing overwrite")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)


def file_pin(path, name=None):
    path = Path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not path.is_symlink(), "pin ordinary file")
    body = path.read_bytes()
    return {"path": name or path.name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _limits(limits):
    require(set(limits) == {"max_files", "max_member_bytes", "max_total_bytes", "max_manifest_bytes"}, "freeze limits")
    for key, value in limits.items():
        positive(value, key)


def freeze_capsule(source_root, members, entrypoint, destination, limits):
    _limits(limits)
    require(isinstance(members, list) and 1 <= len(members) <= limits["max_files"], "capsule file count")
    require(isinstance(entrypoint, str) and "/" not in entrypoint
            and entrypoint.endswith(".py"), "flat Python entrypoint required")
    names = [m["path"] for m in members]
    require(len({n.casefold() for n in names}) == len(names) and entrypoint in names,
            "duplicate capsule path or absent entrypoint")
    require("CAPSULE.json" not in names and all(PurePosixPath(n).suffix in
            (".py", ".json", ".txt", ".md") for n in names), "source files only; assets separate")
    require(sum(m["bytes"] for m in members) <= limits["max_total_bytes"], "capsule aggregate extent")
    bodies = [(m, read_member(source_root, m, limits["max_member_bytes"])) for m in members]
    dest = Path(destination)
    require(dest.is_absolute() and not dest.exists(), "new absolute capsule destination")
    dest.mkdir(parents=True)
    for member, body in bodies:
        write_new(dest / member["path"], body)
        os.chmod(dest / member["path"], 0o444)
    manifest = {"schema": "morse-source-capsule-v1", "entrypoint": entrypoint,
                "files": sorted(members, key=lambda m: m["path"])}
    body = canonical_bytes(manifest)
    require(len(body) <= limits["max_manifest_bytes"], "capsule manifest extent")
    write_new(dest / "CAPSULE.json", body)
    os.chmod(dest / "CAPSULE.json", 0o444)
    return {"root": str(dest), "manifest": manifest, "manifest_pin": file_pin(dest / "CAPSULE.json"),
            "entrypoint": entrypoint, "files": {m["path"]: m["sha256"] for m in members},
            "capsule_sha256": hashlib.sha256(body).hexdigest()}


def seal_fit_state(output_root, destination, limits, *, context_id, capsule_sha256, training_view_sha256):
    """Call only after trusted terminal/cleanup observation of training stage."""
    _limits(limits)
    path, info = ordinary(output_root, "fit_manifest.json")
    require(info.st_size <= limits["max_manifest_bytes"], "fit manifest bound")
    pin = file_pin(path)
    raw = read_member(output_root, pin, limits["max_manifest_bytes"])
    manifest = strict_json(raw)
    require(isinstance(manifest, dict) and set(manifest) == {"context_id", "files"}
            and manifest["context_id"] == context_id, "fit manifest schema/context binding")
    members = manifest["files"]
    require(isinstance(members, list) and 1 <= len(members) <= limits["max_files"], "fit state file count")
    names = [m["path"] for m in members]
    require(len({n.casefold() for n in names}) == len(names) and "FIT_SEAL.json" not in names,
            "fit state names")
    require(sum(m["bytes"] for m in members) <= limits["max_total_bytes"], "fit state aggregate")
    snapshots = [(m, read_member(output_root, m, limits["max_member_bytes"])) for m in members]
    dest = Path(destination)
    require(dest.is_absolute() and not dest.exists(), "new fit seal destination")
    dest.mkdir(parents=True)
    for member, body in snapshots:
        write_new(dest / member["path"], body)
        os.chmod(dest / member["path"], 0o444)
    seal = {"schema": "morse-fit-seal-v1", "context_id": context_id,
            "capsule_sha256": sha(capsule_sha256), "training_view_sha256": sha(training_view_sha256),
            "policy": "P0-training-only-before-query", "files": sorted(members, key=lambda m: m["path"])}
    body = canonical_bytes(seal)
    require(len(body) <= limits["max_manifest_bytes"], "fit seal bound")
    write_new(dest / "FIT_SEAL.json", body)
    os.chmod(dest / "FIT_SEAL.json", 0o444)
    return {"root": str(dest), "seal": seal, "sha256": hashlib.sha256(body).hexdigest()}


def verify_fit_seal(frozen, limits):
    _limits(limits)
    root = Path(frozen["root"])
    body = read_member(root, {"path": "FIT_SEAL.json", "bytes": len(canonical_bytes(frozen["seal"])),
                             "sha256": frozen["sha256"]}, limits["max_manifest_bytes"])
    require(strict_json(body) == frozen["seal"], "fit seal changed")
    for member in frozen["seal"]["files"]:
        read_member(root, member, limits["max_member_bytes"])
    return True


def compile_paired_plan(spec):
    """Pure trusted metadata validation; never changes scientific admission."""
    required = {"schema", "canonical_sha256", "source_receipt_sha256", "representation",
                "policy", "people", "cells", "modes", "capsules", "environment", "stage_limits",
                "broker_limits", "model_spec", "freeze_limits", "prediction_max_bytes",
                "export_max_bytes", "context_max_bytes", "total_reserved_bytes", "max_concurrency",
                "reference_selection", "authoring_exposure", "scientific_holds", "engineering_only",
                "runtime_files", "storage_admission_id", "technical_retry_policy", "seed",
                "host_metadata_max_bytes", "workspace_max_files"}
    require(isinstance(spec, dict) and set(spec) == required, "complete paired plan schema")
    require(spec["schema"] == "morse-paired-candidate-p0-v1" and spec["policy"] == "P0-training-only-before-query", "selected P0 protocol")
    sha(spec["canonical_sha256"]); sha(spec["source_receipt_sha256"])
    require(spec["canonical_sha256"] == CANONICAL_SHA256, "selected early-information canonical required")
    require(spec["representation"] == REPRESENTATION and spec["people"] == list(PEOPLE)
            and spec["cells"] == list(CELLS) and spec["modes"] == list(MODES), "full32/two-mode/six-cell scope")
    require(set(spec["capsules"]) == set(MODES), "two frozen capsules")
    require(set(spec["reference_selection"]) == set(REFERENCE_NAMES), "all five required references")
    require(type(spec["engineering_only"]) is bool, "explicit engineering marker")
    require(isinstance(spec["authoring_exposure"], dict) and spec["authoring_exposure"].get("declared") is True,
            "public authoring/training exposure declaration required")
    require(isinstance(spec["scientific_holds"], list) and len(spec["scientific_holds"]) == 13
            and {h["id"] for h in spec["scientific_holds"]} == set(HOLDS)
            and all(set(h) == {"id", "qualified"} and h["qualified"] is False
                    for h in spec["scientific_holds"]), "retain all13 unresolved scientific holds")
    for name in ("prediction_max_bytes", "export_max_bytes", "context_max_bytes", "total_reserved_bytes", "max_concurrency", "host_metadata_max_bytes", "workspace_max_files"):
        positive(spec[name], name)
    require(spec["max_concurrency"] == 1, "initial concrete controller is sequential; no false concurrency capability")
    require(spec["export_max_bytes"] >= 745285632, "nominal full input representation requires sufficient declared capacity")
    # Retain all32 exports and64 context outputs/fitted states for private review.
    # This is a declared worst-case logical-byte bound, not physical quota proof.
    retained = 32 * spec["export_max_bytes"] + 64 * (2 * (spec["stage_limits"]["output_bytes"]
               + spec["stage_limits"]["workspace_bytes"]) + spec["freeze_limits"]["max_total_bytes"]
               + spec["freeze_limits"]["max_manifest_bytes"] + 2 * spec["context_max_bytes"])
    retained += spec["host_metadata_max_bytes"]
    require(spec["total_reserved_bytes"] >= retained, "total reserve omits retained exports/stages/state")
    _limits(spec["freeze_limits"])
    require(isinstance(spec["environment"], dict) and set(spec["environment"]) ==
            {"image_digest", "python_executable", "container_uid", "container_gid", "runtime_root"}, "environment binding")
    for capsule in spec["capsules"].values():
        sha(capsule["capsule_sha256"])
        require(capsule["entrypoint"] in capsule["files"], "capsule entrypoint binding")
    require(type(spec["runtime_files"]) is list and
            {m["path"] for m in spec["runtime_files"]} == {"morse_bootstrap.py", "morse_protocol.py"}
            and len(spec["runtime_files"]) == 2, "minimal worker runtime only")
    require(isinstance(spec["storage_admission_id"], str) and spec["storage_admission_id"], "storage admission identity")
    require(spec["technical_retry_policy"] == "abort-preserve-no-automatic-retry", "explicit retry selection")
    positive(spec["seed"], "seed", zero=True)
    for selected in spec["reference_selection"].values(): sha(selected)
    frozen = strict_json(canonical_bytes(spec))
    return {"spec": frozen, "sha256": digest(frozen), "logical_contexts": 64, "stage_launches": 128,
            "nominal_counts_only": True, "runnable": False, "research_qualified": False,
            "hidden_transductive_fitting_excluded_by_filesystem_alone": False}
