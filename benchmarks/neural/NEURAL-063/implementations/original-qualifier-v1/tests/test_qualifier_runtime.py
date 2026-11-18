"""Generated-only full-file acquisition and same-file scientific qualification.

The caller supplies an immutable invented HDF5 fixture and pinned old source
roots. No original/provider origin is permitted by this test process.
"""
import argparse
from contextlib import contextmanager
import faulthandler
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock


SOURCE = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(SOURCE))
import acquire_original
import qualifier

ARGS = None
BODY_CAP = 4 * 1024 * 1024
HEADER_CAP = 128 * 1024
RESULT_CAP = 65536
TRACE_CAP = 32768
FIXTURE_SHA = "56e99301faa09b2ef4f583e75a200d5473193d87a2b57f7dde1146f837b94a72"
FIXTURE_BLAKE = "2db4aab872be3c4e92b62312b48ef107e2a33698ffe519ef0151a95bc1c28cc09c1c3e3c21e5db62a696b2cda526ee15b8bd20e2628a9242615d0aeab95c0c50"


def descriptor(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class FixtureServer(HTTPServer):
    allow_reuse_address = False
    def __init__(self, case, mode):
        self.case, self.mode = case, mode
        self.requests, self.errors = [], []
        self.body_reserved = self.body_written = 0
        self.header_reserved = self.header_written = 0
        super().__init__(("127.0.0.1", 0), FixtureHandler)

    def handle_error(self, request, client_address):
        self.errors.append(type(sys.exc_info()[1]).__name__)


class FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def setup(self):
        self.request.settimeout(3)
        super().setup()

    def log_message(self, *args):
        pass

    def flush_headers(self):
        count = sum(len(part) for part in self._headers_buffer)
        case = self.server.case
        with case.lock:
            if case.header_reserved + count > HEADER_CAP:
                raise AssertionError("generated aggregate response-header cap")
            case.header_reserved += count
            self.server.header_reserved += count
        super().flush_headers()
        self.server.header_written += count
        with case.lock:
            case.header_written += count

    def do_HEAD(self):
        self.server.errors.append("unexpected_HEAD")
        self.send_error(405)
        self.close_connection = True

    def do_GET(self):
        case, mode = self.server.case, self.server.mode
        request = {"method": "GET", "path": self.path, "range": self.headers.get("Range"),
                   "if_match": self.headers.get("If-Match"),
                   "accept_encoding": self.headers.get("Accept-Encoding")}
        self.server.requests.append(request)
        if (self.path != case.URL_PATH or self.headers.get("If-Match") != case.ETAG
                or self.headers.get("Accept-Encoding") != "identity"):
            self.server.errors.append("request_identity_mismatch")
            self.send_error(400)
            self.close_connection = True
            return
        if mode == "disconnect":
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if request["range"] is None:
            status, body, expected = 200, case.fixture, len(case.fixture)
            start = end = None
        else:
            match = re.fullmatch(r"bytes=([0-9]+)-([0-9]+)", request["range"])
            if not match:
                self.server.errors.append("malformed_range")
                self.close_connection = True
                return
            start, end = map(int, match.groups())
            if not 0 <= start <= end < len(case.fixture):
                self.server.errors.append("out_of_extent_range")
                self.close_connection = True
                return
            status, expected = 206, end - start + 1
            body = case.fixture[start:end + 1]
        if mode == "redirect":
            status = 302
        if mode == "short":
            body = body[:len(body) // 2]
        if mode == "deadline":
            body = body[:20]
        with case.lock:
            if case.body_reserved + len(body) > BODY_CAP:
                self.server.errors.append("aggregate_body_cap")
                self.close_connection = True
                return
            case.body_reserved += len(body)
            self.server.body_reserved += len(body)
        self.send_response(status)
        self.send_header("Content-Length", str(expected + 1 if mode == "length" else expected))
        if mode == "duplicate_length":
            self.send_header("Content-Length", str(expected))
        self.send_header("x-amz-version-id", "wrong" if mode == "version" else case.VERSION)
        if mode == "duplicate_version":
            self.send_header("x-amz-version-id", case.VERSION)
        self.send_header("ETag", '"wrong"' if mode == "etag" else case.ETAG)
        self.send_header("Content-Encoding", "gzip" if mode == "encoding" else "identity")
        if mode == "transfer":
            self.send_header("Transfer-Encoding", "chunked")
        if mode == "redirect":
            self.send_header("Location", "https://example.invalid/never-follow")
        if mode == "headers":
            for i in range(6):
                self.send_header("X-Generated-" + str(i), "x" * 7000)
        if start is not None:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(case.fixture)}")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            chunks = [bytes([value]) for value in body] if mode == "deadline" else [body]
            for part in chunks:
                self.wfile.write(part)
                self.wfile.flush()
                self.server.body_written += len(part)
                with case.lock:
                    case.body_written += len(part)
                if mode == "deadline":
                    time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.close_connection = True


class GeneratedControls(unittest.TestCase):
    VERSION = "generated+version/one="
    ETAG = '"generated-fixture-etag"'
    URL_PATH = "/generated.nwb?versionId=generated%2Bversion%2Fone%3D"
    allowed = set()
    lock = threading.Lock()
    body_reserved = body_written = 0
    header_reserved = header_written = 0
    evidence = []

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ARGS.range_source))
        import pipeline
        import range_io
        import aiohttp
        import fsspec.asyn
        import h5py
        cls.range, cls.aiohttp, cls.asyn = range_io, aiohttp, fsspec.asyn
        if (aiohttp.__version__, h5py.__version__, fsspec.__version__) != ("3.14.3", "3.16.0", "2026.6.0"):
            raise AssertionError("selected maintained runtime required")
        if fsspec.asyn.loop[0] is not None or fsspec.asyn.iothread[0] is not None:
            raise AssertionError("dedicated process with no pre-existing service loop required")
        pins = json.loads((ARGS.range_source / "ORIGINAL_SOURCES.json").read_text())["files"]
        native, alg, owner_io = pipeline.load_original(ARGS.original_root, pins)
        cls.deps = SimpleNamespace(native=native, alg=alg, io=owner_io, range=range_io, pipeline=pipeline)
        cls.fixture_path = owner_io.ordinary(ARGS.fixture)
        cls.fixture = owner_io.capture(cls.fixture_path, 128 * 1024)
        if (len(cls.fixture) != 25721 or hashlib.sha256(cls.fixture).hexdigest() != FIXTURE_SHA
                or hashlib.blake2b(cls.fixture).hexdigest() != FIXTURE_BLAKE
                or cls.fixture_path.stat().st_mode & 0o222):
            raise AssertionError("exact immutable invented fixture required")
        cls.row = {"ophys_experiment_id": "1", "ophys_session_id": "2", "mouse_id": "3", "split": "query",
                   "rois": [{"cell_roi_id": "101", "cell_specimen_id": "1001"},
                            {"cell_roi_id": "103", "cell_specimen_id": "1003"}],
                   "context": {name: "generated" for name in alg.CONTEXT}}
        real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
        def connect(sock, address):
            if address not in cls.allowed:
                raise AssertionError("connection outside exact generated loopback origin")
            return real_connect(sock, address)
        def connect_ex(sock, address):
            if address not in cls.allowed:
                raise AssertionError("connection outside exact generated loopback origin")
            return real_connect_ex(sock, address)
        for name, replacement in [("connect", connect), ("connect_ex", connect_ex)]:
            patch = mock.patch.object(socket.socket, name, replacement)
            patch.start()
            cls.addClassCleanup(patch.stop)
        cls.addClassCleanup(cls.close_owned_loop)

    @classmethod
    def close_owned_loop(cls):
        loop, thread = cls.asyn.loop[0], cls.asyn.iothread[0]
        if loop is not None:
            if thread is None:
                raise AssertionError("service loop lacks owned thread")
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=5)
            if thread.is_alive():
                raise AssertionError("owned fsspec loop failed to stop")
            loop.close()
            cls.asyn.loop[0] = cls.asyn.iothread[0] = None

    def make_limits(self, mode):
        return acquire_original.AcquisitionLimits(response_body_bytes=len(self.fixture),
            seconds=1 if mode == "deadline" else 10, request_seconds=3, chunk_bytes=4096)

    def make_range_budget(self):
        return self.range.Budget(self.range.Limits(max_requests=128,
            response_body_bytes=512 * 1024, logical_read_bytes=2 * 1024 * 1024,
            record_bytes=65536, block_bytes=4096, cache_blocks=4,
            read_operation_bytes=128 * 1024, hdf5_cache_bytes=8192, seconds=30, request_seconds=5))

    @contextmanager
    def served(self, mode, *, wrong_blake=False):
        cls = type(self)
        server = FixtureServer(cls, mode)
        address = server.server_address
        cls.allowed.add(address)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02},
                                  name="n063-qualifier-generated-server")
        thread.start()
        asset = self.range.Asset("1", "http://127.0.0.1:" + str(address[1]) + self.URL_PATH,
            self.VERSION, self.ETAG, len(self.fixture), "0" * 128 if wrong_blake else FIXTURE_BLAKE)
        def validate_exact(value):
            if value != asset:
                raise AssertionError("generated origin override permits only the selected exact fixture")
            return value
        sessions, connectors, streams, caches = [], [], [], []
        real_session, real_configure = self.aiohttp.ClientSession, self.range.configure_cache
        def session(*args, **kwargs):
            value = real_session(*args, **kwargs)
            sessions.append(value)
            connectors.append(value.connector)
            return value
        def configured(stream, selected, limits):
            real_configure(stream, selected, limits)
            streams.append(stream)
            caches.append(stream.cache)
        try:
            with mock.patch.object(self.range.Asset, "validate", validate_exact), \
                    mock.patch.object(self.aiohttp, "ClientSession", session), \
                    mock.patch.object(self.range, "configure_cache", configured):
                yield SimpleNamespace(asset=asset, server=server)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            cls.allowed.remove(address)
            self.assertFalse(thread.is_alive())
            self.assertTrue(all(x.closed for x in sessions))
            self.assertTrue(all(x.closed for x in connectors))
            self.assertTrue(all(x.closed for x in streams))
            self.assertTrue(all(x._fetch_block_cached.cache_info().currsize == 0 for x in caches))
            self.assertEqual(server.errors, [])
            self.assertLessEqual(cls.body_reserved, BODY_CAP)
            self.assertLessEqual(cls.header_reserved, HEADER_CAP)

    def save_case(self, name, selected, receipt, **extra):
        self.evidence.append({"case": name, "acquisition": receipt,
            "server_requests": len(selected.server.requests),
            "server_body_reserved": selected.server.body_reserved,
            "server_complete_body_writes": selected.server.body_written,
            "server_response_headers_reserved": selected.server.header_reserved,
            "server_complete_response_headers_written": selected.server.header_written,
            "owned_server_client_stream_cache_cleanup": True, **extra})

    def test_01_acquire_and_same_original_comparison(self):
        root = ARGS.evidence_root / "positive"
        root.mkdir(mode=0o700)
        meter = self.deps.io.ByteMeter(4 * 1024 * 1024, 128 * 1024)
        store = self.deps.io.ArtifactStore(root, meter)
        profile = {"metadata_artifact_bytes": 32768, "projection_artifact_bytes": 32768,
            "comparison_artifact_bytes": 8192, "max_presentation_tables": 16,
            "max_fixed_metadata_bytes": 128 * 1024, "max_numeric_chunk_bytes": 128 * 1024,
            "max_dff_slice_bytes": 128 * 1024, "max_supported_omissions": 100,
            "runtime_versions": self.range.SUPPORTED_RUNTIME}
        ranges = self.make_range_budget()
        with self.served("ok") as selected:
            ref, rec = acquire_original.acquire(selected.asset, root / "original.nwb", meter,
                self.make_limits("ok"), owner_io=self.deps.io)
            self.assertEqual(ref["sha256"], FIXTURE_SHA)
            self.assertEqual(ref["bytes"], len(self.fixture))
            self.assertEqual(rec["write_bytes_requested"], len(self.fixture))
            self.assertTrue(rec["full_object_BLAKE2b_verified"])
            self.assertTrue(rec["session_closed"] and rec["connector_closed"] and rec["file_closed"])
            local_refusals = []
            for name, value in (("max_numeric_chunk_bytes", 1), ("max_supported_omissions", 1)):
                refused_root = root / ("refuse_" + name)
                refused_root.mkdir(mode=0o700)
                refused_store = self.deps.io.ArtifactStore(refused_root, meter)
                refused_ranges = self.make_range_budget()
                bounded_profile = dict(profile, **{name: value})
                requests_before = len(selected.server.requests)
                writes_before = meter.write_bytes
                with self.assertRaises(qualifier.QualificationError):
                    qualifier.qualify(selected.asset, ref, self.row, deps=self.deps,
                        store=refused_store, ranges=refused_ranges, profile=bounded_profile)
                self.assertEqual(list(refused_root.iterdir()), [])
                self.assertEqual(getattr(refused_store, "qualification_artifacts", []), [])
                self.assertEqual(meter.write_bytes, writes_before)
                self.assertEqual(refused_ranges.requests, 0)
                self.assertEqual(len(selected.server.requests), requests_before)
                local_refusals.append({"limit": name, "value": value, "range_requests": 0,
                                       "additional_gets": 0, "artifact_writes": 0})
            report_ref = qualifier.qualify(selected.asset, ref, self.row,
                deps=self.deps, store=store, ranges=ranges, profile=profile)
            report = json.loads(Path(report_ref["path"]).read_text())
            self.assertEqual(report["disposition"], "same_original_projection_equivalence")
            self.assertEqual((report["compared_supported_omissions"], report["compared_native_bins"]), (2, 30))
            self.assertTrue(report["projection_equivalence_qualified"])
            self.assertFalse(report["range_full_object_BLAKE2b_verified"])
            self.assertFalse(report["all_plane_session_consensus_established"])
            self.assertFalse(report["full_cohort_scientific_equivalence_qualified"])
            metadata = json.loads((root / "local_metadata.json").read_text())
            self.assertEqual(metadata["support"]["supported"], 2)
            self.assertEqual(metadata["layout_admission"]["decoded_variable_length_heap_bytes"], None)
            self.assertEqual(len(selected.server.requests), 1 + ranges.requests)
            self.assertIsNone(selected.server.requests[0]["range"])
        self.save_case("full_get_then_exact_original_comparison", selected, rec,
            report=report_ref, range_receipt=ranges.receipt(), final_meter=meter.snapshot(),
            local_resource_refusals=local_refusals)

    def refuse(self, mode, *, wrong_blake=False, writer=None):
        name = "wrong_blake" if wrong_blake else (writer or mode)
        meter = self.deps.io.ByteMeter(0, len(self.fixture))
        path = ARGS.evidence_root / (name + ".partial.nwb")
        with self.served(mode, wrong_blake=wrong_blake) as selected:
            if writer:
                original_fdopen = acquire_original.os.fdopen
                class BadWriter:
                    def __init__(self, stream): self.stream = stream
                    def write(self, body):
                        if writer == "short_write":
                            return self.stream.write(body[:max(1, len(body) // 2)])
                        raise OSError("invented writer failure")
                    def __getattr__(self, name): return getattr(self.stream, name)
                def opened(*args, **kwargs): return BadWriter(original_fdopen(*args, **kwargs))
                context = mock.patch.object(acquire_original.os, "fdopen", opened)
            else:
                context = mock.patch.dict({}, {})
            with context:
                with self.assertRaises(acquire_original.AcquisitionError) as caught:
                    acquire_original.acquire(selected.asset, path, meter, self.make_limits(mode), owner_io=self.deps.io)
            rec = caught.exception.receipt
            self.assertEqual(len(selected.server.requests), 1, "failed GET must never retry")
            self.assertEqual(rec["requests_admitted"], 1)
            self.assertEqual(rec["response_body_reserved"], len(self.fixture))
            self.assertEqual(rec["parser_reservation_bytes"], 7_000_000)
            self.assertIsNone(rec["source"])
            self.assertFalse(rec["full_object_BLAKE2b_verified"])
            self.assertTrue(path.is_file())
            self.assertFalse(path.stat().st_mode & 0o222)
            self.assertTrue(rec["session_closed"] and rec["connector_closed"] and rec["file_closed"])
            if writer:
                self.assertTrue(rec["write_custody_uncertain"])
                self.assertIsNone(rec["partial"])
                self.assertNotIn("known_written_sha256", rec)
            else:
                self.assertFalse(rec["write_custody_uncertain"])
                self.assertEqual(rec["partial"]["role"], "source_partial")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), rec["partial"]["sha256"])
            if mode == "deadline":
                self.assertEqual(rec["failure_class"], "TimeoutError")
                self.assertLess(rec["elapsed_seconds"], 3.0)
                self.assertGreater(rec["body_bytes_observed"], 0)
            if wrong_blake:
                self.assertEqual(rec["known_written_bytes"], len(self.fixture))
        self.save_case(name, selected, rec)

    def test_02_identity_headers_and_redirect_refusals(self):
        for mode in ("version", "etag", "length", "duplicate_length", "duplicate_version",
                     "encoding", "transfer", "headers", "redirect"):
            with self.subTest(mode=mode):
                self.refuse(mode)

    def test_03_transport_failure_and_total_deadline(self):
        for mode in ("short", "disconnect", "deadline"):
            with self.subTest(mode=mode):
                self.refuse(mode)

    def test_04_hash_and_uncertain_writer_failures(self):
        self.refuse("ok", wrong_blake=True)
        for writer in ("short_write", "write_error"):
            with self.subTest(writer=writer):
                self.refuse("ok", writer=writer)

    def test_05_production_origin_and_exclusive_output(self):
        path = ARGS.evidence_root / "must_not_exist.nwb"
        asset = self.range.Asset("1", "http://127.0.0.1:1" + self.URL_PATH,
            self.VERSION, self.ETAG, len(self.fixture), FIXTURE_BLAKE)
        meter = self.deps.io.ByteMeter(0, len(self.fixture))
        with self.assertRaises(self.range.RangeContractError):
            acquire_original.acquire(asset, path, meter, self.make_limits("ok"), owner_io=self.deps.io)
        self.assertFalse(path.exists())
        with self.served("ok") as selected:
            with self.assertRaises(ValueError):
                acquire_original.acquire(selected.asset, self.fixture_path, meter,
                    self.make_limits("ok"), owner_io=self.deps.io)
            for reservation in (6_999_999, 7_000_001):
                bad_limits = acquire_original.AcquisitionLimits(len(self.fixture), 10, 3,
                    parser_reservation_bytes=reservation)
                with self.assertRaises(ValueError):
                    acquire_original.acquire(selected.asset, path, meter, bad_limits, owner_io=self.deps.io)
            original_open = acquire_original.os.open
            race_path = ARGS.evidence_root / "raced_creation.nwb"
            def raced_open(target, *args, **kwargs):
                if Path(target) == race_path:
                    raise FileExistsError("invented exclusive-create race")
                return original_open(target, *args, **kwargs)
            with mock.patch.object(acquire_original.os, "open", raced_open):
                with self.assertRaises(acquire_original.AcquisitionError) as raced:
                    acquire_original.acquire(selected.asset, race_path, meter,
                        self.make_limits("ok"), owner_io=self.deps.io)
            self.assertFalse(raced.exception.receipt["exclusive_file_created"])
            self.assertIsNone(raced.exception.partial_path)
            self.assertIsNone(raced.exception.receipt["source"])
            self.assertIsNone(raced.exception.receipt["partial"])
            self.assertEqual(raced.exception.receipt["requests_admitted"], 0)
            created_fds = []
            failed_open_path = ARGS.evidence_root / "failed_fdopen.nwb"
            def capture_open(target, *args, **kwargs):
                fd = original_open(target, *args, **kwargs)
                if Path(target) == failed_open_path:
                    created_fds.append(fd)
                return fd
            with mock.patch.object(acquire_original.os, "open", capture_open), \
                    mock.patch.object(acquire_original.os, "fdopen", side_effect=OSError("invented fdopen failure")):
                with self.assertRaises(acquire_original.AcquisitionError) as failed:
                    acquire_original.acquire(selected.asset, failed_open_path, meter,
                        self.make_limits("ok"), owner_io=self.deps.io)
            self.assertEqual(len(created_fds), 1)
            with self.assertRaises(OSError):
                os.fstat(created_fds[0])
            self.assertTrue(failed.exception.receipt["exclusive_file_created"])
            self.assertTrue(failed.exception.receipt["file_closed"])
            self.assertTrue(failed.exception.receipt["write_custody_uncertain"])
            self.assertEqual(failed.exception.partial_path, str(failed_open_path))
            self.assertIsNone(failed.exception.receipt["source"])
            self.assertIsNone(failed.exception.receipt["partial"])
            self.assertNotIn("known_written_sha256", failed.exception.receipt)
            self.assertEqual(failed.exception.receipt["requests_admitted"], 0)
            self.assertEqual(selected.server.requests, [])
        self.assertEqual(meter.write_bytes, 0)
        self.evidence.append({"case": "production_origin_and_exclusive_output", "requests": 0,
                              "body_bytes": 0, "writes": 0, "exact_parser_reservation_enforced": True,
                              "exclusive_creation_race": raced.exception.receipt,
                              "fdopen_failure": failed.exception.receipt,
                              "failed_fdopen_fd_closed": True})


@contextmanager
def bounded_trace(root):
    path = root / "traceback.once.txt"
    read_fd, write_fd = os.pipe()
    output_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    state = {"seconds": 15, "repeat": False, "bytes_seen": 0, "bytes_retained": 0}
    def drain():
        try:
            while True:
                block = os.read(read_fd, 4096)
                if not block:
                    break
                state["bytes_seen"] += len(block)
                keep = block[:max(0, TRACE_CAP - state["bytes_retained"])]
                while keep:
                    written = os.write(output_fd, keep)
                    if written <= 0:
                        raise OSError("diagnostic short write")
                    state["bytes_retained"] += written
                    keep = keep[written:]
        finally:
            os.close(read_fd)
            os.close(output_fd)
    thread = threading.Thread(target=drain, name="n063-qualifier-trace")
    thread.start()
    faulthandler.dump_traceback_later(15, repeat=False, file=write_fd)
    try:
        yield state
    finally:
        faulthandler.cancel_dump_traceback_later()
        os.close(write_fd)
        thread.join(timeout=5)
        if thread.is_alive():
            raise AssertionError("owned diagnostic thread did not close")
        state["drainer_joined"] = True
        state["artifact"] = descriptor(path)


def main():
    global ARGS
    parser = argparse.ArgumentParser()
    for name in ("range-source", "original-root", "fixture", "evidence-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    ARGS = parser.parse_args()
    if not ARGS.evidence_root.is_dir() or ARGS.evidence_root.is_symlink():
        parser.error("fresh ordinary pre-created evidence root required")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GeneratedControls)
    with bounded_trace(ARGS.evidence_root) as trace:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    value = {"schema": "neural063-generated-original-qualifier-controls-v1", "generated_only": True,
             "success": result.wasSuccessful(), "methods": result.testsRun,
             "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
             "cases": GeneratedControls.evidence, "server_body_reserved": GeneratedControls.body_reserved,
             "server_complete_body_writes": GeneratedControls.body_written, "server_body_cap": BODY_CAP,
             "server_response_headers_reserved": GeneratedControls.header_reserved,
             "server_complete_response_headers_written": GeneratedControls.header_written,
             "server_response_header_cap": HEADER_CAP,
             "traceback": trace, "original_data_requests": 0, "models_or_scoring": False,
             "authentic_cohort_equivalence_qualified": False,
             "owned_service_loop_closed": getattr(GeneratedControls, "asyn", None) is not None and GeneratedControls.asyn.loop[0] is None}
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > RESULT_CAP:
        raise AssertionError("generated result exceeds admitted cap")
    with (ARGS.evidence_root / "RESULT.v1.json").open("xb") as output:
        output.write(data)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
