"""Read-only inspection of the closed EEGPT public source package (standard library only)."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parent
MAX_FILES = 1024
MAX_MEMBER = 2 * 1024 * 1024
MAX_TOTAL = 8 * 1024 * 1024


class InspectionRefused(Exception):
    pass


def require(value, message):
    if not value:
        raise InspectionRefused(message)


def canonical_path(value):
    require(type(value) is str and value and "\\" not in value, "invalid source member path")
    parts = value.split("/")
    require(all(p and p not in (".", "..") for p in parts), "non-relative source member")
    require(not value.startswith("/"), "absolute source member")
    return parts


def ordinary(root, relative, maximum=MAX_MEMBER):
    """Read only an explicit ordinary source member; never follow symlinks."""
    parts = canonical_path(relative)
    owned = []
    try:
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        owned.append(parent)
        for part in parts[:-1]:
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            owned.append(parent)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        owned.append(fd)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and not before.st_mode & 0o111, "source must be single-link non-executable regular file")
        require(before.st_size <= maximum, "source member exceeds bound")
        chunks = []
        remaining = before.st_size + 1
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                break
            chunks.append(part)
            remaining -= len(part)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        named = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        sig = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode, s.st_nlink)
        require(sig(before) == sig(after) == sig(named) and len(raw) == before.st_size, "source changed during inspection")
        raw.decode("utf-8")
        require(b"\x00" not in raw, "ordinary UTF-8 source only")
        return raw
    finally:
        first = None
        while owned:
            fd = owned.pop()
            try:
                os.close(fd)
            except OSError as error:
                if first is None:
                    first = error
        if first is not None and sys.exc_info()[0] is None:
            raise first


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def verify(root=ROOT):
    manifest = decode(ordinary(root, "SOURCE_MANIFEST.json"))
    require(set(manifest) == {"schema", "files", "bytes_total", "manifest_self_reference"}, "exact public manifest fields")
    require(manifest["manifest_self_reference"] is False, "disjoint manifest closure")
    require(manifest["schema"] == "eegpt_public_inspection_source_manifest_v1", "public manifest schema")
    members = manifest["files"]
    require(type(members) is list and 0 < len(members) <= MAX_FILES, "finite source closure")
    paths = [m["path"] for m in members]
    require(len(paths) == len(set(paths)) and "SOURCE_MANIFEST.json" not in paths, "disjoint source closure")
    require(sum(m["bytes"] for m in members) <= MAX_TOTAL, "bounded whole source closure")
    found = []
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            require(not (Path(base) / name).is_symlink(), "symlink directory outside source closure")
        for name in files:
            found.append((Path(base) / name).relative_to(root).as_posix())
    require(set(found) == set(paths) | {"SOURCE_MANIFEST.json"}, "unexpected or missing package member")
    total = 0
    for member in members:
        require(set(member) == {"path", "bytes", "sha256", "git_mode"}, "exact manifest fields")
        raw = ordinary(root, member["path"])
        require(len(raw) == member["bytes"] and hashlib.sha256(raw).hexdigest() == member["sha256"], "source identity mismatch")
        require(member["git_mode"] == "100644", "non-executable ordinary source mode")
        total += len(raw)
    require(total == manifest["bytes_total"], "complete source accounting")
    return manifest


def inspect(root=ROOT):
    manifest = verify(root)
    # The package manifest authenticates cli.py, eegpt and all contracts first.
    # Scientific modules and model libraries are not needed by the actual Scope.
    before = set(sys.modules)
    require(not any(n == "eegpt" or n.startswith("eegpt.") for n in before), "fresh inspection namespace required")
    original_path = list(sys.path)
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location("_eegpt_public_cli", root / "cli.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        result = cli.main(["inspect"])
    finally:
        sys.path[:] = original_path
        for name in set(sys.modules) - before:
            if name == "eegpt" or name.startswith("eegpt."):
                del sys.modules[name]
    require(result["scope"]["all_required_matrix_slots_before_any_alias"] == 15402, "complete programme row scope")
    require(result["scope"]["gates_open"] == 24, "scientific gates remain open")
    require(not ({"numpy", "torch", "tensorflow", "scipy", "mne", "random"} & (set(sys.modules) - before)), "inspection imported a scientific/RNG library")
    disposition = decode(ordinary(root, "PROGRAMME_ROLE_DISPOSITION.json"))
    require(len(disposition["roles"]) == 157, "all original programme roles")
    return {
        "status": "INSPECTION_ONLY_NOT_EXECUTION_READY",
        "scope": result["scope"],
        "source_files_verified": len(manifest["files"]) + 1,
        "bundled_original_roles": disposition["bundled_original_roles"],
        "required_external_original_roles": disposition["external_original_roles"],
        "scientific_source_complete": False,
        "scientific_source_gaps": ["S01", "S02"],
        "uncertainty_limitation": "C01: conditional fitted-state estimates; one-person LOSO is not retraining uncertainty",
        "scientifically_qualified": False,
        "submission_ready": False,
        "scientific_runs_performed": 0,
        "execution": "No selected authority, complete external source, authentic intake or qualified runtime is supplied."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="EEGPT inspection/development source; no execution deployment.")
    parser.add_argument("operation", choices=("inspect", "verify", "execute"))
    args = parser.parse_args(argv)
    if args.operation == "execute":
        raise InspectionRefused("Execution unavailable: this package supplies no execution authority, complete source/license intake, authentic data or qualified runtime.")
    return inspect() if args.operation == "inspect" else {"status": "SOURCE_IDENTITIES_VERIFIED_ONLY", "files": len(verify()["files"]) + 1}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True, ensure_ascii=True))
    except (InspectionRefused, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error), "scientific_qualification_claim": False}, ensure_ascii=True), file=sys.stderr)
        raise SystemExit(2)

