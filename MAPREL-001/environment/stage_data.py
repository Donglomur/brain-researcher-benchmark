"""Portable checksum-pinned MAPREL source staging; no scientific decoders or import I/O.

Opaque transport/tar checks are adapted from qualified PR193 acquisition code.
Build-time downloads only; verify-existing and local-copy modes never network.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import tarfile
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MANIFEST_SHA256 = "279658ffc93a8957287298471b539fc034fb7e11f0836325de322acc4b232f7f"
SCIENCE_ROLES = {"gradient_l", "gradient_r", "thickness_l", "thickness_r", "sphere_l", "sphere_r", "atlas"}
PROVENANCE_ROLES = {"neuromaps_license", "neuromaps_readme", "cbig_license", "cbig_parcellation_readme", "neuromaps_source_catalog", "neuromaps_annotation_metadata"}
SPHERES = {f"atlases/fsLR/tpl-fsLR_den-32k_hemi-{h}_sphere.surf.gii": f"sphere_{h.lower()}" for h in ("L", "R")}


@dataclass(frozen=True)
class Limits:
    received_bytes: int = 16 * 1024**2
    wall_seconds: int = 300
    socket_seconds: int = 30
    redirects: int = 5
    members: int = 64
    expanded_bytes: int = 64 * 1024**2
    tar_stream_bytes: int = 65 * 1024**2
    member_bytes: int = 16 * 1024**2
    disk_reserve_bytes: int = 1024**3


class Refusal(ValueError): pass
def need(ok, code):
    if not ok: raise Refusal(code)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def signature(s): return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def safe_path(value):
    s = os.fspath(value)
    need(s.startswith("/") and "\0" not in s and not any(x in (".", "..") for x in s.split("/")), "unsafe_path")
    p = Path(s)
    for x in (*reversed(p.parents), p):
        if os.path.lexists(x):
            need(not x.is_symlink(), "symlink_path")
            if x != p: need(x.is_dir(), "non_directory_ancestor")
    return p


def relative(name):
    need(isinstance(name, str) and name and "\\" not in name and "\0" not in name and not name.startswith("/")
         and not re.match(r"^[A-Za-z]:", name) and all(p and p not in (".", "..") for p in name.split("/")), "unsafe_member_name")
    return name


def disjoint(a, b): need(a != b and a not in b.parents and b not in a.parents, "overlapping_paths")


@contextmanager
def reader(path):
    p = safe_path(path); before = p.lstat(); need(stat.S_ISREG(before.st_mode), "regular_file_required")
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as f:
        need(signature(os.fstat(f.fileno())) == signature(before), "changed_before_read")
        yield f, before
        need(signature(os.fstat(f.fileno())) == signature(before) == signature(p.lstat()), "changed_during_read")


def strict_json(raw):
    def pairs(rows):
        out = {}
        for k, v in rows: need(k not in out, "duplicate_json_key"); out[k] = v
        return out
    def invalid(_): raise Refusal("invalid_json_constant")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    def finite(v):
        if isinstance(v, float): need(math.isfinite(v), "invalid_json_constant")
        elif isinstance(v, dict):
            for x in v.values(): finite(x)
        elif isinstance(v, list):
            for x in v: finite(x)
    finite(value); return value


def write_json(path, value):
    with os.fdopen(os.open(safe_path(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False); f.write("\n")


def canonical_url(row): return row["source_url"]


def endpoint(url, row, initial=False):
    p = urlsplit(url)
    need(p.scheme == "https" and p.username is None and p.password is None and p.port in (None, 443) and not p.fragment, "endpoint_rejected")
    if initial: need(url == canonical_url(row), "initial_url_mismatch")
    if "source_guid" not in row:
        need(url == canonical_url(row), "atlas_endpoint_rejected")
    else:
        q = parse_qs(p.query, keep_blank_values=True)
        revisions = [q[k] for k in ("revision", "version") if k in q]
        version_ok = bool(revisions) and all(x == ["1"] for x in revisions)
        if p.hostname == "osf.io": need(p.path in (f"/download/{row['source_guid']}", f"/download/{row['source_guid']}/") and version_ok, "osf_identity_revision")
        elif p.hostname in ("files.osf.io", "files.ca-1.osf.io"):
            path = f"/v1/resources/4mw3a/providers/osfstorage/{row['object_id']}"
            need(p.path in (path, path + "/") and version_ok, "waterbutler_identity_revision")
        elif p.hostname == "storage.googleapis.com":
            need(re.fullmatch(r"/cos-osf-prod-files-[a-z0-9-]+/" + row["sha256"], p.path), "storage_object_identity")
            alternatives = (("GoogleAccessId", "Expires", "Signature"),
                            ("X-Goog-Algorithm", "X-Goog-Credential", "X-Goog-Date", "X-Goog-Expires", "X-Goog-Signature"))
            need(any(all(len(q.get(k, [])) == 1 and q[k][0] for k in keys) for keys in alternatives), "unsigned_storage_redirect")
        else: raise Refusal("endpoint_rejected")
    return dict(host=p.hostname, path=p.path, query_keys=sorted(parse_qs(p.query, keep_blank_values=True)))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_): return None


def open_once(url, timeout):
    req = Request(url, headers={"User-Agent": "MAPREL-checksum-capture/1", "Accept-Encoding": "identity"})
    try: return build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout)
    except HTTPError as exc: return exc


def header(headers, key, required=False):
    values = headers.get_all(key, [])
    need(len(values) <= 1 and (not required or len(values) == 1), "missing_or_duplicate_" + key.lower())
    return values[0] if values else None


class Budget:
    def __init__(self, limits=Limits(), clock=time.monotonic):
        self.limits, self.clock, self.start = limits, clock, clock()
        self.received, self.requests, self.started = 0, 0, set()
    def check(self): need(self.clock() - self.start < self.limits.wall_seconds, "wall_deadline")
    def read(self, response, n):
        self.check(); n = min(n, self.limits.received_bytes - self.received)
        need(n > 0, "received_byte_cap")
        chunk = response.read1(n)
        need(isinstance(chunk, bytes) and len(chunk) <= n, "invalid_chunk")
        self.received += len(chunk); self.check(); return chunk


@contextmanager
def timeout(seconds):
    need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), "existing_alarm")
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_): raise Refusal("wall_deadline")
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally: signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous)


def hashers(row):
    result = dict(sha256=hashlib.sha256(), md5=hashlib.md5())
    result["git_blob_sha1"] = hashlib.sha1(b"blob " + str(row["size_bytes"]).encode() + b"\0")
    return result


def check_hashes(row, hs, count):
    need(count == row["size_bytes"], "source_size_mismatch")
    need(all(hs[k].hexdigest() == row[k] for k in hs if k in row), "source_digest_mismatch")
    return {k:h.hexdigest() for k, h in hs.items()}


def file_identity(path, row, budget):
    hs = hashers(row); count = 0
    with reader(path) as (f, s):
        need(s.st_size == row["size_bytes"], "source_size_mismatch")
        while True:
            budget.check(); block = f.read(65536)
            if not block: break
            count += len(block)
            for h in hs.values(): h.update(block)
    return check_hashes(row, hs, count)


def download(row, destination, budget, record, transport=open_once):
    key = row["role"]; budget.check(); need(key not in budget.started and len(budget.started) < 16, "duplicate_or_excess_start"); budget.started.add(key)
    response = None; url = canonical_url(row); seen = set(); count = 0; hs = hashers(row)
    partial, target = destination / (key + ".partial"), destination / (key + ".source")
    record.update(role=key, canonical_source_url=url, status="started", redirects=[], received_bytes=0)
    try:
        with partial.open("xb") as out:
            for hop in range(budget.limits.redirects + 1):
                budget.check(); record["last_endpoint"] = endpoint(url, row, initial=hop == 0)
                need(url not in seen, "redirect_loop"); seen.add(url); budget.requests += 1
                response = transport(url, min(budget.limits.socket_seconds, budget.limits.wall_seconds-(budget.clock()-budget.start)))
                record["http_status"] = int(response.code)
                need(response.geturl() == url, "unhandled_redirect")
                need(sum(len(k)+len(v) for k, v in response.headers.items()) <= 65536, "header_cap")
                if response.code in (301, 302, 303, 307, 308):
                    location = header(response.headers, "Location", True); response.close(); response = None
                    need(hop < budget.limits.redirects and "source_guid" in row, "redirect_limit_or_atlas_redirect")
                    candidate = urljoin(url, location); p = urlsplit(candidate)
                    step = dict(host=p.hostname, path=p.path, query_keys=sorted(parse_qs(p.query, keep_blank_values=True)), allowed=False)
                    record["redirects"].append(step); endpoint(candidate, row); step["allowed"] = True; url = candidate; continue
                need(response.code == 200, "http_status")
                length = header(response.headers, "Content-Length", True)
                need(re.fullmatch(r"[0-9]{1,12}", length) and int(length) == row["size_bytes"], "content_length_mismatch")
                need((header(response.headers, "Content-Encoding") or "identity").lower() == "identity", "encoded_body")
                content_type = (header(response.headers, "Content-Type", True) or "").split(";", 1)[0].lower().strip()
                need(content_type not in ("text/html", "application/xhtml+xml"), "unexpected_html")
                record["safe_headers"] = {k:header(response.headers, k) for k in ("Content-Length", "Content-Type", "ETag", "Last-Modified")}
                while True:
                    chunk = budget.read(response, min(65536, row["size_bytes"] - count + 1))
                    if not chunk: break
                    count += len(chunk); record["received_bytes"] = count
                    need(count <= row["size_bytes"], "source_size_overrun")
                    out.write(chunk)
                    for h in hs.values(): h.update(chunk)
                actual = check_hashes(row, hs, count); budget.check(); break
            else: raise Refusal("redirect_limit")
        partial.chmod(0o444); os.link(partial, target, follow_symlinks=False); partial.unlink()
        record.update(status="verified", path=target.name, size_bytes=count, measured=actual)
        return target
    except BaseException as exc:
        record.update(status="failed", error_type=type(exc).__name__, reason=str(exc) if isinstance(exc, Refusal) else "opaque_transport_failure")
        raise
    finally:
        if response is not None: response.close()


class BoundedTar:
    def __init__(self, stream, budget): self.stream, self.budget, self.count = stream, budget, 0
    def read(self, n=-1):
        self.budget.check(); left = self.budget.limits.tar_stream_bytes - self.count
        need(left > 0, "tar_stream_cap")
        data = self.stream.read(min(65536 if n < 0 else n, left))
        self.count += len(data); self.budget.check(); return data


def tar_inventory(path, budget, selected_dir=None):
    """Opaque archive walk; optional two-member copy only after caller's full auth."""
    rows, seen, regular, total, selected = [], set(), set(), 0, []
    with reader(path) as (f, _), gzip.GzipFile(fileobj=f, mode="rb") as gz:
        bounded = BoundedTar(gz, budget)
        with tarfile.open(fileobj=bounded, mode="r|", bufsize=512) as tf:
            for member in tf:
                budget.check(); name = member.name[:-1] if member.isdir() and member.name.endswith("/") else member.name; relative(name)
                need(member.isfile() or member.isdir(), "tar_nonregular_member")
                need(name not in seen and member.size >= 0, "tar_duplicate_or_negative_size")
                need(not member.isdir() or member.size == 0, "tar_directory_payload")
                need(not any(p.as_posix() in regular for p in PurePosixPath(name).parents), "tar_file_directory_collision")
                if member.isfile():
                    need(not any(s.startswith(name + "/") for s in seen), "tar_file_directory_collision"); regular.add(name)
                seen.add(name); total += member.size
                need(len(seen) <= budget.limits.members and total <= budget.limits.expanded_bytes, "tar_inventory_cap")
                rows.append(dict(path=name, size_bytes=member.size, directory=member.isdir()))
                if name in SPHERES:
                    need(member.isfile() and 0 < member.size <= budget.limits.member_bytes, "sphere_size_type")
                    if selected_dir is not None:
                        source = tf.extractfile(member); need(source is not None, "sphere_stream")
                        output = selected_dir / (SPHERES[name] + ".surf.gii"); count = 0; digest = hashlib.sha256()
                        with source, output.open("xb") as out:
                            while True:
                                budget.check(); b = source.read(min(65536, member.size-count+1))
                                if not b: break
                                count += len(b); need(count <= member.size, "sphere_size_overrun"); digest.update(b); out.write(b)
                        need(count == member.size, "sphere_truncated"); output.chmod(0o444)
                        selected.append(dict(role=SPHERES[name], path=output.name, archive_member=name, size_bytes=count, sha256=digest.hexdigest()))
        while True:
            tail = bounded.read(65536)
            if not tail: break
            need(not any(tail), "tar_nonzero_trailing_data")
    need(set(SPHERES) <= regular, "required_spheres_missing")
    return rows, selected


def read_manifest(path):
    with reader(path) as (f, info):
        need(info.st_size <= 262144, "manifest_cap"); raw = f.read(262145)
    need(len(raw) <= 262144 and sha(raw) == MANIFEST_SHA256, "manifest_pin")
    doc = strict_json(raw)
    need(doc.get("task_id") == "MAPREL-001" and doc.get("schema_version") == "maprel-source-v2", "manifest_identity")
    files, objects = doc["files"], doc["objects"]
    need(isinstance(files, list) and len(files) == 13 and isinstance(objects, list) and len(objects) == 12, "manifest_count")
    need(doc.get("source_file_count") == 13 and doc.get("download_object_count") == 12
         and doc.get("runtime_data_directory") == "/app/data/maprel"
         and doc.get("source_manifest_inside_data_root") is True, "manifest_layout")
    need({r["role"] for r in files} == SCIENCE_ROLES | PROVENANCE_ROLES, "manifest_roles")
    need(len({r["path"] for r in files}) == 13 and len({r["key"] for r in objects}) == 12, "manifest_duplicates")
    object_roles = (SCIENCE_ROLES - {"sphere_l", "sphere_r"}) | {"spheres_archive"} | PROVENANCE_ROLES
    need({r["role"] for r in objects} == object_roles and all(r["key"] == r["role"] for r in objects), "manifest_object_roles")
    for r in files + objects:
        need(type(r.get("size_bytes")) is int and 0 < r["size_bytes"] <= 16 * 1024**2, "manifest_member_size")
        need(isinstance(r.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", r["sha256"]), "manifest_sha256")
        for k, length in (("md5", 32), ("git_blob_sha1", 40)):
            if k in r: need(isinstance(r[k], str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", r[k]), "manifest_optional_digest")
    need(sum(r["size_bytes"] for r in files) == doc["source_bytes"] <= 32*1024**2, "manifest_source_total")
    need(sum(r["size_bytes"] for r in objects) == doc["download_bytes"] <= Limits().received_bytes, "manifest_download_total")
    by_key = {r["key"]:r for r in objects}
    for r in objects:
        if r.get("transport") == "osf":
            need(r.get("node_id") == "4mw3a" and r.get("source_version") == 1 and "md5" in r, "osf_manifest_identity")
            need(isinstance(r.get("source_guid"), str) and re.fullmatch(r"[a-z0-9]{5}", r["source_guid"]), "osf_guid")
            need(re.fullmatch(r"[0-9a-f]{24}", r.get("object_id", "")), "osf_object")
            need(r["source_url"] == f"https://osf.io/download/{r['source_guid']}/?revision=1", "osf_canonical_url")
        else:
            need(r.get("transport") == "raw_commit" and "git_blob_sha1" in r and re.fullmatch(r"[0-9a-f]{40}", r.get("commit", "")), "git_manifest_identity")
            need(r.get("repository") in ("netneurolab/neuromaps", "ThomasYeoLab/CBIG"), "git_repository")
            prefix = f"https://raw.githubusercontent.com/{r['repository']}/{r['commit']}/"
            need(r["source_url"].startswith(prefix), "git_canonical_url"); relative(r["source_url"][len(prefix):])
    for r in files:
        relative(r["path"]); need(r["path"] != "source_manifest.json" and r["object_key"] in by_key, "manifest_file_object")
        need(not any(other["path"].startswith(r["path"] + "/") for other in files), "manifest_path_collision")
        obj = by_key[r["object_key"]]
        if "archive_member" in r:
            need(r["object_key"] == "spheres_archive" and SPHERES.get(r["archive_member"]) == r["role"], "manifest_archive_member")
        else:
            need(r["size_bytes"] == obj["size_bytes"] and r["sha256"] == obj["sha256"], "manifest_direct_identity")
            need(all(k not in r or r[k] == obj.get(k) for k in ("md5", "git_blob_sha1")), "manifest_direct_digest")
    archive = by_key["spheres_archive"]
    need(archive.get("archive_format") == "tar.gz" and set(archive["required_members"]) == set(SPHERES), "manifest_archive_selection")
    need(isinstance(archive.get("inventory"), list) and len(archive["inventory"]) <= 64, "manifest_inventory")
    return doc, raw


def check_inventory(root, files):
    root = safe_path(root); need(root.is_dir(), "source_directory")
    expected = {r["path"] for r in files} | {"source_manifest.json"}
    directories = {p.as_posix() for name in expected for p in PurePosixPath(name).parents if p.as_posix() != "."}
    actual, dirs = set(), set()
    for base, children, names in os.walk(root, followlinks=False):
        for name in children:
            p = Path(base)/name; need(not p.is_symlink() and p.is_dir(), "source_directory_symlink_or_type")
            dirs.add(p.relative_to(root).as_posix())
        for name in names:
            p = Path(base)/name; need(stat.S_ISREG(p.lstat().st_mode), "source_nonregular_file")
            actual.add(p.relative_to(root).as_posix())
        need(len(actual) <= 32 and len(dirs) <= 32, "source_inventory_cap")
    need(actual == expected and dirs == directories, "source_closed_inventory")


def verify_staged(data_dir, manifest_path="/app/source_manifest.json"):
    manifest, raw = read_manifest(manifest_path); root = safe_path(data_dir)
    check_inventory(root, manifest["files"])
    with reader(root/"source_manifest.json") as (f, s):
        need(s.st_size == len(raw) and f.read(len(raw)+1) == raw, "staged_manifest_identity")
    budget = Budget()
    for row in manifest["files"]: file_identity(root/row["path"], row, budget)
    return manifest


def copy_file(source, target, row, budget):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial"); hs = hashers(row); count = 0
    with reader(source) as (f, s), partial.open("xb") as out:
        need(s.st_size == row["size_bytes"], "copy_source_size")
        while True:
            budget.check(); b = f.read(min(65536, row["size_bytes"]-count+1))
            if not b: break
            count += len(b); need(count <= row["size_bytes"], "copy_size_overrun")
            for h in hs.values(): h.update(b)
            out.write(b)
    check_hashes(row, hs, count); partial.chmod(0o444)
    os.link(partial, target, follow_symlinks=False); partial.unlink()


def publish_no_replace(source, destination):
    # Ubuntu/Linux atomic no-replace directory publication, avoiding rename races.
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2; fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]; fn.restype = ctypes.c_int
    if fn(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        raise OSError(ctypes.get_errno(), "exclusive_source_publication_failed")


def stage(destination, work_dir, manifest_path, source_dir=None, transport=open_once):
    manifest, raw = read_manifest(manifest_path)
    dst, work, mp = safe_path(destination), safe_path(work_dir), safe_path(manifest_path)
    disjoint(dst, work); disjoint(dst, mp); disjoint(work, mp)
    need(not os.path.lexists(dst) and not os.path.lexists(work), "fresh_staging_paths")
    source = safe_path(source_dir) if source_dir is not None else None
    if source is not None:
        for p in (dst, work): disjoint(p, source)
        verify_staged(source, manifest_path)  # All local originals before writes.
    ancestor = work.parent
    while not ancestor.exists(): ancestor = ancestor.parent
    need(shutil.disk_usage(ancestor).free >= Limits().disk_reserve_bytes, "disk_reserve")
    work.parent.mkdir(parents=True, exist_ok=True); work.mkdir(mode=0o700)
    pending = work/"pending"; pending.mkdir(); budget = Budget()
    report = dict(status="running", source_manifest_sha256=MANIFEST_SHA256, mode="local_verified_copy" if source else "public_download",
                  objects=[], automatic_retries=0, workers=1, source_files=13, source_bytes=manifest["source_bytes"], scientific_values_parsed=False)
    write_json(work/"attempt.json", report)
    try:
        with timeout(budget.limits.wall_seconds):
            if source is not None:
                for row in manifest["files"]: copy_file(source/row["path"], pending/row["path"], row, budget)
            else:
                objects = work/"objects"; objects.mkdir()
                for row in manifest["objects"]:
                    rec = {}; report["objects"].append(rec); download(row, objects, budget, rec, transport)
                archive = next(r for r in manifest["objects"] if r["role"] == "spheres_archive")
                archive_path = objects/"spheres_archive.source"
                file_identity(archive_path, archive, budget); observed, _ = tar_inventory(archive_path, budget)
                file_identity(archive_path, archive, budget)
                need(observed == archive["inventory"], "published_archive_inventory_changed")
                selected = work/"selected"; selected.mkdir()
                _, extracted = tar_inventory(archive_path, budget, selected); file_identity(archive_path, archive, budget)
                for row in manifest["files"]:
                    if "archive_member" in row:
                        item = next(x for x in extracted if x["role"] == row["role"])
                        need(item["size_bytes"] == row["size_bytes"] and item["sha256"] == row["sha256"], "extracted_member_pin")
                        origin = selected/item["path"]
                    else: origin = objects/(row["object_key"]+".source")
                    copy_file(origin, pending/row["path"], row, budget)
            with (pending/"source_manifest.json").open("xb") as f: f.write(raw)
            (pending/"source_manifest.json").chmod(0o444)
            verify_staged(pending, manifest_path); budget.check()
            dst.parent.mkdir(parents=True, exist_ok=True); safe_path(dst)
            publish_no_replace(pending, dst)
            report["status"] = "verified_closed_source_bundle"
    except BaseException as exc:
        report.update(status="failed_preserved", error_type=type(exc).__name__, reason=str(exc) if isinstance(exc, Refusal) else "source_staging_failure"); raise
    finally:
        report.update(elapsed_seconds=budget.clock()-budget.start, received_body_bytes=budget.received, network_requests=budget.requests, object_starts=len(budget.started))
        write_json(work/"result.json", report)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",default="/app/source_manifest.json"); p.add_argument("--destination",default="/app/data/maprel")
    p.add_argument("--work-dir");p.add_argument("--source-dir");p.add_argument("--verify-existing",action="store_true")
    a=p.parse_args(argv)
    if not a.verify_existing and not a.work_dir:p.error("--work-dir required for staging")
    try:
        if a.verify_existing:
            need(a.source_dir is None, "verify_source_override_refused")
            doc=verify_staged(a.destination,a.manifest)
            print(json.dumps(dict(status="verified",source_manifest_sha256=MANIFEST_SHA256,source_file_count=len(doc["files"]),source_bytes=doc["source_bytes"],network_requests=0)));return 0
        result=stage(a.destination,a.work_dir,a.manifest,a.source_dir)
        print(json.dumps(result,sort_keys=True));return 0
    except BaseException as exc:
        print(json.dumps(dict(status="failed_preserved",reason=str(exc) if isinstance(exc,Refusal) else "source_staging_failure",error_type=type(exc).__name__)));return 1


if __name__ == "__main__":raise SystemExit(main())
