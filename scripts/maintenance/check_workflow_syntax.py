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
import time
from urllib.error import HTTPError, URLError
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
ACQUISITION_SECONDS = 45
REQUEST_SECONDS = 20
DOWNLOAD_ATTEMPTS = 2
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


class AcquisitionDeadline(TimeoutError):
    """The whole acquisition budget expired, rather than one transport call."""


def transport_timeout(error):
    if isinstance(error, HTTPError):
        return False
    reason = error.reason if isinstance(error, URLError) else error
    # urllib may wrap an alarm exception in URLError. The aggregate deadline
    # must never become another request attempt.
    return isinstance(reason, TimeoutError) and not isinstance(reason, AcquisitionDeadline)


def verify_archive(body, asset):
    require(len(body) == asset["bytes"], "Actionlint archive size mismatch")
    require(hashlib.sha256(body).hexdigest() == asset["sha256"],
            "Actionlint archive SHA256 mismatch")


def download_archive(asset):
    """Worker-only acquisition; the parent bounds even a blocked C resolver."""
    require(0 < asset["bytes"] <= ARCHIVE_LIMIT, "Invalid pinned archive bound")
    url = checked_url(
        f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/{asset['name']}")
    deadline = time.monotonic() + ACQUISITION_SECONDS
    attempt, stage = 0, "request setup"

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise AcquisitionDeadline(
                f"Actionlint acquisition exceeded {ACQUISITION_SECONDS}s "
                f"on attempt {attempt}/{DOWNLOAD_ATTEMPTS} during {stage}")
        return seconds

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        stage = "request open"
        print(f"Actionlint archive attempt {attempt}/{DOWNLOAD_ATTEMPTS}: {stage}",
              file=sys.stderr, flush=True)
        try:
            request = Request(url, headers={"User-Agent": "neurobench-workflow-syntax/1"})
            with build_opener(ReleaseRedirects()).open(
                    request, timeout=min(REQUEST_SECONDS, remaining())) as response:
                stage = "response validation"
                checked_url(response.geturl())
                require(response.status == 200, "Actionlint archive request did not succeed")
                stage = "response read"
                print(f"Actionlint archive attempt {attempt}/{DOWNLOAD_ATTEMPTS}: {stage}",
                      file=sys.stderr, flush=True)
                body = response.read(asset["bytes"] + 1)
            remaining()
            stage = "archive size/SHA256 verification"
            verify_archive(body, asset)
            remaining()
            return body
        except (OSError, ValueError) as error:
            print(f"Actionlint archive attempt {attempt}/{DOWNLOAD_ATTEMPTS} "
                  f"failed during {stage}: {type(error).__name__}: {error}",
                  file=sys.stderr)
            if attempt == DOWNLOAD_ATTEMPTS or not transport_timeout(error):
                raise
            remaining()
            print("Retrying actionlint transport timeout once within the original "
                  f"{ACQUISITION_SECONDS}s acquisition deadline.", file=sys.stderr)


def acquisition_main(name):
    """Private same-script child mode: only a reviewed asset name is admitted."""
    try:
        selected = [asset for asset in ASSETS.values() if asset["name"] == name]
        require(len(selected) == 1, "Exactly one pinned actionlint asset required")
        body = download_archive(selected[0])
        sys.stdout.buffer.write(body)
        return 0
    except (OSError, ValueError) as error:
        print(f"Actionlint archive acquisition failed: {error}", file=sys.stderr)
        return 1


def download(asset):
    # A Python signal handler can be delayed inside a C DNS resolver. Keep
    # acquisition in this same script's dedicated child, whose parent timeout
    # covers both transport attempts, worker imports and binary transfer.
    # OS process creation precedes subprocess.run's communication timeout.
    # subprocess.run kills and waits for the child on timeout. The worker does
    # not launch other processes; there is no parent-side retry.
    require(asset in ASSETS.values(), "Reviewed actionlint asset required")
    command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
               "--download-archive", asset["name"]]
    try:
        completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                   capture_output=True, timeout=ACQUISITION_SECONDS,
                                   check=False)
    except subprocess.TimeoutExpired as error:
        if error.stderr:
            sys.stderr.write(error.stderr.decode("utf-8", errors="replace"))
        raise
    if completed.stderr:
        sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
    require(completed.returncode == 0,
            f"Actionlint archive worker failed with exit code {completed.returncode}")
    verify_archive(completed.stdout, asset)
    return completed.stdout


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
    stage = "platform selection"
    try:
        selected = (platform.system(), platform.machine())
        require(selected in ASSETS,
                "Pinned actionlint assets support Linux x86_64 and macOS arm64")
        stage = "workflow roster"
        paths = workflow_paths()
        stage = "archive acquisition"
        body = download(ASSETS[selected])
        with tempfile.TemporaryDirectory(prefix="neurobench-actionlint-") as scratch:
            stage = "archive extraction"
            binary = extract_binary(body, Path(scratch))
            environment = os.environ.copy()
            environment.update(GOMAXPROCS="1", GOMEMLIMIT="256MiB")
            stage = "lint"
            completed = subprocess.run(
                [str(binary), "-no-color", "-shellcheck=", "-pyflakes=", *map(str, paths)],
                cwd=ROOT, env=environment, timeout=60, check=False,
            )
        if completed.returncode != 0:
            print(f"Workflow syntax check failed during lint: actionlint exited "
                  f"{completed.returncode}", file=sys.stderr)
            return 1
        print(f"actionlint {VERSION}: core syntax and expression checks passed for "
              f"{len(paths)} workflows; no scientific execution.")
        return 0
    except (OSError, ValueError, tarfile.TarError, subprocess.TimeoutExpired) as error:
        print(f"Workflow syntax check failed during {stage}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        raise SystemExit(main())
    if len(sys.argv) == 3 and sys.argv[1] == "--download-archive":
        raise SystemExit(acquisition_main(sys.argv[2]))
    print("Unexpected workflow syntax checker arguments", file=sys.stderr)
    raise SystemExit(2)
