"""Verify the exact Debian index inputs used by a future image build.

This does not install packages or authorize a benchmark run. APT still verifies
the Debian signatures; this additionally binds the cleartext index to the lock.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import urllib.request


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


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
    raw = args.lock.read_bytes()
    require(len(raw) <= 1048576, "Bounded environment lock")
    lock = json.loads(raw)
    require(lock["schema"] == "find032_environment_inputs_v1", "Lock schema")
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
                "User-Agent": "find032-environment-source-build/1"})
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
            before = path.lstat()
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    before.st_size <= 2097152, "Bounded ordinary APT metadata")
            body = path.read_bytes()
            after = path.lstat()
            require((before.st_dev, before.st_ino, before.st_size,
                     before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size,
                     after.st_mtime_ns, after.st_ctime_ns), "Stable APT metadata")
            checked(cleartext(body), row)
            location = str(path)
        evidence.append({"name": row["name"], "sha256": row["sha256"],
                         "bytes": row["bytes"], "location": location})
    print(json.dumps({"schema": "find032_apt_snapshot_check_v1",
                      "mode": args.mode, "indexes": evidence,
                      "scientific_qualification": False}, sort_keys=True))


if __name__ == "__main__":
    main()
