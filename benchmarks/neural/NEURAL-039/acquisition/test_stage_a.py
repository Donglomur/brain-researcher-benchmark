"""Generated metadata and mocked transport controls; never uses a network."""
import copy
from contextlib import contextmanager
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stage_a", HERE / "stage_a.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def generated():
    bodies = {"readme": ("DataLad\ndatalad install -r -s " + s.REPOSITORY + ".git\n").encode()}
    requests = copy.deepcopy(s.expected_policy()["requests"])
    for subject, *_ in s.ORIGINALS:
        bodies[subject] = s.original(subject)[1]
    for row in requests:
        row.update(bytes=len(bodies[row["id"]]), sha256=s.sha(bodies[row["id"]]))
    return requests, bodies


class Response:
    def __init__(self, body, budget, record, status=200, headers=None):
        self.stream, self.budget, self.record = io.BytesIO(body), budget, record
        self.status, self.headers, self.closed = status, headers or {}, False

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, count):
        part = self.stream.read(count)
        self.budget.charge(len(part), self.record)
        return part

    def close(self):
        self.closed = True


class Transport:
    def __init__(self, bodies, status=200, headers=None, close_error=False):
        self.bodies, self.status, self.headers = bodies, status, headers
        self.close_error, self.responses = close_error, []

    @contextmanager
    def open(self, request, budget, record):
        response = Response(self.bodies[request["id"]], budget, record, self.status, self.headers)
        self.responses.append(response)
        try:
            yield response
        finally:
            response.close()
            if self.close_error:
                record["cleanup_errors"].append("OSError")


class SocketFile(io.RawIOBase):
    def __init__(self, sock):
        self.sock = sock
        self.sock.refs += 1

    def readable(self):
        return True

    def read(self, n=-1):
        if self.closed or (self.sock.owner_closed and not self.sock.refs):
            raise OSError("socket closed without file reference")
        self.sock.read_count += 1
        if self.sock.after_read is not None:
            self.sock.after_read()
        return self.sock.stream.read(n)

    def close(self):
        if not self.closed:
            self.sock.refs -= 1
        super().close()


class FakeSocket:
    def __init__(self, wire):
        self.stream, self.refs, self.owner_closed = io.BytesIO(wire), 0, False
        self.timeouts, self.sent, self.read_count = [], [], 0
        self.after_read = None

    def makefile(self, mode, buffering=0):
        assert mode == "rb" and buffering == 0
        return SocketFile(self)

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.owner_closed = True


@contextmanager
def stack(wire):
    sock = FakeSocket(wire)
    instances = []

    class Connection(http.client.HTTPConnection):
        def __init__(self, host, port, timeout, context):
            super().__init__(host, port, timeout=timeout)
            instances.append(self)

        def connect(self):
            self.sock = sock

    with mock.patch.object(s.http.client, "HTTPSConnection", Connection):
        yield sock, instances


def request_for(body):
    row = copy.deepcopy(s.expected_policy()["requests"][0])
    row.update(bytes=len(body), sha256=s.sha(body))
    return row


class StageATests(unittest.TestCase):
    def test_exact_five_policy_and_original_identity(self):
        policy = s.validate_policy((HERE / "REQUEST_POLICY.json").read_bytes())
        self.assertEqual(len(policy["requests"]), 5)
        self.assertEqual(sum(row[1] for row in s.ORIGINALS), 368950005)
        for row in policy["requests"][1:]:
            item, body = s.original(row["id"])
            self.assertEqual(len(body), 137)
            self.assertEqual(s.sha(body), row["sha256"])
            self.assertIn("parcel-1000Par7Net", item["source_path"])

    def test_policy_mutation_and_typed_numbers_refused(self):
        for mutate in (lambda p: p["requests"][0].update(url="https://example.org/payload"),
                       lambda p: p["requests"].append(p["requests"][0]),
                       lambda p: p.update(retries=False),
                       lambda p: p["limits"].update(requests=12.0),
                       lambda p: p["requests"][0].update(sha256="0" * 64)):
            value = copy.deepcopy(s.expected_policy()); mutate(value)
            with self.assertRaises(s.Refusal): s.validate_policy(s.canonical(value))
        with self.assertRaisesRegex(s.Refusal, "duplicate_json_key"):
            s.parse(b'{"x":1,"x":1}')

    def test_generated_success_keeps_transport_and_science_held(self):
        requests, bodies = generated(); transport = Transport(bodies)
        result = s.collect(requests, transport, s.Budget())
        self.assertTrue(result["metadata_complete"])
        self.assertEqual(result["cost"]["attempts"], 5)
        self.assertEqual(len(result["routes"]), 4)
        self.assertFalse(result["physical_payload_transport_ready"])
        self.assertFalse(result["b_c_admitted"])
        self.assertTrue(all(r["payload_url"] is None and not r["payload_get_authorized"] for r in result["routes"]))
        self.assertTrue(all(r.closed for r in transport.responses))
        modified = copy.deepcopy(s.expected_policy()); modified["requests"] = requests
        with self.assertRaises(s.Refusal): s.validate_policy(s.canonical(modified))

    def test_extent_digest_encoding_and_framing_fail_closed(self):
        body = b"abcdef"; request = request_for(body)
        for value, headers, failure in [
            (body[:-1], {}, "body_extent_differs"),
            (body + b"!", {}, "body_extent_differs"),
            (b"ghijkl", {}, "body_digest_differs"),
            (body, {"Content-Encoding": "gzip"}, "content_encoding_rejected"),
            (body, {"Content-Length": "7"}, "declared_extent_differs"),
            (body, {"Content-Length": "6", "Transfer-Encoding": "chunked"}, "conflicting_http_framing")]:
            budget = s.Budget(); transport = Transport({"readme": value}, headers=headers)
            with self.assertRaisesRegex(s.Refusal, failure): s.fetch(request, transport, budget)
            self.assertEqual(budget.attempts, 1)
            self.assertTrue(transport.responses[0].closed)
            self.assertFalse(budget.records[0]["verified"])

    def test_cleanup_failure_never_marks_verified(self):
        request = request_for(b"ok"); budget = s.Budget()
        with self.assertRaisesRegex(s.Refusal, "transport_cleanup_failed"):
            s.fetch(request, Transport({"readme": b"ok"}, close_error=True), budget)
        self.assertEqual(budget.received, 2)
        self.assertFalse(budget.records[0]["verified"])

    def test_real_http_parser_survives_connection_close_large_body(self):
        body = b"a" * 12500; request = request_for(body)
        wire = b"HTTP/1.1 200 OK\r\nContent-Length: 12500\r\nConnection: close\r\n\r\n" + body
        budget = s.Budget()
        with stack(wire) as (sock, connections):
            self.assertEqual(s.fetch(request, s.HTTPTransport(), budget), body)
            self.assertEqual(len(connections), 1)
            self.assertTrue(sock.owner_closed)
            self.assertEqual(sock.refs, 0)
            self.assertGreater(sock.read_count, 1)
            self.assertTrue(all(0 < t <= 10 for t in sock.timeouts))
            self.assertEqual(budget.received, len(wire))
            self.assertIn(b"Connection: close", b"".join(sock.sent))

    def test_redirect_is_closed_charged_and_never_followed(self):
        wire = b"HTTP/1.1 302 Found\r\nLocation: https://example.org/payload\r\nConnection: close\r\n\r\n"
        budget = s.Budget()
        with stack(wire) as (sock, connections):
            with self.assertRaisesRegex(s.Refusal, "http_status_rejected"):
                s.fetch(request_for(b"x"), s.HTTPTransport(), budget)
            self.assertEqual(len(connections), 1)
            self.assertTrue(sock.owner_closed)
            self.assertEqual(sock.refs, 0)
            self.assertEqual(budget.attempts, 1)
            self.assertEqual(budget.received, len(wire))

    def test_chunked_framing_charged_and_extent_plus_one_rejected(self):
        for body, extra, succeeds in [(b"abc", b"", True), (b"abc", b"d", False)]:
            data = body + extra
            wire = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n" + hex(len(data))[2:].encode() + b"\r\n" + data + b"\r\n0\r\n\r\n"
            budget = s.Budget()
            with stack(wire) as (sock, _):
                if succeeds: self.assertEqual(s.fetch(request_for(body), s.HTTPTransport(), budget), body)
                else:
                    with self.assertRaisesRegex(s.Refusal, "body_extent_differs"):
                        s.fetch(request_for(body), s.HTTPTransport(), budget)
                self.assertEqual(budget.received, len(wire))
                self.assertEqual(sock.refs, 0)

    def test_malformed_http_headers_release_handles(self):
        wire = b"invalid status line\r\n\r\n"; budget = s.Budget()
        with stack(wire) as (sock, _):
            with self.assertRaises(s.Refusal): s.fetch(request_for(b"x"), s.HTTPTransport(), budget)
            self.assertEqual(sock.refs, 0)
            self.assertTrue(sock.owner_closed)
            self.assertEqual(budget.received, len(wire))

    def test_endpoint_guard_precedes_connection(self):
        request = request_for(b"x"); request["url"] = "https://example.org/payload"
        with mock.patch.object(s.http.client, "HTTPSConnection") as connection:
            with self.assertRaisesRegex(s.Refusal, "endpoint_not_allowlisted"):
                s.fetch(request, s.HTTPTransport(), s.Budget())
            connection.assert_not_called()

    def test_attempt_cap_and_plaintext_cap_include_failures(self):
        limits = dict(s.LIMITS, requests=1, received_http_plaintext_bytes=2)
        budget = s.Budget(limits); request = request_for(b"xx")
        record = budget.begin(request); budget.charge(2, record)
        with self.assertRaisesRegex(s.Refusal, "receive_budget_exhausted"):
            budget.allowance(record, request)
        with self.assertRaisesRegex(s.Refusal, "request_budget_exhausted"): budget.begin(request)
        self.assertEqual((budget.attempts, budget.received), (1, 2))

    def test_deadline_on_every_raw_read_and_failed_bytes_retained(self):
        now = [0.0]; budget = s.Budget(clock=lambda: now[0])
        request = request_for(b"ab"); record = budget.begin(request)
        sock = FakeSocket(b"ab"); raw = s.CountedRaw(sock, budget, request, record)
        try:
            now[0] = 299.5
            self.assertEqual(raw.readinto(bytearray(1)), 1)
            self.assertEqual(sock.timeouts[-1], 0.5)
            sock.after_read = lambda: now.__setitem__(0, 301)
            with self.assertRaisesRegex(s.Refusal, "deadline_exhausted"):
                raw.readinto(bytearray(1))
            self.assertEqual(budget.received, 2)
            with self.assertRaises(s.Refusal): raw.readinto(bytearray(1))
            self.assertEqual(sock.read_count, 2)
        finally: raw.close()
        self.assertEqual(sock.refs, 0)

    def test_exact_limit_and_oversize_stream_cannot_read_past_budget(self):
        limits = dict(s.LIMITS, received_http_plaintext_bytes=3)
        budget = s.Budget(limits); request = request_for(b"x"); record = budget.begin(request)
        sock = FakeSocket(b"1234"); raw = s.CountedRaw(sock, budget, request, record)
        try:
            self.assertEqual(raw.readinto(bytearray(10)), 3)
            with self.assertRaises(s.Refusal): raw.readinto(bytearray(10))
            self.assertEqual(sock.stream.tell(), 3)
        finally: raw.close()

    def test_admission_requires_selection_identity_output_and_typed_limits(self):
        policy, source = b"policy", b"source"
        value = {"schema": "neural039-stagea-admission-v1", "task_id": "NEURAL-039", "stage": "A",
                 "decision": "root_selected_authentic_metadata", "operation_id": "future-run",
                 "source_sha256": s.sha(source), "policy_sha256": s.sha(policy),
                 "output": "/future/result.json", "limits": dict(s.LIMITS),
                 "runtime_profile": "linux-rlimit-as-sigalrm-default-v1"}
        self.assertEqual(s.validate_admission(s.canonical(value), policy, source, Path(value["output"])), value)
        for field, item in [("decision", "proposal_only"), ("source_sha256", "0" * 64),
                            ("output", "/different/result.json"), ("runtime_profile", "darwin")]:
            bad = copy.deepcopy(value); bad[field] = item
            with self.assertRaises(s.Refusal): s.validate_admission(s.canonical(bad), policy, source, Path(value["output"]))
        bad = copy.deepcopy(value); bad["limits"]["requests"] = 12.0
        with self.assertRaises(s.Refusal): s.validate_admission(s.canonical(bad), policy, source, Path(value["output"]))

    def test_runtime_installs_default_fatal_alarm_and_verified_limits(self):
        states = {}; alarms = []; handlers = []
        resource = SimpleNamespace(RLIMIT_AS=1, RLIMIT_FSIZE=2,
            setrlimit=lambda key, value: states.__setitem__(key, value), getrlimit=lambda key: states[key])
        signals = SimpleNamespace(SIGALRM=14, SIG_DFL=0, ITIMER_REAL=0,
            signal=lambda *args: handlers.append(args), setitimer=lambda *args: alarms.append(args))
        s.install_limits(resource, signals, "linux")
        self.assertEqual(states, {1: (536870912,) * 2, 2: (65536,) * 2})
        self.assertEqual(handlers, [(14, 0)])
        self.assertEqual(alarms, [(0, 300)])
        with self.assertRaisesRegex(s.Refusal, "linux_runtime_required"):
            s.install_limits(resource, signals, "darwin")
        resource.getrlimit = lambda _: (0, 0)
        with self.assertRaisesRegex(s.Refusal, "resource_limit_not_installed"):
            s.install_limits(resource, signals, "linux")

    def test_output_exclusive_ordinary_and_bounded_inputs(self):
        base = Path(os.environ.get("NEURAL039_STAGEA_TEST_TMP", tempfile.gettempdir())).resolve()
        with tempfile.TemporaryDirectory(prefix="generated-control-", dir=base) as directory:
            directory = Path(directory); path = directory / "out"
            fd = s.reserve_output(path)
            try: self.assertEqual(s.write_result(fd, {"x": 1}), 8)
            finally: os.close(fd)
            with self.assertRaises(FileExistsError): s.reserve_output(path)
            self.assertEqual(s.bounded_file(path), b'{"x":1}\n')
            link = directory / "link"; link.symlink_to(directory, target_is_directory=True)
            with self.assertRaisesRegex(s.Refusal, "symlink_path"): s.reserve_output(link / "other")
            with self.assertRaises(s.Refusal): s.bounded_file(path, cap=2)

    def test_large_result_is_refused_before_write_and_short_write_fails(self):
        with mock.patch.object(s.os, "write") as write:
            with self.assertRaisesRegex(s.Refusal, "result_size_exceeded"):
                s.write_result(1, {"x": "x" * 65536})
            write.assert_not_called()
        with mock.patch.object(s.os, "write", return_value=0), mock.patch.object(s.os, "fsync") as sync:
            with self.assertRaisesRegex(s.Refusal, "result_short_write"): s.write_result(1, {"x": 1})
            sync.assert_not_called()

    def test_partial_writes_finish_but_fsync_error_remains_failure(self):
        output = bytearray()
        def write(_, body): output.extend(body[:2]); return min(2, len(body))
        with mock.patch.object(s.os, "write", side_effect=write), mock.patch.object(s.os, "fsync", side_effect=OSError):
            with self.assertRaises(OSError): s.write_result(1, {"x": 1})
        self.assertEqual(output, b'{"x":1}\n')


if __name__ == "__main__":
    unittest.main(verbosity=2)
