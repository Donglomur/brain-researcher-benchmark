"""Build-time, checksum-pinned NETSEG source staging; verify_staged is offline.

No scientific payload is parsed. No automatic retry, cache search, overwrite, or
runtime fetch. Partial staging and external receipts remain on failure.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MANIFEST_SHA256 = "d0c4f2afdfe9161907fe64d74ab07e85e6162726f5efc0b10ff46cf2ece954f1"
MANIFEST_NAME = "source_manifest.json"
EXPECTED_COUNT = 86
EXPECTED_BYTES = 249626034
MAX_BYTES = 260000000
MAX_SECONDS = 600
MAX_REDIRECTS = 5
CHUNK_BYTES = 1024 * 1024
PROVENANCE_ALIASES = {
    "provenance/processing_README_version2.md": "OSF_README_version2.md",
    "provenance/nilearn_0_12_1_data_notice.rst": "nilearn_0_12_1_datasets__description__development_fmri.rst",
    "provenance/CBIG_LICENSE.md": "cbig_LICENSE.md",
}


class Refusal(RuntimeError):
    """Safe stable diagnostic code, never an untrusted URL or response body."""


def need(condition, code):
    if not condition:
        raise Refusal(code)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith("/") and "\x00" not in raw,
         "absolute_path_required")
    # Check the original spelling BEFORE normalization can erase symlink/.. .
    need(not any(p in (".", "..") for p in raw.split("/")), "path_traversal")
    path, current = Path(raw), Path("/")
    for component in path.parts[1:]:
        current /= component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(mode), "symlink_component")
        if current != path:
            need(stat.S_ISDIR(mode), "non_directory_ancestor")
    return path


def relative_path(value):
    need(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
         "invalid_manifest_path")
    pieces = value.split("/")
    need(all(p not in ("", ".", "..") for p in pieces) and not value.startswith("/"),
         "invalid_manifest_path")
    return PurePosixPath(value)


def disjoint(a, b):
    need(a != b and a not in b.parents and b not in a.parents, "source_destination_overlap")


def publish_no_replace(pending, destination):
    """Linux renameat2 gives atomic publication AND refuses an existing directory."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    result = rename(-100, os.fsencode(pending), -100, os.fsencode(destination), 1)
    if result != 0:
        raise OSError(ctypes.get_errno(), "atomic_publication_refused")


def load_manifest(path=None):
    path = safe_path(path or Path(__file__).absolute().with_name(MANIFEST_NAME))
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_size < 2_000_000, "manifest_type_or_size")
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == MANIFEST_SHA256, "manifest_hash_mismatch")
    manifest = json.loads(body)
    rows = manifest["files"]
    need(len(rows) == EXPECTED_COUNT == manifest["n_files"], "manifest_count")
    seen = set()
    for row in rows:
        relative_path(row["path"])
        need(row["path"] != MANIFEST_NAME and row["path"] not in seen, "duplicate_manifest_path")
        seen.add(row["path"])
        need(type(row["size_bytes"]) is int and row["size_bytes"] > 0, "manifest_size")
        need(re.fullmatch("[a-f0-9]{64}", row["sha256"]) is not None, "manifest_digest")
        if "md5" in row:
            need(re.fullmatch("[a-f0-9]{32}", row["md5"]) is not None, "manifest_md5")
        if "git_blob_sha1" in row:
            need(re.fullmatch("[a-f0-9]{40}", row["git_blob_sha1"]) is not None, "manifest_git_blob")
        endpoint(row["source_url"], row, initial=True)
    need(sum(r["size_bytes"] for r in rows) == EXPECTED_BYTES == manifest["total_bytes"],
         "manifest_total_bytes")
    return manifest, body


def hashers(row):
    git = hashlib.sha1()
    git.update(f"blob {row['size_bytes']}\0".encode("ascii"))
    return {"sha256": hashlib.sha256(), "md5": hashlib.md5(), "git_blob_sha1": git}


def verify_digests(row, hashes, size):
    need(size == row["size_bytes"], "source_size_mismatch")
    for name, digest in hashes.items():
        if name in row:
            need(digest.hexdigest() == row[name], "source_" + name + "_mismatch")


def file_identity(path, row, deadline=None):
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode), "source_not_regular")
    need(before.st_size == row["size_bytes"], "source_size_mismatch")
    hashes, size = hashers(row), 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno())
        need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "source_changed")
        while True:
            if deadline is not None:
                need(time.monotonic() < deadline, "elapsed_cap")
            data = handle.read(CHUNK_BYTES)
            if not data:
                break
            size += len(data)
            need(size <= row["size_bytes"], "source_size_mismatch")
            for h in hashes.values():
                h.update(data)
        after = os.fstat(handle.fileno())
        need((opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) ==
             (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "source_changed")
    verify_digests(row, hashes, size)


def inventory(root, manifest):
    root = safe_path(root)
    need(root.is_dir(), "source_root_not_directory")
    expected = {r["path"] for r in manifest["files"]} | {MANIFEST_NAME}
    directories = {str(p) for name in expected for p in PurePosixPath(name).parents if str(p) != "."}
    found = set()
    for path in root.rglob("*"):
        name, mode = path.relative_to(root).as_posix(), path.lstat().st_mode
        if stat.S_ISDIR(mode):
            need(name in directories, "unexpected_directory")
        else:
            need(stat.S_ISREG(mode), "nonregular_inventory_member")
            need(name in expected, "unexpected_file")
            found.add(name)
    need(found == expected, "missing_source_file")


def verify_staged(data_dir):
    """Authenticate exact original/provenance inventory; no network or parsing."""
    root = safe_path(data_dir)
    manifest, _ = load_manifest(root / MANIFEST_NAME)
    inventory(root, manifest)
    for row in manifest["files"]:
        file_identity(root / row["path"], row)
    return manifest


def endpoint(url, row, initial=False):
    parts = urlsplit(url)
    need(parts.scheme == "https" and parts.username is None and parts.password is None
         and parts.port in (None, 443) and not parts.fragment, "endpoint_rejected")
    host, path = parts.hostname, parts.path
    if initial:
        need(url == row["source_url"], "initial_url_mismatch")
    if "source_guid" in row:
        if host == "osf.io":
            need(path in (f"/download/{row['source_guid']}/", f"/download/{row['source_guid']}"), "osf_path_mismatch")
            need(parse_qs(parts.query).get("revision") == [str(row["source_version"])], "osf_revision_mismatch")
        elif host == "files.osf.io":
            expected = f"/v1/resources/5hju4/providers/osfstorage/{row['osf_object_id']}"
            need(path in (expected, expected + "/"), "waterbutler_path_mismatch")
            need(parse_qs(parts.query).get("revision") == [str(row["source_version"])], "waterbutler_revision_mismatch")
        elif host == "storage.googleapis.com":
            need(path == f"/cos-osf-prod-files-us-east1/{row['sha256']}", "storage_object_mismatch")
        else:
            raise Refusal("endpoint_rejected")
    else:
        need(host == "raw.githubusercontent.com" and url == row["source_url"] and not parts.query,
             "immutable_github_endpoint_required")
        need(re.fullmatch("[a-f0-9]{40}", row["source_commit"]) is not None and
             row["source_commit"] in path.split("/"), "immutable_commit_required")
    return {"host": host, "path": path}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_once(url, timeout):
    request = Request(url, method="GET", headers={"Accept-Encoding": "identity", "User-Agent": "NETSEG-pinned-source-stager"})
    try:
        return build_opener(NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc:
        return exc


def transfer(row, target, state, deadline, local=None, transport=None):
    """Stream and authenticate once. A failed .partial remains for inspection."""
    response, input_handle = None, None
    hashes, size = hashers(row), 0
    partial = target.with_name(target.name + ".partial")
    state.update(phase="copy" if local is not None else "download", current_record_path=row["path"])
    try:
        if local is not None:
            local = safe_path(local)
            original = local.lstat()
            need(stat.S_ISREG(original.st_mode) and original.st_size == row["size_bytes"], "local_type_or_size")
            input_handle = os.fdopen(os.open(local, os.O_RDONLY | os.O_NOFOLLOW), "rb")
            before = os.fstat(input_handle.fileno())
            need((before.st_dev, before.st_ino) == (original.st_dev, original.st_ino), "source_changed")
        else:
            url, seen = row["source_url"], set()
            for hop in range(MAX_REDIRECTS + 1):
                need(time.monotonic() < deadline, "elapsed_cap")
                safe = endpoint(url, row, initial=hop == 0)
                need(url not in seen, "redirect_loop")
                seen.add(url)
                state["requests"] += 1
                state["last_endpoint"] = safe
                response = (transport or open_once)(url, min(30, deadline - time.monotonic()))
                code = int(response.code)
                state["http_status"] = code
                need(sum(len(str(k)) + len(str(v)) for k, v in response.headers.items()) <= 65536, "headers_cap")
                if code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    response.close()
                    response = None
                    need(hop < MAX_REDIRECTS and isinstance(location, str) and location, "redirect_cap_or_location")
                    url = urljoin(url, location)
                    continue
                need(code == 200 and safe["host"] != "osf.io", "http_status_or_terminal_host")
                length = response.headers.get("Content-Length")
                need(length is not None and length.isdigit() and int(length) == row["size_bytes"], "content_length_mismatch")
                need(response.headers.get("Content-Encoding", "identity").lower() == "identity", "content_encoding_rejected")
                input_handle = response
                break
        need(input_handle is not None, "missing_input")
        # HTTPResponse.read(n) can keep filling n bytes while a peer drips data;
        # read1 returns after one underlying read, allowing deadline checks.
        read_chunk = input_handle.read if local is not None else input_handle.read1
        target.parent.mkdir(parents=True, exist_ok=True)
        with partial.open("xb") as output:
            while True:
                need(time.monotonic() < deadline, "elapsed_cap")
                data = read_chunk(min(CHUNK_BYTES, row["size_bytes"] - size + 1))
                if not data:
                    break
                size += len(data)
                state["body_bytes"] += len(data)
                need(state["body_bytes"] <= MAX_BYTES, "aggregate_byte_cap")
                need(size <= row["size_bytes"], "body_size_exceeded")
                output.write(data)
                for h in hashes.values():
                    h.update(data)
            need(time.monotonic() < deadline, "elapsed_cap")
            output.flush()
            os.fsync(output.fileno())
        if local is not None:
            after = os.fstat(input_handle.fileno())
            need((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                 (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "source_changed")
        verify_digests(row, hashes, size)
        os.chmod(partial, 0o444)
        os.link(partial, target)  # Atomic no-replace, unlike rename over an existing file.
        partial.unlink()
        state["files_verified"] += 1
    finally:
        if input_handle is not None:
            input_handle.close()
        elif response is not None:
            response.close()


def stage(destination, source_root=None, provenance_root=None, manifest_path=None, transport=None):
    started = time.monotonic()
    state = {"status": "running", "phase": "preflight", "files_verified": 0,
             "body_bytes": 0, "requests": 0, "automatic_retries": 0,
             "source_manifest_sha256": MANIFEST_SHA256}
    receipt = None
    try:
        dest = safe_path(destination)
        need(dest != Path("/") and dest.parent.is_dir(), "destination_parent_required")
        manifest, body = load_manifest(manifest_path)
        source = safe_path(source_root) if source_root is not None else None
        provenance = safe_path(provenance_root) if provenance_root is not None else None
        need(provenance is None or source is not None, "provenance_requires_local_source")
        for root in (source, provenance):
            if root is not None:
                need(root.is_dir(), "local_source_not_directory")
                disjoint(dest, root)
        if dest.exists():
            verify_staged(dest)
            state.update(status="verified_existing", phase="complete", files_verified=len(manifest["files"]))
            return state
        receipt = dest.with_name(dest.name + ".staging_receipt.json")
        safe_path(receipt)
        need(not receipt.exists(), "existing_staging_receipt")
        pending = Path(tempfile.mkdtemp(prefix=dest.name + ".partial-", dir=dest.parent))
        state["pending_directory"] = str(pending)
        os.chmod(pending, 0o755)
        deadline = started + MAX_SECONDS
        for row in manifest["files"]:
            local = None
            if source is not None:
                local = (provenance / PROVENANCE_ALIASES[row["path"]]
                         if provenance is not None and row["path"] in PROVENANCE_ALIASES
                         else source / row["path"])
            transfer(row, pending / row["path"], state, deadline, local, transport)
        with (pending / MANIFEST_NAME).open("xb") as handle:
            handle.write(body)
        os.chmod(pending / MANIFEST_NAME, 0o444)
        state["phase"] = "final_verification"
        inventory(pending, manifest)
        for row in manifest["files"]:
            file_identity(pending / row["path"], row, deadline)
        publish_no_replace(pending, dest)
        state.update(status="ok", phase="complete")
        return state
    except Exception as exc:
        state.update(status="failed", error_type=type(exc).__name__,
                     error_code=str(exc) if isinstance(exc, Refusal) else "transport_or_io_error")
        raise
    finally:
        state["elapsed_seconds"] = time.monotonic() - started
        if receipt is not None and not receipt.exists():
            with receipt.open("x") as handle:
                json.dump(state, handle, indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
        print(json.dumps(state, sort_keys=True, allow_nan=False), file=sys.stderr if state["status"] == "failed" else sys.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default="/app/data/netseg")
    parser.add_argument("--source-root")
    parser.add_argument("--provenance-root")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()
    started_stage = False
    previous_handler = signal.getsignal(signal.SIGALRM)
    def hard_deadline(signum, frame):
        raise Refusal("elapsed_cap")
    try:
        # The portable Ubuntu CLI runs in the main thread. Interrupt even blocked
        # network I/O at the total cap; partials/receipt are handled by stage().
        signal.signal(signal.SIGALRM, hard_deadline)
        signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
        # Reject invalid source relationships before even creating an empty parent.
        dest = safe_path(args.destination)
        for value in (args.source_root, args.provenance_root):
            if value is not None:
                disjoint(dest, safe_path(value))
        dest.parent.mkdir(parents=True, exist_ok=True)
        started_stage = True
        stage(args.destination, args.source_root, args.provenance_root, args.manifest)
        return 0
    except Exception as exc:
        if not started_stage:
            print(json.dumps({"status": "failed", "phase": "cli_preflight", "error_type": type(exc).__name__,
                              "error_code": str(exc) if isinstance(exc, Refusal) else "local_io_error"}), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
