"""One selected N063 original object, one full GET, one immutable local file.

No connection or third-party import occurs on import. The caller supplies the
unchanged, verified owner.io module and a separately selected exact Asset.
This is a single-object qualification helper, not a cohort-stage replacement.
"""
import asyncio
from dataclasses import dataclass
import hashlib
import os
import stat
import time


PARSER_RESERVATION = 7_000_000
ACCEPTED_HEADER_CAP = 32_768
PRODUCER = "neural063-original-qualification-v1"


class AcquisitionError(ValueError):
    """A failed attempt retains its cost receipt and any exclusive partial."""
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt
        self.partial_path = receipt.get("path") if receipt.get("exclusive_file_created") else None


@dataclass(frozen=True)
class AcquisitionLimits:
    response_body_bytes: int
    seconds: int
    request_seconds: int
    chunk_bytes: int = 65_536
    parser_reservation_bytes: int = PARSER_RESERVATION
    decoded_header_bytes: int = ACCEPTED_HEADER_CAP

    def validate(self):
        if any(type(v) is not int or v <= 0 for v in vars(self).values()):
            raise ValueError("positive finite integer acquisition limits required")
        if (self.chunk_bytes > 1_048_576 or self.decoded_header_bytes > ACCEPTED_HEADER_CAP
                or self.parser_reservation_bytes != PARSER_RESERVATION):
            raise ValueError("unqualified acquisition buffer/header limits")
        return self


def _one(headers, name, optional=False):
    values = headers.getall(name, [])
    if optional and not values:
        return None
    if len(values) != 1:
        raise ValueError("missing or duplicate header: " + name)
    return values[0]


def acquire(asset, output_path, meter, limits, *, owner_io):
    """Return (native_source descriptor, receipt), or a retained-failure error.

    Exactly the selected body extent and one parser allowance are reserved
    before dispatch, without refunds. Parser reservation is a conservative
    planning charge, NOT a hostile-wire byte/RAM sandbox. Final raw header
    bytes are separately measured after aiohttp parsing; interim headers,
    TLS/socket buffers and physical wire bytes are not measured here.

    aiohttp enforces one total request timeout, including streaming awaits;
    monotonic checks also cover local work. The enclosing owned-process wall
    deadline remains necessary for OS/DNS finalization or stalled file I/O.
    There are no retries, redirects, proxy/environment credentials or resume.
    """
    asset.validate()
    limits.validate()
    if asset.extent_bytes > limits.response_body_bytes:
        raise ValueError("exact full object exceeds selected body allowance")
    path = owner_io.guard_namespace(output_path)
    owner_io.ordinary(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        raise ValueError("fresh exclusive output path required")
    if meter.write_limit - meter.write_bytes < asset.extent_bytes:
        raise ValueError("complete original file write allowance required")
    # Fixed runtime compatibility: private retry disable is intentionally pinned.
    import aiohttp
    from yarl import URL
    if aiohttp.__version__ != "3.14.3":
        raise ValueError("unqualified aiohttp version")
    started = time.monotonic()
    deadline = started + limits.seconds
    rec = {"schema": "neural063-original-full-get-v1", "experiment": asset.experiment,
           "url": asset.url, "version_id": asset.version_id, "etag": asset.etag,
           "expected_bytes": asset.extent_bytes, "path": str(path), "status": "pending",
           "exclusive_file_created": False,
           "requests_admitted": 0, "response_body_reserved": 0,
           "parser_reservation_bytes": 0, "decoded_header_bytes_observed": None,
           "accepted_decoded_header_bytes": None,
           "body_bytes_observed": 0, "write_bytes_requested": 0,
           "known_written_bytes": 0, "write_custody_uncertain": False,
           "full_object_SHA256_computed": False, "full_object_BLAKE2b_verified": False,
           "retained_file_bytes": None, "source": None, "partial": None,
           "session_closed": False, "connector_closed": False, "file_closed": False,
           "physical_wire_bytes": None, "physical_os_io": None,
           "parser_reservation_is_hard_wire_bound": False}
    sha, blake = hashlib.sha256(), hashlib.blake2b()
    stream = None
    before = None
    error = None

    def check_time():
        if time.monotonic() >= deadline:
            raise TimeoutError("overall acquisition deadline exhausted")

    async def download():
        trace = aiohttp.TraceConfig()
        async def before_request(session, context, params):
            check_time()
            if (rec["requests_admitted"] != 0 or params.method != "GET"
                    or str(params.url) != asset.url
                    or _one(params.headers, "If-Match") != asset.etag
                    or _one(params.headers, "Accept-Encoding") != "identity"):
                raise ValueError("unexpected acquisition request identity")
            rec["requests_admitted"] = 1
            rec["response_body_reserved"] = asset.extent_bytes
            rec["parser_reservation_bytes"] = PARSER_RESERVATION
        trace.on_request_start.append(before_request)
        timeout = aiohttp.ClientTimeout(total=max(0.001, deadline - time.monotonic()),
            connect=limits.request_seconds, sock_connect=limits.request_seconds,
            sock_read=limits.request_seconds, ceil_threshold=limits.seconds + 1)
        # Default ssl=True validates HTTPS certificates and host names. Asset's
        # production validator admits only the exact HTTPS provider origin.
        connector = aiohttp.TCPConnector(limit=1, force_close=True, ssl=True)
        session = None
        try:
            session = aiohttp.ClientSession(connector=connector, connector_owner=True,
                trust_env=False, auto_decompress=False, timeout=timeout,
                cookie_jar=aiohttp.DummyCookieJar(), trace_configs=[trace],
                read_bufsize=65_536, max_line_size=8192, max_field_size=8192,
                max_headers=128)
            if getattr(session, "_retry_connection", None) is not True:
                raise ValueError("unqualified aiohttp retry configuration")
            session._retry_connection = False
            if session._retry_connection is not False:
                raise ValueError("cannot disable idempotent retries")
            async with session.get(URL(asset.url, encoded=True), allow_redirects=False,
                    proxy=None, headers={"Accept-Encoding": "identity", "If-Match": asset.etag}) as response:
                check_time()
                header_bytes = sum(len(k) + len(v) + 4 for k, v in response.raw_headers)
                rec["decoded_header_bytes_observed"] = header_bytes
                rec["response_status"] = response.status
                if (response.status != 200 or str(response.url) != asset.url or response.history
                        or header_bytes > limits.decoded_header_bytes):
                    raise ValueError("status/URL/history/decoded-header bound mismatch")
                if (_one(response.headers, "Content-Length") != str(asset.extent_bytes)
                        or _one(response.headers, "x-amz-version-id") != asset.version_id
                        or _one(response.headers, "ETag") != asset.etag
                        or _one(response.headers, "Content-Encoding", True) not in (None, "identity")
                        or _one(response.headers, "Transfer-Encoding", True) is not None):
                    raise ValueError("full original response identity/length/encoding mismatch")
                rec["accepted_decoded_header_bytes"] = header_bytes
                while rec["body_bytes_observed"] < asset.extent_bytes:
                    check_time()
                    count = min(limits.chunk_bytes, asset.extent_bytes - rec["body_bytes_observed"])
                    body = await response.content.read(count)
                    if not body:
                        raise ValueError("truncated complete original body")
                    rec["body_bytes_observed"] += len(body)
                    meter.write(len(body))
                    rec["write_bytes_requested"] += len(body)
                    try:
                        written = stream.write(body)
                        if written != len(body):
                            raise OSError("short original file write")
                    except BaseException:
                        rec["write_custody_uncertain"] = True
                        raise
                    rec["known_written_bytes"] += written
                    sha.update(body)
                    blake.update(body)
                    check_time()
                # Strict Content-Length controls the maintained parser. Never
                # request a speculative byte beyond the pre-reserved extent.
        finally:
            if session is not None:
                await session.close()
                rec["session_closed"] = session.closed
            else:
                await connector.close()
            rec["connector_closed"] = connector.closed

    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        rec["exclusive_file_created"] = True
        # An unbuffered writer exposes short writes immediately; no second body
        # copy or a later buffering flush is needed to know written bytes.
        try:
            stream = os.fdopen(fd, "wb", buffering=0)
        except BaseException:
            os.close(fd)
            rec["file_closed"] = True
            rec["write_custody_uncertain"] = True
            raise
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size:
            raise ValueError("fresh ordinary exclusive original required")
        asyncio.run(download())
        check_time()
        try:
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            rec["write_custody_uncertain"] = True
            raise
        check_time()
        if (rec["known_written_bytes"] != asset.extent_bytes
                or blake.hexdigest() != asset.provider_blake2b):
            raise ValueError("complete original BLAKE2b/extent mismatch")
        rec["status"] = "success"
    except BaseException as exc:
        error = exc
        rec.update(status="failed", failure_class=type(exc).__name__, failure=str(exc)[:1024])
    finally:
        if stream is not None:
            try:
                final = os.fstat(stream.fileno())
                named = owner_io.ordinary(path).stat()
                if ((final.st_dev, final.st_ino) != (before.st_dev, before.st_ino)
                        or owner_io.identity(final) != owner_io.identity(named)
                        or final.st_nlink != 1 or final.st_mode & 0o222
                        or final.st_size != rec["known_written_bytes"]):
                    rec["write_custody_uncertain"] = True
                rec["retained_file_bytes"] = final.st_size
            except BaseException as exc:
                rec["write_custody_uncertain"] = True
                if error is None:
                    error = exc
            finally:
                try:
                    stream.close()
                except BaseException as exc:
                    rec["write_custody_uncertain"] = True
                    if error is None:
                        error = exc
                rec["file_closed"] = stream.closed
        if rec["write_custody_uncertain"]:
            rec["status"] = "failed"
            rec.setdefault("failure_class", "UncertainWriteCustody")
            rec.setdefault("failure", "partial retained; no body hash or source role certified")
        elif stream is not None and rec["retained_file_bytes"] == rec["known_written_bytes"]:
            role = "native_source" if rec["status"] == "success" else "source_partial"
            descriptor = owner_io.Artifact(str(path), rec["known_written_bytes"], sha.hexdigest(),
                role, "operator", PRODUCER, "application/x-nwb" if role == "native_source" else "application/octet-stream").object()
            rec["source" if role == "native_source" else "partial"] = descriptor
            rec["known_written_sha256"] = sha.hexdigest()
            rec["known_written_blake2b_512"] = blake.hexdigest()
            if role == "native_source":
                rec["full_object_SHA256_computed"] = True
                rec["full_object_BLAKE2b_verified"] = True
        rec["elapsed_seconds"] = time.monotonic() - started
        rec["meter"] = meter.snapshot()
    if rec["status"] != "success":
        raise AcquisitionError(rec.get("failure", "original acquisition failed"), rec) from error
    return rec["source"], rec
