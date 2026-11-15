"""Owned isolated-actor child CLI; admission and actual parent identity are mandatory."""
from hashlib import sha256
import argparse
import json
import os
import re
from pathlib import Path
import stat
import sys
import types

sys.dont_write_bytecode = True


def need(ok, message):
    if not ok:
        raise ValueError(message)


def capture(path, cap):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), "No linked actor bootstrap input")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "Bounded actor bootstrap metadata")
        chunks, total = [], 0
        while total <= cap:
            body = os.read(fd, min(65536, cap + 1 - total))
            if not body:
                break
            chunks.append(body); total += len(body)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        need(total == before.st_size and all(getattr(before, x) == getattr(after, x) for x in fields),
             "Stable complete actor bootstrap metadata")
        return b"".join(chunks)
    finally:
        os.close(fd)


def unique(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate actor bootstrap JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs)


def bootstrap(config_path, config_sha):
    body = capture(config_path, 262144)
    need(sha256(body).hexdigest() == config_sha, "Exact root-selected actor config")
    value = unique(body)
    root = Path(value["repository_root"]).absolute()
    here = Path(__file__).absolute()
    need(here.is_relative_to(root / "authoring"), "Fixed source namespace")
    pin = value["successor_freeze"]
    need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"} and
         not Path(pin["path"]).is_absolute() and ".." not in Path(pin["path"]).parts,
         "Selected actor source closure")
    source_body = capture(root / pin["path"], 131072)
    need(len(source_body) == pin["bytes"] and sha256(source_body).hexdigest() == pin["sha256"],
         "Exact source freeze before importing the owned entrypoint")
    freeze = unique(source_body)
    files = freeze["files"]
    entry = freeze["entrypoint"]
    need(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"} and
         not Path(entry["path"]).is_absolute() and ".." not in Path(entry["path"]).parts and
         entry["path"].startswith("authoring/") and
         files.get(entry["path"]) == {"bytes": entry["bytes"], "sha256": entry["sha256"]},
         "Exact concrete source-admitted driver entrypoint")
    selected = {}
    for name, path in (("actor_service.py", here), ("driver", root / entry["path"])):
        expected = files[path.relative_to(root).as_posix()]
        source = capture(path, 262144)
        need(len(source) == expected["bytes"] and sha256(source).hexdigest() == expected["sha256"],
             "Exact actor/entrypoint source before execution")
        selected[name] = source
    module = types.ModuleType("_isolated_actor_owned_entry")
    module.__file__ = str(root / entry["path"])
    need(module.__name__ not in sys.modules, "One owned driver bootstrap namespace")
    sys.modules[module.__name__] = module
    exec(compile(selected["driver"], module.__file__, "exec"), module.__dict__)
    config_module, config, stack, runtime = module.bootstrap(config_path, config_sha)
    need(Path(stack.actor_service.__file__) == here, "Actual child source equals admitted actor module")
    return config_module, config, stack, runtime


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--owner-directory", required=True)
    args = parser.parse_args(argv)
    need(re.fullmatch("[A-Za-z0-9_][A-Za-z0-9_-]{0,63}", args.mode) is not None,
         "One literal admitted context key")
    unused, config, stack, runtime = bootstrap(args.config, args.config_sha256)
    stack.actor_runtime.run_owned_actor(config, stack, runtime, args.mode, args.owner_directory)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # These bounded trusted-controller logs remain operator-side.
        print(json.dumps({"status": "actor_failed", "error_type": type(error).__name__}))
        raise SystemExit(1)

