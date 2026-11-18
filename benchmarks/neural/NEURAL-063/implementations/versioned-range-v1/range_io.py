"""N063's explicitly weaker, version-bound NWB access alternative.

No third-party import, connection, or data access occurs at module import.
HTTP body reservations are not measurements of TLS or physical wire bytes.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import gc
import hashlib
import io
import json
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit

SUPPORTED_RUNTIME = {"aiohttp": "3.14.3", "fsspec": "2026.6.0", "h5py": "3.16.0"}


class RangeContractError(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def positive(value, name):
    if type(value) is not int or value <= 0:
        raise RangeContractError("positive integer required: " + name)
    return value


def one(headers, name, optional=False):
    pairs = headers.items() if hasattr(headers, "items") else headers
    values = [str(v) for k, v in pairs if str(k).lower() == name.lower()]
    if optional and not values:
        return None
    if len(values) != 1:
        raise RangeContractError("missing or duplicate header: " + name)
    return values[0]


@dataclass(frozen=True)
class Asset:
    experiment: str
    url: str
    version_id: str
    etag: str
    extent_bytes: int
    provider_blake2b: str

    def validate(self):
        if not re.fullmatch(r"[0-9]{1,20}", self.experiment):
            raise RangeContractError("invalid experiment identity")
        positive(self.extent_bytes, "extent")
        parsed = urlsplit(self.url)
        if (parsed.scheme != "https" or parsed.netloc !=
                "visual-behavior-ophys-data.s3.us-west-2.amazonaws.com"
                or parsed.fragment or parsed.username or parsed.password):
            raise RangeContractError("unexpected source origin")
        expected = ("/visual-behavior-ophys/behavior_ophys_experiments/"
                    "behavior_ophys_experiment_" + self.experiment + ".nwb")
        if parsed.path != expected or parse_qs(parsed.query, strict_parsing=True) != {"versionId": [self.version_id]}:
            raise RangeContractError("fixed original path/version required")
        if (not self.version_id or len(self.version_id) > 512 or
                not re.fullmatch(r'"[A-Za-z0-9-]{1,128}"', self.etag) or
                not re.fullmatch(r"[0-9a-f]{128}", self.provider_blake2b)):
            raise RangeContractError("invalid source identity fields")
        return self


@dataclass(frozen=True)
class Limits:
    max_requests: int
    response_body_bytes: int
    logical_read_bytes: int
    record_bytes: int
    block_bytes: int
    cache_blocks: int
    read_operation_bytes: int
    hdf5_cache_bytes: int
    seconds: int
    request_seconds: int

    def validate(self):
        for name, value in vars(self).items():
            positive(value, name)
        if self.block_bytes > self.read_operation_bytes:
            raise RangeContractError("block exceeds admitted logical read operation")
        return self


class Budget:
    """One shared budget across all files in a selected operation.

    A request reserves its entire declared response body and one bounded receipt
    before dispatch; failures retain these reservations. No refunds or retries.
    The response parser and TLS buffers are not a hostile-wire memory sandbox.
    """
    def __init__(self, limits):
        self.limits = limits.validate()
        self.deadline = time.monotonic() + limits.seconds
        self.requests = self.body_reserved = self.logical_reads = 0
        self.record_reserved = self.body_observed = 0
        self.records = []
        self.pending = None
        self.failed = False
        self.lock = threading.Lock()

    def check_time(self):
        if time.monotonic() >= self.deadline:
            raise RangeContractError("operation deadline exhausted")

    def begin(self, asset, method, url, headers):
        with self.lock:
            self.check_time()
            if self.failed or self.pending is not None:
                raise RangeContractError("closed or concurrent request")
            if method != "GET" or str(url) != asset.url:
                raise RangeContractError("unexpected request method or exact URL")
            if one(headers, "Accept-Encoding") != "identity" or one(headers, "If-Match") != asset.etag:
                raise RangeContractError("request identity guards missing")
            match = re.fullmatch(r"bytes=([0-9]+)-([0-9]+)", one(headers, "Range"))
            if not match:
                raise RangeContractError("explicit closed range required")
            start, end = map(int, match.groups())
            count = end - start + 1
            if (not 0 <= start <= end < asset.extent_bytes or count > self.limits.block_bytes
                    or count == asset.extent_bytes):
                raise RangeContractError("range outside admitted block/extent")
            if (self.requests + 1 > self.limits.max_requests or
                    self.body_reserved + count > self.limits.response_body_bytes or
                    self.record_reserved + 512 > self.limits.record_bytes):
                raise RangeContractError("request budget exhausted before dispatch")
            self.requests += 1
            self.body_reserved += count
            self.record_reserved += 512
            self.pending = {"experiment": asset.experiment, "start": start,
                            "end": end, "bytes": count, "headers_verified": False}

    def response(self, asset, status, url, headers, history=()):
        with self.lock:
            self.check_time()
            p = self.pending
            if p is None or p["experiment"] != asset.experiment or p["headers_verified"]:
                raise RangeContractError("response lacks unique request intent")
            if status != 206 or str(url) != asset.url or history:
                raise RangeContractError("redirect/full-body/non-range response refused")
            if (one(headers, "x-amz-version-id") != asset.version_id or
                    one(headers, "ETag") != asset.etag or
                    one(headers, "Content-Encoding", optional=True) not in (None, "identity") or
                    one(headers, "Transfer-Encoding", optional=True) is not None):
                raise RangeContractError("response source/encoding mismatch")
            if one(headers, "Content-Range") != f'bytes {p["start"]}-{p["end"]}/{asset.extent_bytes}':
                raise RangeContractError("exact response range/total mismatch")
            if one(headers, "Content-Length") != str(p["bytes"]):
                raise RangeContractError("exact response length mismatch")
            # Checked after the maintained HTTP parser, not a pre-parser wire cap.
            if sum(len(str(k).encode()) + len(str(v).encode()) + 4 for k, v in headers.items()) > 32768:
                raise RangeContractError("parsed response header allowance exceeded")
            p["headers_verified"] = True

    def body(self, asset, body):
        with self.lock:
            self.check_time()
            p = self.pending
            if (p is None or p["experiment"] != asset.experiment or
                    not p["headers_verified"] or len(body) != p["bytes"]):
                raise RangeContractError("short/extra/unbound response body")
            record = {k: p[k] for k in ("experiment", "start", "end", "bytes")}
            record.update(sha256=hashlib.sha256(body).hexdigest(), status="accepted_versioned_range")
            if len(canonical(record)) > 512:
                raise RangeContractError("range receipt size exceeded")
            self.records.append(record)
            self.body_observed += len(body)
            self.pending = None

    def logical(self, count):
        with self.lock:
            self.check_time()
            if type(count) is not int or count < 0 or count > self.limits.read_operation_bytes:
                raise RangeContractError("unbounded/oversize logical read")
            if self.logical_reads + count > self.limits.logical_read_bytes:
                raise RangeContractError("logical read budget exhausted")
            self.logical_reads += count

    def abort(self):
        with self.lock:
            self.failed = True

    def receipt(self):
        return {"requests_admitted": self.requests,
                "response_body_bytes_reserved_including_failures": self.body_reserved,
                "complete_response_body_bytes_observed": self.body_observed,
                "logical_bytes_requested": self.logical_reads,
                "range_receipt_bytes_reserved": self.record_reserved,
                "unresolved_request": self.pending,
                "failed": self.failed, "ranges": self.records,
                "full_object_BLAKE2b_verified": False,
                "physical_wire_bytes": None,
                "wire_limit_scope": "HTTP response-body reservations only; TLS/header/parser/kernel overhead unmeasured"}


class BoundedFile(io.RawIOBase):
    """Do not expose fsspec's read(-1)/whole-file fallback to h5py."""
    def __init__(self, stream, asset, budget):
        self.stream, self.asset, self.budget = stream, asset, budget
    def readable(self): return True
    def seekable(self): return True
    def writable(self): return False
    def tell(self): return self.stream.tell()
    def seek(self, offset, whence=0):
        if type(offset) is not int or whence not in (0, 1, 2):
            raise RangeContractError("invalid seek")
        base = 0 if whence == 0 else self.tell() if whence == 1 else self.asset.extent_bytes
        target = base + offset
        if not 0 <= target <= self.asset.extent_bytes:
            raise RangeContractError("seek outside original extent")
        return self.stream.seek(target)
    def read(self, size=-1):
        if type(size) is not int or size < 0 or size > self.budget.limits.read_operation_bytes:
            raise RangeContractError("explicit bounded read length required")
        count = min(size, self.asset.extent_bytes - self.tell())
        self.budget.logical(count)
        body = self.stream.read(count)
        if len(body) != count:
            raise RangeContractError("short logical read")
        return body
    def readinto(self, buffer):
        body = self.read(len(buffer))
        buffer[:len(body)] = body
        return len(body)


def clipped_fetch(fetcher, extent):
    """BlockCache's final block may extend past EOF; close that range first."""
    def fetch(start, end):
        if not 0 <= start < extent or end <= start:
            raise RangeContractError("invalid cache fetch")
        return fetcher(start, min(end, extent))
    return fetch


def configure_cache(stream, asset, limits):
    if (stream.cache.name != "blockcache" or stream.cache.maxblocks != limits.cache_blocks
            or stream.cache.blocksize != limits.block_bytes):
        raise RangeContractError("unexpected maintained cache")
    stream.cache.fetcher = clipped_fetch(stream.cache.fetcher, asset.extent_bytes)


def close_runtime(stream, close_session):
    try:
        if stream is not None:
            cache = stream.cache
            try:
                stream.close()
            finally:
                cache._fetch_block_cached.cache_clear()
    finally:
        close_session()


@contextmanager
def open_versioned(asset, budget, runtime_versions):
    """Maintained reader for explicitly selected operations or generated controls."""
    from importlib.metadata import version
    if runtime_versions != SUPPORTED_RUNTIME:
        raise RangeContractError("unreviewed maintained-reader versions")
    for distribution in ("aiohttp", "fsspec", "h5py"):
        if version(distribution) != runtime_versions[distribution]:
            raise RangeContractError("runtime version differs: " + distribution)
    import aiohttp
    import h5py
    from fsspec.implementations.http import HTTPFileSystem
    from fsspec.asyn import sync

    asset.validate()
    fs = stream = None
    trace = aiohttp.TraceConfig()
    async def before(session, context, params):
        budget.begin(asset, params.method, params.url, params.headers)
    async def checked(response):
        budget.response(asset, response.status, response.url, response.headers, response.history)
    async def body(session, context, params):
        budget.body(asset, params.chunk)
    async def failed(session, context, params):
        budget.abort()
    trace.on_request_start.append(before)
    trace.on_response_chunk_received.append(body)
    trace.on_request_exception.append(failed)

    async def client(**kwargs):
        session = aiohttp.ClientSession(**kwargs)
        # Pinned aiohttp compatibility dependency: default idempotent retry sits
        # inside one on_request_start callback and would escape attempt counting.
        if getattr(session, "_retry_connection", None) is not True:
            await session.close()
            raise RangeContractError("unqualified aiohttp retry configuration")
        session._retry_connection = False
        return session

    try:
        budget.check_time()
        fs = HTTPFileSystem(encoded=True, skip_instance_cache=True,
            block_size=budget.limits.block_bytes, cache_type="blockcache",
            cache_options={"maxblocks": budget.limits.cache_blocks},
            allow_redirects=False,
            headers={"Accept-Encoding": "identity", "If-Match": asset.etag},
            get_client=client,
            client_kwargs={"auto_decompress": False, "trust_env": False,
                "raise_for_status": checked, "trace_configs": [trace],
                "timeout": aiohttp.ClientTimeout(total=budget.limits.request_seconds),
                "read_bufsize": 65536, "max_line_size": 8192, "max_field_size": 8192})
        stream = fs.open(asset.url, "rb", size=asset.extent_bytes,
                         block_size=budget.limits.block_bytes,
                         cache_type="blockcache", cache_options={"maxblocks": budget.limits.cache_blocks})
        configure_cache(stream, asset, budget.limits)
        bounded = BoundedFile(stream, asset, budget)
        # h5py documents that service-thread cyclic GC can deadlock against its
        # global lock during file-object callbacks. The operator uses a serial,
        # dedicated process: suspend process-global cyclic GC through HDF5 close
        # and preserve the entering state. Never collect on the service thread.
        gc_was_enabled = gc.isenabled()
        if gc_was_enabled:
            gc.disable()
        try:
            with h5py.File(bounded, "r", rdcc_nbytes=budget.limits.hdf5_cache_bytes) as file:
                yield file
        finally:
            if gc_was_enabled:
                gc.enable()
        if budget.pending is not None or budget.failed:
            raise RangeContractError("unclosed or failed range request")
    except BaseException:
        budget.abort()
        raise
    finally:
        # h5py context closes before the Python file object/session.
        def close_session():
            if fs is not None and fs._session is not None:
                sync(fs.loop, fs._session.close)
        close_runtime(stream, close_session)
