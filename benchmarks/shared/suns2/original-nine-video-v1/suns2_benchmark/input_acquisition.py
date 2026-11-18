"""Bounded SUNS2 whole-object acquisition and streaming ZIP authentication.

No call in this module runs automatically. The coordinator supplies an externally
pinned source identity, private fresh destinations and a separately admitted run.
HTTP framing derives from the retained reviewed directory driver; streaming and
the empty directory branch are new and require their own generated controls.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import ssl
import stat
import struct
import time
from urllib.parse import urlsplit
import zlib

R2_HOST = "44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com"
SOURCE_HOST = "ndownloader.figshare.com"
OBJECT_ID = 49636131
HEADER_CAP = 16384
TRANSACTION_CAP = 3
INPUT_CHUNK = 65536
OUTPUT_CHUNK = 1048576
ARCHIVE_READ_CAP = 1048576
LOCAL = struct.Struct("<4s5H3I2H")
EOCD = struct.Struct("<4s4H2IH")
RECEIPT_CAP = 65536


class IntakeRefusal(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise IntakeRefusal(message)


def _tick(deadline):
    need(time.monotonic() < deadline, "intake deadline exceeded")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _exclusive_file(path):
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                   0o600)


def _save_json(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False) + "\n").encode()
    need(len(raw) <= RECEIPT_CAP, "receipt exceeds its separate evidence bound")
    with os.fdopen(_exclusive_file(path), "wb") as stream:
        stream.write(raw)


def _raw_write_all(sink, data, report, field):
    """Raw writes can be short; count accepted bytes without assuming completion."""
    view = memoryview(data)
    while view:
        accepted = sink.write(view)
        need(type(accepted) is int and 0 < accepted <= len(view), "raw write made no progress")
        report[field] += accepted
        view = view[accepted:]


def _observe_output(sink_fd, record):
    try:
        observed = os.fstat(sink_fd)
        need(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1,
             "created output changed type or alias count")
        record["observed_bytes"] = observed.st_size
        record["observation_status"] = "fstat_known"
    except BaseException as exc:
        record.update(observed_bytes=None, observation_status="unverified",
                      observation_error=f"{type(exc).__name__}: {exc}")


def _write_accounting(report):
    rows = report["created_outputs"]
    accepted = report["written_payload_bytes"]
    observed = sum(row["observed_bytes"] for row in rows if row["observed_bytes"] is not None)
    unknown_bound = sum(row["expected_bytes"] for row in rows if row["observed_bytes"] is None)
    report.update(write_call_accepted_bytes=accepted, written_payload_bytes=observed,
                  observed_payload_bytes=observed,
                  unverified_write_upper_bound_bytes=unknown_bound,
                  conservative_payload_charge_bytes=observed + unknown_bound,
                  write_observations_complete=all(row["observed_bytes"] is not None for row in rows))


def admitted_url(url):
    """Only the exact source object and its retained R2 object prefix."""
    need(type(url) is str and len(url) <= 8192, "artifact URL length")
    parsed = urlsplit(url)
    need(parsed.scheme == "https" and not parsed.username and not parsed.password
         and not parsed.fragment and parsed.port in (None, 443), "unsafe artifact URL")
    need(parsed.hostname in {SOURCE_HOST, R2_HOST}, "unapproved source host")
    if parsed.hostname == SOURCE_HOST:
        need(parsed.path == f"/files/{OBJECT_ID}" and not parsed.query,
             "wrong source object")
    else:
        need(parsed.path.startswith(f"/figshare-com-storage/{OBJECT_ID}/"),
             "wrong R2 object prefix")
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    need(not any(ord(c) < 33 or ord(c) > 126 for c in target), "unsafe request target")
    return parsed.hostname, target


def _response_summary(headers):
    """Raw headers are retained separately; bound JSON duplication on failure."""
    result = {}
    for key in ("content-length", "content-range", "etag", "location",
                "content-encoding", "transfer-encoding", "content-disposition",
                "last-modified"):
        if key in headers:
            raw = headers[key].encode("latin1")
            result[key] = headers[key] if len(raw) <= 512 else {
                "bytes": len(raw), "sha256": _sha(raw), "value_omitted_from_JSON": True}
    return result


def parse_headers(raw):
    need(len(raw) <= HEADER_CAP and raw.endswith(b"\r\n\r\n"), "header framing/cap")
    lines = raw[:-4].split(b"\r\n")
    match = re.fullmatch(rb"HTTP/1\.[01] ([0-9]{3})(?: [^\r\n]*)?", lines[0])
    need(match is not None, "invalid HTTP status")
    result = {}
    critical = {"content-length", "content-range", "etag", "location",
                "content-encoding", "transfer-encoding", "content-disposition"}
    for line in lines[1:]:
        need(b":" in line and not line.startswith((b" ", b"\t")), "folded/invalid header")
        key, value = line.split(b":", 1)
        need(re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) is not None,
             "invalid header key")
        key, value = key.decode("ascii").lower(), value.decode("latin1").strip()
        need(not any(ord(c) < 32 and c != "\t" for c in value), "control in header")
        need(key not in critical or key not in result, "duplicate critical header")
        result[key] = value
    return int(match.group(1)), result


class Wire:
    def __init__(self, deadline):
        self.deadline = deadline

    def timeout(self):
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, "HTTP deadline exceeded")
        return min(20, remaining)

    def connect(self, url):
        host, target = admitted_url(url)
        sock = socket.create_connection((host, 443), timeout=self.timeout())
        try:
            tls = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        except BaseException:
            sock.close()
            raise
        try:
            tls.settimeout(self.timeout())
            request = (f"GET {target} HTTP/1.1\r\nHost: {host}\r\n"
                       "User-Agent: SUNS2-complete-input-intake/1\r\n"
                       "Accept-Encoding: identity\r\nConnection: close\r\n\r\n")
            tls.sendall(request.encode("ascii"))
            return tls
        except BaseException:
            tls.close()
            raise


def _validate_full_headers(headers, expected_bytes):
    need(headers.get("content-encoding", "identity").lower() == "identity",
         "encoded response refused before body")
    need("transfer-encoding" not in headers, "transfer encoding refused before body")
    need(headers.get("content-length") == str(expected_bytes), "exact Content-Length required")
    tag = headers.get("etag", "")
    need(len(tag) <= 256 and re.fullmatch(r'"[!#-~]+"', tag) is not None and not tag.startswith("W/"),
         "strong ETag required before body")
    need("content-range" not in headers, "unsolicited partial framing")
    disposition = headers.get("content-disposition")
    if disposition is not None:
        need(re.fullmatch(r'attachment;\s*filename="?data_TUnCaT\.zip"?', disposition,
                          flags=re.IGNORECASE) is not None, "unexpected attachment identity")
    return tag


def acquire_complete_archive(identity, destination, evidence_directory, *, wire=None, wall_seconds=180):
    """One GET chain; save all failures and captured bytes, never retry.

    `identity` must come from the coordinator's pinned source manifest. A fake
    Wire may be injected by generated controls. No caller-controlled URLs exist.
    """
    expected = identity["archive_bytes"]
    need(type(expected) is int and 0 < expected <= 248562067, "archive byte bound")
    need(identity["object_id"] == OBJECT_ID, "exact configured source object required")
    need(re.fullmatch(r"[0-9a-f]{32}", identity["published_MD5"]) is not None,
         "expected MD5 format")
    destination = Path(destination)
    evidence_directory = Path(evidence_directory)
    need(not evidence_directory.absolute().is_relative_to(destination.absolute()) and
         not destination.absolute().is_relative_to(evidence_directory.absolute()),
         "raw capture and JSON evidence require separate allocation paths")
    destination.mkdir(mode=0o700, exist_ok=False)
    evidence_directory.mkdir(mode=0o700, exist_ok=False)
    deadline = time.monotonic() + wall_seconds
    transport = wire or Wire(deadline)
    report = {"schema": "suns2-complete-object-acquisition/v1", "status": "started",
              "object_id": OBJECT_ID, "attempts": [], "captured_body_bytes": 0,
              "written_body_bytes": 0, "written_overrun_bytes": 0, "captured_header_bytes": 0,
              "redirect_body_bytes": 0, "scientific_arrays_loaded": False}
    url = f"https://{SOURCE_HOST}/files/{OBJECT_ID}"
    archive = destination / "archive.zip"
    try:
        for number in range(1, TRANSACTION_CAP + 1):
            _tick(deadline)
            admitted_url(url)
            record = {"number": number, "url_without_query": url.split("?", 1)[0],
                      "full_url_sha256": _sha(url.encode("ascii")),
                      "method": "GET", "status": "attempted"}
            report["attempts"].append(record)
            # Durable attempt identity precedes connection; no retry after failure.
            _save_json(evidence_directory / f"{number:02d}-attempt.json", record)
            raw, connection = bytearray(), None
            try:
                connection = transport.connect(url)
                while not raw.endswith(b"\r\n\r\n"):
                    _tick(deadline)
                    need(len(raw) < HEADER_CAP, "response header cap")
                    connection.settimeout(transport.timeout())
                    byte = connection.recv(1)
                    need(bool(byte), "EOF in response header")
                    raw.extend(byte)
                status, headers = parse_headers(bytes(raw))
                record.update(http_status=status, response_headers=_response_summary(headers))
                if status in {301, 302, 303, 307, 308}:
                    need(number < TRANSACTION_CAP, "redirect cap")
                    target = headers.get("location", "")
                    # A literal absolute HTTPS URL is required; no relative resolution.
                    host, _ = admitted_url(target)
                    need(host == R2_HOST, "redirect must target exact retained R2 host")
                    record["status"] = "redirect_headers_only"
                    url = target
                    continue
                need(status == 200 and urlsplit(url).hostname == R2_HOST,
                     "full response must be 200 from retained R2 host")
                tag = _validate_full_headers(headers, expected)
                md5, sha256 = hashlib.md5(), hashlib.sha256()
                with os.fdopen(_exclusive_file(archive), "wb") as sink:
                    while report["captured_body_bytes"] < expected:
                        _tick(deadline)
                        connection.settimeout(transport.timeout())
                        block = connection.recv(min(INPUT_CHUNK, expected - report["captured_body_bytes"]))
                        need(bool(block), "truncated complete object")
                        report["captured_body_bytes"] += len(block)
                        md5.update(block)
                        sha256.update(block)
                        sink.write(block)
                        report["written_body_bytes"] += len(block)
                    connection.settimeout(transport.timeout())
                    extra = connection.recv(1)
                    if extra:
                        report["captured_body_bytes"] += len(extra)
                        with os.fdopen(_exclusive_file(destination / "overrun.bin"), "wb") as overflow:
                            overflow.write(extra)
                        report["written_overrun_bytes"] = len(extra)
                        raise IntakeRefusal("unexpected body byte beyond exact Content-Length")
                need(md5.hexdigest() == identity["published_MD5"], "complete object MD5 mismatch")
                report.update(status="complete_object_md5_authenticated", archive_path=str(archive),
                              archive_sha256=sha256.hexdigest(), archive_md5=md5.hexdigest(),
                              etag=tag, last_modified=_response_summary(headers).get("last-modified"),
                              archive_bytes=expected)
                record["status"] = "complete_body_authenticated"
                return report
            except BaseException as exc:
                record.update(status="refused_or_failed", error=f"{type(exc).__name__}: {exc}")
                raise
            finally:
                if connection is not None:
                    connection.close()
                report["captured_header_bytes"] += len(raw)
                with os.fdopen(_exclusive_file(destination / f"{number:02d}-headers.raw"), "wb") as header_file:
                    header_file.write(raw)
                record.update(captured_header_bytes=len(raw), header_sha256=_sha(raw))
                _save_json(evidence_directory / f"{number:02d}-response.json", record)
        raise IntakeRefusal("no complete object within transaction bound")
    except BaseException as exc:
        report.update(status="partial_or_refused", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if archive.exists():
            try:
                observed_archive = archive.lstat()
                need(stat.S_ISREG(observed_archive.st_mode) and observed_archive.st_nlink == 1,
                     "captured archive changed type or alias count")
                report["observed_archive_file_bytes"] = observed_archive.st_size
                report["archive_write_observation"] = "known; capture charge still includes every received byte"
            except BaseException as exc:
                report["archive_write_observation"] = f"unknown: {type(exc).__name__}"
        report["captured_total_bytes"] = report["captured_body_bytes"] + report["captured_header_bytes"]
        report["transaction_count"] = len(report["attempts"])
        _save_json(evidence_directory / "ACQUISITION_RECEIPT.json", report)


def _validate_roster(identity):
    entries = identity["all_20_entries"]
    need(len(entries) == identity["expected_files"] + identity["expected_directories"] == 20,
         "exact twenty-entry roster required")
    need(identity["expected_files"] == 19 and identity["expected_directories"] == 1,
         "exact original role counts required")
    names, folded = set(), set()
    for i, entry in enumerate(entries):
        name = entry["name"]
        pure = PurePosixPath(name)
        need(entry["index"] == i and name not in names and name.casefold() not in folded,
             "entry order/duplicate/case collision")
        need(not pure.is_absolute() and "\\" not in name and
             not any(part in {"", ".", ".."} for part in name.rstrip("/").split("/")) and
             not any(ord(c) < 32 or ord(c) == 127 for c in name) and
             not re.match(r"^[A-Za-z]:", name), "unsafe member path")
        need(not entry["symlink"] and entry["flags"] in (0, 2048) and
             entry["version_needed"] < 45, "unsupported entry flags/type/version")
        if entry["directory"]:
            need(name == "GT Masks/" and entry["compression_method"] == 0 and
                 entry["compressed_bytes"] == entry["uncompressed_bytes"] == 0 and
                 entry["crc32_unverified"] == "00000000", "exact empty directory branch")
        else:
            need(entry["compression_method"] == 8 and
                 0 < entry["uncompressed_bytes"] <= 30001400, "bounded nonempty deflate file")
        names.add(name)
        folded.add(name.casefold())
    need(sum(e["uncompressed_bytes"] for e in entries) == identity["expected_expanded_bytes"]
         <= 270030454, "expanded byte total")
    return entries


class _ArchiveReader:
    def __init__(self, file, size, deadline):
        self.file, self.size, self.deadline = file, size, deadline
        self.position = 0
        self.md5, self.sha256 = hashlib.md5(), hashlib.sha256()

    def read(self, amount):
        _tick(self.deadline)
        need(type(amount) is int and 0 <= amount <= ARCHIVE_READ_CAP and
             self.position + amount <= self.size, "bounded archive read")
        value = self.file.read(amount)
        need(len(value) == amount, "truncated archive")
        self.position += amount
        self.md5.update(value)
        self.sha256.update(value)
        return value


def _open_bank_file(root_fd, entry):
    parts = PurePosixPath(entry["name"]).parts
    parent_fd, close_parent = root_fd, False
    try:
        if len(parts) == 2:
            need(parts[0] == "GT Masks", "unapproved nested directory")
            parent_fd = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=root_fd)
            close_parent = True
        else:
            need(len(parts) == 1, "unexpected path depth")
        return os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                       0o600, dir_fd=parent_fd)
    finally:
        if close_parent:
            os.close(parent_fd)


def extract_complete_archive(archive_path, identity, bank_directory, *,
                             expected_archive_sha256, expected_gt_pins,
                             wall_seconds=120):
    """Authenticate every source byte while writing each payload exactly once.

    The bank is provisional until this function returns successfully. A failure
    preserves every partial file, and the coordinator must not project that bank.
    No MAT/HDF5 array parser is invoked here.
    """
    entries = _validate_roster(identity)
    need(re.fullmatch(r"[0-9a-f]{64}", expected_archive_sha256) is not None,
         "full archive SHA256 required from admitted acquisition receipt")
    needed_gt = {e["name"] for e in entries if e["name"].startswith("GT Masks/") and not e["directory"]}
    need(set(expected_gt_pins) == needed_gt and len(needed_gt) == 9,
         "exact nine previously authenticated manual-mask pins required")
    path, bank = Path(archive_path), Path(bank_directory)
    bank.mkdir(mode=0o700, exist_ok=False)
    root_fd = os.open(bank, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    source_fd = None
    report = {"schema": "suns2-complete-input-ZIP-authentication/v1", "status": "started",
              "members": [], "written_payload_bytes": 0, "MAT_arrays_loaded": False,
              "HDF5_arrays_loaded": False, "object_id": identity["object_id"], "created_outputs": []}
    deadline = time.monotonic() + wall_seconds
    try:
        source_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        initial = os.fstat(source_fd)
        need(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1 and
             initial.st_size == identity["archive_bytes"], "regular exclusive source identity")
        with os.fdopen(source_fd, "rb") as source:
            source_fd = None
            reader = _ArchiveReader(source, initial.st_size, deadline)
            for entry in entries:
                _tick(deadline)
                need(reader.position == entry["local_header_offset"], "noncontiguous local member span")
                local = reader.read(LOCAL.size)
                sig, version, flags, method, _time, _date, crc, csize, usize, nlen, xlen = LOCAL.unpack(local)
                need(sig == b"PK\x03\x04" and version == entry["version_needed"] < 45 and
                     flags == entry["flags"] and method == entry["compression_method"] and
                     crc == int(entry["crc32_unverified"], 16) and
                     csize == entry["compressed_bytes"] and usize == entry["uncompressed_bytes"],
                     "local header does not match pinned directory")
                raw_name = bytes.fromhex(entry["name_raw_hex"])
                need(nlen == len(raw_name) and nlen <= 1024 and xlen <= 65535,
                     "local name/extra length bound")
                need(reader.read(nlen) == raw_name, "local filename mismatch")
                extra = reader.read(xlen)
                cursor = 0
                while cursor < len(extra):
                    need(cursor + 4 <= len(extra), "truncated local extra")
                    tag, size = struct.unpack_from("<HH", extra, cursor)
                    need(tag != 1 and cursor + 4 + size <= len(extra), "ZIP64/bad local extra")
                    cursor += 4 + size
                if entry["directory"]:
                    os.mkdir("GT Masks", mode=0o700, dir_fd=root_fd)
                    continue
                sink_fd = _open_bank_file(root_fd, entry)
                observation = {"name": entry["name"], "expected_bytes": usize,
                               "observed_bytes": None, "observation_status": "pending"}
                report["created_outputs"].append(observation)
                expanded, checksum = 0, 0
                expanded_sha, compressed_sha = hashlib.sha256(), hashlib.sha256()
                decoder = zlib.decompressobj(-15)
                compressed_remaining = csize
                with os.fdopen(sink_fd, "wb", buffering=0) as sink:
                    try:
                        while compressed_remaining:
                            encoded = reader.read(min(INPUT_CHUNK, compressed_remaining))
                            compressed_remaining -= len(encoded)
                            compressed_sha.update(encoded)
                            pending = encoded
                            while pending:
                                _tick(deadline)
                                decoded = decoder.decompress(pending, min(OUTPUT_CHUNK, usize - expanded + 1))
                                pending = decoder.unconsumed_tail
                                need(not decoder.unused_data, "trailing compressed data")
                                need(expanded + len(decoded) <= usize and
                                     report["written_payload_bytes"] + len(decoded) <= identity["expected_expanded_bytes"],
                                     "member/total expansion overrun")
                                _raw_write_all(sink, decoded, report, "written_payload_bytes")
                                expanded += len(decoded)
                                checksum = zlib.crc32(decoded, checksum)
                                expanded_sha.update(decoded)
                                need(decoded or not pending, "deflate decoder made no progress")
                        need(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data and
                             expanded == usize and checksum == crc, "deflate termination/size/CRC failure")
                    finally:
                        _observe_output(sink_fd, observation)
                need(observation["observed_bytes"] == usize, "unverified/truncated extracted output")
                payload_hash = expanded_sha.hexdigest()
                if entry["name"] in expected_gt_pins:
                    need(payload_hash == expected_gt_pins[entry["name"]], "manual-mask identity changed")
                report["members"].append({"name": entry["name"], "path": str(bank / entry["name"]),
                    "bytes": expanded, "sha256": payload_hash, "crc32": f"{checksum:08x}",
                    "compressed_sha256": compressed_sha.hexdigest(), "source_object_id": identity["object_id"]})
            end = identity["EOCD"]
            need(reader.position == end["central_directory_offset"], "member spans do not meet central directory")
            central = reader.read(end["central_directory_bytes"])
            need(_sha(central) == identity["retained_directory_SHA256"], "complete directory changed")
            need(reader.position == end["eocd_offset"], "EOCD offset changed")
            tail = reader.read(EOCD.size)
            need(EOCD.unpack(tail) == (b"PK\x05\x06", 0, 0, 20, 20,
                                      end["central_directory_bytes"], end["central_directory_offset"], 0),
                 "EOCD/multivolume/comment layout changed")
            need(reader.position == initial.st_size and reader.md5.hexdigest() == identity["published_MD5"] and
                 reader.sha256.hexdigest() == expected_archive_sha256, "full archive content identity changed")
            final = os.fstat(source.fileno())
            need((initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns, initial.st_ctime_ns) ==
                 (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns),
                 "source file identity changed during extraction")
            need(len(report["members"]) == 19 and report["written_payload_bytes"] == identity["expected_expanded_bytes"],
                 "incomplete original input roster")
            _write_accounting(report)
            need(report["write_observations_complete"] and report["observed_payload_bytes"] == identity["expected_expanded_bytes"],
                 "extracted output byte observations incomplete")
            report.update(status="complete_original_input_ZIP_authenticated", archive_sha256=reader.sha256.hexdigest(),
                          archive_md5=reader.md5.hexdigest(), archive_logical_bytes_read=reader.position,
                          directory_sha256=_sha(central), bank=str(bank), scientific_preparation_complete=False)
            return report
    except BaseException as exc:
        _write_accounting(report)
        report.update(status="partial_or_refused", error=f"{type(exc).__name__}: {exc}")
        error = IntakeRefusal(report["error"])
        error.receipt = report
        raise error from exc
    finally:
        if source_fd is not None:
            os.close(source_fd)
        os.close(root_fd)
