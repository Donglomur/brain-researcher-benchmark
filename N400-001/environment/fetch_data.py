"""Build-time-only exact OSF source staging. Runtime verification never fetches."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MANIFEST_NAME = "data_manifest.json"
MANIFEST_PATH = Path(__file__).with_name(MANIFEST_NAME)
MANIFEST_SHA256 = "09483405a6b48aec79d9e40c96409709a7e0c4e462cb0deb646551fe6cfb2616"
HOSTS = {"osf.io", "files.osf.io", "files.us.osf.io", "storage.googleapis.com"}
SAFE_HEADERS = {"content-length", "content-type", "content-encoding", "etag", "last-modified", "date", "x-goog-generation", "x-goog-hash", "x-goog-stored-content-length"}

def validate_entry(entry):
    if entry["version"] != 1 or not re.fullmatch(r"[0-9a-f]{24}", entry["file_id"]):
        raise ValueError("Invalid original file/version identity")
    ext = entry["name"].rsplit(".", 1)[-1]
    if entry["name"] != f"{entry['subject']}_N400_shifted_ds.{ext}" or ext not in ("set", "fdt"):
        raise ValueError("Unsafe or nonoriginal basename")
    if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) or not re.fullmatch(r"[0-9a-f]{32}", entry["md5"]):
        raise ValueError("Missing published source digest")
    if not isinstance(entry["size_bytes"], int) or entry["size_bytes"] <= 0:
        raise ValueError("Invalid exact source size")
    validate_url(entry["download_url"], entry, first=True)


def public_endpoint(url):
    parsed = urllib.parse.urlsplit(url)
    return {"scheme": parsed.scheme, "hostname": parsed.hostname, "path": parsed.path,
            "query_parameter_names": sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True))}


def safe_headers(headers):
    return {k.lower(): str(v) for k, v in headers.items() if k.lower() in SAFE_HEADERS}


def validate_url(url, entry, first=False, previous=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment:
        raise ValueError("Unapproved source transport endpoint")
    if first:
        if parsed.hostname != "osf.io" or url != entry["download_url"] or urllib.parse.parse_qs(parsed.query).get("revision") != ["1"]:
            raise ValueError("Acquisition must start at the exact captured OSF version URL")
        return
    if parsed.hostname == "osf.io":
        original = urllib.parse.urlsplit(entry["download_url"])
        if parsed.path.rstrip("/") != original.path.rstrip("/") or urllib.parse.parse_qs(parsed.query).get("revision") != ["1"]:
            raise ValueError("Unexpected OSF source alias/version redirect")
    elif parsed.hostname in {"files.osf.io", "files.us.osf.io"}:
        path = f"/v1/resources/29xpq/providers/osfstorage/{entry['file_id']}"
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path.rstrip("/") != path or query.get("version", query.get("revision")) != ["1"]:
            raise ValueError("Unexpected OSF file/node/version redirect")
    else:
        if parsed.path != "/cos-osf-prod-files-us-east1/" + entry["sha256"]:
            raise ValueError("Unapproved Google storage object")
        if previous is None or urllib.parse.urlsplit(previous).hostname not in {"files.osf.io", "files.us.osf.io"}:
            raise ValueError("Storage URL must come directly from the observed official OSF redirect")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def no_symlink(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Symlinked source/destination component")
    return path


def save_new(path, obj):
    with Path(path).open("x") as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write("\n")


def verify_file(path, entry):
    path = no_symlink(path)
    if not path.is_file() or path.stat().st_size != entry["size_bytes"]:
        raise ValueError("Exact source size mismatch")
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            sha.update(chunk)
            md5.update(chunk)
    if sha.hexdigest() != entry["sha256"] or md5.hexdigest() != entry["md5"]:
        raise ValueError("Original source checksum mismatch")


def transfer_file(entry, destination, ledger, budget, opener=None):
    """Exactly one attempt; preserve partial and sanitized evidence on failure."""
    validate_entry(entry)
    destination = no_symlink(destination)
    target = destination / entry["name"]
    partial = destination / (entry["name"] + ".partial")
    if target.exists() or target.is_symlink() or partial.exists() or partial.is_symlink():
        raise FileExistsError("Preserve existing source evidence")
    opener = opener or urllib.request.build_opener(NoRedirect())
    row = {"subject": entry["subject"], "name": entry["name"], "file_id": entry["file_id"], "version": 1,
           "expected_bytes": entry["size_bytes"], "expected_sha256": entry["sha256"], "expected_md5": entry["md5"],
           "redirect_chain": [], "measured_bytes": 0, "status": "in_progress"}
    ledger.append(row)
    url, previous = entry["download_url"], None
    sha, md5 = hashlib.sha256(), hashlib.md5()
    try:
        for hop in range(6):
            validate_url(url, entry, first=hop == 0, previous=previous)
            request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"}, method="GET")
            try:
                response = opener.open(request, timeout=min(30, max(0.1, budget["deadline"] - time.monotonic())))
            except urllib.error.HTTPError as error:
                response = error
            with response:
                step = {"endpoint": public_endpoint(url), "status": response.code,
                        "safe_headers": safe_headers(response.headers)}
                row["redirect_chain"].append(step)
                if response.code in {301, 302, 303, 307, 308}:
                    newurl = urllib.parse.urljoin(url, response.headers.get("Location", ""))
                    # Validation precedes any request to the next host. No redirect body read.
                    step["redirect_endpoint"] = public_endpoint(newurl)
                    validate_url(newurl, entry, previous=url)
                    previous, url = url, newurl
                    continue
                if response.code != 200:
                    raise ValueError("Original full source response is not HTTP200")
                if response.headers.get("Content-Encoding", "identity").lower() not in ("identity", ""):
                    raise ValueError("Unexpected transfer content encoding")
                if int(response.headers.get("Content-Length", "-1")) != entry["size_bytes"]:
                    raise ValueError("Original response exact length mismatch")
                with partial.open("xb") as stream:
                    while True:
                        if time.monotonic() >= budget["deadline"]:
                            raise TimeoutError("Approved source acquisition deadline reached")
                        remaining = budget["cap"] - budget["used"]
                        if remaining <= 0:
                            raise ValueError("Approved aggregate source body cap reached")
                        # Read at most expected bytes+one sentinel, never trust headers alone.
                        limit = min(1048576, remaining, entry["size_bytes"] - row["measured_bytes"] + 1)
                        chunk = response.read(limit)
                        if not chunk:
                            break
                        budget["used"] += len(chunk)
                        row["measured_bytes"] += len(chunk)
                        stream.write(chunk)
                        sha.update(chunk)
                        md5.update(chunk)
                        if row["measured_bytes"] > entry["size_bytes"]:
                            raise ValueError("Original response body exceeds pinned length")
                if row["measured_bytes"] != entry["size_bytes"] or sha.hexdigest() != entry["sha256"] or md5.hexdigest() != entry["md5"]:
                    raise ValueError("Original response length or checksum mismatch")
                partial.rename(target)
                row.update(status="verified", measured_sha256=sha.hexdigest(), measured_md5=md5.hexdigest())
                return row
        raise ValueError("Source redirect limit exceeded")
    except BaseException as exc:
        row.update(status="failed", error_type=type(exc).__name__,
                   measured_sha256=sha.hexdigest(), measured_md5=md5.hexdigest(),
                   partial_preserved=partial.exists())
        # Never interpolate an upstream HTTP exception containing a signed URL.
        raise RuntimeError(f"Acquisition failed for {entry['name']}; sanitized receipt retained ({type(exc).__name__})") from None



def read_manifest(path=MANIFEST_PATH):
    path = no_symlink(path)
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("Missing or oversized manifest")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Frozen source manifest checksum mismatch; no pin refresh")
    manifest = json.loads(raw)
    entries = manifest["files"]
    if manifest["dataset_id"] != "erp-core-n400" or manifest["osf_node"] != "29xpq" or manifest["file_version"] != 1:
        raise ValueError("Wrong original source identity")
    if len(entries) != 24 or {(e["subject"], e["role"]) for e in entries} != {(s, r) for s in range(1, 13) for r in ("set", "fdt")}:
        raise ValueError("Expected exactly twelve original SET/FDT pairs")
    for entry in entries:
        validate_entry(entry)
        if entry["path"] != entry["name"] or entry["role"] != entry["name"].rsplit(".", 1)[1]:
            raise ValueError("Unsafe or mismatched original file path/role")
    if len({e["file_id"] for e in entries}) != 24 or len({e["path"] for e in entries}) != 24:
        raise ValueError("Duplicate original source identity")
    if manifest["acquisition_limits"] != {"total_body_bytes": 220000000, "timeout_seconds": 600, "concurrent_requests": 1, "automatic_retries": 0}:
        raise ValueError("Source resource/retry contract changed")
    if sum(e["size_bytes"] for e in entries) > 220000000:
        raise ValueError("Source inventory exceeds approved byte budget")
    return manifest, raw


def verify_staged(data_dir):
    root = no_symlink(data_dir)
    manifest, _ = read_manifest(root / MANIFEST_NAME)
    names = {MANIFEST_NAME, *(entry["path"] for entry in manifest["files"])}
    if {path.name for path in root.iterdir()} != names:
        raise ValueError("Runtime source inventory must contain exactly24originals and manifest")
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Nonregular or symlinked source file")
    for entry in manifest["files"]:
        verify_file(root / entry["path"], entry)
    return manifest


def stage_data(destination, source_root=None, manifest_path=MANIFEST_PATH, receipt_path=None):
    manifest, raw_manifest = read_manifest(manifest_path)
    destination = no_symlink(destination)
    if destination.exists():
        verify_staged(destination)
        return {"status": "existing_verified", "scientific_processing": False}
    if source_root is not None:
        source_root = no_symlink(source_root)
        if not source_root.is_dir():
            raise ValueError("Missing local original source")
    receipt_path = no_symlink(receipt_path or destination.with_name(destination.name + "_staging_receipt.json"))
    if destination in receipt_path.parents or receipt_path == destination or receipt_path.exists():
        raise ValueError("New staging receipt must remain outside runtime data directory")
    destination.mkdir(parents=True)
    started = time.monotonic()
    limits = manifest["acquisition_limits"]
    budget = {"used": 0, "cap": limits["total_body_bytes"], "deadline": started + limits["timeout_seconds"]}
    receipt = {"status": "in_progress", "mode": "local_verified_copy" if source_root else "build_time_download",
               "source_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(), "files": [],
               "automatic_retries": 0, "scientific_processing": False}
    def expire(signum, frame):
        raise TimeoutError("Approved source staging deadline reached")
    previous = signal.signal(signal.SIGALRM, expire)
    signal.alarm(limits["timeout_seconds"])
    try:
        for entry in manifest["files"]:
            if source_root is None:
                transfer_file(entry, destination, receipt["files"], budget)
            else:
                origin = source_root / entry["path"]
                verify_file(origin, entry)
                partial = destination / (entry["path"] + ".partial")
                sha, md5 = hashlib.sha256(), hashlib.md5()
                count = 0
                with origin.open("rb") as source, partial.open("xb") as target:
                    for chunk in iter(lambda: source.read(1048576), b""):
                        if time.monotonic() >= budget["deadline"]:
                            raise TimeoutError("Approved source staging deadline reached")
                        target.write(chunk)
                        sha.update(chunk)
                        md5.update(chunk)
                        count += len(chunk)
                if count != entry["size_bytes"] or sha.hexdigest() != entry["sha256"] or md5.hexdigest() != entry["md5"]:
                    raise ValueError("Local source changed during verified copy")
                partial.rename(destination / entry["path"])
                receipt["files"].append({"path": entry["path"], "file_id": entry["file_id"], "version": 1,
                                         "size_bytes": count, "sha256": sha.hexdigest(), "md5": md5.hexdigest(), "status": "verified"})
        with (destination / MANIFEST_NAME).open("xb") as stream:
            stream.write(raw_manifest)
        verify_staged(destination)
        receipt["status"] = "verified"
    except BaseException as exc:
        receipt.update(status="failed", error_type=type(exc).__name__)
        raise RuntimeError("Source staging failed; original evidence and sanitized receipt preserved") from None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        receipt.update(body_bytes=budget["used"], elapsed_seconds=time.monotonic() - started)
        save_new(receipt_path, receipt)
        if receipt["status"] == "failed":
            # BuildKit discards a failed layer, so retain the safe diagnostic in
            # stderr too. Never emit upstream exception strings/signed queries.
            diagnostic = {"status": "failed", "error_type": receipt.get("error_type"),
                          "body_bytes": budget["used"], "files": []}
            for row in receipt["files"]:
                diagnostic["files"].append({key: row[key] for key in
                    ("name", "path", "status", "error_type", "measured_bytes", "redirect_chain") if key in row})
            print(json.dumps(diagnostic, allow_nan=False), file=sys.stderr, flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/erpcore_n400"))
    parser.add_argument("--source-root", type=Path, help="Verified local originals; this mode makes no network request")
    parser.add_argument("--receipt", type=Path, help="New receipt outside runtime source folder")
    args = parser.parse_args()
    result = stage_data(args.destination, args.source_root, receipt_path=args.receipt)
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
