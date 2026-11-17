"""Bounded consistency inspection of the complete inactive MC_Maze source.

The caller selects this ordinary inspector and the standalone entry. This checks
matching source identities, not a self-authenticating signature or qualification.
No local module, data, numerical library, model or native operation is imported.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

READ_CAP = 2 * 2**20
MEMBER_CAP = 2**20


def inspect_source(root):
    root = Path(os.path.abspath(root))
    for part in (root, *root.parents):
        if part.is_symlink():
            raise ValueError("ordinary source ancestry required")
    charged = 0

    def read(path, cap=MEMBER_CAP):
        nonlocal charged
        for parent in (path.parent, *path.parent.parents):
            if parent.is_symlink():
                raise ValueError("ordinary source ancestry required")
            if parent == root.parent:
                break
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= cap:
                raise ValueError("bounded ordinary single-link source required")
            if charged + before.st_size > READ_CAP:
                raise ValueError("complete inspection read cap")
            chunks = []
            remaining = before.st_size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    raise ValueError("short source read")
                charged += len(chunk)
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(fd)
            keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            if any(getattr(before, k) != getattr(after, k) for k in keys):
                raise ValueError("source changed during capture")
            return b"".join(chunks)
        finally:
            os.close(fd)

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate metadata key")
            out[key] = value
        return out

    def decode(raw):
        return json.loads(raw, object_pairs_hook=pairs)

    entry = read(root / "nlb_entry.py")
    tree = ast.parse(entry, filename="selected:nlb_entry.py")
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("MANIFEST_BYTES", "MANIFEST_SHA256"):
                if name in constants or not isinstance(node.value, ast.Constant):
                    raise ValueError("exact entry manifest constants")
                constants[name] = node.value.value
    if set(constants) != {"MANIFEST_BYTES", "MANIFEST_SHA256"}:
        raise ValueError("entry manifest constants absent")
    manifest_raw = read(root / "SOURCE_MANIFEST.json")
    if len(manifest_raw) != constants["MANIFEST_BYTES"] or hashlib.sha256(manifest_raw).hexdigest() != constants["MANIFEST_SHA256"]:
        raise ValueError("entry and manifest identity mismatch")
    manifest = decode(manifest_raw)
    if manifest["schema"] != "NLB017_complete_operator_source_v1" or len(manifest["files"]) != 73:
        raise ValueError("complete current 73-payload manifest required")
    if (manifest["group_count"], manifest["query_cases"], manifest["scientific_role_count"]) != (100, 574, 28844):
        raise ValueError("complete original scope required")
    if manifest["source_only"] is not True or manifest["native_qualified"] is not False or manifest["scientific_qualified"] is not False:
        raise ValueError("source-only qualification boundary required")
    bodies = {}
    for row in manifest["files"]:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("closed payload descriptor")
        name = row["path"]
        p = PurePosixPath(name)
        if type(name) is not str or p.is_absolute() or str(p) != name or any(z in ("", ".", "..") for z in p.parts) or name in bodies:
            raise ValueError("canonical unique payload path")
        raw = read(root.joinpath(*p.parts))
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("payload identity mismatch: " + name)
        bodies[name] = raw
    for name in ("source_inspection.py", "THIRD_PARTY_NOTICES.md", "nlb/operator_compiler.py", "nlb/scientific/GPFA_SOURCE_CONTRACT.json"):
        if name not in bodies:
            raise ValueError("complete selected source role absent")
    if "S13_SOURCE_MANIFEST.json" in bodies or "S13_DESIGN_MANIFEST.json" in bodies:
        raise ValueError("historical private inventories are not public payloads")
    expected_files = set(bodies) | {"SOURCE_MANIFEST.json", "nlb_entry.py"}
    expected_dirs = {"."}
    for name in expected_files:
        expected_dirs.update(str(parent) for parent in PurePosixPath(name).parents)
    pending = [root]
    seen_files = set()
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for directory_entry in entries:
                relative = str(Path(directory_entry.path).relative_to(root))
                if directory_entry.is_symlink():
                    raise ValueError("linked entry outside ordinary source census")
                if directory_entry.is_dir(follow_symlinks=False):
                    if relative not in expected_dirs:
                        raise ValueError("unlisted source directory")
                    pending.append(Path(directory_entry.path))
                elif directory_entry.is_file(follow_symlinks=False) and relative in expected_files:
                    seen_files.add(relative)
                else:
                    raise ValueError("unlisted source member")
    if seen_files != expected_files:
        raise ValueError("complete finite source census")
    contract_sha = hashlib.sha256(bodies["nlb/scientific/GPFA_SOURCE_CONTRACT.json"]).hexdigest()
    contract = decode(bodies["nlb/scientific/GPFA_SOURCE_CONTRACT.json"])
    if any(key in contract for key in ("additional_optimizer_source_provenance", "source_lock", "source_spec", "support_source_lock")):
        raise ValueError("private evidence locators are not public contract fields")
    if len(contract["distribution_versions"]) != 10 or len(contract["installed_source_members"]) != 14:
        raise ValueError("complete external scientific source requirements")
    for name in ("nlb/operator_compiler.py", "nlb/scientific/native_state.py"):
        values = [n.value for n in ast.walk(ast.parse(bodies[name])) if isinstance(n, ast.Constant)]
        if values.count(contract_sha) != 1:
            raise ValueError("exact native/compiler source contract join")
    sidecar = decode(read(root.parent / "SOURCE_COMPONENTS.json", 65536))
    selected = [x for x in sidecar["components"] if x["id"] == "complete-operator"]
    pin = {"path": "complete-operator/SOURCE_MANIFEST.json", "bytes": len(manifest_raw), "sha256": hashlib.sha256(manifest_raw).hexdigest()}
    if len(selected) != 1 or selected[0]["source_manifest"] != pin or selected[0]["status"] != "source_only":
        raise ValueError("source-discovery manifest join")
    if selected[0]["inspection"] != {"argv": ["{python}", "complete-operator/source_inspection.py", "--inspect"]}:
        raise ValueError("actual bounded inspection route required")
    return {"schema": "NLB017_public_source_consistency_v1", "status": "source_consistency_passed",
            "source_bodies": 75, "payload_bodies": 73, "python_bodies": sum(name.endswith(".py") for name in bodies) + 1,
            "groups": 100, "query_cases": 574, "scientific_roles": 28844,
            "manifest_sha256": pin["sha256"], "entry_sha256": hashlib.sha256(entry).hexdigest(),
            "logical_source_bytes_read": charged, "self_authentication_claim": False,
            "local_module_execution": False, "native_qualified": False, "scientific_qualified": False,
            "data_or_model_execution": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect_source(Path(__file__).absolute().parent), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
