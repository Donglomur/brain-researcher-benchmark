"""Once-only same-process caller for the exact CONSENSUS35 primitive-header owner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

HERE = Path(__file__).resolve().parent
EXPECTED_OUTPUT = Path('/UNCONFIGURED/producer')
EXPECTED_PYTHON = '/UNCONFIGURED/python'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def capture(path, size, sha):
    p = Path(path).absolute()
    need(".." not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)),
         "ordinary selected metadata/source path")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        before = os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and type(size) is int and 0 < size <= 262144 and before.st_size == size,
             "exact bounded selected extent")
        body = f.read(size + 1)
        after = os.fstat(f.fileno())
    keys = ("st_dev","st_ino","st_size","st_mtime_ns","st_ctime_ns")
    need(all(getattr(before,k) == getattr(after,k) == getattr(p.lstat(),k) for k in keys)
         and len(body) == size and hashlib.sha256(body).hexdigest() == sha,
         "stable complete selected bytes")
    return body


def launch(path, size, sha):
    body = capture(path, size, sha)
    b = json.loads(body)
    need(b.get("execution_authority") is True and b.get("automatic_retry") is False,
         "root-selected actual only; inert request cannot launch")
    need(b["schema"] == "consensus-original35-header-owner-binding-v1"
         and b["output_path"] == str(EXPECTED_OUTPUT)
         and b["owner"]["path"] == str(HERE/"header_owner.py")
         and b["python"]["path"] == EXPECTED_PYTHON,
         "exact task-local owner/interpreter/output")
    need(type(b["observer_cpu_reserved_slots"]) is int
         and 2 <= b["observer_cpu_reserved_slots"] <= 64,
         "current root-selected CPU booking")
    capture(**dict(path=b["owner"]["path"],size=b["owner"]["bytes"],sha=b["owner"]["sha256"]))
    need(not EXPECTED_OUTPUT.exists()
         and not any(p.is_symlink() for p in (EXPECTED_OUTPUT, *EXPECTED_OUTPUT.parents)),
         "fresh once-only external output")
    os.setsid() if os.getsid(0) != os.getpid() else None
    need(os.getpid() == os.getpgrp() == os.getsid(0), "owned same-process outer group")
    argv = [EXPECTED_PYTHON, "-I", "-S", "-B", str(HERE/"header_owner.py"),
            "--owner", str(Path(path).absolute()), str(size), sha]
    birth = EXPECTED_OUTPUT.parent/(EXPECTED_OUTPUT.name+".OUTER_BIRTH.json")
    raw = (json.dumps({"pid":os.getpid(),"group_id":os.getpgrp(),"session_id":os.getsid(0),
                      "argv":argv,"selected_request":{"path":str(path),"bytes":size,"sha256":sha},
                      "started_unix":time.time(),"started_monotonic":time.monotonic(),
                      "retry":False},sort_keys=True)+"\n").encode()
    fd = os.open(birth, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    try:
        need(os.write(fd,raw) == len(raw), "complete durable outer birth")
        os.fsync(fd)
    finally:
        os.close(fd)
    os.execv(EXPECTED_PYTHON, argv)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request",required=True)
    p.add_argument("--bytes",required=True,type=int)
    p.add_argument("--sha256",required=True)
    a = p.parse_args()
    launch(a.request,a.bytes,a.sha256)
