"""Authenticate the complete REP013 source closure, then load its existing API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types

MANIFEST = "SOURCE_MANIFEST.json"
MAX_MEMBER = 65536
MAX_TOTAL = 1048576
ADAPTER = "components/purkinje-paired-execution/paired_execution.py"
PAIRED = "components/purkinje-paired-access"
PRODUCER = "benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1"
# The fixed roster is generated once during source construction, not from input.
MEMBERS = ('LICENSE', 'OPERATOR.md', 'OPERATOR_PATHS.template.json', 'README.md', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/INPUT_PINS.json', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/REFERENCE_PINS.json', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/SCHEMA.json', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/TASK.md', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/boundary.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/bridge.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/bundle.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/common.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/docker_owner.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/durable_evidence.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/numeric_score.py', 'benchmarks/neuroscience/paper-find-rep-013-purkinje-morphology/program-v1/schema.py', 'components/purkinje-artifacts/artifact.py', 'components/purkinje-paired-access/A.json', 'components/purkinje-paired-access/ATTRIBUTION.md', 'components/purkinje-paired-access/B.json', 'components/purkinje-paired-access/COMMON.json', 'components/purkinje-paired-access/CONTRACT.json', 'components/purkinje-paired-access/HARNESS_REVIEW.template.json', 'components/purkinje-paired-access/NOTICES.md', 'components/purkinje-paired-access/RUN_REQUEST_A.template.json', 'components/purkinje-paired-access/RUN_REQUEST_B.template.json', 'components/purkinje-paired-access/SCHEMA.json', 'components/purkinje-paired-access/TASK.md', 'components/purkinje-paired-access/paired_packet.py', 'components/purkinje-paired-execution/NOTICES.md', 'components/purkinje-paired-execution/OWNER_AUTHORIZATION.template.json', 'components/purkinje-paired-execution/paired_execution.py', 'portable.py', 'test_portable.py')

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()

def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

def strict(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, "duplicate metadata key")
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite metadata")))

def ordinary(value):
    p = Path(value).absolute()
    need(".." not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)),
         "ordinary package path")
    return p

def exact(path, expected):
    need(type(expected) is dict and set(expected) == {"bytes", "sha256"} and
         type(expected["bytes"]) is int and 0 < expected["bytes"] <= MAX_MEMBER and
         type(expected["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", expected["sha256"]),
         "exact bounded source descriptor")
    path = ordinary(path)
    before = path.lstat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected["bytes"],
         "ordinary source extent")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(stamp(before) == stamp(os.fstat(fd)), "source changed before open")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()) and pin(body) == expected,
             "source identity changed")
        return body
    finally:
        os.close(fd)

def verify(root, expected_manifest_sha256):
    root = ordinary(root)
    need(type(expected_manifest_sha256) is str and
         re.fullmatch("[0-9a-f]{64}", expected_manifest_sha256), "reviewed manifest digest")
    p = root / MANIFEST
    raw = exact(p, {"bytes": p.lstat().st_size, "sha256": expected_manifest_sha256})
    manifest = strict(raw)
    need(type(manifest) is dict and set(manifest) == {"schema", "files"} and
         manifest["schema"] == "purkinje-paired-portable-source-v1" and
         type(manifest["files"]) is dict and set(manifest["files"]) == set(MEMBERS),
         "complete fixed source manifest")
    need(sum(v["bytes"] for v in manifest["files"].values()) <= MAX_TOTAL, "whole source extent")
    names = set(MEMBERS) | {MANIFEST}
    directories = {str(parent) for name in names for parent in Path(name).parents if str(parent) != "."}
    found, seen_dirs, pending = set(), set(), [root]
    while pending:
        d = pending.pop()
        with os.scandir(d) as entries:
            for entry in entries:
                p = Path(entry.path)
                relative = str(p.relative_to(root))
                st = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    need(relative in directories and relative not in seen_dirs, "unexpected source directory")
                    seen_dirs.add(relative)
                    pending.append(p)
                else:
                    need(relative in names and relative not in found and stat.S_ISREG(st.st_mode)
                         and st.st_nlink == 1, "unexpected or nonordinary source file")
                    found.add(relative)
    need(found == names and seen_dirs == directories, "complete source inventory")
    captured = {name: exact(root / name, descriptor) for name, descriptor in manifest["files"].items()}
    return manifest, captured

def load_executor(root, expected_manifest_sha256):
    """Source-only constructor. No provider, reference, runtime or candidate reads."""
    root = ordinary(root)
    manifest, captured = verify(root, expected_manifest_sha256)
    module = types.ModuleType("purkinje_portable_paired_execution")
    module.__file__ = str(root / ADAPTER)
    # Execute the exact captured bytes only after the complete source is authenticated.
    exec(compile(captured[ADAPTER], module.__file__, "exec"), module.__dict__)
    return module.PairExecutor(repo=root, paired_root=root / PAIRED,
                               producer_root=root / PRODUCER,
                               expected_source=manifest["files"][ADAPTER])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--root", default=str(Path(__file__).absolute().parent))
    args = parser.parse_args()
    executor = load_executor(args.root, args.manifest_sha256)
    print(json.dumps({"task_id": executor.paired_module.TASK, "source_complete": True,
                      "packet_files": {c: len(executor.paired.inventory(c)) for c in ("A", "B")},
                      "scope": executor.paired.contract["scope"],
                      "runtime_qualified": False, "execution_selected": False,
                      "scientific_count_delta": 0}, sort_keys=True))

if __name__ == "__main__":
    main()

