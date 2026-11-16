"""Authenticate a DUNL package, then test an isolated copy of its checked bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

MEMBERS = {"README.md", "PROVENANCE.json", "reconstruction.py",
           "test_reconstruction.py", "verify_and_test.py"}
MANIFEST = "SOURCE_MANIFEST.json"
MEMBER_CAP = 262144
CHILD_CONTROLS = r'''import hashlib, pathlib, sys, types, unittest
path = pathlib.Path(sys.argv[1])
source = path.read_bytes()
if hashlib.sha256(source).hexdigest() != sys.argv[2]:
    raise SystemExit('captured test identity changed')
module = types.ModuleType('dunl_verified_generated_controls')
module.__file__ = str(path)
exec(compile(source, str(path), 'exec'), vars(module))
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
result = unittest.TextTestRunner(verbosity=2).run(suite)
complete = (result.wasSuccessful() and result.testsRun == 18 and not result.skipped
            and not result.expectedFailures and not result.unexpectedSuccesses)
raise SystemExit(0 if complete else 1)
'''


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def read_member(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= MEMBER_CAP,
                "ordinary bounded member required")
        data = stream.read(MEMBER_CAP + 1)
        require(len(data) <= MEMBER_CAP and len(data) == before.st_size,
                "member size mismatch")
        require(identity(os.fstat(stream.fileno())) == identity(before),
                "member changed while reading")
    data.decode("utf-8")
    return data


def no_duplicates(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate manifest field")
        result[key] = value
    return result


def invalid_constant(value):
    raise Refusal("nonfinite manifest constant")


def authenticate(package, expected_bytes, expected_sha256):
    require(type(expected_bytes) is int and 1 <= expected_bytes <= MEMBER_CAP,
            "trusted manifest size")
    require(type(expected_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", expected_sha256), "trusted manifest digest")
    require(package.is_dir() and not package.is_symlink(), "ordinary package directory")
    require({p.name for p in package.iterdir()} == MEMBERS | {MANIFEST},
            "package has missing or unexpected members")
    raw = read_member(package / MANIFEST)
    require(len(raw) == expected_bytes and hashlib.sha256(raw).hexdigest() == expected_sha256,
            "trusted manifest identity")
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates,
                     parse_constant=invalid_constant)
    require(type(obj) is dict and set(obj) == {"schema", "family", "files"},
            "manifest fields")
    require(obj["schema"] == "dunl_public_package_manifest_v1" and
            obj["family"] == "PAPER-CANDIDATE-20261114-DUNL", "manifest identity")
    require(type(obj["files"]) is list and len(obj["files"]) == len(MEMBERS),
            "manifest member count")
    checked = {}
    for row in obj["files"]:
        require(type(row) is dict and set(row) == {"path", "bytes", "sha256"},
                "manifest member fields")
        name = row["path"]
        require(type(name) is str and name in MEMBERS and name not in checked,
                "exact unique member name")
        require(type(row["bytes"]) is int and 0 <= row["bytes"] <= MEMBER_CAP,
                "member size field")
        require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                "member digest field")
        data = read_member(package / name)
        require(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"],
                "member content identity")
        checked[name] = data
    require(set(checked) == MEMBERS, "complete authenticated package")
    return checked


def run_checked(checked):
    # Neither code nor bytecode is reread from the original package after verification.
    with tempfile.TemporaryDirectory(prefix="dunl-verified-controls-") as directory:
        target = Path(directory)
        for name in ("reconstruction.py", "test_reconstruction.py"):
            path = target / name
            with path.open("xb") as stream:
                stream.write(checked[name])
            path.chmod(0o600)
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", CHILD_CONTROLS,
                                 str(target / "test_reconstruction.py"),
                                 hashlib.sha256(checked["test_reconstruction.py"]).hexdigest()],
                                check=False, timeout=60)
        return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-bytes", type=int, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        checked = authenticate(Path(__file__).absolute().parent,
                               args.manifest_bytes, args.manifest_sha256)
        print(json.dumps({"authenticated_members": len(checked),
                          "authenticated_bytes": sum(map(len, checked.values())),
                          "scientific_qualification": False}), flush=True)
        return run_checked(checked)
    except (OSError, ValueError, RecursionError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "refused", "error_type": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
