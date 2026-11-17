"""Container-only adapter for the original single-file candidate CLI.

This file is never used to execute a candidate on the operator host.
The entire producer container is removed before the operator reads its output.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    request_raw = Path("/request.json").read_bytes()
    request = json.loads(request_raw)
    result = subprocess.run(
        [sys.executable, "-I", "-B", "/program/candidate.py", "--input", "/input", "--out", "/output"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return 1
    path = Path("/output/predictions.npz")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= 1_000_000:
            return 2
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(1_000_001)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if len(raw) != before.st_size or any(getattr(before, k) != getattr(after, k) for k in fields):
            return 2
    finally:
        os.close(fd)
    # These are untrusted candidate-environment reports; only the external
    # transport proves producer closure and the original host scorer validates.
    summary = encoded({"schema": "neural023_candidate_output_v1", "candidate_exit": 0})
    with Path("/output/RESULT.json").open("xb") as stream:
        stream.write(summary)
    manifest = {"schema": "osl_transport_output_manifest_v1", "phase_id": request["phase_id"],
                "request_sha256": pin(request_raw)["sha256"],
                "files": {"predictions.npz": pin(raw), "RESULT.json": pin(summary)}}
    with Path("/output/OUTPUTS.json").open("xb") as stream:
        stream.write(encoded(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
