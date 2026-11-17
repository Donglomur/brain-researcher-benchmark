"""Exact ordinary original-source preparation; no data/model downloads or imports."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType
import time
from urllib.parse import quote
import urllib.error
import urllib.request

from .io_core import (SourceError, OwnedFD, _raise_with_close, capture_path, encode,
                      open_directory, publish_tree, read_at, relative, strict_json, verify_inventory)

REVISION = "703a10fb43fc7fe0076c9c331e6b52d3195b5e60"
REPOSITORY = "Npix-routines/NeuroPyxels"
MANIFEST_SHA256 = "5473073dfa73ff97a600709d06e5890d26d76e94f7e3e788091a1d5218b57d70"
MANIFEST_BYTES = 14984
ARTICLE_BYTES = 283513
ARTICLE_SHA256 = "90c512b3ba1fc80519eea8c5183898f4b5fb4ff691a39f6c15d1a59372610323"
RECEIPT = "SOURCE_RECEIPT.json"

@dataclass(frozen=True)
class VerifiedDependencies:
    root: Path
    revision: str
    manifest_sha256: str
    files: object
    qualification: str = "ordinary source bytes only; scientific/native/rights qualification unissued"

def specification():
    path = Path(__file__).resolve().parents[1] / "REQUIRED_ORIGINAL_SOURCE.json"
    raw = capture_path(path, MANIFEST_BYTES)
    return _specification_bytes(raw)

def _specification_bytes(raw):
    if type(raw) is not bytes:
        raise SourceError("captured fixed manifest must be bytes")
    if len(raw) != MANIFEST_BYTES or hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise SourceError("fixed source manifest changed")
    spec = strict_json(raw)
    expected = {"schema", "repository", "revision", "files", "file_count", "total_bytes",
                "member_cap", "batch_cap", "distribution", "rights_clearance",
                "package_runtime_qualified", "original_notice_closure"}
    if set(spec) != expected or spec["schema"] != "c4.required-original-source.v1":
        raise SourceError("fixed complete source-manifest schema")
    if spec["revision"] != REVISION or spec["repository"] != REPOSITORY:
        raise SourceError("fixed upstream source identity")
    if spec["member_cap"] != 1048576 or spec["batch_cap"] != 16777216:
        raise SourceError("fixed source limits")
    rows = spec["files"]
    if type(rows) is not list or type(spec["file_count"]) is not int or len(rows) != spec["file_count"] or not 1 <= len(rows) <= 2048:
        raise SourceError("complete bounded source roster")
    names = set()
    total = 0
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256", "git_blob", "url"}:
            raise SourceError("exact original-source row")
        path = relative(row["path"])
        if path.suffix not in (".py", ".toml", ".md") or row["path"].casefold() in names or row["path"] == RECEIPT:
            raise SourceError("unique selected ordinary source names")
        names.add(row["path"].casefold())
        if type(row["bytes"]) is not int or not 0 <= row["bytes"] <= 1048576:
            raise SourceError("bounded original source")
        for key, length in (("sha256", 64), ("git_blob", 40)):
            value = row[key]
            if type(value) is not str or len(value) != length or any(c not in "0123456789abcdef" for c in value):
                raise SourceError("fixed source hash")
        required_url = "https://raw.githubusercontent.com/" + REPOSITORY + "/" + REVISION + "/" + quote(row["path"], safe="/")
        if row["url"] != required_url:
            raise SourceError("only selected immutable ordinary-source URL permitted")
        total += row["bytes"]
    if total != spec["total_bytes"] or total > 16777216:
        raise SourceError("whole selected source extent")
    if spec["rights_clearance"] is not False or spec["package_runtime_qualified"] is not False:
        raise SourceError("source verification cannot issue rights/runtime qualification")
    return spec

def _verified_body(row, raw):
    if type(raw) is not bytes or len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise SourceError("original source bytes do not match fixed selection")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != row["git_blob"]:
        raise SourceError("original source Git blob identity mismatch")
    if b"\0" in raw:
        raise SourceError("binary original refused")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceError("ordinary UTF-8 original required") from exc
    return raw

def _receipt(spec):
    return {"schema": "c4.verified-original-source.v1", "revision": REVISION,
            "manifest_sha256": MANIFEST_SHA256, "status": "verified-ordinary-source-only",
            "files": [{k: row[k] for k in ("path", "bytes", "sha256", "git_blob")} for row in spec["files"]],
            "file_count": len(spec["files"]), "total_bytes": spec["total_bytes"],
            "rights_clearance": False, "scientific_or_native_qualification": False}

def verify_dependencies(root):
    spec = specification()
    root = Path(root).absolute()
    files = {}
    with OwnedFD(open_directory(root)) as fd:
        verify_inventory(fd, [row["path"] for row in spec["files"]] + [RECEIPT])
        receipt = strict_json(read_at(fd, RECEIPT, 1048576))
        if receipt != _receipt(spec):
            raise SourceError("complete dependency receipt identity")
        for row in spec["files"]:
            files[row["path"]] = _verified_body(row, read_at(fd, row["path"], row["bytes"]))
    return VerifiedDependencies(root, REVISION, MANIFEST_SHA256, MappingProxyType(files))

def load_required_article(path):
    if path is None:
        raise SourceError("exact separately admitted article is required in both arms")
    body = capture_path(path, ARTICLE_BYTES)
    if len(body) != ARTICLE_BYTES or hashlib.sha256(body).hexdigest() != ARTICLE_SHA256:
        raise SourceError("required original article identity; no substitute accepted")
    if b"\0" in body:
        raise SourceError("ordinary exact article required")
    body.decode("utf-8")
    return body

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise SourceError("redirect from selected immutable source URL refused")
    def http_error_302(self, request, fp, code, message, headers):
        primary = SourceError("redirect from selected immutable source URL refused")
        failures = []
        try:
            fp.close()
        except BaseException as exc:
            exc.c4_close_owner = fp
            failures.append(exc)
        _raise_with_close(primary, failures)
    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

class _ResponseOwner:
    def __init__(self, response):
        self.response = response
        self.close_failure = None
    def __enter__(self):
        return self.response
    def __exit__(self, typ, primary, tb):
        failures = []
        try:
            self.response.close()
        except BaseException as exc:
            self.close_failure = exc
            exc.c4_close_owner = self
            failures.append(exc)
        if failures:
            _raise_with_close(primary, failures)
        return False

def _fetch(row, opener, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SourceError("whole source-fetch wall budget exhausted")
    request = urllib.request.Request(row["url"], headers={"Accept-Encoding": "identity", "User-Agent": "C4-fixed-source-preparer/1"})
    try:
        opened = opener.open(request, timeout=min(10.0, remaining))
    except urllib.error.HTTPError as primary:
        failures = []
        try:
            primary.close()
        except BaseException as exc:
            exc.c4_close_owner = primary
            failures.append(exc)
        _raise_with_close(primary, failures)
    with _ResponseOwner(opened) as response:
        if time.monotonic() >= deadline:
            raise SourceError("whole source-fetch wall budget exhausted after open")
        if response.status != 200 or response.geturl() != row["url"]:
            raise SourceError("immutable source URL/status changed")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise SourceError("encoded response refused")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdecimal() or int(length) != row["bytes"]):
            raise SourceError("source response extent")
        data = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise SourceError("whole source-fetch wall budget exhausted")
            chunk = response.read(min(65536, row["bytes"] + 1 - len(data)))
            if time.monotonic() >= deadline:
                raise SourceError("whole source-fetch wall budget exhausted after read/EOF")
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > row["bytes"]:
                raise SourceError("source stream exceeds pinned extent")
        body = _verified_body(row, bytes(data))
    if time.monotonic() >= deadline:
        raise SourceError("whole source-fetch wall budget exhausted after response close")
    return body

def prepare_dependencies(output, *, source_root=None, fetch=False):
    if (source_root is None) == (fetch is False) or type(fetch) is not bool:
        raise SourceError("choose exactly one explicit local source root or selected-source fetch")
    spec = specification()
    files = []
    if fetch:
        from .fetch_owner import fetch_sources
        files = fetch_sources(spec)
    else:
        # Only exact selected names are read from the operator's input checkout.
        # Unselected contents, data, archives and hidden files are never traversed.
        with OwnedFD(open_directory(source_root)) as fd:
            for row in spec["files"]:
                files.append((row["path"], _verified_body(row, read_at(fd, row["path"], row["bytes"]))))
    receipt = encode(_receipt(spec))
    if len(receipt) > 1048576:
        raise SourceError("bounded dependency receipt")
    publication = publish_tree(output, files + [(RECEIPT, receipt)],
                               max_files=2048, max_bytes=16777216, max_member_bytes=1048576)
    # Reopen the actual published root, checking every member and exact absence
    # of extras. A post-publication failure retains that custody, never success.
    try:
        verified = verify_dependencies(output)
    except BaseException as exc:
        exc.add_note("C4 dependency root was published; final independent readback failed; preserve root " + str(output))
        raise
    return {"publication": publication, "source_files": len(verified.files),
            "manifest_sha256": verified.manifest_sha256, "scientific_or_native_qualification": False}
