"""Fixed initialized launch barrier; no Harbor import before owner activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time


def need(ok, text):
    if not ok:
        raise ValueError(text)


def read(path, limit=1048576):
    path = Path(path)
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= limit
         and not any(p.is_symlink() for p in (path, *path.parents)), "fixed private journal")
    with open(path, "rb") as f:
        body = f.read(limit + 1)
    need(len(body) == s.st_size, "complete bounded private journal")
    return json.loads(body), body


def atomic(root, name, value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    need(len(body) <= 65536, "fixed bootstrap metadata")
    path = root / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--deadline", type=float, required=True)
    parser.add_argument("--cache-prefix", required=True)
    args = parser.parse_args()
    need(os.uname().sysname == "Linux" and os.geteuid() == 0 and os.getpid() == os.getpgrp(),
         "fixed privileged caretaker group")
    need(len(args.token) == 32 and all(c in "0123456789abcdef" for c in args.token), "owner token")
    cache = Path(args.cache_prefix)
    need(cache.is_absolute() and str(cache) == os.path.normpath(str(cache))
         and not any(p.is_symlink() for p in (cache, *cache.parents)), "literal fixed cache prefix")
    cs = cache.lstat()
    need(stat.S_ISDIR(cs.st_mode) and cs.st_uid == 0 and stat.S_IMODE(cs.st_mode) == 0o550
         and sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1
         and sys.pycache_prefix == str(cache)
         and sys._xoptions.get("pycache_prefix") == str(cache), "actual isolated no-write cache startup")
    with os.scandir(cache) as entries:
        need(next(entries, None) is None, "empty selected cache before activation")
    cache_identity = {"path": str(cache), "device": cs.st_dev, "inode": cs.st_ino,
                      "uid": cs.st_uid, "gid": cs.st_gid, "mode": stat.S_IMODE(cs.st_mode)}
    root = Path(args.owner).parent
    atomic(root, "READY.json", {"schema": "tms_figure2b_bootstrap_ready_v1",
                                "token": args.token, "pid": os.getpid(), "pgid": os.getpgrp()})
    while not (root / "ACTIVATE.json").exists():
        need(time.monotonic() < args.deadline, "activation deadline")
        time.sleep(.01)
    owner, _ = read(args.owner)
    gate, _ = read(root / "ACTIVATE.json")
    need(gate == {"token": args.token, "activate": True} and owner["token"] == args.token
         and owner["bootstrap"]["pid"] == os.getpid(), "durable owner before activation")
    need(owner["bytecode_cache"] == cache_identity
         and cache_identity["gid"] == owner["host_gid"], "original selected cache and host-group identity")
    need(owner["host_uid"] > 0 and owner["host_gid"] > 0 and
         all(type(g) is int and g > 0 for g in owner["supplementary_gids"]), "explicit unprivileged controller")
    need(Path(owner["controller"]) == Path(__file__).resolve().with_name("host_child.py"),
         "one source-frozen controller")
    descriptor = owner["child_configuration"]
    _, config = read(descriptor["path"])
    need(len(config) == descriptor["bytes"] and hashlib.sha256(config).hexdigest() == descriptor["sha256"],
         "private child configuration")
    argv = [owner["python"], "-I", "-B", "-X", "pycache_prefix=" + str(cache), owner["controller"],
            "--configuration", descriptor["path"], "--bytes", str(descriptor["bytes"]),
            "--sha256", descriptor["sha256"],
            "--read-bytes", str(owner["child_read_bytes"]),
            "--write-bytes", str(owner["child_write_bytes"]),
            "--deadline", repr(owner["actor_deadline"]), "--cache-prefix", str(cache)]
    # The child stays in the observed group and preselected cgroup leaf.
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, user=owner["host_uid"],
                            group=owner["host_gid"], extra_groups=owner["supplementary_gids"],
                            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                                 "PYTHONDONTWRITEBYTECODE": "1"})
    remaining = owner["closure_deadline"] - time.monotonic()
    need(remaining > 0, "original actor and closure lifetime")
    code = proc.wait(timeout=remaining)
    atomic(root, "COMPLETION.json", {"schema": "tms_figure2b_controller_completion_v1",
           "token": args.token, "child_pid": proc.pid, "returncode": code,
           "natural_wait": True, "leader_waits_for_owner_stop": True})
    while time.monotonic() < owner["closure_deadline"]:
        time.sleep(.05)
    raise TimeoutError("owner failed to stop caretaker by original deadline")


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        # Fixed bounded stderr keeps the original type visible to outer capture.
        try:
            os.write(2, ("fixed_bootstrap_failure:" + type(error).__name__ + "\n").encode())
        except BaseException:
            pass
        raise
    finally:
        # Any exceptional caretaker exit stops only its owned original group.
        # The separate outer cgroup owner still must prove whole subtree absence.
        try:
            if os.getpid() == os.getpgrp():
                os.killpg(os.getpgrp(), signal.SIGKILL)
        finally:
            os._exit(124)
