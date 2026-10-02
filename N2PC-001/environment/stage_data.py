"""Portable integrity-only staging of the fixed24 ERP CORE N2pc originals.

Offline verification and explicit local-copy/build-time-fetch modes. No source
parser, answer cache, host-cache discovery, retry, resume, or import-time IO.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import threading
import time
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MANIFEST_SHA256 = "ada7a37ede5c498063d324bc9d5c254b457c5aecab9d41c622c66c38a8e21541"
METADATA_SHA256 = "5628aac47c1dc46a2e555abeeab558cb07bb5c17401e02247fc3637390e4b804"
MANIFEST = Path(__file__).with_name("source_manifest.json")
NOTICE = Path(__file__).with_name("SOURCE_NOTICE.md")
NOTICE_SHA256 = "6cc59f632b1fd5868fd3abc99ef2bb28f32b92c861198759a56577550305628e"
DEFAULT_DESTINATION = Path("/app/data/n2pc")
SUBJECTS = (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
TOTAL_BYTES = 1_051_981_416
REQUEST_HEADERS = {"Accept-Encoding": "identity", "User-Agent": "N2PC-fixed-originals/1.0"}


@dataclass(frozen=True)
class Limits:
    payload_cap: int = TOTAL_BYTES + 24
    wall_seconds: float = 900
    socket_seconds: float = 30
    workers: int = 2
    chunk_bytes: int = 65536
    max_redirects: int = 5
    disk_reserve: int = 5 * 1024**3


class CaptureError(ValueError):
    """Only fixed error codes are placed in receipts, never transport secrets."""


def need(condition, code):
    if not condition:
        raise CaptureError(code)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith("/") and "\0" not in raw, "absolute_path_required")
    need(not any(p in (".", "..") for p in raw.split("/")), "path_traversal")
    path = Path(raw)
    for part in (*reversed(path.parents), path):
        if os.path.lexists(part):
            mode = part.lstat().st_mode
            need(not stat.S_ISLNK(mode), "symlink_path")
            if part != path: need(stat.S_ISDIR(mode), "non_directory_ancestor")
    return path


def write_bytes(path, raw):
    path = safe_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)


def write_json(path, value):
    write_bytes(path, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def strict_json(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            need(k not in result, "duplicate_json_key"); result[k] = v
        return result
    def invalid(_): raise CaptureError("nonfinite_json")
    result = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    def finite(v):
        if isinstance(v, float): need(math.isfinite(v), "nonfinite_json")
        elif isinstance(v, dict):
            for x in v.values(): finite(x)
        elif isinstance(v, list):
            for x in v: finite(x)
    finite(result)
    return result


def safe_url(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.hostname or "", p.path, "", ""))


def failure_details(error):
    """Preserve diagnostic HTTP identity without reading or logging error bodies."""
    result = dict(error_type=type(error).__name__,
                  error_code=str(error) if isinstance(error, CaptureError) else "transport_or_local_io_failure")
    if isinstance(error, HTTPError):
        result["error_code"] = "http_error"
        result["http_status"] = error.code if type(error.code) is int else None
        try:
            result["http_error_url_without_query"] = safe_url(error.geturl())
        except (TypeError, ValueError):
            result["http_error_url_without_query"] = None
        result["http_error_body_read"] = False
        try:
            error.close()
            result["http_error_body_closed"] = True
        except Exception as close_error:
            result["http_error_body_closed"] = False
            result["http_error_close_error_type"] = type(close_error).__name__
    return result


def allowed_url(url, entry):
    need(isinstance(url, str) and len(url) <= 8192 and not any(ord(c) < 32 for c in url), "invalid_url")
    p = urlsplit(url)
    need(p.scheme == "https" and p.username is None and p.password is None
         and p.port in (None, 443) and not p.fragment, "https_url_required")
    if p.hostname == "osf.io":
        locator = urlsplit(entry["download_url"]).path.rstrip("/").split("/")[-1]
        ids = (locator, entry["object_id"])
        need(p.path.rstrip("/") in {v for i in ids for v in (f"/download/{i}", f"/{i}/download")}, "osf_object_path")
        need(parse_qs(p.query, strict_parsing=True) in ({"revision": ["1"]}, {"version": ["1"]}), "osf_revision")
    elif p.hostname == "files.osf.io":
        need(p.path.rstrip("/") == f"/v1/resources/yefrq/providers/osfstorage/{entry['object_id']}", "osfstorage_object_path")
        query = parse_qs(p.query, keep_blank_values=True)
        for key in ("revision", "version"):
            if key in query: need(query[key] == ["1"], "osfstorage_revision")
    elif p.hostname == "storage.googleapis.com":
        need(p.path == "/cos-osf-prod-files-us-east1/" + entry["sha256"], "gcs_digest_object_path")
    else:
        raise CaptureError("redirect_host_refused")
    return url


def validate_manifest(doc):
    need(doc["osf_node"] == "yefrq" and doc["subjects"] == list(SUBJECTS), "cohort_identity")
    rows = doc["files"]
    need(len(rows) == doc["n_original_files"] == 24, "source_count")
    need({(r["subject"], r["role"]) for r in rows} == {(s, e) for s in SUBJECTS for e in ("set", "fdt")}, "subject_role_coverage")
    need(len({r["path"] for r in rows}) == len({r["object_id"] for r in rows}) == 24, "duplicate_source_identity")
    for row in rows:
        need(type(row["subject"]) is int and row["path"] == f"sub-{row['subject']:03d}_task-N2pc_eeg.{row['role']}", "original_path")
        need(re.fullmatch(r"[0-9a-f]{24}", row["object_id"]) is not None, "object_id")
        need(type(row["version"]) is int and row["version"] == 1 and row["node"] == "yefrq", "source_version")
        need(type(row["size_bytes"]) is int and row["size_bytes"] > 0, "source_size")
        for key, width in (("sha256", 64), ("md5", 32)):
            need(re.fullmatch(rf"[0-9a-f]{{{width}}}", row[key]) is not None, "source_digest")
        need(row["content_type"] == "application/octet-stream", "source_content_type")
        need(urlsplit(row["download_url"]).netloc == "osf.io", "initial_source_host")
        allowed_url(row["download_url"], row)
    need(sum(r["size_bytes"] for r in rows) == doc["total_original_bytes"], "source_total")
    return doc


def load_manifest(path):
    path = safe_path(path)
    need(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= 65536, "manifest_regular_bounded")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        raw = stream.read(65537)
    need(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, "manifest_sha256")
    doc = validate_manifest(strict_json(raw))
    need(doc["total_original_bytes"] == TOTAL_BYTES and doc["source_metadata_ledger_sha256"] == METADATA_SHA256, "frozen_metadata_identity")
    return doc, raw


@contextmanager
def hard_timeout(seconds):
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "existing_timer")
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_): raise CaptureError("wall_deadline")
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous)


class State:
    def __init__(self, root, limits, clock=time.monotonic):
        self.root, self.limits, self.clock = root, limits, clock
        self.started = clock(); self.received = self.reserved = 0
        self.starts = set(); self.lock = threading.Lock(); self.stop = threading.Event()

    def check(self, *, network=False):
        need(not self.stop.is_set(), "capture_cancelled")
        left = self.limits.wall_seconds - (self.clock() - self.started)
        # Quiesce new socket activity before the hard wall deadline.
        need(left > (self.limits.socket_seconds + 2 if network else 0), "wall_deadline")
        return left

    def start(self, oid):
        with self.lock:
            self.check(network=True)
            need(oid not in self.starts and len(self.starts) < 24, "duplicate_or_excess_start")
            self.starts.add(oid)

    def read(self, response, requested):
        with self.lock:
            self.check(network=True)
            n = min(requested, self.limits.payload_cap - self.received - self.reserved)
            need(n > 0, "aggregate_payload_cap"); self.reserved += n
        try:
            data = getattr(response, "read1", response.read)(n)
        except BaseException:
            with self.lock: self.reserved -= n
            raise
        with self.lock:
            self.reserved -= n
            need(isinstance(data, bytes), "invalid_body_type")
            self.received += len(data)
            need(len(data) <= n and self.received <= self.limits.payload_cap, "body_exceeds_read_budget")
        self.check()
        return data


class Redirects(HTTPRedirectHandler):
    def __init__(self, entry, state, ledger):
        self.entry, self.state, self.ledger = entry, state, ledger

    def http_error_302(self, req, fp, code, msg, headers):
        try:
            self.state.check(network=True)
            need(len(self.ledger) < self.state.limits.max_redirects, "redirect_cap")
            values = headers.get_all("Location", [])
            need(len(values) == 1, "redirect_location")
            candidate = urljoin(req.full_url, values[0])
            row = dict(status_code=code, source=safe_url(req.full_url), destination=safe_url(candidate), allowed=False)
            self.ledger.append(row)
            allowed_url(candidate, self.entry); row["allowed"] = True
        finally:
            fp.close()  # urllib's default redirect path reads the body; this does not.
        # A live opener injects Host into req's unredirected headers. Never carry
        # it (or cookies/auth/body headers) across the OSF -> storage host change.
        return self.parent.open(Request(candidate, headers=REQUEST_HEADERS), timeout=self.state.limits.socket_seconds)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def download_one(entry, state, opener_factory=None):
    state.start(entry["object_id"])
    target = state.root / "originals" / entry["path"]
    partial = target.with_name(target.name + ".partial")
    record = dict(path=entry["path"], object_id=entry["object_id"], version=1, status="started", attempts=1, redirects=[], received_bytes=0)
    sha, md5 = hashlib.sha256(), hashlib.md5()
    try:
        print(json.dumps({"path":entry["path"], "status":"starting", "expected_bytes":entry["size_bytes"]}), flush=True)
        handler = Redirects(entry, state, record["redirects"])
        opener = opener_factory(handler) if opener_factory else build_opener(ProxyHandler({}), handler)
        request = Request(allowed_url(entry["download_url"], entry), headers=REQUEST_HEADERS)
        with partial.open("xb") as stream:
            with opener.open(request, timeout=state.limits.socket_seconds) as response:
                need(response.status == 200, "full_object_http200_required")
                allowed_url(response.geturl(), entry)
                record["final_url_without_query"] = safe_url(response.geturl())
                headers = response.headers
                lengths = headers.get_all("Content-Length", [])
                need(len(lengths) == 1 and re.fullmatch(r"[0-9]{1,18}", lengths[0]) is not None, "content_length_required")
                need(int(lengths[0]) == entry["size_bytes"], "content_length_mismatch")
                need(headers.get("Content-Encoding", "identity").lower() in ("identity", ""), "encoded_source_body")
                need(headers.get("Content-Type", "").split(";", 1)[0].strip().lower() == entry["content_type"], "source_content_type_mismatch")
                record["safe_headers"] = {k: headers[k] for k in ("Content-Length", "Content-Type", "Content-Encoding", "ETag", "Last-Modified") if k in headers}
                while True:
                    chunk = state.read(response, min(state.limits.chunk_bytes, entry["size_bytes"] - record["received_bytes"] + 1))
                    if not chunk: break
                    stream.write(chunk); sha.update(chunk); md5.update(chunk)
                    record["received_bytes"] += len(chunk)
                    need(record["received_bytes"] <= entry["size_bytes"], "source_body_too_long")
            record.update(sha256=sha.hexdigest(), md5=md5.hexdigest())
            need(record["received_bytes"] == entry["size_bytes"], "source_body_truncated")
            need(record["sha256"] == entry["sha256"] and record["md5"] == entry["md5"], "published_digests_mismatch")
        partial.chmod(0o444)
        os.link(partial, target, follow_symlinks=False)  # Atomic no-overwrite publication.
        partial.unlink()  # Successful bytes remain at their exact original basename.
        record["status"] = "verified"
        print(json.dumps({"path": entry["path"], "status": "verified", "bytes": record["received_bytes"]}), flush=True)
        return record
    except BaseException as error:
        state.stop.set()
        record.update(status="failed_preserved", **failure_details(error), sha256=sha.hexdigest(), md5=md5.hexdigest())
        print(json.dumps({"path":entry["path"], "status":"failed_preserved", **failure_details(error)}), flush=True)
        raise
    finally:
        write_json(state.root / "object_receipts" / (entry["path"] + ".json"), record)


def parallel(rows, operation, state):
    results = [None] * len(rows); todo = iter(enumerate(rows))
    with ThreadPoolExecutor(max_workers=state.limits.workers) as pool:
        pending = {}
        try:
            for _ in range(state.limits.workers):
                pair = next(todo, None)
                if pair is not None:
                    index, row = pair; pending[pool.submit(operation, row)] = index
            while pending:
                state.check()
                done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                for future in done: results[pending.pop(future)] = future.result()
                for _ in done:
                    state.check(network=True)
                    pair = next(todo, None)
                    if pair is not None:
                        index, row = pair; pending[pool.submit(operation, row)] = index
        except BaseException:
            state.stop.set()
            for future in pending: future.cancel()
            raise
    return results


def read_notice(path):
    path = safe_path(path)
    need(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= 65536, "notice_regular_bounded")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        raw = stream.read(65537)
    need(hashlib.sha256(raw).hexdigest() == NOTICE_SHA256, "notice_sha256")
    return raw


def exact_inventory(directory, names):
    directory = safe_path(directory)
    need(directory.is_dir(), "source_directory_required")
    paths = list(directory.iterdir())
    need({p.name for p in paths} == set(names)
         and all(stat.S_ISREG(p.lstat().st_mode) for p in paths), "closed_regular_inventory")
    return directory


def hash_original(path, entry, *, copy_to=None, state=None):
    """Stream exact bytes; an optional exclusive copy never changes source inode."""
    path = safe_path(path)
    need(stat.S_ISREG(path.lstat().st_mode), "original_regular_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    sha, md5, received = hashlib.sha256(), hashlib.md5(), 0
    destination = None
    try:
        with os.fdopen(fd, "rb") as stream:
            need(os.fstat(stream.fileno()).st_size == entry["size_bytes"], "original_size_mismatch")
            if copy_to is not None:
                copy_to = safe_path(copy_to)
                destination = os.fdopen(os.open(copy_to, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb")
            while True:
                if state is not None: state.check()
                chunk = stream.read(min(65536, entry["size_bytes"] - received + 1))
                if not chunk: break
                received += len(chunk)
                need(received <= entry["size_bytes"], "original_body_too_long")
                sha.update(chunk); md5.update(chunk)
                if destination is not None: destination.write(chunk)
    finally:
        if destination is not None: destination.close()
    need(received == entry["size_bytes"] and sha.hexdigest() == entry["sha256"]
         and md5.hexdigest() == entry["md5"], "original_hash_mismatch")
    if copy_to is not None: copy_to.chmod(0o444)
    return dict(path=entry["path"], size_bytes=received, sha256=sha.hexdigest(), md5=md5.hexdigest(), status="verified")


def verify_staged(data_dir):
    """No writes, fetches, source decoding or mutable external-helper trust."""
    root = safe_path(data_dir)
    manifest, _ = load_manifest(root / "source_manifest.json")
    read_notice(root / "SOURCE_NOTICE.md")
    exact_inventory(root, [r["path"] for r in manifest["files"]] + ["source_manifest.json", "SOURCE_NOTICE.md"])
    for row in manifest["files"]: hash_original(root / row["path"], row)
    return manifest


def disjoint(left, right):
    need(left != right and left not in right.parents and right not in left.parents, "source_output_overlap")


def stage(destination, *, manifest_path=MANIFEST, notice_path=NOTICE, receipt_dir=None,
          source_dir=None, opener_factory=None, disk_free=None):
    """Local source is authenticated in full before either output root is made."""
    destination = safe_path(destination)
    receipt_dir = safe_path(receipt_dir or destination.with_name(destination.name + "_staging_receipt"))
    manifest_path, notice_path = safe_path(manifest_path), safe_path(notice_path)
    source_dir = safe_path(source_dir) if source_dir is not None else None
    disjoint(destination, receipt_dir)
    for output in (destination, receipt_dir):
        need(not os.path.lexists(output), "fresh_output_required")
        for protected in (manifest_path, notice_path, Path(__file__).resolve().parent):
            disjoint(output, protected)
        if source_dir is not None: disjoint(output, source_dir)
    manifest, raw_manifest = load_manifest(manifest_path)
    raw_notice = read_notice(notice_path)
    names = [r["path"] for r in manifest["files"]]
    limits = Limits()
    anchor = destination.parent
    while not anchor.exists(): anchor = anchor.parent
    free = disk_free(anchor) if disk_free else shutil.disk_usage(anchor).free
    need(free >= manifest["total_original_bytes"] + limits.disk_reserve, "disk_reserve")
    state = State(receipt_dir, limits)
    result = dict(status="incomplete", mode="verified_local_copy" if source_dir else "bounded_public_fetch",
                  source_manifest_sha256=MANIFEST_SHA256, source_notice_sha256=NOTICE_SHA256,
                  original_values_parsed=False, cache_writes=False, retries=0,
                  started_at_utc=datetime.now(timezone.utc).isoformat(), limits=asdict(limits))
    created = False
    try:
        with hard_timeout(limits.wall_seconds):
            if source_dir is not None:
                exact_inventory(source_dir, names)
                for row in manifest["files"]: hash_original(source_dir / row["path"], row, state=state)
            # No parent or output-directory mutation until all local bytes pass.
            receipt_dir.parent.mkdir(parents=True, exist_ok=True)
            receipt_dir.mkdir(mode=0o755); created = True
            write_json(receipt_dir / "attempt.json", result)
            if source_dir is None:
                (receipt_dir / "originals").mkdir(mode=0o755)
                (receipt_dir / "object_receipts").mkdir(mode=0o755)
                parallel(manifest["files"], lambda row: download_one(row, state, opener_factory), state)
                source_dir = receipt_dir / "originals"
                exact_inventory(source_dir, names)
                need(state.received == manifest["total_original_bytes"], "network_byte_total")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.mkdir(mode=0o755)
            result["files"] = [hash_original(source_dir / row["path"], row,
                                  copy_to=destination / row["path"], state=state) for row in manifest["files"]]
            write_bytes(destination / "source_manifest.json", raw_manifest)
            write_bytes(destination / "SOURCE_NOTICE.md", raw_notice)
            for name in ("source_manifest.json", "SOURCE_NOTICE.md"): (destination / name).chmod(0o444)
            verify_staged(destination)
            state.check()
            result.update(status="verified", source_file_count=24, bundle_file_count=26,
                          source_bytes=manifest["total_original_bytes"])
    except BaseException as error:
        state.stop.set()
        result.update(status="failed_preserved", **failure_details(error))
        print(json.dumps({"status":"failed_preserved", **failure_details(error)}), flush=True)
        raise
    finally:
        result.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      wall_seconds=time.monotonic()-state.started, network_body_bytes=state.received,
                      objects_started=len(state.starts))
        if created: write_json(receipt_dir / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--notice", type=Path, default=NOTICE)
    parser.add_argument("--receipt-dir", type=Path)
    args = parser.parse_args(argv)
    if args.verify_existing and (args.source_dir is not None or args.receipt_dir is not None):
        parser.error("verify-existing cannot stage or write receipts")
    try:
        if args.verify_existing:
            manifest = verify_staged(args.destination)
            result = dict(status="verified", mode="offline_read_only", source_file_count=24, bundle_file_count=26,
                          source_bytes=manifest["total_original_bytes"], source_manifest_sha256=MANIFEST_SHA256,
                          source_notice_sha256=NOTICE_SHA256, network_body_bytes=0)
        else:
            result = stage(args.destination, manifest_path=args.manifest, notice_path=args.notice,
                           receipt_dir=args.receipt_dir, source_dir=args.source_dir)
        print(json.dumps({k:v for k,v in result.items() if k != "files"}, allow_nan=False)); return 0
    except BaseException as error:
        print(json.dumps({"status":"failed_preserved", **failure_details(error)})); return 1


if __name__ == "__main__":
    raise SystemExit(main())
