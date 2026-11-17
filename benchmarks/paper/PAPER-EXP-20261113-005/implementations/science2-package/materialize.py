"""Materialize the single PFC Science2 task without running science or Docker.

Image strings are immutable-reference syntax, not image admission. The operator
must independently admit their content and platform before selecting a build.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
SOURCE_MANIFEST_SHA256 = "914881559f331bf06192aebe5fd894b2a53f7ece5e8067101256c0ae637b3b97"
TASK_SLUG = "pfc-conditional-reconstruction"
NOTICE_NAMES = ("ATTRIBUTION.md", "PUBLIC_LINEAGE.json", "DANDI_TERMS.md", "RELEASE_NOTES.md")
ASSETS = {
    "participant-packet.json": (5368996, "8f6dc8ffff5e6ab4aa3be41dd3e9b0847c829b345142204d154124847908b21e"),
    "paper.xml": (182214, "0f09c47e6e5d4feaf61fbbe6e0ae58d36c30513ba7087264ea19e902765b871a"),
    "category_matching.py": (12651, "16738744d3b5b9d08970193121a4c2ac3fcf6d170565caaf74c752311f95b7b1"),
    "LICENSE": (1300, "beeebec59505f45b936c0129cf92fbd6f705cd7c9062b248bbe12010c39e509a"),
}
IMAGE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+@sha256:[0-9a-f]{64}\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def plain_path(path, *, exists=True):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute nontraversing path")
    for parent in (path, *path.parents):
        try:
            s = parent.lstat()
        except FileNotFoundError:
            require(parent == path and not exists, "missing ancestor")
            continue
        require(not stat.S_ISLNK(s.st_mode), "symlink path")
        if parent != path:
            require(stat.S_ISDIR(s.st_mode), "ordinary ancestor directory")
    return path


class Reads:
    """Managed bodies only; this is not an OS, Git or Docker I/O meter."""
    def __init__(self, maximum=32 * 1024**2):
        self.maximum = maximum
        self.bytes = 0

    def read(self, path, limit, expected=None):
        path = plain_path(path)
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "ordinary single-link file")
        require(before.st_size <= limit, "member extent")
        require(self.bytes + before.st_size + 1 <= self.maximum, "managed read allowance")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            opened = os.fstat(fd)
            require(stamp(before) == stamp(opened), "opened physical identity")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                body = handle.read(before.st_size + 1)
                self.bytes += len(body)
            require(len(body) == before.st_size <= limit, "complete extent")
            require(stamp(opened) == stamp(os.fstat(fd)) == stamp(path.lstat()),
                    "stable physical identity")
        finally:
            os.close(fd)
        digest = hashlib.sha256(body).hexdigest()
        if expected is not None:
            require((len(body), digest) == expected, "exact source or asset identity")
        return body


def file_roster(root):
    root = plain_path(root)
    require(root.is_dir(), "ordinary source directory")
    result = set()
    entries = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            entries += 1
            require(entries <= 128, "bounded namespace entries")
            p = Path(directory) / name
            s = p.lstat()
            require(not stat.S_ISLNK(s.st_mode), "source namespace symlink")
            require(stat.S_ISDIR(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_nlink == 1),
                    "ordinary source namespace")
            if stat.S_ISREG(s.st_mode):
                result.add(str(p.relative_to(root)))
        require(len(result) <= 64, "source file count")
    return result


def admit_request(request):
    require(type(request) is dict and set(request) == {
        "schema", "asset_root", "output_root", "agent_image", "verifier_image", "notices"
    }, "exact request fields")
    require(request["schema"] == "PFC_SCIENCE2_MATERIALIZE_V1", "request schema")
    for field in ("agent_image", "verifier_image"):
        require(type(request[field]) is str and IMAGE.fullmatch(request[field]) is not None,
                "explicit repository manifest digest")
    require(type(request["asset_root"]) is str and type(request["output_root"]) is str,
            "path strings")
    asset_root = plain_path(Path(request["asset_root"]))
    output_root = plain_path(Path(request["output_root"]), exists=False)
    require(not output_root.exists(), "fresh output directory")
    require(output_root.parts[-4:] == ("tasks", "life-sciences", "neuroscience", TASK_SLUG),
            "exact target taxonomy and task slug")
    require(asset_root != output_root and asset_root not in output_root.parents and
            output_root not in asset_root.parents, "disjoint assets and task")
    require(type(request["notices"]) is list and len(request["notices"]) == 4,
            "four exact release notices")
    notices = {}
    for row, name in zip(request["notices"], NOTICE_NAMES):
        require(type(row) is dict and set(row) == {"name", "bytes", "sha256"} and
                row["name"] == name, "ordered exact notice names")
        require(type(row["bytes"]) is int and 0 < row["bytes"] <= 262144,
                "bounded notice extent")
        require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                "notice digest")
        notices[name] = (row["bytes"], row["sha256"])
    return asset_root, output_root, notices


def render_dockerfile(body, token, image):
    text = body.decode("utf-8")
    require(text.count(token) == 1 and ("FROM " + token) in text, "one frozen FROM token")
    # Drop only the unmaterialized preamble; preserve every operative instruction.
    text = text[text.index("FROM " + token):]
    return text.replace(token, image).encode()


def materialize(request, *, source_root=None, reader=None):
    source_root = HERE if source_root is None else Path(source_root)
    reader = Reads() if reader is None else reader
    asset_root, output_root, notices = admit_request(request)
    raw_manifest = reader.read(source_root / "SOURCE_MANIFEST.json", 262144)
    require(hashlib.sha256(raw_manifest).hexdigest() == SOURCE_MANIFEST_SHA256,
            "frozen source manifest")
    manifest = decode(raw_manifest)
    require(manifest["schema"] == "PFC_SCIENCE2_SOURCE_MANIFEST_V1", "source schema")
    expected = {row["path"] for row in manifest["files"]}
    require(len(expected) == len(manifest["files"]) == 15, "complete source roster")
    require(file_roster(source_root / "task") == expected, "exact task source namespace")
    require(file_roster(asset_root) == set(ASSETS) | set(NOTICE_NAMES),
            "exact released asset namespace")
    bodies = {}
    for row in manifest["files"]:
        name = row["path"]
        require(not Path(name).is_absolute() and ".." not in Path(name).parts,
                "source relative member")
        bodies[name] = reader.read(source_root / "task" / name, 1048576,
                                   (row["bytes"], row["sha256"]))
    asset_bodies = {name: reader.read(asset_root / name, 8388608, pin)
                    for name, pin in ASSETS.items()}
    notice_bodies = {name: reader.read(asset_root / name, 262144, pin)
                     for name, pin in notices.items()}
    for name, field, token in (
        ("environment", "agent_image", "__REVIEWED_PFC_RUNTIME_REFERENCE__"),
        ("tests", "verifier_image", "__REVIEWED_PFC_VERIFIER_RUNTIME_REFERENCE__"),
    ):
        old = name + "/Dockerfile.template"
        bodies[name + "/Dockerfile"] = render_dockerfile(bodies.pop(old), token, request[field])
    for name, body in asset_bodies.items():
        bodies["environment/assets/" + name] = body
    bodies["tests/assets/participant-packet.json"] = asset_bodies["participant-packet.json"]
    for name, body in notice_bodies.items():
        bodies["environment/assets/notices/" + name] = body
        bodies["tests/assets/notices/" + name] = body
    require(sum(map(len, bodies.values())) <= 16 * 1024**2, "retained task extent")
    # All input validation precedes the first write. Write failures retain partial
    # output and never fabricate a success report or overwrite an earlier task.
    output_root.mkdir(mode=0o700)
    for name, body in sorted(bodies.items()):
        dest = output_root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        dest.chmod(0o755 if name in {"solution/solve.sh", "tests/test.sh"} else 0o644)
    rows = []
    for name, expected_body in sorted(bodies.items()):
        body = reader.read(output_root / name, 8388608,
                           (len(expected_body), hashlib.sha256(expected_body).hexdigest()))
        rows.append({"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    require(file_roster(output_root) == set(bodies), "complete materialized namespace")
    report = {
        "schema": "PFC_SCIENCE2_LOCAL_PACKAGE_V1", "files": rows,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "agent_image_reference": request["agent_image"],
        "verifier_image_reference": request["verifier_image"],
        "managed_body_read_bytes": reader.bytes,
        "task_source_and_assets_materialized": True,
        "image_content_platform_and_availability_verified": False,
        "native_harbor_validation": False, "author_metadata_verified": False,
        "full_upstream_source_checks": False, "submission_ready": False,
        "scientific_or_benchmark_count_delta": 0,
    }
    return report


def main(argv):
    require(len(argv) == 1, "usage: materialize.py REQUEST.json")
    reader = Reads()
    request = decode(reader.read(Path(argv[0]), 65536))
    report = materialize(request, reader=reader)
    sys.stdout.buffer.write(encode(report))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
