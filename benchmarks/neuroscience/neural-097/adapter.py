"""Central routing only; scientific code and deployment refusal stay upstream.

No candidate, review, target, dataset or native file is read by this adapter.
This module has no qualification/permission override and launches no child.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import stat
import sys

TASK_ID = "NEURAL-097"
CONDITIONS = ("complete", "A-F", "A-I", "B-F", "B-I")
STAGES = ("prepare", "references", "candidate", "assemble", "interpretation", "final-report")
LOCK_BYTES = 6895
LOCK_SHA256 = "224572aa09563d5706b1f8578d209250410025fd3fb9ac560371192370a84ffe"


class PackagingRefusal(ValueError):
    """A source/routing refusal is not a scientific score or gate closure."""


def need(value, message):
    if not value:
        raise PackagingRefusal(message)


def reserve(value):
    need(type(value) is str and value.isascii() and value.isdecimal(), "Reserve must be nonnegative decimal bytes")
    return int(value)


def parse(route, argv):
    need(route in ("run", "score", "operator"), "Unknown package route")
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--submission" if route == "score" else "--program", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--other-reserve-bytes", required=True, type=reserve)
    if route == "run":
        parser.add_argument("--condition", choices=CONDITIONS, default="complete")
    if route == "operator":
        parser.add_argument("--stage", choices=STAGES, required=True)
        parser.add_argument("--condition", choices=CONDITIONS, default="complete")
    args = parser.parse_args(argv)
    stage = "assemble" if route == "score" else (args.stage if route == "operator" else "candidate")
    condition = "complete" if route == "score" else args.condition
    need(stage == "candidate" or condition == "complete", "Named conditions belong only to candidate contributions")
    program = args.submission if route == "score" else args.program
    # A scorer consumes the original submission descriptor (not prediction JSON).
    # Actual four contributions are selected by the protected review, upstream.
    operands = (program, args.output, args.review)
    need(all(type(v) is str and v and "\0" not in v for v in operands), "Nonempty literal path operands required")
    return ["--program", program, "--output", args.output, "--review", args.review,
            "--other-reserve-bytes", str(args.other_reserve_bytes), "--condition", condition, "--stage", stage]


def source_body(root, relative, expected_bytes, expected_sha256):
    need(type(relative) is str and relative and "\\" not in relative
         and not relative.startswith("/") and all(x not in ("", ".", "..") for x in relative.split("/")), "Confined runtime source path")
    path = root / relative
    need(not root.is_symlink() and all(not p.is_symlink() for p in (path, *path.parents)), "No source symlink")
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == expected_bytes,
         "Exact ordinary source extent")
    need(type(expected_bytes) is int and 0 <= expected_bytes <= 1_048_576, "Bounded source member")
    with path.open("rb") as stream:
        body = stream.read(expected_bytes)
        after = os.fstat(stream.fileno())
    identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    need(len(body) == expected_bytes and identity(info) == identity(after), "Unchanged complete source read")
    need(hashlib.sha256(body).hexdigest() == expected_sha256, "Runtime source identity changed")
    return body


def verify_runtime(root):
    # These are ordinary source reads, not a data/target or runtime admission.
    # Their overhead must be included in any later qualified launch envelope.
    body = source_body(root, "RUNTIME_LOCK.json", LOCK_BYTES, LOCK_SHA256)
    lock = json.loads(body)
    need(lock["schema"] == "neural097-public-runtime-lock-v2" and lock["task_id"] == TASK_ID
         and lock["deployment_enabled"] is False and lock["scientific_source_changed"] is False, "Exact inactive source lock")
    need(set(lock) == {"schema", "task_id", "deployment_enabled", "scientific_source_changed", "source_representation_changed", "source_file_count", "source_bytes", "files"}
         and lock["source_representation_changed"] is True and lock["source_bytes"] == 375255, "Closed exact public runtime lock")
    files = lock["files"]
    need(type(files) is dict and len(files) == lock["source_file_count"] == 41
         and sum(pin["bytes"] for pin in files.values()) == 375255, "Complete 41-role public runtime projection")
    for relative, pin in files.items():
        need(relative.startswith("full-cogitate-meg-v1/"), "Only pinned public runtime source")
        source_body(root, relative, pin["bytes"], pin["sha256"])
    return root / "full-cogitate-meg-v1" / "entry.py"


def main(route, argv=None):
    original_argv = parse(route, sys.argv[1:] if argv is None else argv)
    root = Path(__file__).absolute().parent
    entry = verify_runtime(root)
    need(not any(name == "n097" or name.startswith("n097.") for name in sys.modules), "Fresh original programme module namespace required")
    previous = sys.argv
    sys.argv = [str(entry), *original_argv]
    # The original entry's deployment guard remains false. Qualification needs
    # a separately reviewed source successor; editing this adapter cannot grant it.
    try:
        runpy.run_path(str(entry), run_name="__main__")
    finally:
        sys.argv = previous
    return 0
