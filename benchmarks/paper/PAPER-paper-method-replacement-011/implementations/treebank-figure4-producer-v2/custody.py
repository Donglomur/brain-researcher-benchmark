"""Source/input custody utilities; no imports of author or scientific code."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

AUTHOR_COMMIT = "c54ba38eab7814538bc03b1b6d29a3f50f034e12"
TASK_ID = "PAPER-paper-method-replacement-011"
METADATA_PINS = {
    "labels": (7917, "68790f9359305be87e62b4b8f1f168ec4e5f8a5bf9f9470a4f2817db6ab19b4d"),
    "subjects": (7944, "8d1d48fcf30876601e41da88cea693608594bfb6ef5214437368954438c66b60"),
    "localization": (453364, "e376cc971f9489e568c84c17300f07c3a8c248c6c2436ac3b46d803651b88581"),
    "corrupted": (None, "86760a363037d57c578f20fd002ba0fe9fd1ce2f747ef12a2975e4a18b5b2c88"),
}
LOADER_PINS = {
    "data/h5_data.py": "c25489d42505979109d2d74bfc36314c7d411f207122fb1efecceaac62fdeef8",
    "data/h5_data_reader.py": "775b992b15199e762bcb915f23ce13d2060332a9b742817a30db4efffea9628d",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def no_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(raw):
    return json.loads(raw, object_pairs_hook=no_duplicate_pairs,
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"nonfinite JSON {token}")))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_bounded(path, limit):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"regular file required: {path}")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, f"file exceeds byte limit: {path}")
    return raw


def pinned_metadata(path, name):
    raw = read_bounded(path, 2 * 1024 * 1024)
    size, sha = METADATA_PINS[name]
    require((size is None or len(raw) == size) and digest(raw) == sha,
            f"wrong authenticated {name} metadata bytes")
    return raw


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def write_json_exclusive(path, value):
    """Publish a complete JSON file without replacing an existing file."""
    path = Path(path)
    raw = canonical_bytes(value) + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=".treebank-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"bytes": len(raw), "sha256": digest(raw)}


def source_git(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS="1", GIT_OPTIONAL_LOCKS="0",
               GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="")
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                             "-c", "protocol.allow=never", "-C", str(repo), *args], env=env, check=False,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    require(result.returncode == 0, "source Git inspection failed: " + result.stderr.decode(errors="replace")[:1000])
    return result.stdout


def verify_checkout(repo, expected_commit=AUTHOR_COMMIT):
    """Verify tracked bytes against the pinned Git tree without importing it.

    All tracked regular files are verified, not just two previously inspected
    loaders. Untracked/ignored files are rejected, including injected modules
    and stale bytecode. Keep data and generated caches outside this checkout.
    """
    repo = Path(repo).resolve(strict=True)
    require(source_git(repo, "rev-parse", "HEAD").decode().strip() == expected_commit,
            "source checkout is not the pinned author revision")
    require(not source_git(repo, "ls-files", "--others", "-z"),
            "source checkout contains untracked/ignored files; use a clean dedicated checkout")
    rows = source_git(repo, "ls-tree", "-rz", "--full-tree", expected_commit).split(b"\0")
    index_rows = source_git(repo, "ls-files", "--stage", "-z").split(b"\0")
    index = {}
    for row in filter(None, index_rows):
        header, encoded_path = row.split(b"\t", 1)
        mode, blob, stage = header.decode().split()
        require(stage == "0", "unmerged source index")
        relative = encoded_path.decode("utf-8")
        require(relative not in index, "duplicate source index path")
        index[relative] = (mode, blob)
    records = {}
    for row in filter(None, rows):
        header, encoded_path = row.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        relative = encoded_path.decode("utf-8")
        parts = PurePosixPath(relative).parts
        require(kind == "blob" and mode in ("100644", "100755"), "unsupported source symlink/submodule")
        require(index.get(relative) == (mode, blob), f"staged source change: {relative}")
        require(parts and ".." not in parts and not relative.startswith("/"), "unsafe source tree path")
        path = repo.joinpath(*parts)
        require(path.resolve(strict=True).is_relative_to(repo) and not path.is_symlink(), "source path escapes checkout")
        raw = read_bounded(path, 8 * 1024 * 1024)
        git_hash = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        require(git_hash == blob, f"modified source file: {relative}")
        records[relative] = {"git_blob_sha1": blob, "sha256": digest(raw), "bytes": len(raw)}
    require(set(index) == set(records), "source index contains added/removed paths")
    if expected_commit == AUTHOR_COMMIT:
        for name, sha in LOADER_PINS.items():
            require(records.get(name, {}).get("sha256") == sha, f"authenticated loader differs: {name}")
    return {"commit": expected_commit, "files": records}


def zip_member(archive, name, limit=2 * 1024 * 1024):
    """Read one named metadata member; never extract paths or execute contents."""
    names = [item.filename for item in archive.infolist()]
    require(len(names) == len(set(names)), "duplicate ZIP member")
    require(name in names, f"missing metadata member: {name}")
    item = archive.getinfo(name)
    require(not item.is_dir() and item.file_size <= limit and not item.flag_bits & 1,
            "metadata member is oversized, a directory, or encrypted")
    require((item.external_attr >> 16) & 0o170000 != 0o120000, "ZIP symlink rejected")
    with archive.open(item) as handle:
        raw = handle.read(limit + 1)
    require(len(raw) == item.file_size and len(raw) <= limit, "metadata ZIP size mismatch")
    return raw


def finite(value, context="number"):
    require(type(value) in (int, float) and math.isfinite(value), f"finite real {context} required")
    return float(value)
