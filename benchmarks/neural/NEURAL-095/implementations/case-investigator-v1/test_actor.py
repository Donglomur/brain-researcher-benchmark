"""Generated actor/protocol controls, never scientific arrays or model calls."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
TEMPLATE = (HERE / "actor.py").read_bytes()
spec = importlib.util.spec_from_file_location("generated_assembly", HERE / "assemble.py")
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)
FIXTURE_BYTES = 0
TOOL = "dmfc_predict@" + "a" * 64
CONFIG = {"schema": "dmfc-case-investigator/v1", "mode": "case_adaptive__neural",
          "tool_id": TOOL, "policy": "stateful_case_decisions/v1"}


def source(callback):
    body = assembly.assemble(TEMPLATE, callback.encode())
    module = types.ModuleType("generated_actor")
    exec(compile(body, "<generated assembled actor>", "exec"), module.__dict__)
    return module, body


def write(path, body):
    global FIXTURE_BYTES
    path.write_bytes(body)
    FIXTURE_BYTES += len(body)


def prediction(expression="1000.0"):
    return "def decide(c):\n    return {'action':'predict','case_id':c['current']['case_id'],'prediction_ms':" + expression + "}\n"


ADAPTIVE = """
visits = 0
def decide(c):
    global visits
    visits += 1
    current = c['current']
    i = current['completed_cases']
    observations = [r for r in c['tool_observations'] if r['case_id'] == current['case_id']]
    inspect = i == 0 or (i == 1 and c['committed_predictions'][0]['prediction_ms'] > 500)
    if inspect and not observations:
        return {'action':'tool','tool_id':c['tool_id'],'arguments':{'case_id':current['case_id'],'analysis':'frozen_diagnostic'}}
    value = observations[-1]['observation']['value'] if observations else i + visits
    return {'action':'predict','case_id':current['case_id'],'prediction_ms':value}
"""


class Host:
    def __init__(self, module, offset=100.0):
        self.module, self.offset = module, offset
        self.index = 0
        self.calls, self.outputs = [], []
        self.pending = None
        self.finished = False
        self.freeze = False

    def call(self, value):
        assert value["op"] == "freeze" and not self.freeze
        self.freeze = True
        self.calls.append(copy.deepcopy(value))
        return hashlib.sha256(value["source"].encode()).hexdigest()

    def public(self, request):
        assert self.freeze and not self.finished
        self.calls.append(copy.deepcopy(request))
        kind = request["kind"]
        if kind == "prepare":
            return {"training_artifacts_sha256": "b" * 64}
        if kind == "next":
            return {"case_id": f"case{self.index:07d}", "completed_cases": self.index, "full_query_batch_visible": True}
        if kind == "action":
            action = request["action"]
            if action["action"] == "tool":
                assert self.pending is None
                self.pending = copy.deepcopy(action)
            else:
                assert action["case_id"] == f"case{self.index:07d}" and self.pending is None
                self.outputs.append(copy.deepcopy(action))
                self.index += 1
            return {"accepted": True}
        assert kind == "tool" and self.pending is not None
        assert request["tool_id"] == self.pending["tool_id"] and request["arguments"] == self.pending["arguments"]
        self.pending = None
        return {"value": self.offset + self.index}

    def finish(self):
        assert self.index == 258 and self.pending is None
        self.finished = True


class ActorControls(unittest.TestCase):
    def run_actor(self, callback=ADAPTIVE, offset=100.0, config=None):
        module, body = source(callback)
        host = Host(module, offset)
        report = module.investigate(host, config or CONFIG, body)
        return module, host, report

    def test_observation_changes_later_decision_and_complete_258_outputs(self):
        _, low, first = self.run_actor(offset=100.0)
        _, high, second = self.run_actor(offset=900.0)
        self.assertEqual((len(low.outputs), len(high.outputs)), (258, 258))
        self.assertTrue(low.finished and high.finished)
        self.assertEqual(first["tool_calls"], 1)
        self.assertEqual(second["tool_calls"], 2)
        self.assertEqual(low.outputs[0]["prediction_ms"], 100)
        self.assertEqual(high.outputs[0]["prediction_ms"], 900)
        self.assertEqual(high.outputs[1]["prediction_ms"], 901)
        self.assertNotEqual(low.outputs[1], high.outputs[1])
        self.assertEqual(len({row["case_id"] for row in high.outputs}), 258)

    def test_sixteen_tools_and_all_predictions_fit_exact292_operations(self):
        callback = """def decide(c):
    if c['remaining_tool_calls']:
        return {'action':'tool','tool_id':c['tool_id'],'arguments':{'i':c['remaining_tool_calls']}}
    return {'action':'predict','case_id':c['current']['case_id'],'prediction_ms':-1.0}
"""
        _, host, report = self.run_actor(callback)
        self.assertEqual((report["tool_calls"], report["decision_calls"], report["reserved_operation_count"]), (16, 274, 292))
        self.assertEqual(len(host.outputs), 258)
        self.assertEqual(host.outputs[-1]["prediction_ms"], -1)

    def test_seventeenth_tool_refused_without_dispatch_or_finish(self):
        module, body = source("def decide(c):\n    return {'action':'tool','tool_id':c['tool_id'],'arguments':{}}\n")
        host = Host(module)
        with self.assertRaisesRegex(module.ActorError, "sixteen-tool"):
            module.investigate(host, CONFIG, body)
        self.assertEqual(sum(row.get("kind") == "tool" for row in host.calls), 16)
        self.assertFalse(host.finished)

    def test_callback_initialization_occurs_after_first_case_and_state_resets_between_cells(self):
        callback = """counter = 0
def decide(c):
    global counter
    counter += 1
    return {'action':'predict','case_id':c['current']['case_id'],'prediction_ms':counter}
"""
        module, body = source(callback)
        events = []
        original = module.load_decision
        module.load_decision = lambda raw: (events.append("callback_load"), original(raw))[1]
        for _ in range(2):
            host = Host(module)
            original_public = host.public
            def public(request):
                events.append(request["kind"])
                return original_public(request)
            host.public = public
            module.investigate(host, CONFIG, body)
            self.assertEqual(host.outputs[0]["prediction_ms"], 1)
            self.assertEqual(host.outputs[-1]["prediction_ms"], 258)
        self.assertEqual(events[:3], ["prepare", "next", "callback_load"])

    def test_callback_cannot_mutate_already_committed_history(self):
        callback = """def decide(c):
    if c['committed_predictions']:
        c['committed_predictions'][0]['prediction_ms'] = 999999
    return {'action':'predict','case_id':c['current']['case_id'],'prediction_ms':c['current']['completed_cases']}
"""
        _, host, _ = self.run_actor(callback)
        self.assertEqual(host.outputs[0]["prediction_ms"], 0)

    def test_current_case_cannot_change_after_tool(self):
        module, body = source(ADAPTIVE)
        host = Host(module)
        original = host.public
        count = 0
        def public(request):
            nonlocal count
            result = original(request)
            if request["kind"] == "next":
                count += 1
                if count == 2: result["case_id"] = "wrong_case"
            return result
        host.public = public
        with self.assertRaisesRegex(module.ActorError, "advance or replace"):
            module.investigate(host, CONFIG, body)
        self.assertFalse(host.finished)

    def test_duplicate_case_and_missing_full_batch_permission_refused(self):
        for variant in ("duplicate", "batch"):
            module, body = source(prediction())
            host = Host(module)
            original = host.public
            def public(request):
                result = original(request)
                if request["kind"] == "next":
                    if variant == "duplicate" and host.index == 1: result["case_id"] = "case0000000"
                    if variant == "batch": result["full_query_batch_visible"] = False
                return result
            host.public = public
            with self.assertRaises(module.ActorError): module.investigate(host, CONFIG, body)
            self.assertFalse(host.finished)

    def test_invalid_prediction_or_unlisted_tool_fails_before_commit(self):
        for expression in ("True", "float('nan')", "10**1000"):
            module, body = source(prediction(expression))
            host = Host(module)
            with self.assertRaises(module.ActorError): module.investigate(host, CONFIG, body)
            self.assertEqual(host.outputs, [])
        module, body = source("def decide(c):\n    return {'action':'tool','tool_id':'foreign','arguments':{}}\n")
        host = Host(module)
        with self.assertRaisesRegex(module.ActorError, "admitted frozen-fit"):
            module.investigate(host, CONFIG, body)

    def test_false_acknowledgement_or_integer_true_refused(self):
        for value in (False, 1):
            module, body = source(prediction())
            host = Host(module)
            original = host.public
            def public(request):
                result = original(request)
                return {"accepted": value} if request["kind"] == "action" else result
            host.public = public
            with self.assertRaisesRegex(module.ActorError, "not accepted"):
                module.investigate(host, CONFIG, body)
            self.assertFalse(host.finished)

    def test_callback_protocol_stdout_is_refused(self):
        module, body = source("def decide(c):\n    print('unexpected protocol output')\n    return {}\n")
        host = Host(module)
        with self.assertRaisesRegex(module.ActorError, "protocol stdout"):
            module.investigate(host, CONFIG, body)

    def test_corrupt_callback_pin_and_wrong_condition_refused(self):
        module, body = source(prediction())
        module.CALLBACK_PIN["sha256"] = "0" * 64
        host = Host(module)
        with self.assertRaisesRegex(module.ActorError, "identity changed"):
            module.investigate(host, CONFIG, body)
        self.assertFalse(host.freeze)
        module, body = source(prediction())
        for key, value in (("mode", "frozen_program__neural"), ("policy", "single_frozen_fit_batch/v1")):
            config = dict(CONFIG, **{key: value})
            with self.assertRaises(module.ActorError): module.investigate(Host(module), config, body)

    def test_oversize_tool_observation_fails_without_retry(self):
        module, body = source(ADAPTIVE)
        host = Host(module)
        original = host.public
        def public(request):
            result = original(request)
            return {"value": "x" * 65536} if request["kind"] == "tool" else result
        host.public = public
        with self.assertRaisesRegex(module.ActorError, "state cap"):
            module.investigate(host, CONFIG, body)
        self.assertEqual(sum(row.get("kind") == "tool" for row in host.calls), 1)

    def test_wire_rejects_duplicate_keys_truncation_oversize_and_bad_freeze(self):
        module, _ = source(prediction())
        for body in (b'{"a":1,"a":2}\n', b'{}', b'{}\n' + b'x' * 20):
            wire = module.Wire(io.BytesIO(body), io.BytesIO())
            if body.startswith(b'{}\n'):
                with self.assertRaises(module.ActorError): wire.read(2)
            else:
                with self.assertRaises(module.ActorError): wire.read(100)
        wire = module.Wire(io.BytesIO(b'{"status":"committed","controller_sha256":"wrong"}\n'), io.BytesIO())
        with self.assertRaisesRegex(module.ActorError, "exact assembled"):
            wire.call({"op": "freeze", "source": "generated"})

    def test_single_source_cli_drives_complete_original_wire_without_callback_mount(self):
        callback = """def decide(c):
    if c['current']['completed_cases'] == 0 and not c['tool_observations']:
        return {'action':'tool','tool_id':c['tool_id'],'arguments':{'analysis':'diagnostic'}}
    return {'action':'predict','case_id':c['current']['case_id'],'prediction_ms':c['current']['completed_cases']+c['tool_observations'][0]['observation']['value']}
"""
        module, body = source(callback)
        replies = [CONFIG, {"status": "committed", "controller_sha256": hashlib.sha256(body).hexdigest()},
                   {"status": "ok", "payload": {"training_artifacts_sha256": "b" * 64}}]
        for i in range(258):
            current = {"case_id": f"case{i:07d}", "completed_cases": i, "full_query_batch_visible": True}
            replies.append({"status": "ok", "payload": current})
            if i == 0:
                replies.extend([{"status": "ok", "payload": {"accepted": True}},
                                {"status": "ok", "payload": {"value": 7}},
                                {"status": "ok", "payload": current}])
            replies.append({"status": "ok", "payload": {"accepted": True}})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "program.py"
            write(path, body)
            result = subprocess.run([sys.executable, "-I", "-B", str(path)],
                                    input=b"".join(module.encode(row) + b"\n" for row in replies),
                                    capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        requests = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(requests[0], {"op": "freeze", "source": body.decode()})
        self.assertEqual(requests[-1], {"op": "finish"})
        predictions = [row["request"]["action"] for row in requests if row.get("op") == "public"
                       and row["request"].get("kind") == "action" and row["request"]["action"].get("action") == "predict"]
        self.assertEqual(len(predictions), 258)
        self.assertEqual(predictions[-1]["prediction_ms"], 264)

    def test_assembler_does_not_execute_candidate_and_refuses_bad_signature_or_pin(self):
        callback = b"raise RuntimeError('must not execute during assembly')\ndef decide(c):\n    return {}\n"
        self.assertLessEqual(len(assembly.assemble(TEMPLATE, callback)), 65536)
        with self.assertRaises(ValueError): assembly.assemble(TEMPLATE, b"def decide(a,b):\n    return {}\n")
        with self.assertRaises(ValueError): assembly.assemble(TEMPLATE, b"#" + b"x" * 65000 + b"\ndef decide(c):\n    return {}\n")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "callback.py"
            write(path, callback)
            with self.assertRaisesRegex(ValueError, "pin mismatch"): assembly.capture(path, "0" * 64)


if __name__ == "__main__":
    result = unittest.main(exit=False)
    print(json.dumps({"generated_fixture_file_bytes_written": FIXTURE_BYTES, "authentic_data_reads": 0,
                      "model_calls": 0, "native_preparation": False}))
    raise SystemExit(not result.result.wasSuccessful())
