"""Verify the exact Debian index inputs used by a future image build.

This does not install packages or authorize a benchmark run. APT still verifies
the Debian signatures; this additionally binds the cleartext index to the lock.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import urllib.request


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def capture(path, ceiling):
    """Capture one bounded ordinary metadata body without following links."""
    require(path.is_absolute() and not any(
        p.is_symlink() for p in (path, *path.parents)),
        "Absolute unlinked metadata path")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            0 < before.st_size <= ceiling, "Bounded ordinary metadata")
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                       s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                 os.O_CLOEXEC)
    first = None
    close_error = None
    parts = []
    try:
        require(stamp(before) == stamp(os.fstat(fd)), "Opened metadata identity")
        remaining = before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            require(bool(part), "Short metadata body")
            parts.append(part)
            remaining -= len(part)
        require(not os.read(fd, 1), "Metadata body grew")
        require(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()),
                "Stable opened and named metadata identity")
    except BaseException as error:
        first = error
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            close_error = error
    if first is not None:
        if close_error is not None:
            first.metadata_close_failure = close_error
            first.add_note("Secondary metadata close: " + repr(close_error))
        raise first
    if close_error is not None:
        raise close_error
    return b"".join(parts)


def checked(body, row):
    require(len(body) == row["bytes"], "Release extent mismatch")
    require(hashlib.sha256(body).hexdigest() == row["sha256"],
            "Release digest mismatch")


def cleartext(body):
    require(body.startswith(b"-----BEGIN PGP SIGNED MESSAGE-----\n"),
            "Expected APT-authenticated InRelease cleartext")
    start = body.find(b"\n\n")
    end = body.find(b"\n-----BEGIN PGP SIGNATURE-----", start + 2)
    require(start >= 0 and end > start, "Malformed InRelease framing")
    lines = body[start + 2:end].split(b"\n")
    return b"\n".join(line[2:] if line.startswith(b"- ") else line
                      for line in lines) + b"\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--mode", choices=("remote", "apt-cache"), required=True)
    args = parser.parse_args()
    raw = capture(args.lock.absolute(), 1048576)
    lock = json.loads(raw)
    require(lock["schema"] == "neural083_environment_v1", "Lock schema")
    rows = lock["apt"]["release_files"]
    require(len(rows) == 3, "All three selected repositories are required")
    evidence = []
    for row in rows:
        require(type(row["bytes"]) is int and 0 < row["bytes"] <= 1048576,
                "Bounded Release extent")
        require(re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
                "Exact Release SHA256")
        url = row["url"]
        require(url.startswith("https://snapshot.debian.org/archive/"),
                "Selected snapshot service only")
        if args.mode == "remote":
            request = urllib.request.Request(url, headers={
                "User-Agent": "neural083-environment-source-build/1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(row["bytes"] + 1)
            checked(body, row)
            location = url
        else:
            suite = url.rsplit("/", 2)[1]
            require(suite in {"bookworm", "bookworm-updates", "bookworm-security"},
                    "Exact suite")
            matches = list(Path("/var/lib/apt/lists").glob(
                "snapshot.debian.org_archive_*_20250409T000000Z_dists_" +
                suite + "_InRelease"))
            require(len(matches) == 1, "One actual APT index per selected suite")
            path = matches[0]
            body = capture(path, 2097152)
            checked(cleartext(body), row)
            location = str(path)
        evidence.append({"name": row["name"], "sha256": row["sha256"],
                         "bytes": row["bytes"], "location": location})
    print(json.dumps({"schema": "neural083_apt_snapshot_check_v1",
                      "mode": args.mode, "indexes": evidence,
                      "scientific_qualification": False}, sort_keys=True))


if __name__ == "__main__":
    main()
