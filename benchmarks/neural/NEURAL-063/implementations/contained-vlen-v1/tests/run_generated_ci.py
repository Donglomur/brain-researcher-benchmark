"""Same-process portable CI entry; prints only validated json-controls results."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types


def source(path, *, expected=None, cap=131072):
    path = Path(path).resolve(strict=True)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= cap:
            raise ValueError("bounded source entry")
        body = bytearray()
        while len(body) < before.st_size:
            piece = os.read(fd, min(65536, before.st_size - len(body)))
            if not piece:
                raise ValueError("incomplete source entry")
            body.extend(piece)
        after, named = os.fstat(fd), path.lstat()
        stamp = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        if os.read(fd, 1) or stamp(before) != stamp(after) or stamp(before) != stamp(named):
            raise ValueError("source entry changed")
    finally:
        os.close(fd)
    if expected is not None and (len(body) != expected["bytes"] or
            hashlib.sha256(body).hexdigest() != expected["sha256"] or str(path) != expected["path"]):
        raise ValueError("selected runner identity differs")
    return path, bytes(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("component-root", "range-source-root", "original-root", "artifact-root",
                "python", "runtime-profile"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args(argv)
    # This entry/helper belong to the ownership-pinned CI source row; dynamic
    # component hashes then bind exactly the generated code actually exercised.
    component = Path(args.component_root).resolve(strict=True)
    if Path(__file__).resolve(strict=True) != component / "tests/run_generated_ci.py":
        raise ValueError("CI entry belongs to selected component")
    root = Path(args.artifact_root).expanduser()
    if root.exists() or root.is_symlink() or root.name in ("", ".", ".."):
        raise ValueError("fresh external artifact directory required")
    root = root.parent.resolve(strict=True) / root.name
    if len(str(root).encode()) > 2048 or not root.parent.is_dir():
        raise ValueError("bounded ordinary artifact parent")
    root.mkdir(mode=0o700)
    helper_path, helper_body = source(component / "tests/make_generated_plan.py", cap=32768)
    helper = types.ModuleType("_n063_portable_plan_builder")
    helper.__file__ = str(helper_path)
    exec(compile(helper_body, str(helper_path), "exec"), helper.__dict__)
    plan = helper.build_plan(component, args.range_source_root, args.original_root,
        root / "evidence", python=args.python, runtime_profile=args.runtime_profile)
    if (plan["plan_builder"]["sha256"] != hashlib.sha256(helper_body).hexdigest() or
            plan["plan_builder"]["bytes"] != len(helper_body)):
        raise ValueError("plan-builder source changed while constructing plan")
    ref = helper.publish_plan(root / "PLAN.json", plan)
    worker_path, worker_body = source(plan["runner"]["path"], expected=plan["runner"])
    worker = types.ModuleType("_n063_portable_generated_worker")
    worker.__file__ = str(worker_path)
    exec(compile(worker_body, str(worker_path), "exec"), worker.__dict__)
    return worker.main(["--plan", ref["path"], "--plan-sha256", ref["sha256"]])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # A bounded non-success JSON object cannot equal the maintained success
        # marker. Any partial generated plan remains retained; there is no retry.
        print(json.dumps({"error": type(exc).__name__ + ": " + str(exc)[:500]}, sort_keys=True))
        raise SystemExit(1)
