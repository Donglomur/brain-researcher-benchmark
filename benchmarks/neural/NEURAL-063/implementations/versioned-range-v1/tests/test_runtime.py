"""Four generated HDF5/loopback and six mocked ownership controls.

Neither is original-data qualification.

Run only in the explicitly selected maintained runtime. The loopback origin
exception and socket guard exist solely here, never in production code.
"""
import argparse
import asyncio
import faulthandler
import gc
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

SOURCE = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(SOURCE))
import pipeline
import range_io

ARGS = None
FIXTURE_CAP = 128 * 1024
SERVER_BODY_CAP = 4 * 1024 * 1024
RESULT_CAP = 32768
TRACE_CAP = 32768


def descriptor(path):
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}


class FixtureServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, case, mode):
        self.case, self.mode = case, mode
        self.requests = []
        self.errors = []
        self.body_reserved = self.body_written = 0
        super().__init__(("127.0.0.1", 0), FixtureHandler)

    def handle_error(self, request, client_address):
        self.errors.append(type(sys.exc_info()[1]).__name__)


class FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *args):
        pass

    def do_HEAD(self):
        self.server.requests.append({"method": "HEAD", "path": self.path})
        self.send_error(405)
        self.close_connection = True

    def do_GET(self):
        case, mode = self.server.case, self.server.mode
        match = re.fullmatch(r"bytes=([0-9]+)-([0-9]+)", self.headers.get("Range", ""))
        record = {"method": "GET", "path": self.path,
                  "range": self.headers.get("Range"),
                  "if_match": self.headers.get("If-Match"),
                  "accept_encoding": self.headers.get("Accept-Encoding"),
                  "cyclic_gc_enabled": gc.isenabled()}
        self.server.requests.append(record)
        if (self.path != case.URL_PATH or not match or
                self.headers.get("If-Match") != case.ETAG or
                self.headers.get("Accept-Encoding") != "identity"):
            self.send_error(400)
            self.close_connection = True
            return
        start, end = map(int, match.groups())
        if not 0 <= start <= end < len(case.fixture):
            self.send_error(416)
            self.close_connection = True
            return
        if mode == "disconnect":
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        response = case.fixture[start:end + 1]
        if mode == "full_body":
            response = case.fixture
        elif mode == "short":
            response = response[:max(1, len(response) // 2)]
        with case.body_lock:
            if case.body_reserved + len(response) > case.body_allowance:
                self.server.errors.append("aggregate_response_body_cap")
                self.close_connection = True
                return
            case.body_reserved += len(response)
            self.server.body_reserved += len(response)
        self.send_response(200 if mode == "full_body" else 206)
        self.send_header("Content-Length", str(len(case.fixture) if mode == "full_body" else end - start + 1))
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(case.fixture)}")
        self.send_header("x-amz-version-id", "wrong-version" if mode == "version" else case.VERSION)
        self.send_header("ETag", '"wrong-etag"' if mode == "etag" else case.ETAG)
        self.send_header("Content-Encoding", "identity")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(response)
            self.wfile.flush()
            self.server.body_written += len(response)
            with case.body_lock:
                case.body_written += len(response)
        except (BrokenPipeError, ConnectionResetError):
            # A rejected header can close the client before its body is written.
            # The full offered body remains conservatively reserved above.
            pass
        finally:
            self.close_connection = True


class ResponseOwnershipControls(unittest.TestCase):
    """Exercise the actual checked callback and cleanup order with stdlib doubles.

    These controls do not qualify aiohttp/HDF5 or create a network service.
    The existing four RuntimeControls retain real-library/loopback coverage.
    """

    @contextmanager
    def reader(self, *, enabled=True, rejection=None, close_error=None,
               fail_at=None):
        events = []
        state = {"gc": enabled}
        cleanup_error = RuntimeError("generated owned cleanup failure")
        callback = {}

        def event(name):
            events.append((name, state["gc"]))
            if name == fail_at:
                raise cleanup_error

        class Response:
            status = 206
            url = "generated://bounded-response"
            headers = {"generated": "headers"}
            history = ()
            closed = False

            def close(self):
                event("response.close")
                if close_error is not None:
                    raise close_error
                self.closed = True

            def read(self):
                if self.closed:
                    raise RuntimeError("generated response is already closed")
                return b"generated unread body"

        response = Response()
        limits = SimpleNamespace(block_bytes=4096, cache_blocks=4,
                                 request_seconds=5, hdf5_cache_bytes=8192)
        budget = SimpleNamespace(limits=limits, pending=None, failed=False,
                                 check_time=lambda: None)
        budget.response = mock.Mock(side_effect=rejection)

        def abort():
            event("budget.abort")
            budget.failed = True
        budget.abort = abort
        asset = SimpleNamespace(validate=lambda: None, url=response.url,
                                etag='"generated"', extent_bytes=8193)
        cache = SimpleNamespace(_fetch_block_cached=SimpleNamespace(
            cache_clear=lambda: event("cache.clear")))
        stream = SimpleNamespace(cache=cache,
                                 close=lambda: event("stream.close"))

        async def session_close():
            event("session.close.begin")
            await asyncio.sleep(0)
            event("session.close.end")

        def filesystem(**kwargs):
            callback["checked"] = kwargs["client_kwargs"]["raise_for_status"]
            return SimpleNamespace(loop=object(),
                _session=SimpleNamespace(close=session_close),
                open=lambda *args, **kw: stream)

        @contextmanager
        def hdf5_file(*args, **kwargs):
            event("hdf5.enter")
            asyncio.run(callback["checked"](response))
            try:
                yield SimpleNamespace(response=response)
            finally:
                event("hdf5.close")

        aiohttp = ModuleType("aiohttp")
        aiohttp.TraceConfig = lambda: SimpleNamespace(on_request_start=[],
            on_response_chunk_received=[], on_request_exception=[])
        aiohttp.ClientTimeout = lambda **kwargs: kwargs
        h5py = ModuleType("h5py")
        h5py.File = hdf5_file
        fsspec = ModuleType("fsspec")
        implementations = ModuleType("fsspec.implementations")
        http = ModuleType("fsspec.implementations.http")
        asynchronous = ModuleType("fsspec.asyn")
        http.HTTPFileSystem = filesystem
        asynchronous.sync = lambda loop, close: asyncio.run(close())
        fsspec.implementations = implementations
        fsspec.asyn = asynchronous
        implementations.http = http
        modules = {"aiohttp": aiohttp, "h5py": h5py, "fsspec": fsspec,
                   "fsspec.implementations": implementations,
                   "fsspec.implementations.http": http,
                   "fsspec.asyn": asynchronous}

        def disable():
            event("gc.disable")
            state["gc"] = False

        def enable():
            event("gc.restore")
            state["gc"] = True

        with mock.patch.dict(sys.modules, modules), \
             mock.patch("importlib.metadata.version",
                        side_effect=lambda name: range_io.SUPPORTED_RUNTIME[name]), \
             mock.patch.object(range_io, "configure_cache", lambda *args: None), \
             mock.patch.object(range_io.gc, "isenabled", lambda: state["gc"]), \
             mock.patch.object(range_io.gc, "disable", disable), \
             mock.patch.object(range_io.gc, "enable", enable):
            yield SimpleNamespace(response=response, asset=asset, budget=budget,
                state=state, events=events, cleanup_error=cleanup_error,
                opened=lambda: range_io.open_versioned(
                    asset, budget, dict(range_io.SUPPORTED_RUNTIME)))

    def test_rejected_response_closes_and_preserves_exception(self):
        rejection = range_io.RangeContractError("generated header refusal")
        with self.reader(rejection=rejection) as case:
            with self.assertRaises(range_io.RangeContractError) as caught:
                with case.opened():
                    self.fail("rejected response became usable")
            self.assertIs(caught.exception, rejection)
            self.assertTrue(case.response.closed)
            case.budget.response.assert_called_once_with(case.asset, 206,
                case.response.url, case.response.headers, ())
            names = [name for name, _ in case.events]
            self.assertLess(names.index("response.close"), names.index("budget.abort"))
            self.assertEqual(names.count("response.close"), 1)

    def test_accepted_response_remains_usable(self):
        with self.reader() as case:
            with case.opened() as file:
                self.assertIs(file.response, case.response)
                self.assertFalse(case.response.closed)
                self.assertEqual(file.response.read(), b"generated unread body")
            case.budget.response.assert_called_once_with(case.asset, 206,
                case.response.url, case.response.headers, ())
            self.assertFalse(case.response.closed)
            self.assertNotIn("response.close", [name for name, _ in case.events])
            self.assertFalse(case.budget.failed)

    def test_cancelled_check_closes_and_preserves_cancellation(self):
        rejection = asyncio.CancelledError("generated callback cancellation")
        with self.reader(rejection=rejection) as case:
            with self.assertRaises(asyncio.CancelledError) as caught:
                with case.opened():
                    self.fail("cancelled response became usable")
            self.assertIs(caught.exception, rejection)
            self.assertTrue(case.response.closed)
            self.assertTrue(case.budget.failed)

    def test_close_failure_retains_original_rejection_context(self):
        rejection = range_io.RangeContractError("generated header refusal")
        close_error = RuntimeError("generated response close failure")
        with self.reader(rejection=rejection, close_error=close_error) as case:
            with self.assertRaises(RuntimeError) as caught:
                with case.opened():
                    self.fail("response close failure was suppressed")
            self.assertIs(caught.exception, close_error)
            self.assertIs(caught.exception.__context__, rejection)
            self.assertEqual([name for name, _ in case.events].count("response.close"), 1)
            self.assertTrue(case.budget.failed)

    def test_gc_restoration_follows_all_owned_cleanup(self):
        for enabled in (True, False):
            with self.subTest(initial_gc_enabled=enabled), self.reader(enabled=enabled) as case:
                with case.opened():
                    self.assertFalse(case.state["gc"])
                expected = ["hdf5.close", "stream.close", "cache.clear",
                            "session.close.begin", "session.close.end"]
                observed = [(name, state) for name, state in case.events if name in expected]
                self.assertEqual(observed, [(name, False) for name in expected])
                self.assertEqual(case.state["gc"], enabled)
                restores = [name for name, _ in case.events if name == "gc.restore"]
                self.assertEqual(restores, ["gc.restore"] if enabled else [])
                if enabled:
                    self.assertEqual(case.events[-1][0], "gc.restore")

    def test_gc_restoration_survives_cleanup_failure(self):
        for enabled in (True, False):
            for failing in ("hdf5.close", "stream.close", "cache.clear", "session.close.end"):
                with self.subTest(initial_gc_enabled=enabled, failing=failing), \
                     self.reader(enabled=enabled, fail_at=failing) as case:
                    with self.assertRaises(RuntimeError) as caught:
                        with case.opened():
                            pass
                    self.assertIs(caught.exception, case.cleanup_error)
                    expected = ["hdf5.close", "stream.close", "cache.clear",
                                "session.close.begin", "session.close.end"]
                    observed = [(name, state) for name, state in case.events if name in expected]
                    self.assertEqual(observed, [(name, False) for name in expected])
                    self.assertEqual(case.state["gc"], enabled)
                    if enabled:
                        self.assertEqual(case.events[-1][0], "gc.restore")


class RuntimeControls(unittest.TestCase):
    VERSION = "generated+version/one="
    ETAG = '"generated-fixture-etag"'
    URL_PATH = "/generated.nwb?versionId=generated%2Bversion%2Fone%3D"
    evidence = []
    body_reserved = 0
    body_written = 0
    body_lock = threading.Lock()
    allowed_addresses = set()
    lifecycle_loop = None
    lifecycle_diagnostics = []
    lifecycle_overflow = False
    lifecycle_lock = threading.Lock()

    @classmethod
    def observe_lifecycle_loop(cls):
        loop = asyncio.get_running_loop()
        if cls.lifecycle_loop is not None:
            if cls.lifecycle_loop is not loop:
                raise AssertionError("unexpected second generated service loop")
            return
        cls.lifecycle_loop = loop
        previous = loop.get_exception_handler()
        def observed(current, context):
            try:
                message = str(context.get("message", ""))
                error = context.get("exception")
                row = {"message": message[:512], "truncated": len(message) > 512,
                       "exception_type": type(error).__name__ if error is not None else None,
                       "has_connection": context.get("client_connection") is not None,
                       "has_response": context.get("client_response") is not None}
                with cls.lifecycle_lock:
                    if len(cls.lifecycle_diagnostics) < 16:
                        cls.lifecycle_diagnostics.append(row)
                    else:
                        cls.lifecycle_overflow = True
            finally:
                # Retain the original diagnostic path and full context/logging.
                if previous is None:
                    current.default_exception_handler(context)
                else:
                    previous(current, context)
        loop.set_exception_handler(observed)

    @classmethod
    def drain_lifecycle(cls):
        if threading.current_thread() is not threading.main_thread():
            raise AssertionError("generated collection must run on the main thread")
        if cls.lifecycle_loop is None:
            return
        async def barrier():
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        for _ in range(2):
            gc.collect()
            cls.asyn.sync(cls.lifecycle_loop, barrier)

    @classmethod
    def setUpClass(cls):
        import aiohttp
        import h5py
        import numpy as np
        import fsspec.asyn
        from importlib.metadata import version

        cls.aiohttp, cls.h5py, cls.np = aiohttp, h5py, np
        cls.asyn = fsspec.asyn
        cls.runtime = {name: version(name) for name in range_io.SUPPORTED_RUNTIME}
        if cls.runtime != range_io.SUPPORTED_RUNTIME:
            raise AssertionError("selected runtime versions differ")
        cls.initial_loop = fsspec.asyn.loop[0]
        cls.initial_thread = fsspec.asyn.iothread[0]
        if cls.initial_loop is not None or cls.initial_thread is not None:
            raise AssertionError("dedicated generated process already has a service loop")
        pins = json.loads((SOURCE / "ORIGINAL_SOURCES.json").read_bytes())["files"]
        cls.native, cls.alg, cls.owner_io = pipeline.load_original(ARGS.original_root, pins)
        cls.body_allowance = SERVER_BODY_CAP - ARGS.prior_body_upper
        if not 0 < cls.body_allowance <= SERVER_BODY_CAP:
            raise AssertionError("invalid remaining cumulative server-body allowance")
        if ARGS.reuse_fixture:
            cls.fixture_path = ARGS.evidence_root.parent / "invented_fixture.nwb"
            ref = cls.owner_io.Artifact(str(cls.fixture_path), 25721,
                "56e99301faa09b2ef4f583e75a200d5473193d87a2b57f7dde1146f837b94a72",
                "generated_fixture", "operator", "first-generated-runtime-attempt", "application/x-hdf5")
            cls.fixture = cls.owner_io.capture(cls.fixture_path, FIXTURE_CAP, descriptor=ref)
            if hashlib.blake2b(cls.fixture).hexdigest() != "2db4aab872be3c4e92b62312b48ef107e2a33698ffe519ef0151a95bc1c28cc09c1c3e3c21e5db62a696b2cda526ee15b8bd20e2628a9242615d0aeab95c0c50":
                raise AssertionError("reused generated fixture BLAKE2b differs")
            if cls.fixture_path.stat().st_mode & 0o222:
                raise AssertionError("reused fixture must remain readonly")
        else:
            clock = np.arange(241, dtype=np.float64) / 20.0
            data = np.column_stack((2.0 * clock, 0.5 * clock, 1_000_000.0 + clock))
            memory = io.BytesIO()
            with h5py.File(memory, "w") as file:
                table = file.create_group("processing/ophys/image_segmentation/cell_specimen_table")
                table.create_dataset("id", data=np.array([101, 102, 103], dtype="i8"))
                table.create_dataset("cell_specimen_id", data=np.array([1001, 1002, 1003], dtype="i8"))
                table.create_dataset("valid_roi", data=np.array([True, False, True], dtype="?"))
                traces = file.create_group("processing/ophys/dff/traces")
                signal = traces.create_dataset("data", data=data, chunks=(32, 3), compression="gzip")
                signal.attrs["unit"] = "NA"
                signal.attrs["conversion"] = 1.0
                signal.attrs["offset"] = 0.0
                timestamps = traces.create_dataset("timestamps", data=clock)
                timestamps.attrs["unit"] = "seconds"
                rois = traces.create_dataset("rois", data=np.array([2, 0, 1], dtype="i8"))
                rois.attrs["neurodata_type"] = "DynamicTableRegion"
                rois.attrs["table"] = table.ref
                presentations = file.create_group("intervals/presentations")
                presentations.create_dataset("id", data=np.arange(16, dtype="i8"))
                presentations.create_dataset("start_time", data=np.arange(16, dtype="f8") * 0.75)
                omitted = np.zeros(16, dtype="?")
                omitted[[4, 10]] = True
                presentations.create_dataset("omitted", data=omitted)
                names = ["omitted" if omitted[i] else "invented-image-" + str(i % 3) for i in range(16)]
                presentations.create_dataset("image_name", data=names, dtype=h5py.string_dtype("utf-8"), chunks=(4,))
            body = memory.getvalue()
            memory.close()
            # Deliberate harmless trailer ensures a non-block-aligned final range.
            cls.fixture = body + b"\0" * (37 if len(body) % 4096 != 4096 - 37 else 38)
            if len(cls.fixture) > FIXTURE_CAP or len(cls.fixture) % 4096 == 0:
                raise AssertionError("generated HDF5 exceeds frozen fixture extent")
            cls.fixture_path = ARGS.evidence_root / "invented_fixture.nwb"
            with cls.fixture_path.open("xb") as output:
                output.write(cls.fixture)
            cls.fixture_path.chmod(0o444)
        cls.sha = hashlib.sha256(cls.fixture).hexdigest()
        cls.blake = hashlib.blake2b(cls.fixture).hexdigest()
        cls.row = {"ophys_experiment_id": "1", "ophys_session_id": "2", "mouse_id": "3", "split": "query",
                   "rois": [{"cell_roi_id": "101", "cell_specimen_id": "1001"},
                            {"cell_roi_id": "103", "cell_specimen_id": "1003"}],
                   "context": {name: "generated" for name in cls.alg.CONTEXT}}
        original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
        def guarded_connect(sock, address):
            if address not in cls.allowed_addresses:
                raise AssertionError("generated test attempted a non-fixture connection")
            return original_connect(sock, address)
        def guarded_connect_ex(sock, address):
            if address not in cls.allowed_addresses:
                raise AssertionError("generated test attempted a non-fixture connection")
            return original_connect_ex(sock, address)
        cls.connect_patch = mock.patch.object(socket.socket, "connect", guarded_connect)
        cls.connect_ex_patch = mock.patch.object(socket.socket, "connect_ex", guarded_connect_ex)
        cls.connect_patch.start()
        cls.connect_ex_patch.start()
        cls.addClassCleanup(cls.connect_patch.stop)
        cls.addClassCleanup(cls.connect_ex_patch.stop)
        cls.addClassCleanup(cls.stop_owned_loop)

    @classmethod
    def stop_owned_loop(cls):
        try:
            cls.drain_lifecycle()
        finally:
            loop, thread = cls.asyn.loop[0], cls.asyn.iothread[0]
            if loop is not None:
                if thread is None or thread is cls.initial_thread:
                    raise AssertionError("unidentified generated service loop")
                loop.call_soon_threadsafe(loop.stop)
                thread.join(timeout=5)
                if thread.is_alive():
                    raise AssertionError("owned fsspec service thread did not stop")
                loop.close()
                cls.asyn.loop[0] = None
                cls.asyn.iothread[0] = None
        if cls.lifecycle_diagnostics or cls.lifecycle_overflow:
            raise AssertionError("retained loop lifecycle diagnostics during generated controls")

    def make_budget(self):
        return range_io.Budget(range_io.Limits(
            max_requests=64, response_body_bytes=256 * 1024,
            logical_read_bytes=2 * 1024 * 1024, record_bytes=65536,
            block_bytes=4096, cache_blocks=4, read_operation_bytes=FIXTURE_CAP,
            hdf5_cache_bytes=8192, seconds=40, request_seconds=5))

    @contextmanager
    def served(self, mode):
        cls = type(self)
        server = FixtureServer(cls, mode)
        address = server.server_address
        cls.allowed_addresses.add(address)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05},
                                  name="n063-generated-fixture-server")
        thread.start()
        url = "http://127.0.0.1:" + str(address[1]) + self.URL_PATH
        asset = range_io.Asset("1", url, self.VERSION, self.ETAG, len(self.fixture), self.blake)
        def fixture_origin(value):
            if value != asset:
                raise range_io.RangeContractError("test origin exception is exact-fixture only")
            return value
        sessions, connectors, streams, caches = [], [], [], []
        responses, cleanup_events = [], []
        lifecycle = {}
        real_session = self.aiohttp.ClientSession
        real_configure = range_io.configure_cache
        real_close_runtime = range_io.close_runtime
        def capture_session(*args, **kwargs):
            cls.observe_lifecycle_loop()
            checked = kwargs["raise_for_status"]
            async def observed_check(response):
                if len(responses) >= 64:
                    raise AssertionError("generated response population exceeds request cap")
                record = {"response": response, "read": response.read,
                          "close": response.close, "close_calls": 0,
                          "accepted": False, "rejected": False,
                          "reads": 0, "read_failures": 0}
                responses.append(record)
                def observed_close():
                    record["close_calls"] += 1
                    return record["close"]()
                async def observed_read():
                    try:
                        body = await record["read"]()
                    except BaseException:
                        record["read_failures"] += 1
                        self.assertTrue(response.closed)
                        self.assertIsNone(response.connection)
                        raise
                    record["reads"] += 1
                    return body
                response.close = observed_close
                response.read = observed_read
                try:
                    await checked(response)
                except BaseException:
                    record["rejected"] = True
                    self.assertEqual(record["close_calls"], 1)
                    self.assertTrue(response.closed)
                    self.assertIsNone(response.connection)
                    raise
                else:
                    record["accepted"] = True
                    # EOF may already be buffered; do not require closed=False.
                    self.assertEqual(record["close_calls"], 0)
            kwargs["raise_for_status"] = observed_check
            session = real_session(*args, **kwargs)
            sessions.append(session)
            connectors.append(session.connector)
            return session

        def capture_close_runtime(stream, close_session):
            cleanup_events.append(("runtime.begin", gc.isenabled()))
            def observed_close_session():
                cleanup_events.append(("session.begin", gc.isenabled()))
                try:
                    return close_session()
                finally:
                    cleanup_events.append(("session.end", gc.isenabled()))
            try:
                return real_close_runtime(stream, observed_close_session)
            finally:
                cleanup_events.append(("runtime.end", gc.isenabled()))

        def release_response_instrumentation():
            for record in responses:
                response = record["response"]
                response.read = record["read"]
                response.close = record["close"]
            responses.clear()
        def capture_cache(stream, selected, limits):
            real_configure(stream, selected, limits)
            streams.append(stream)
            caches.append(stream.cache)
        try:
            with mock.patch.object(range_io.Asset, "validate", fixture_origin), \
                 mock.patch.object(self.aiohttp, "ClientSession", capture_session), \
                 mock.patch.object(range_io, "configure_cache", capture_cache), \
                 mock.patch.object(range_io, "close_runtime", capture_close_runtime):
                yield SimpleNamespace(server=server, asset=asset, sessions=sessions,
                                      streams=streams, caches=caches, lifecycle=lifecycle)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            cls.allowed_addresses.remove(address)
            try:
                self.assertFalse(thread.is_alive(), "fixture server thread must stop")
                self.assertTrue(all(session.closed for session in sessions))
                self.assertTrue(all(connector.closed for connector in connectors))
                self.assertTrue(all(stream.closed for stream in streams))
                self.assertTrue(all(cache._fetch_block_cached.cache_info().currsize == 0 for cache in caches))
                self.assertEqual(server.errors, [])
                self.assertLessEqual(cls.body_reserved, cls.body_allowance)
                self.assertTrue(all(r.get("cyclic_gc_enabled") is False for r in server.requests))
                accepted = sum(record["accepted"] for record in responses)
                rejected = sum(record["rejected"] for record in responses)
                reads = sum(record["reads"] for record in responses)
                read_failures = sum(record["read_failures"] for record in responses)
                lifecycle.update(mode=mode, responses=len(responses), accepted=accepted,
                    rejected=rejected, successful_body_reads=reads,
                    failed_body_reads=read_failures, cleanup_events=cleanup_events,
                    rejected_closed_and_connection_cleared=all(
                        record["response"].closed and record["response"].connection is None
                        for record in responses if record["rejected"]))
                if mode in ("full_body", "version", "etag"):
                    self.assertEqual((len(responses), accepted, rejected, reads), (1, 0, 1, 0))
                elif mode == "ok":
                    self.assertGreater(accepted, 0)
                    self.assertEqual(rejected, 0)
                    self.assertGreater(reads, 0)
                    self.assertEqual(read_failures, 0)
                elif mode == "short":
                    self.assertEqual((len(responses), accepted, rejected, reads, read_failures),
                                     (1, 1, 0, 0, 1))
                else:
                    self.assertEqual(mode, "disconnect")
                    self.assertEqual(len(responses), 0)
                self.assertEqual(cleanup_events, [(name, False) for name in
                    ("runtime.begin", "session.begin", "session.end", "runtime.end")])
                self.assertLessEqual(len(range_io.canonical(lifecycle)), 4096)
            finally:
                # Release instrumented response/method references before main-thread GC.
                release_response_instrumentation()
                cls.drain_lifecycle()
                lifecycle["diagnostic_count"] = len(cls.lifecycle_diagnostics)
                lifecycle["diagnostic_overflow"] = cls.lifecycle_overflow
                self.assertEqual(cls.lifecycle_diagnostics, [])
                self.assertFalse(cls.lifecycle_overflow)

    def summarize(self, case, selected, budget, **extra):
        receipt = budget.receipt()
        self.evidence.append({"case": case, "server_requests": len(selected.server.requests),
            "server_response_body_bytes_reserved": selected.server.body_reserved,
            "server_complete_body_writes_bytes": selected.server.body_written,
            "reader_requests_admitted": receipt["requests_admitted"],
            "reader_body_reserved": receipt["response_body_bytes_reserved_including_failures"],
            "reader_complete_body_observed": receipt["complete_response_body_bytes_observed"],
            "reader_receipt_sha256": hashlib.sha256(range_io.canonical(receipt)).hexdigest(),
            "accepted_ranges": len(receipt["ranges"]), "reader_failed": receipt["failed"],
            "full_object_BLAKE2b_verified": receipt["full_object_BLAKE2b_verified"],
            "all_requests_with_cyclic_gc_disabled": all(r.get("cyclic_gc_enabled") is False for r in selected.server.requests),
            "sessions_connectors_streams_closed_and_cache_cleared": True,
            "response_lifecycle": selected.lifecycle, **extra})

    def test_full_local_range_projection_and_cleanup(self):
        meter = self.owner_io.ByteMeter(4 * 1024 * 1024, 0)
        ctx = SimpleNamespace(require_scientific=lambda: None, store=SimpleNamespace(meter=meter))
        ref = self.owner_io.Artifact(str(self.fixture_path), len(self.fixture), self.sha,
                                    "native_source", "operator", "generated-runtime-control", "application/x-hdf5")
        with self.native.opened(ctx, ref, self.blake) as file:
            local_layouts = pipeline.field_layouts(file, self.native)
            local_data, local_metadata = self.native.neural_metadata(file, self.row)
            local_records = self.native.presentations(file)
            plane = {"experiment": "1", "session": "2", "mouse": "3", "split": "query",
                     "presentations": local_records, "presentation_sha256": pipeline.digest(local_records),
                     "neural_metadata": local_metadata}
            schedule, support = pipeline.derive_session([self.row], {"1": plane}, self.alg)
            expected = [self.alg.population(lambda left, right: local_data[left:right, :].tolist(),
                                           local_metadata["columns"], event["spans"])
                        for event in support["1"]["supported_events"]]
        self.assertEqual(schedule["scheduled"], 2)
        self.assertEqual(support["1"]["supported"], 2)
        self.assertEqual(local_metadata["columns"], [1, 0])
        self.assertEqual(local_metadata["valid_roi_count"], 2)
        vlen = local_layouts["intervals/presentations/image_name"]
        self.assertTrue(vlen["contains_variable_length_or_reference"])
        for name in ("full_logical_array_bytes", "uncompressed_chunk_bytes", "heap_payload_bytes"):
            self.assertIsNone(vlen[name])
        self.assertFalse(vlen["storage_size_covers_variable_length_heap"])
        budget = self.make_budget()
        gc_before = gc.isenabled()
        self.assertTrue(gc_before)
        with self.served("ok") as selected:
            with range_io.open_versioned(selected.asset, budget, self.runtime) as file:
                self.assertFalse(gc.isenabled())
                self.assertEqual(pipeline.field_layouts(file, self.native), local_layouts)
                ranged_data, ranged_metadata = self.native.neural_metadata(file, self.row)
                ranged_records = self.native.presentations(file)
                self.assertEqual(ranged_metadata, local_metadata)
                self.assertEqual(ranged_records, local_records)
                projected, hashes = pipeline.project_events(ranged_data, ranged_metadata, ranged_records,
                                                           support["1"], self.alg, self.row)
                self.assertEqual([(item["history"], item["target"]) for item in projected], expected)
                self.assertEqual(len(hashes), 30)
                self.assertTrue(all(len(item["history"]) == 12 and len(item["target"]) == 3 for item in projected))
                self.assertTrue(all(item["history"][-1] == 0 and max(item["target"]) < 10 for item in projected))
                # Exercise the actual clipped maintained cache at the final block.
                bounded = range_io.BoundedFile(selected.streams[0], selected.asset, budget)
                bounded.seek(len(self.fixture) - 9)
                self.assertEqual(bounded.read(9), self.fixture[-9:])
                request_count = budget.requests
                bounded.seek(len(self.fixture) - 9)
                self.assertEqual(bounded.read(9), self.fixture[-9:])
                self.assertEqual(budget.requests, request_count, "repeat final block must hit cache")
                self.assertLessEqual(selected.caches[0]._fetch_block_cached.cache_info().currsize, 4)
            self.assertEqual(gc.isenabled(), gc_before)
            receipt = budget.receipt()
            self.assertFalse(receipt["failed"])
            self.assertIsNone(receipt["unresolved_request"])
            self.assertEqual(len(selected.server.requests), budget.requests)
            self.assertTrue(any(r["end"] == len(self.fixture) - 1 and r["bytes"] < 4096 for r in receipt["ranges"]))
            self.assertFalse(receipt["full_object_BLAKE2b_verified"])
        self.summarize("local_range_parity", selected, budget,
                       supported_omissions=2, native_bins_per_omission=15,
                       valid_rois=2, original_full_file_comparator_authenticated=True,
                       original_local_meter=meter.snapshot(), vlen_heap_extent_unknown=True)

    def refuse(self, mode, message=None):
        budget = self.make_budget()
        with self.served(mode) as selected:
            caught = None
            gc_before = gc.isenabled()
            entering_enabled = mode != "etag"
            if not entering_enabled:
                gc.disable()
            try:
                with range_io.open_versioned(selected.asset, budget, self.runtime):
                    self.fail("invalid response was accepted")
            except (range_io.RangeContractError, self.aiohttp.ClientError, OSError) as exc:
                caught = exc
            finally:
                restored = gc.isenabled() == entering_enabled
                if gc_before:
                    gc.enable()
                else:
                    gc.disable()
            self.assertTrue(restored, "original cyclic-GC state must be restored after refusal")
            self.assertIsNotNone(caught)
            if message is not None:
                self.assertIsInstance(caught, range_io.RangeContractError)
                self.assertIn(message, str(caught))
            self.assertEqual(len(selected.server.requests), 1, "no hidden transport retry")
            self.assertEqual(budget.requests, 1)
            self.assertTrue(budget.failed)
            self.assertEqual(budget.body_observed, 0)
            self.assertEqual(budget.records, [])
            if mode == "short":
                self.assertTrue(budget.pending["headers_verified"])
                self.assertLess(selected.server.body_reserved, budget.body_reserved)
            elif mode == "disconnect":
                self.assertFalse(budget.pending["headers_verified"])
                self.assertEqual(selected.server.body_reserved, 0)
        self.summarize(mode, selected, budget, exception_type=type(caught).__name__)

    def test_refuse_full_body_200(self):
        self.refuse("full_body", "redirect/full-body/non-range response refused")

    def test_refuse_wrong_version_and_etag(self):
        for mode in ("version", "etag"):
            with self.subTest(mode=mode):
                self.refuse(mode, "response source/encoding mismatch")

    def test_refuse_short_body_without_retry(self):
        for mode in ("short", "disconnect"):
            with self.subTest(mode=mode):
                self.refuse(mode)



@contextmanager
def one_shot_trace(root):
    """One diagnostic only, actively drained to at most32KiB on disk."""
    trace_path = root / "traceback.once.txt"
    read_fd, write_fd = os.pipe()
    output_fd = os.open(trace_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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
                    count = os.write(output_fd, keep)
                    if count <= 0:
                        raise OSError("short diagnostic write")
                    state["bytes_retained"] += count
                    keep = keep[count:]
        finally:
            os.close(read_fd)
            os.close(output_fd)
    thread = threading.Thread(target=drain, name="n063-generated-trace-drain")
    thread.start()
    faulthandler.dump_traceback_later(15, repeat=False, file=write_fd)
    try:
        yield state
    finally:
        faulthandler.cancel_dump_traceback_later()
        os.close(write_fd)
        thread.join(timeout=5)
        if thread.is_alive():
            raise AssertionError("owned traceback drainer did not stop")
        state["drainer_joined"] = True
        state["truncated"] = state["bytes_seen"] > state["bytes_retained"]
        state["artifact"] = descriptor(trace_path)


def main():
    global ARGS
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--reuse-fixture", action="store_true")
    parser.add_argument("--prior-body-upper", type=int, default=0)
    ARGS = parser.parse_args()
    ARGS.evidence_root = ARGS.evidence_root.absolute()
    if not ARGS.evidence_root.is_dir() or ARGS.evidence_root.is_symlink():
        parser.error("ordinary pre-created evidence root required")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeControls)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ResponseOwnershipControls))
    with one_shot_trace(ARGS.evidence_root) as trace:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    value = {"schema": "neural063-generated-real-reader-controls-v1", "generated_only": True,
             "methods": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
             "skips": len(result.skipped), "success": result.wasSuccessful(),
             "runtime": getattr(RuntimeControls, "runtime", None),
             "fixture": descriptor(RuntimeControls.fixture_path) if hasattr(RuntimeControls, "fixture_path") else None,
             "server_body_reserved_including_failed_writes": RuntimeControls.body_reserved,
             "server_complete_body_writes_bytes": RuntimeControls.body_written,
             "server_body_cap": SERVER_BODY_CAP, "prior_attempt_body_upper": ARGS.prior_body_upper,
             "cumulative_body_upper": ARGS.prior_body_upper + RuntimeControls.body_reserved,
             "one_shot_trace": trace, "cases": RuntimeControls.evidence,
             "owned_service_loop_closed": getattr(RuntimeControls, "asyn", None) is not None and RuntimeControls.asyn.loop[0] is None,
             "lifecycle_diagnostics": RuntimeControls.lifecycle_diagnostics,
             "lifecycle_diagnostic_overflow": RuntimeControls.lifecycle_overflow,
             "scientific_equivalence_of_authentic_cohort": False,
             "original_data_requests": 0, "models_or_scoring": False}
    body = range_io.canonical(value)
    if len(body) > RESULT_CAP:
        raise AssertionError("generated result exceeds frozen cap")
    with (ARGS.evidence_root / "RESULT.v1.json").open("xb") as output:
        output.write(body)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
