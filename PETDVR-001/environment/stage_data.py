"""Stage only the checksum-pinned PET TAC/source-lineage bundle at image build."""
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MANIFEST_SHA256 = "9ca371309a1a5b5e8ebbc80b5c40d1b766bff666774b9f243f6cc27ca1def6a6"
GIT_COMMIT_SHA = "2b21a6d6e57cf712ec068faf594be4bbf14cdcbe"
GIT_TREE_SHA = "c937d6f6c05c0e7c788190f4962c0393534a7212"
BASE = "https://openneuro.org/crn/datasets/ds001420/snapshots/1.2.0/files/"
DOWNLOAD_TOTAL_TIMEOUT_SECONDS = 180
DIAGNOSTIC = {"phase": "startup", "record_path": None}
SCANS = [(sub, ses) for sub in ("sub-01", "sub-02") for ses in ("ses-baseline", "ses-rescan")]


class SourceHTTPError(RuntimeError):
    def __init__(self, status):
        self.http_status = int(status)
        super().__init__(f"Source HTTP status {self.http_status}")


def expected_files():
    result = {"dataset_description.json": ("dataset_metadata", None, None),
              "README": ("readme", None, None), "CHANGES": ("changelog", None, None)}
    for sub, ses in SCANS:
        stem = f"{sub}_{ses}"
        prefix = f"derivatives/PETPrep1/{sub}/{ses}/pet/"
        for path, role in [(f"{sub}/{ses}/pet/{stem}_pet.json", "pet_metadata"),
            (prefix+f"{stem}_pvc-nopvc_desc-mc_tacs.tsv", "tac"),
            (prefix+f"{stem}_desc-mc_pet.json", "motion_metadata"),
            (prefix+"agtm/mri_gtmpvc.log", "extraction_log"),
            (prefix+"agtm/km.ref.tac.dat", "reference_tac_provenance")]:
            result[path] = (role, sub, ses)
    result["derivatives/PETPrep1/sub-01/ses-baseline/pet/agtm/aux/seg.ctab"] = ("segmentation_labels", "sub-01", "ses-baseline")
    return result


def validate_manifest(manifest):
    if (manifest.get("dataset_id") != "ds001420" or manifest.get("snapshot") != "1.2.0"
            or manifest.get("git_tree_sha1") != GIT_TREE_SHA or manifest.get("git_tag_commit_sha1") != GIT_COMMIT_SHA
            or manifest.get("license") != "CC0"):
        raise ValueError("Manifest must identify the pinned published snapshot and license")
    records = manifest.get("files", [])
    expected = expected_files()
    if len(records) != len(expected) or {r["path"] for r in records} != set(expected):
        raise ValueError("Only the exact 24 original source/lineage files are allowed")
    for record in records:
        role, subject, session = expected[record["path"]]
        if (record["role"], record.get("subject"), record.get("session")) != (role, subject, session):
            raise ValueError("Source role or scan identity mismatch")
        if record["url"] != BASE+record["path"].replace("/", ":"):
            raise ValueError("Only the official pinned snapshot URL is allowed")
        if (type(record["size_bytes"]) is not int or not 0 < record["size_bytes"] < 100_000
                or re.fullmatch("[a-f0-9]{64}", record["sha256"]) is None
                or re.fullmatch("[a-f0-9]{40}", record["git_blob_sha1"]) is None):
            raise ValueError("Invalid source size or checksum")
        kind = record.get("git_entry_kind")
        if kind not in ("direct_text_blob", "annex_symlink"):
            raise ValueError("Unknown Git source identity")
        if kind == "annex_symlink":
            pointer = record["annex_pointer"].encode()
            pointer_hash = hashlib.sha1(f"blob {len(pointer)}\0".encode()+pointer).hexdigest()
            anchor = re.search(rb"MD5E-s(\d+)--([0-9a-f]{32})", pointer)
            if (pointer_hash != record["git_blob_sha1"] or anchor is None
                    or int(anchor[1]) != record["size_bytes"] or anchor[2].decode() != record["annex_md5"]):
                raise ValueError("Published Git-annex pointer does not bind content identity")


def read_manifest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Manifest must be a regular file")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Source manifest SHA256 mismatch; do not silently refresh pins")
    manifest = json.loads(content)
    validate_manifest(manifest)
    return manifest, content


def verify_file(path, record):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source must be a regular file")
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Source size mismatch: {record['path']}")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"Source SHA256 mismatch: {record['path']}")
    if record["git_entry_kind"] == "direct_text_blob":
        actual = hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
        expected = record["git_blob_sha1"]
    else:
        actual, expected = hashlib.md5(data).hexdigest(), record["annex_md5"]
    if actual != expected:
        raise ValueError(f"Published source checksum mismatch: {record['path']}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def checked_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in ("", ".", "..") for p in path.parts):
        raise ValueError("Unsafe source-relative path")
    root = Path(root).absolute()
    for parent in (root, *root.parents):
        if parent.is_symlink():
            raise ValueError("Symlink source/destination ancestor")
    target = root/path
    for part in (target, *target.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("Symlink source/destination member")
    return target


def inventory(root, records, require_manifest):
    root = Path(root)
    checked_path(root, "source_manifest.json")
    if not root.is_dir():
        raise ValueError("Source/destination must be a regular directory")
    expected = {r["path"] for r in records}
    found = set()
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            if (Path(base)/name).is_symlink():
                raise ValueError("Symlink directory in source bundle")
        for name in files:
            path = Path(base)/name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Nonregular source member")
            found.add(path.relative_to(root).as_posix())
    permitted = expected | {"source_manifest.json"}
    if found-permitted or expected-found or (require_manifest and "source_manifest.json" not in found):
        raise ValueError("Unexpected or missing source bundle file")


def allowed_endpoint(url, record):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.username is not None or parts.password is not None or parts.port not in (None, 443):
        return False
    if url == record["url"]:
        return True
    # Official OpenNeuro versioned-file endpoint resolves to the published S3 dataset path.
    expected = "/openneuro.org/ds001420/"+record["path"]
    observed_alias = {
        "derivatives/PETPrep1/sub-01/ses-baseline/pet/agtm/aux/seg.ctab":
        "/openneuro.org/ds001420/derivatives/PETPrep1/sub-02/ses-rescan/pet/agtm/aux/seg.ctab"
    }
    # One official content-deduplication redirect was confirmed by a retained
    # header-only probe. It is not permission for arbitrary bucket paths;
    # requested-record size/SHA256/published annex MD5 still bind the body.
    paths = {expected}
    if record["path"] in observed_alias:
        paths.add(observed_alias[record["path"]])
    return parts.hostname == "s3.amazonaws.com" and urllib.parse.unquote(parts.path) in paths


def failure_code(error):
    exact = {
        "Unapproved source endpoint": "endpoint_rejected",
        "Source Content-Length mismatch": "content_length_mismatch",
        "Download exceeds pinned size": "body_size_limit_exceeded",
        "Expected complete original source": "unexpected_http_status",
        "Missing source redirect location": "missing_redirect_location",
        "Source redirect cap exceeded": "redirect_cap_exceeded",
        "Published Git-annex pointer does not bind content identity": "annex_pointer_identity_mismatch",
        "Unexpected or missing source bundle file": "source_inventory_mismatch",
        "Source manifest SHA256 mismatch; do not silently refresh pins": "manifest_hash_mismatch",
    }
    if isinstance(error, SourceHTTPError):
        return "http_status_error"
    if isinstance(error, TimeoutError):
        return "deadline_exceeded"
    message = str(error)
    for prefix, code in (("Source size mismatch:", "body_size_mismatch"),
                         ("Source SHA256 mismatch:", "body_hash_mismatch"),
                         ("Published source checksum mismatch:", "published_identity_mismatch")):
        if message.startswith(prefix):
            return code
    return exact.get(message, "unclassified_local_failure")


def download_file(record, target, deadline=None):
    # This branch is build-time only. Native staging uses --source-dir and never calls it.
    deadline = time.monotonic()+60 if deadline is None else deadline
    opener = urllib.request.build_opener(NoRedirect())
    endpoint = record["url"]
    for _ in range(5):
        if not allowed_endpoint(endpoint, record):
            raise ValueError("Unapproved source endpoint")
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Source staging deadline")
        request = urllib.request.Request(endpoint, headers={"User-Agent": "petdvr-source-staging/2.0"})
        try:
            response = opener.open(request, timeout=remaining)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                exc.close()
                if not location:
                    raise ValueError("Missing source redirect location") from None
                endpoint = urllib.parse.urljoin(endpoint, location)
                continue
            raise SourceHTTPError(exc.code) from None
        with response, target.open("xb") as output:
            if response.status != 200:
                raise ValueError("Expected complete original source")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != record["size_bytes"]:
                raise ValueError("Source Content-Length mismatch")
            count = 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Source staging deadline")
                block = response.read(min(65536, record["size_bytes"]+1-count))
                if not block:
                    break
                count += len(block)
                if count > record["size_bytes"]:
                    raise ValueError("Download exceeds pinned size")
                output.write(block)
        verify_file(target, record)
        return
    raise ValueError("Source redirect cap exceeded")


def verify_staged(data_dir):
    data_dir = Path(data_dir)
    manifest, _ = read_manifest(checked_path(data_dir, "source_manifest.json"))
    inventory(data_dir, manifest["files"], require_manifest=True)
    for record in manifest["files"]:
        verify_file(checked_path(data_dir, record["path"]), record)
    return manifest


def stage_data(destination, manifest_path, source_dir=None):
    DIAGNOSTIC.update(phase="validate_manifest", record_path=None)
    destination = Path(destination)
    manifest, manifest_bytes = read_manifest(Path(manifest_path))
    checked_path(destination, "source_manifest.json")
    if destination.exists():
        DIAGNOSTIC.update(phase="verify_existing_destination", record_path=None)
        # A complete existing bundle is idempotent. Preserve partial/conflicting bundles.
        current = verify_staged(destination)
        if current != manifest:
            raise ValueError("Existing destination manifest differs; preserve it")
        return current
    if source_dir is not None:
        DIAGNOSTIC.update(phase="verify_source_inventory", record_path=None)
        source_dir = Path(source_dir)
        inventory(source_dir, manifest["files"], require_manifest=False)
        for record in manifest["files"]:
            DIAGNOSTIC.update(phase="verify_local_source", record_path=record["path"])
            verify_file(checked_path(source_dir, record["path"]), record)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="petdvr-source-", dir=destination.parent))
    # Preserve a failed stage for diagnosis; publish only a wholly verified directory.
    deadline = time.monotonic()+(DOWNLOAD_TOTAL_TIMEOUT_SECONDS if source_dir is None else 60)
    for record in manifest["files"]:
        DIAGNOSTIC.update(phase="download_source" if source_dir is None else "copy_verified_source",
                          record_path=record["path"])
        if time.monotonic() >= deadline:
            raise TimeoutError("Source staging deadline")
        target = checked_path(temporary, record["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if source_dir is None:
            download_file(record, target, deadline=deadline)
        else:
            shutil.copyfile(checked_path(source_dir, record["path"]), target)
            verify_file(target, record)
        target.chmod(0o444)
    (temporary/"source_manifest.json").write_bytes(manifest_bytes)
    (temporary/"source_manifest.json").chmod(0o444)
    DIAGNOSTIC.update(phase="verify_complete_stage", record_path=None)
    verify_staged(temporary)
    # mkdtemp starts at0700. The build runs as root but the task may run as a
    # different user: publish traversable directories and read-only files.
    # Only this newly created stage is changed, never the shared source cache.
    for directory, _, _ in os.walk(temporary, followlinks=False):
        Path(directory).chmod(0o755)
    if destination.exists():
        raise ValueError("Destination appeared during staging; preserve both bundles")
    DIAGNOSTIC.update(phase="publish_verified_stage", record_path=None)
    temporary.replace(destination)
    print(json.dumps({"status": "ok", "n_files": len(manifest["files"]),
                      "total_source_bytes": sum(r["size_bytes"] for r in manifest["files"]),
                      "manifest_sha256": MANIFEST_SHA256,
                      "source_sha256": {r["path"]: r["sha256"] for r in manifest["files"]}},
                     sort_keys=True), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/petdvr"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("source_manifest.json"))
    parser.add_argument("--source-dir", "--source-root", type=Path,
                        help="Optional exact local bundle, fully reverified before reuse")
    args = parser.parse_args()
    try:
        stage_data(args.destination, args.manifest, args.source_dir)
    except Exception as exc:
        # Do not expose redirects, query strings, credentials or server response bodies.
        failure = {"status": "failed_precondition", "error_type": type(exc).__name__,
                   "error_code": failure_code(exc),
                   "phase": DIAGNOSTIC["phase"],
                   "record_path": DIAGNOSTIC["record_path"] if DIAGNOSTIC["record_path"] in expected_files() else None}
        if isinstance(exc, SourceHTTPError):
            failure["http_status"] = exc.http_status
        print(json.dumps(failure), file=sys.stderr, flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
