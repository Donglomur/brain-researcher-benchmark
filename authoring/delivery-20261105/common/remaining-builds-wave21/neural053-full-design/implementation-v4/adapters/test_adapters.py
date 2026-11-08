"""Small invented transport controls only; no provider/Docker/model invocation.

Three owned Python children print tiny invented strings/exit codes. The HTTP
client is doubled before any connection and carries only an invented key.
This complete run reserves192KiB cumulative fixture payload, live128KiB,
retained0; source/library process I/O and RSS are not fixture telemetry.
"""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from adapters.common import AdapterError, BoundAdapter, CaseBudget, authenticate, canonical, file_pin
from adapters.contexts import ProviderContext, case_key
from adapters.process import ProcessObserver, workspace_extent
from adapters.provider import ChatCompletionTransport, ENDPOINT, parse_completion
from adapters.worker import INPUT_NAMES, container_path


class TinyBudget:
    def __init__(self):
        self.origin_monotonic = time.monotonic() - 1
        self.deadline_monotonic = time.monotonic() + 10
        self.limits = {x: 1000000 for x in ("provider_calls", "provider_tokens", "tool_calls", "source_read", "artifact_write", "stream_bytes")}
        self.used = {x: 0 for x in self.limits}

    def check_clock(self):
        if time.monotonic() > self.deadline_monotonic: raise AdapterError("invented deadline")

    def charge(self, name, amount=1):
        self.check_clock()
        if type(amount) is not int or amount < 0 or name not in self.limits or self.used[name]+amount > self.limits[name]:
            raise AdapterError("invented resource refusal")
        self.used[name] += amount


def response(finish="stop"):
    return {"id": "invented-response", "model": "invented-model", "choices": [{"index": 0,
            "finish_reason": finish, "message": {"role": "assistant", "content": "invented text"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}}


class AdapterControls(unittest.TestCase):
    def test_01_absent_authority_refuses_before_source_or_operands(self):
        with patch.object(BoundAdapter, "source_manifest", side_effect=AssertionError("source sentinel")) as source:
            with self.assertRaises(AdapterError):
                BoundAdapter({}, TinyBudget(), {"receipt": {}, "approved": frozenset()}, "author_candidates")
            source.assert_not_called()

    def test_02_case_clock_and_reservations_keep_parent_history(self):
        parent = TinyBudget(); parent.used["provider_calls"] = 2
        limits = {k: 10 for k in parent.limits}
        child = CaseBudget(parent, limits, 20)
        self.assertEqual(child.origin_monotonic, parent.origin_monotonic)
        self.assertEqual(child.deadline_monotonic, parent.deadline_monotonic)
        child.charge("provider_calls", 3)
        self.assertEqual(parent.used["provider_calls"], 5)
        with self.assertRaises(AdapterError): child.charge("provider_calls", True)
        with self.assertRaises(AdapterError): child.charge("provider_calls", 8)

    def test_03_provider_finish_usage_and_tool_schema_fail_closed(self):
        message, finish, usage = parse_completion(response())
        self.assertEqual(finish, "stop"); self.assertEqual(usage["total_tokens"], 5)
        for bad in ("length", "content_filter", None):
            with self.assertRaises(AdapterError): parse_completion(response(bad))
        wrong = response(); wrong["usage"]["completion_tokens"] = True
        with self.assertRaises(AdapterError): parse_completion(wrong)
        wrong = response(); wrong["choices"][0]["index"] = False
        with self.assertRaises(AdapterError): parse_completion(wrong)
        tool = response("tool_calls")
        tool["choices"][0]["message"] = {"role": "assistant", "content": None,
            "tool_calls": [{"id": "invented-call", "type": "function", "function": {"name": "python", "arguments": '{"code":"print(1)"}'}}]}
        self.assertEqual(parse_completion(tool)[1], "tool_calls")
        tool["choices"][0]["message"]["tool_calls"][0]["function"]["name"] = "query_lookup"
        with self.assertRaises(AdapterError): parse_completion(tool)

    def test_04_bounded_http_double_records_transcript_without_network(self):
        class Reply:
            status = 200
            def __init__(self): self.data = io.BytesIO(canonical(response())); self.closed = False
            def getheader(self, key): return "invented-request-id" if key == "x-request-id" else None
            def read(self, size): return self.data.read(size)
            def close(self): self.closed = True
        class Connection:
            sock = None
            def __init__(self, host, timeout): self.reply = Reply(); self.closed = False
            def request(self, method, path, body, headers):
                document = json.loads(body)
                assert method == "POST" and path == "/v1/chat/completions"
                assert document["store"] is False and document["stream"] is False and document["n"] == 1
                assert "tools" not in document
                assert headers["Authorization"] == "Bearer invented-not-auth"
            def getresponse(self): return self.reply
            def close(self): self.closed = True
        config = {"endpoint": ENDPOINT, "model": "invented-model", "api_key_env": "NEURAL053_ENGINEERING_KEY",
                  "max_completion_tokens": 8, "prompt_token_reservation": 5120,
                  "request_cap_bytes": 1024, "response_cap_bytes": 512, "request_timeout_seconds": 2}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"NEURAL053_ENGINEERING_KEY": "invented-not-auth"}), \
             patch("adapters.provider.http.client.HTTPSConnection", Connection):
            budget = TinyBudget(); transport = ChatCompletionTransport(config, budget, Path(directory)/"evidence")
            _, finish = transport.complete([{"role": "user", "content": "invented static task"}], allow_tools=False)
            self.assertEqual(finish, "stop")
            self.assertEqual(budget.used["provider_tokens"], 5128)
            record = transport.records[0]
            self.assertTrue(record["response_stream_closed"])
            for key in ("request_artifact", "response_artifact"):
                authenticate(record[key], budget)
            self.assertNotIn("invented-not-auth", json.dumps(record))

    def test_05_fixed_program_cannot_train_before_data_free_seal(self):
        context = ProviderContext.__new__(ProviderContext)
        context.case = {"mode": "fixed_program"}; context.phase = "new"; context.program = None
        with self.assertRaises(AdapterError): context.train_fixed({}, {"sentinel": "training"}, object())
        with self.assertRaises(AdapterError): context.investigate("static", {}, object())
        with self.assertRaises(AdapterError): context._run({"sentinel": "must not be read"})
        self.assertEqual(case_key({"mode": "fixed_program", "replication": 0, "fold_ordinal": 0, "arm": "neural"}),
                         ("fixed_program", 0, 0, "neural"))

    @unittest.skip("Historical V2 live-process control; V3 requires separately qualified Linux namespace. Use fake observer controls here.")
    def test_06_actual_owned_python_process_natural_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = ProcessObserver().run([sys.executable, "-I", "-B", "-c", "print('tiny')"],
                cwd=directory, env={"PATH": "/usr/bin:/bin"}, budget=TinyBudget(), seconds=2,
                cleanup_seconds=0.2, stream_cap=128)
            obs = result["observation"]
            self.assertIs(type(obs["natural_exit_code"]), int); self.assertEqual(obs["natural_exit_code"], 0)
            self.assertTrue(obs["process_reaped"] and obs["process_group_absent"] and obs["streams_closed"])
            self.assertEqual(result["stdout"], b"tiny\n")

    @unittest.skip("Historical V2 live-process control; V3 requires separately qualified Linux namespace. Use fake observer controls here.")
    def test_07_process_nonzero_and_stream_overflow_preserve_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            for source, cap in [("import sys;sys.exit(3)", 128), ("print('x'*1000)", 16)]:
                with self.assertRaises(AdapterError) as caught:
                    ProcessObserver().run([sys.executable, "-I", "-B", "-c", source], cwd=directory,
                        env={"PATH": "/usr/bin:/bin"}, budget=TinyBudget(), seconds=2, cleanup_seconds=0.2, stream_cap=cap)
                self.assertTrue(caught.exception.evidence["process_reaped"])
                self.assertTrue(caught.exception.evidence["process_group_absent"])

    def test_08_artifact_substitution_and_worker_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"invented.json"; path.write_text('{"x":1}')
            pin = file_pin(path, 20)
            path.write_text('{"x":2}')
            with self.assertRaises(AdapterError): authenticate(pin, TinyBudget())
            self.assertEqual(workspace_extent(directory), 7)
        self.assertEqual(container_path("query"), "/case/query.npy")
        self.assertIn("reference_selection", INPUT_NAMES); self.assertIn("query_descriptor", INPUT_NAMES)
        self.assertNotIn("targets", INPUT_NAMES)

    def test_09_equal_fixed_wall_envelope_and_unicode_canonical_bytes(self):
        adapter = BoundAdapter.__new__(BoundAdapter)
        adapter.config = {"schema": "neural053_production_adapters_v2", "provider": {},
            "workspace_root": "/invented", "source": {"root": "/invented", "files": []},
            "case_limits": {**{x: 10 for x in ("provider_calls", "provider_tokens", "tool_calls", "source_read", "artifact_write", "stream_bytes")}, "wall_seconds": 10},
            "sandbox": {"docker_binary": {}, "docker_endpoint": "unix:///invented.sock", "image_digest": "sha256:" + "0"*64,
                "python": "/usr/bin/python", "memory_bytes": 100, "cpus": 1, "pids_limit": 1, "tmpfs_bytes": 100,
                "tool_seconds": 9, "cleanup_seconds": 1, "stream_cap_bytes": 100, "workspace_cap_bytes": 100, "poll_seconds": 1}}
        with self.assertRaises(AdapterError): adapter._validate_config()
        adapter.config["sandbox"]["tool_seconds"] = 10
        adapter._validate_config()
        self.assertEqual(canonical({"name": "méthod"}), '{"name":"méthod"}'.encode())

    def test_10_staged_source_is_checked_against_approved_member(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"tiny.py"; path.write_text("x=1\n")
            pin = file_pin(path, 10)
            adapter = BoundAdapter.__new__(BoundAdapter)
            adapter.config = {"source": {"files": [{**pin, "path": "tiny.py"}]}}
            adapter.verify_staged_source(Path(directory), TinyBudget())
            path.write_text("x=2\n")
            with self.assertRaises(AdapterError): adapter.verify_staged_source(Path(directory), TinyBudget())


if __name__ == "__main__": unittest.main(verbosity=2)
