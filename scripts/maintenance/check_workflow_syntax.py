#!/usr/bin/env python3
"""Run SHA256-pinned actionlint core checks before source/package CI jobs.

This is a source lint check, not a benchmark run or scientific qualification.
The temporary download and executable are removed when the command finishes.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.7.12"
# Release tags can move. These exact compressed sizes and SHA256 values bind
# the reviewed assets independently of the tag and are verified before parsing.
ASSETS = {
    ("Linux", "x86_64"): {
        "name": "actionlint_1.7.12_linux_amd64.tar.gz",
        "bytes": 2353908,
        "sha256": "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    },
    ("Darwin", "arm64"): {
        "name": "actionlint_1.7.12_darwin_arm64.tar.gz",
        "bytes": 2164202,
        "sha256": "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    },
}
ARCHIVE_LIMIT = 8 * 1024 * 1024
EXPANDED_LIMIT = 16 * 1024 * 1024
HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
MEMBERS = {
    "LICENSE.txt", "README.md", "docs/README.md", "docs/api.md",
    "docs/checks.md", "docs/config.md", "docs/install.md", "docs/reference.md",
    "docs/usage.md", "man/actionlint.1", "actionlint",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_url(url):
    parts = urlsplit(url)
    require(parts.scheme == "https" and parts.hostname in HOSTS
            and parts.port in (None, 443) and parts.username is None
            and parts.password is None, "Unexpected actionlint release URL")
    return url


class ReleaseRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        checked_url(new_url)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def download(asset):
    require(0 < asset["bytes"] <= ARCHIVE_LIMIT, "Invalid pinned archive bound")
    url = checked_url(
        f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/{asset['name']}")
    request = Request(url, headers={"User-Agent": "neurobench-workflow-syntax/1"})
    with build_opener(ReleaseRedirects()).open(request, timeout=30) as response:
        checked_url(response.geturl())
        require(response.status == 200, "Actionlint archive request did not succeed")
        body = response.read(asset["bytes"] + 1)
    require(len(body) == asset["bytes"], "Actionlint archive size mismatch")
    require(hashlib.sha256(body).hexdigest() == asset["sha256"],
            "Actionlint archive SHA256 mismatch")
    return body


def extract_binary(body, directory):
    # Stream the authenticated tar; never use extract/extractall or restore its
    # permissions. Every member must be an expected, unique ordinary file.
    seen, total, binary = set(), 0, None
    with tarfile.open(fileobj=io.BytesIO(body), mode="r|gz") as archive:
        for member in archive:
            name = member.name
            require(member.isfile() and name in MEMBERS and name not in seen
                    and PurePosixPath(name).as_posix() == name
                    and not PurePosixPath(name).is_absolute()
                    and ".." not in PurePosixPath(name).parts,
                    "Unexpected, duplicate, or nonregular actionlint archive member")
            require(member.size >= 0, "Invalid actionlint member size")
            total += member.size
            require(total <= EXPANDED_LIMIT, "Actionlint expansion bound exceeded")
            seen.add(name)
            if name == "actionlint":
                with archive.extractfile(member) as handle:
                    binary = handle.read(member.size + 1)
                require(len(binary) == member.size and binary,
                        "Actionlint executable extent mismatch")
    require(seen == MEMBERS and binary is not None, "Incomplete actionlint archive")
    destination = directory / "actionlint"
    with destination.open("xb") as handle:
        handle.write(binary)
    destination.chmod(0o700)
    return destination


def workflow_paths():
    directory = ROOT / ".github/workflows"
    require(directory.is_dir() and not directory.is_symlink(),
            "Ordinary workflow directory required")
    paths = sorted(directory.iterdir())
    require(0 < len(paths) <= 100, "Bounded workflow roster required")
    require(all(p.is_file() and not p.is_symlink() and p.suffix in (".yml", ".yaml")
                for p in paths), "Unexpected workflow member")
    require(sum(p.stat().st_size for p in paths) <= 4 * 1024 * 1024,
            "Workflow source bound exceeded")
    return paths


def main():
    try:
        selected = (platform.system(), platform.machine())
        require(selected in ASSETS,
                "Pinned actionlint assets support Linux x86_64 and macOS arm64")
        paths = workflow_paths()
        body = download(ASSETS[selected])
        with tempfile.TemporaryDirectory(prefix="neurobench-actionlint-") as scratch:
            binary = extract_binary(body, Path(scratch))
            environment = os.environ.copy()
            environment.update(GOMAXPROCS="1", GOMEMLIMIT="256MiB")
            completed = subprocess.run(
                [str(binary), "-no-color", "-shellcheck=", "-pyflakes=", *map(str, paths)],
                cwd=ROOT, env=environment, timeout=60, check=False,
            )
        if completed.returncode != 0:
            return 1
        print(f"actionlint {VERSION}: core syntax and expression checks passed for "
              f"{len(paths)} workflows; no scientific execution.")
        return 0
    except (OSError, ValueError, tarfile.TarError, subprocess.TimeoutExpired) as error:
        print(f"Workflow syntax check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
