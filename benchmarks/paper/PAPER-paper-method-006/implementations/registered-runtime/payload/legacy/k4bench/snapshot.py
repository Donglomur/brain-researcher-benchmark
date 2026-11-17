"""Authenticate the actual effective mount trees, request and candidate seal."""
import os
from pathlib import Path
from .protocol import require, validate_pin, ObjectStore, digest, parse_json, relative
from .admission import packet_members
from .identity import plan_digest, job_digest, profile_digest


def content_equal(a, b):
    return a["bytes"] == b["bytes"] and a["sha256"] == b["sha256"]


def tree_paths(root, max_files):
    files, dirs = [], []
    for folder, subdirs, names in os.walk(root, followlinks=False):
        for name in subdirs + names:
            path = Path(folder) / name
            require(not path.is_symlink(), "snapshot-symlink", str(path))
        for name in names:
            path = Path(folder) / name
            require(path.is_file(), "snapshot-special-file", str(path))
            files.append(str(path.relative_to(root)))
            require(len(files) <= max_files, "snapshot-file-cap", str(root))
        dirs.extend(str((Path(folder) / name).relative_to(root)) for name in subdirs)
        require(len(files) + len(dirs) <= max_files * 64, "snapshot-directory-cap", str(root))
    return set(files), set(dirs)


def verify_snapshot(store, manifest, job, profile, snapshot_pin, input_roots):
    snapshot = store.json(validate_pin(snapshot_pin), 4 * 1024 * 1024)
    require(snapshot["schema"] == "kilosort4_mount_snapshot_v2", "snapshot-schema", job["id"])
    require(snapshot["plan_digest"] == plan_digest(manifest)
            and snapshot["job_digest"] == job_digest(job)
            and snapshot["producer_profile_digest"] == profile_digest(profile)
            and snapshot["job_id"] == job["id"]
            and snapshot["cell"] == job["cell"]
            and snapshot.get("query_id") == job.get("query_id"),
            "snapshot-identity-mismatch", job["id"])
    roots = {row["root_id"]: row for row in snapshot["roots"]}
    require(len(roots) == len(snapshot["roots"]) and set(roots) == set(input_roots),
            "snapshot-root-set", job["id"])
    specs = {row["root_id"]: row for row in profile["mounts"]}
    require(set(specs) == set(roots), "snapshot-profile-mount-set", job["id"])
    members = {row["id"]: row for row in manifest["members"]}
    allowed = set(job["input_member_ids"])
    require(allowed <= set(members), "unknown-selected-member", job["id"])
    if job["audience"] == "candidate":
        public_ids = {row["id"] for row in packet_members(manifest["members"], job["cell"])}
        require(allowed <= public_ids, "protected-member-exposure", job["cell"])
    else:
        require(job["audience"] in {"protected_reference", "protected_constructor"},
                "unsupported-worker-audience", job["id"])
    seal = None
    if profile["worker_kind"] == "candidate":
        seal = store.json(validate_pin(snapshot["candidate_seal_pin"]), 1024 * 1024)
        require(seal["cell"] == job["cell"] and seal["state"] == "sealed",
                "candidate-seal-cell", job["cell"])
    else:
        require(snapshot.get("candidate_seal_pin") is None, "unexpected-program-seal", job["id"])
    seen_members, actual_pins, effective = set(), {}, []
    request_body = None
    request_spec = snapshot["request"]
    internal = snapshot["internal_files"]
    require(set(internal) <= {"request.json", "dispatch.json", "environment.json", "tool-caps.json"}
            and "request.json" in internal, "internal-request-inventory", job["id"])
    for root_id, row in roots.items():
        root = Path(row["host_path"])
        require(root.is_absolute() and root == root.resolve(strict=True)
                and not root.is_symlink() and root.is_dir(), "snapshot-root-alias", root_id)
        require(str(Path(input_roots[root_id]).absolute()) == str(root),
                "snapshot-root-substitution", root_id)
        require(row["target"] == specs[root_id]["target"]
                and specs[root_id]["read_only"] is True, "snapshot-target-mismatch", root_id)
        inventory = {entry["pin"]["path"]: entry for entry in row["files"]}
        require(len(inventory) == len(row["files"]), "duplicate-snapshot-path", root_id)
        actual_files, actual_dirs = tree_paths(root, snapshot["max_files"])
        expected_dirs = {str(parent) for name in inventory for parent in Path(name).parents if str(parent) != "."}
        require(actual_files == set(inventory) and actual_dirs == expected_dirs,
                "snapshot-extra-or-missing-member", root_id)
        mounted_store = ObjectStore(root, store.meter)
        before = root.stat()
        for name, entry in inventory.items():
            pin = validate_pin(entry["pin"])
            mounted_store.read(pin)
            container_path = row["target"].rstrip("/") + "/" + name
            actual_pins[container_path] = pin
            category = entry["category"]
            if category == "selected-member":
                member_id = entry["member_id"]
                require(member_id in allowed and member_id not in seen_members,
                        "unselected-or-duplicate-mounted-member", member_id)
                member = members[member_id]
                require(entry["role"] == member["role"] and content_equal(pin, member["pin"]),
                        "mounted-member-content-or-role", member_id)
                seen_members.add(member_id)
            elif category == "internal-request":
                require(row["target"] == "/run" and name in internal
                        and pin == internal[name], "unselected-internal-file", name)
            elif category == "sealed-program":
                require(seal is not None and row["target"] == "/candidate",
                        "unselected-program-mount", name)
                sealed = {x["path"]: x for x in seal["files"]}
                require(name in sealed and pin == sealed[name], "candidate-program-mutated", name)
            else:
                require(False, "unknown-snapshot-role", category)
            if root_id == request_spec["root_id"] and name == request_spec["path"]:
                require(pin == request_spec["pin"] and pin == internal["request.json"]
                        and container_path == "/run/request.json", "request-pin-mismatch", name)
                request_body = mounted_store.json(pin, 4 * 1024 * 1024)
        after = root.stat()
        require((before.st_dev, before.st_ino, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_mtime_ns), "snapshot-root-changed", root_id)
        effective.append({"root_id": root_id, "source": str(root), "target": row["target"],
                          "read_only": True, "tree_digest": digest(row["files"]),
                          "device": after.st_dev, "inode": after.st_ino})
    require(seen_members == allowed, "selected-input-not-mounted", job["id"])
    require(request_body is not None, "request-not-mounted", job["id"])
    context = request_body["execution_context"]
    require(context == {"plan_digest": plan_digest(manifest), "job_digest": job_digest(job),
                        "producer_profile_digest": profile_digest(profile), "job_id": job["id"],
                        "cell": job["cell"], "query_id": job.get("query_id")},
            "request-execution-context", job["id"])
    if profile["worker_kind"] == "candidate":
        require(request_body["case_id"] == job["query_id"]
                and request_body["candidate_seal_digest"] == digest(seal),
                "request-program-case-binding", job["id"])
        program_files = {path.removeprefix("/candidate/") for path in actual_pins if path.startswith("/candidate/")}
        require(program_files == {x["path"] for x in seal["files"]}, "incomplete-sealed-program", job["id"])
    # Every declared native input/source pin must identify the bytes actually
    # mounted at that absolute container path, never another store-only object.
    named = list(request_body.get("source_pins", []))
    for key in ("signal_pin", "probe_pin", "environment_receipt", "dispatch_receipt", "backend_executable_pin"):
        if key in request_body:
            named.append(request_body[key])
    for entry in request_body.get("inputs", {}).values():
        if entry is not None:
            named.append(entry["pin"])
    for entry in request_body.get("sidecars", {}).values():
        named.append(entry["pin"])
    for pin in named:
        require(pin["path"] in actual_pins and content_equal(pin, actual_pins[pin["path"]]),
                "request-pin-not-effective-mount", pin["path"])
    return {"schema": "kilosort4_verified_mounts_v2", "snapshot_pin": snapshot_pin,
            "plan_digest": plan_digest(manifest), "job_digest": job_digest(job),
            "producer_profile_digest": profile_digest(profile), "mounts": effective,
            "request_pin": request_spec["pin"], "request": request_body,
            "candidate_seal_pin": snapshot.get("candidate_seal_pin"),
            "physical_immutability_qualification": "separate admitted filesystem/isolation receipt required"}
