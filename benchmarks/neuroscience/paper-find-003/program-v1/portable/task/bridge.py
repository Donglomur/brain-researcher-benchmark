"""Container-only bridge for the existing file-output program ABI.
No reference, grader, host path or scientific transformation is present.
"""
import os
from pathlib import Path
import stat
import subprocess
import sys

MAX_BYTES = 262144

def capture_output(directory):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("ordinary output directory")
    entries = list(root.iterdir())
    if len(entries) != 1 or entries[0].name != "submission.json":
        raise ValueError("exactly one submission.json")
    path = entries[0]
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= MAX_BYTES):
            raise ValueError("bounded single-link ordinary submission")
        with os.fdopen(fd, "rb", closefd=False) as f:
            body = f.read(MAX_BYTES + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                           s.st_mtime_ns, s.st_ctime_ns)
        if not (len(body) == before.st_size and
                stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat())):
            raise ValueError("stable complete submission")
        return body
    finally:
        os.close(fd)

def main():
    # Candidate stdout/stderr go to the bounded container stderr channel.
    # The bridge stdout is solely the exact file bytes. The host owner enforces
    # the original 20-second candidate interval, then destroys the container.
    result = subprocess.run(
        [sys.executable, "-I", "/program/program.py", "--input", "/input",
         "--out", "/output"], stdin=subprocess.DEVNULL,
        stdout=sys.stderr, stderr=sys.stderr, check=False)
    if result.returncode != 0:
        return result.returncode if 0 < result.returncode < 126 else 70
    body = capture_output("/output")
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

