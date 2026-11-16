"""One complete DOI release; bounded bytes, no fit and no candidate-visible answers."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import time
import urllib.error
import urllib.request
import zipfile
import zlib


def require(ok, why):
    if not ok:
        raise ValueError(why)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def ordinary(path):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), "no path aliases")
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "ordinary single-link file")
    return s


class Budget:
    """Counts direct application reads/writes, not native allocations or OS paging."""
    def __init__(self, root, deadline, read_limit=32 * 1024**2, write_limit=15 * 1024**2):
        self.root = Path(root)
        self.deadline = deadline
        self.read_limit, self.write_limit = read_limit, write_limit
        self.read_bytes = self.write_bytes = 0
        self.outputs = []

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("original complete-operation work deadline")

    @property
    def remaining_read(self):
        return self.read_limit - self.read_bytes

    def charge_read(self, n):
        self.check()
        require(type(n) is int and 0 <= n <= self.remaining_read, "application-read ceiling")
        self.read_bytes += n

    def charge_write(self, n):
        self.check()
        require(type(n) is int and 0 <= n <= self.write_limit - self.write_bytes,
                "new retained-output ceiling")
        self.write_bytes += n

    def write_json(self, name, value):
        require(Path(name).name == name and name not in ("", ".", ".."), "literal receipt basename")
        data = (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\n").encode()
        require(len(data) <= 2 * 1024**2, "single census receipt ceiling")
        self.charge_write(len(data))
        path = self.root / name
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                               0o600), "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        pin = {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.outputs.append(pin)
        return pin


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()
        raise ValueError("DOI archive redirect refused")

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def acquire(ledger, budget, *, opener=None):
    """Exactly one GET. Preserve partial bytes and transport outcome on failure."""
    expected = ledger["archive_bytes"]
    url = ledger["archive_url"]
    require(url == "https://doi.gin.g-node.org/10.12751/g-node.xzmv31/10.12751_g-node.xzmv31.zip",
            "exact selected DOI source")
    require(type(expected) is int and expected == 3015691, "complete release extent")
    require(budget.remaining_read >= expected + 1, "pre-admit complete response plus EOF probe")
    budget.check()
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers={"If-Match": ledger["archive_http_etag"],
        "Accept-Encoding": "identity", "User-Agent": "Findlay-complete-census/1"})
    path = budget.root / "release.zip.partial"
    sha = hashlib.sha256()
    seen = 0
    received = 0
    failed = False
    response = None
    receipt = {"url": url, "method": "GET", "if_match": ledger["archive_http_etag"],
               "attempts": 1, "etag_is_opaque_not_sha256": True, "complete": False}
    try:
        response = opener.open(request, timeout=max(.001, min(20, budget.deadline-time.monotonic())))
        headers = list(response.headers.items())
        require(sum(len(str(k))+len(str(v)) for k, v in headers) <= 32768,
                "decoded response-header ceiling (not wire-level)")
        receipt.update(status=response.status, final_url=response.geturl(), headers=headers)
        require(response.status == 200 and response.geturl() == url, "one exact full response")
        require(response.headers.get("Content-Length") == str(expected), "complete content length")
        require(response.headers.get("ETag") == ledger["archive_http_etag"], "selected representation")
        require(len(response.headers.get_all("Content-Length", [])) == 1
                and len(response.headers.get_all("ETag", [])) == 1, "unambiguous representation headers")
        require(response.headers.get("Content-Encoding", "identity").lower() == "identity",
                "no HTTP content transformation")
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                               0o600), "wb") as out:
            while True:
                budget.check()
                block = response.read(min(65536, expected-seen+1))
                budget.charge_read(len(block))
                received += len(block)
                if not block:
                    break
                require(seen + len(block) <= expected, "response exceeds selected release")
                budget.charge_write(len(block))
                out.write(block)
                sha.update(block)
                seen += len(block)
            out.flush()
            os.fsync(out.fileno())
        require(seen == expected, "short complete release")
        budget.check()
        require(not (budget.root / "release.zip").exists(), "exclusive final archive")
        os.chmod(path, 0o400)
        path.rename(budget.root / "release.zip")
        receipt["complete"] = True
    except BaseException as exc:
        failed = True
        if isinstance(exc, urllib.error.HTTPError):
            receipt.update(status=exc.code, response_body_read=False)
            exc.close()
        receipt["failure"] = {"type": type(exc).__name__, "message": str(exc)[:2048]}
        raise
    finally:
        if response is not None:
            response.close()
        receipt.update(response_body_bytes=received, retained_body_bytes=seen,
                       retained_body_sha256=sha.hexdigest())
        # If the work deadline already elapsed, the owner records the refusal;
        # partial bytes remain even when this cooperative write cannot complete.
        try:
            budget.write_json("HTTP.private.json", receipt)
        except BaseException:
            if not failed:
                raise
    return budget.root / "release.zip"


def read_all(path, budget, cap):
    before = ordinary(path)
    require(before.st_size <= cap, "bounded stored input")
    require(budget.remaining_read >= before.st_size, "pre-admit stored input read")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
        require(identity(os.fstat(f.fileno())) == identity(before), "opened input identity")
        data = f.read(before.st_size + 1)
        budget.charge_read(len(data))
        require(identity(os.fstat(f.fileno())) == identity(before), "input unchanged while read")
    require(identity(ordinary(path)) == identity(before) and len(data) == before.st_size,
            "stored input stable extent")
    return data


def directory(data, ledger):
    """Validate entire classic stored archive before creating any extracted member."""
    require(len(data) == ledger["archive_bytes"] and len(data) >= 22, "archive exact size")
    eocd = data.rfind(b"PK\x05\x06", max(0, len(data)-65557))
    require(eocd >= 0 and eocd + 22 <= len(data), "complete ZIP end record")
    sig, disk, c_disk, n_disk, count, cd_size, cd_start, comment = struct.unpack_from("<4s4H2IH", data, eocd)
    require(disk == c_disk == 0 and n_disk == count == len(ledger["members"]) == 17,
            "exact single-volume 17-member ZIP")
    require(comment == 0 and eocd + 22 == len(data) and cd_start + cd_size == eocd,
            "no ZIP64, trailing bytes or hidden directory")
    require(data[max(0, eocd-20):eocd][:4] != b"PK\x06\x07", "no ZIP64 end locator")
    expected = {m["path"]: m for m in ledger["members"]}
    require(len(expected) == 17, "unique complete expected member list")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        require(len(infos) == 17 and len({i.filename for i in infos}) == 17, "unique exact entries")
        require({i.filename for i in infos} == set(expected), "all and only selected members")
        spans = []
        for i in infos:
            m = expected[i.filename]
            require(Path(i.filename).name == i.filename and i.filename not in ("", ".", "..")
                    and "\\" not in i.filename and "\0" not in i.filename,
                    "literal safe release filename")
            require(i.compress_type == m["zip_method"] == 0 and i.flag_bits == 8,
                    "stored nonencrypted descriptor archive")
            require(i.file_size == i.compress_size == m["bytes"] == m["zip_compressed_bytes"]
                    and i.CRC == int(m["zip_crc32"], 16), "central exact size and CRC")
            require(i.create_system == 3 and i.external_attr >> 16 == int(m["unix_mode"], 8)
                    and stat.S_ISREG(i.external_attr >> 16), "ordinary selected member mode")
            start = i.header_offset
            require(0 <= start <= cd_start - 30, "local header extent")
            fields = struct.unpack_from("<4s5H3I2H", data, start)
            signature, version, flags, method, tm, dt, crc, packed, size, name_n, extra_n = fields
            require(signature == b"PK\x03\x04" and flags == i.flag_bits and method == 0,
                    "local/central method and flags")
            require(crc in (0, i.CRC) and packed in (0, i.compress_size) and size in (0, i.file_size),
                    "valid deferred local fields")
            require(name_n <= 256 and extra_n <= 4096, "bounded local fields")
            payload = start + 30 + name_n + extra_n
            require(payload + i.file_size + 12 <= cd_start, "complete local payload/descriptor")
            require(data[start+30:start+30+name_n] == i.filename.encode("utf-8"), "exact local name")
            # Both classic descriptor encodings have a known exact payload end;
            # no scanning for a signature inside data, and no ZIP64 fallback.
            end = payload+i.file_size
            signed = data[end:end+4] == b"PK\x07\x08"
            descriptor_start = end + (4 if signed else 0)
            require(descriptor_start + 12 <= cd_start, "complete data descriptor")
            descriptor = struct.unpack_from("<3I", data, descriptor_start)
            require(descriptor == (i.CRC, i.compress_size, i.file_size), "exact data descriptor")
            spans.append((start, descriptor_start+12, i.filename, payload))
        spans.sort()
        require(spans[0][0] == 0 and spans[-1][1] == cd_start
                and all(a[1] == b[0] for a, b in zip(spans, spans[1:])),
                "all local spans contiguous, unique and nonoverlapping")
        require(sum(i.file_size for i in infos) == ledger["expanded_bytes"], "complete expanded sum")
        return spans


def extract_verify(path, ledger, budget):
    data = read_all(path, budget, ledger["archive_bytes"])
    spans = directory(data, ledger)
    root = budget.root / "members"
    root.mkdir(mode=0o700)
    expected = {m["path"]: m for m in ledger["members"]}
    pins = []
    for _, _, name, offset in spans:
        budget.check()
        m = expected[name]
        body = data[offset:offset+m["bytes"]]
        require(zlib.crc32(body) & 0xffffffff == int(m["zip_crc32"], 16), "complete member CRC")
        budget.charge_write(len(body))
        target = root / name
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                               0o400), "wb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        sha = hashlib.sha256(body).hexdigest()
        independently_read = read_all(target, budget, m["bytes"])
        require(hashlib.sha256(independently_read).hexdigest() == sha, "stored-byte hash parity")
        if name.endswith(".pqt"):
            require(independently_read[:4] == independently_read[-4:] == b"PAR1", "Parquet magic")
            n = struct.unpack_from("<I", independently_read, len(independently_read)-8)[0]
            require(0 < n <= len(independently_read)-12, "bounded complete Parquet footer")
            require(hashlib.sha256(independently_read[-8-n:-8]).hexdigest() == m["footer_sha256"],
                    "exact previously inspected Parquet footer")
        pins.append({"path": str(target), "name": name, "bytes": len(body), "sha256": sha,
                     "zip_crc32": m["zip_crc32"], "stored_byte_recheck": True})
    result = {"archive": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
              "members": sorted(pins, key=lambda p: p["name"]), "complete": True,
              "provider_sha256_available": False, "scientific_qualification": False}
    return root, budget.write_json("INTEGRITY.private.json", result)
