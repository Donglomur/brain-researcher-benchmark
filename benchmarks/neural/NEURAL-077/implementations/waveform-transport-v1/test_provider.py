"""Independent generated Responses-adapter controls; no HTTP, keys or models."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PREFIX = struct.Struct("!I")
QUERY_ID = "development-001-" + "a" * 24
MODEL = "generated-fixed-model-001"
TOKENS = 128


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


p = module(HERE / "provider_bridge.py", "independent_neural077_provider")
t = module(HERE / "transport.py", "independent_neural077_provider_transport")
PROMPT = p.NO_TOOLS + '\nGenerated software fixture.\n{"trial_id":"' + QUERY_ID + '","channels":[[0],[1]]}\n'
ANSWER = json.dumps({"trial_id": QUERY_ID, "target_probability": 0.25})


def response(text=ANSWER):
    return {
        "object": "response", "status": "completed", "error": None, "incomplete_details": None,
        "tools": [], "tool_choice": "none", "parallel_tool_calls": False, "store": False,
        "truncation": "disabled", "previous_response_id": None, "conversation": None,
        "model": MODEL, "max_output_tokens": TOKENS, "id": "resp_generated_001",
        "output": [{"type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    }


def raw(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def frame(body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return PREFIX.pack(len(body)) + body


class RequestControls(unittest.TestCase):
    def test_exact_single_prompt_and_declared_no_tools_policy(self):
        body = p.request_body(PROMPT, MODEL, TOKENS)
        value = json.loads(body)
        self.assertEqual(value["input"], [{"role": "user", "content": [{"type": "input_text", "text": PROMPT}]}])
        self.assertEqual(value["tools"], [])
        self.assertEqual(value["tool_choice"], "none")
        self.assertIs(value["parallel_tool_calls"], False)
        self.assertIs(value["store"], False)
        self.assertIs(value["stream"], False)
        self.assertIs(value["background"], False)
        self.assertEqual(value["truncation"], "disabled")
        self.assertEqual(value["model"], MODEL)
        self.assertEqual(value["max_output_tokens"], TOKENS)
        self.assertNotIn("previous_response_id", value)
        self.assertNotIn("conversation", value)
        self.assertNotIn("instructions", value)
        fmt = value["text"]["format"]
        self.assertEqual(fmt["type"], "json_schema")
        self.assertIs(fmt["strict"], True)
        self.assertEqual(fmt["schema"]["properties"]["trial_id"]["enum"], [QUERY_ID])
        self.assertEqual(fmt["schema"]["required"], ["trial_id", "target_probability"])
        self.assertIs(fmt["schema"]["additionalProperties"], False)

    def test_matched_programme_and_changed_query_policy_refused(self):
        prompts = [PROMPT.replace(p.NO_TOOLS, "Numerical tools and candidate code execution are allowed for this query."),
                   PROMPT + p.NO_TOOLS, PROMPT + "development-002-" + "b" * 24,
                   p.NO_TOOLS + "\nNo development identifier here"]
        for prompt in prompts:
            with self.subTest(prompt=prompt), self.assertRaises(ValueError):
                p.request_body(prompt, MODEL, TOKENS)

    def test_prompt_byte_cap_and_no_silent_truncation(self):
        for prompt in ("", b"not a string", PROMPT + "x" * p.PROMPT_CAP,
                       PROMPT + "\u03b1" * (p.PROMPT_CAP // 2)):
            with self.subTest(kind=type(prompt).__name__), self.assertRaises(ValueError):
                p.request_body(prompt, MODEL, TOKENS)
        exact = PROMPT + "x" * (p.PROMPT_CAP - len(PROMPT.encode()))
        self.assertEqual(json.loads(p.request_body(exact, MODEL, TOKENS))["input"][0]["content"][0]["text"], exact)

    def test_explicit_model_and_output_allocation_bounds(self):
        for model in ("", "bad\nmodel", "a" * 161, None, True):
            with self.subTest(model=model), self.assertRaises(ValueError):
                p.request_body(PROMPT, model, TOKENS)
        for tokens in (True, 0, -1, 32769, float("nan"), 1.5):
            with self.subTest(tokens=tokens), self.assertRaises(ValueError):
                p.request_body(PROMPT, MODEL, tokens)


class ResponseControls(unittest.TestCase):
    def test_complete_scalar_and_token_accounting(self):
        answer, metadata = p.completed_text(raw(response()), QUERY_ID, MODEL, TOKENS)
        self.assertEqual(answer, ANSWER.encode())
        self.assertEqual(metadata, {"provider_response_id": "resp_generated_001", "model": MODEL,
                                    "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}})

    def test_reasoning_item_can_precede_one_final_answer(self):
        value = response()
        value["output"].insert(0, {"type": "reasoning", "id": "rs_generated", "summary": []})
        answer, _ = p.completed_text(raw(value), QUERY_ID, MODEL, TOKENS)
        self.assertEqual(answer, ANSWER.encode())

    def test_failure_incomplete_refusal_and_tool_items_refused(self):
        mutations = []
        for key, val in (("status", "incomplete"), ("error", {"code": "generated_failure"}),
                         ("incomplete_details", {"reason": "max_output_tokens"}), ("object", "other")):
            value = response(); value[key] = val; mutations.append(value)
        value = response(); value["output"][0]["content"] = [{"type": "refusal", "refusal": "generated"}]; mutations.append(value)
        for kind in ("function_call", "code_interpreter_call", "web_search_call", "file_search_call"):
            value = response(); value["output"].insert(0, {"type": kind}); mutations.append(value)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.completed_text(raw(value), QUERY_ID, MODEL, TOKENS)

    def test_history_policy_model_and_allocation_mismatches_refused(self):
        cases = (("tools", [{"type": "web_search"}]), ("tool_choice", "auto"),
                 ("parallel_tool_calls", True), ("store", True), ("truncation", "auto"),
                 ("previous_response_id", "resp_previous"), ("conversation", {"id": "conv_old"}),
                 ("model", "a-different-model"), ("max_output_tokens", TOKENS + 1),
                 ("max_output_tokens", True), ("id", "missing_required_prefix"))
        for key, value in cases:
            changed = response(); changed[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                p.completed_text(raw(changed), QUERY_ID, MODEL, TOKENS)

    def test_original_scalar_rules_are_not_relaxed_by_provider_schema(self):
        answers = ["{}", "prose " + ANSWER, ANSWER.replace("0.25", "true"),
                   ANSWER.replace("0.25", "NaN"), ANSWER.replace("0.25", "1.1"),
                   ANSWER.replace(QUERY_ID, "development-002-" + "b" * 24),
                   '{"trial_id":' + json.dumps(QUERY_ID) + ',"target_probability":0.1,"target_probability":0.2}',
                   json.dumps({"trial_id": QUERY_ID, "target_probability": 0.2, "extra": 1})]
        for answer in answers:
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                p.completed_text(raw(response(answer)), QUERY_ID, MODEL, TOKENS)

    def test_exactly_one_completed_assistant_output_required(self):
        changes = []
        value = response(); value["output"] = []; changes.append(value)
        value = response(); value["output"] *= 2; changes.append(value)
        value = response(); value["output"][0]["role"] = "user"; changes.append(value)
        value = response(); value["output"][0]["status"] = "in_progress"; changes.append(value)
        value = response(); value["output"][0]["content"] *= 2; changes.append(value)
        value = response(); value["output"] *= 33; changes.append(value)
        for value in changes:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.completed_text(raw(value), QUERY_ID, MODEL, TOKENS)

    def test_duplicate_nonfinite_and_invalid_utf8_provider_json(self):
        good = raw(response())
        bodies = [good.replace(b'"status":"completed"', b'"status":"completed","status":"completed"', 1),
                  good.replace(b'"input_tokens":100', b'"input_tokens":NaN', 1), b"\xff", b"[]"]
        for body in bodies:
            with self.subTest(body=body[:80]), self.assertRaises((ValueError, UnicodeError)):
                p.completed_text(body, QUERY_ID, MODEL, TOKENS)

    def test_provider_body_and_scalar_size_caps(self):
        for body in (b"", b"x" * (p.PROVIDER_RESPONSE_CAP + 1), "not bytes"):
            with self.subTest(kind=type(body).__name__), self.assertRaises(ValueError):
                p.completed_text(body, QUERY_ID, MODEL, TOKENS)
        with self.assertRaises(ValueError):
            p.completed_text(raw(response(" " * 4096 + ANSWER)), QUERY_ID, MODEL, TOKENS)

    def test_invalid_token_counts_and_budget_overrun_refused(self):
        invalid = [None, {}, {"input_tokens": True, "output_tokens": 20, "total_tokens": 21},
                   {"input_tokens": -1, "output_tokens": 20, "total_tokens": 19},
                   {"input_tokens": 100, "output_tokens": 20, "total_tokens": 121},
                   {"input_tokens": 100, "output_tokens": TOKENS + 1, "total_tokens": 100 + TOKENS + 1}]
        for usage in invalid:
            value = response(); value["usage"] = usage
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                p.completed_text(raw(value), QUERY_ID, MODEL, TOKENS)


class ExchangeControls(unittest.TestCase):
    def test_one_sender_one_receipt_exact_request_and_answer(self):
        calls, receipts = [], []
        body = raw(response())
        def sender(request):
            calls.append(request)
            return body
        answer = p.exchange(PROMPT, model=MODEL, max_output_tokens=TOKENS,
                            send_json=sender, record=receipts.append)
        self.assertEqual(calls, [p.request_body(PROMPT, MODEL, TOKENS)])
        self.assertEqual(answer, ANSWER.encode())
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual(receipt["sender_calls_attempted"], 1)
        self.assertEqual(receipt["retry_count"], 0)
        self.assertEqual(receipt["status"], "complete_unscored_answer")
        self.assertEqual(receipt["response"], p.pin(body))
        self.assertEqual(receipt["answer"], p.pin(answer))
        self.assertIs(receipt["provider_execution_qualified"], False)
        self.assertIs(receipt["provider_capacity_qualified"], False)
        self.assertIs(receipt["scientific_qualification"], False)
        self.assertNotIn("input", receipt)

    def test_sender_exception_is_sanitized_and_never_retried(self):
        calls, receipts = [], []
        secret = "generated-Authorization-secret-do-not-log"
        def sender(request):
            calls.append(request)
            raise RuntimeError(secret)
        with self.assertRaises(ValueError) as caught:
            p.exchange(PROMPT, model=MODEL, max_output_tokens=TOKENS,
                       send_json=sender, record=receipts.append)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["status"], "failed_no_answer")
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, json.dumps(receipts))
        self.assertIsNone(receipts[0]["response"])
        self.assertIsNone(receipts[0]["answer"])

    def test_invalid_provider_body_is_recorded_without_answer(self):
        receipts = []
        bad = raw(response()).replace(b'"status":"completed"', b'"status":"incomplete"', 1)
        with self.assertRaises(ValueError):
            p.exchange(PROMPT, model=MODEL, max_output_tokens=TOKENS,
                       send_json=lambda request: bad, record=receipts.append)
        self.assertEqual(receipts[0]["response"], p.pin(bad))
        self.assertIsNone(receipts[0]["answer"])
        self.assertEqual(receipts[0]["status"], "failed_no_answer")

    def test_record_failure_prevents_any_answer_frame(self):
        output = io.BytesIO()
        calls = []
        def sender(request):
            calls.append(request)
            return raw(response())
        def sink(receipt):
            raise OSError("generated receipt sink failure")
        with self.assertRaises((ValueError, OSError)):
            p.serve(io.BytesIO(frame(PROMPT)), output, model=MODEL, max_output_tokens=TOKENS,
                    send_json=sender, record=sink)
        self.assertEqual(len(calls), 1)
        self.assertEqual(output.getvalue(), b"")

    def test_wrong_condition_refused_before_sender(self):
        calls, receipts = [], []
        with self.assertRaises(ValueError):
            p.exchange(PROMPT.replace(p.NO_TOOLS, "Tools allowed"), model=MODEL, max_output_tokens=TOKENS,
                       send_json=lambda value: calls.append(value), record=receipts.append)
        self.assertEqual(calls, [])
        self.assertEqual(receipts, [])


class PipeControls(unittest.TestCase):
    def test_shipped_scripted_client_completes_generated_prompt(self):
        with tempfile.TemporaryDirectory(prefix="generated-neural077-example-") as tmp:
            root = Path(tmp).resolve()
            row = {"ordinal": 0, "trial_id": QUERY_ID, "prompt": PROMPT,
                   "context_sha256": hashlib.sha256(PROMPT.encode()).hexdigest()}
            output = root / "episode"
            envelope, _ = t.run_episode(row, "legacy_waveform_no_tools", output,
                                        HERE / "scripted_client.py", sys.executable,
                                        sandbox="protocol_only")
            self.assertEqual(envelope["status"], "ok")
            self.assertEqual(json.loads(envelope["response"]),
                             {"trial_id": QUERY_ID, "target_probability": 0.5})
            self.assertEqual((output / "INPUT.bin").read_bytes(), frame(PROMPT))
            written = sum(path.stat().st_size for path in root.rglob("*")
                          if path.is_file() and not path.is_symlink())
            print("GENERATED_PUBLIC_CLIENT_FIXTURE_BYTES " + str(written))

    def test_binary_serve_roundtrip_and_partial_output_writes(self):
        class PartialWriter:
            def __init__(self):
                self.body = bytearray(); self.flushed = False
            def write(self, body):
                self.body.extend(body[:3]); return min(3, len(body))
            def flush(self):
                self.flushed = True
        output = PartialWriter()
        calls, receipts = [], []
        def sender(request):
            calls.append(request); return raw(response())
        p.serve(io.BytesIO(frame(PROMPT)), output, model=MODEL, max_output_tokens=TOKENS,
                send_json=sender, record=receipts.append)
        self.assertEqual(bytes(output.body), frame(ANSWER))
        self.assertTrue(output.flushed)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(receipts), 1)

    def test_malformed_or_extra_input_frames_never_call_sender(self):
        inputs = [b"", b"\x00", PREFIX.pack(0), PREFIX.pack(p.PROMPT_CAP + 1),
                  PREFIX.pack(50) + b"short", frame(b"\xff"), frame(PROMPT) + frame(PROMPT)]
        for body in inputs:
            calls, receipts = [], []
            output = io.BytesIO()
            with self.subTest(body=body[:40]), self.assertRaises((ValueError, UnicodeError)):
                p.serve(io.BytesIO(body), output, model=MODEL, max_output_tokens=TOKENS,
                        send_json=lambda value: calls.append(value), record=receipts.append)
            self.assertEqual(calls, [])
            self.assertEqual(receipts, [])
            self.assertEqual(output.getvalue(), b"")

    def test_oversized_prefix_is_refused_before_body_read(self):
        class PrefixOnly:
            def __init__(self): self.calls = []
            def read(self, n):
                self.calls.append(n)
                if len(self.calls) == 1: return PREFIX.pack(2**32 - 1)
                raise AssertionError("oversized body must never be read")
        source = PrefixOnly()
        with self.assertRaises(ValueError):
            p.serve(source, io.BytesIO(), model=MODEL, max_output_tokens=TOKENS,
                    send_json=lambda value: self.fail("sender called"), record=lambda value: self.fail("receipt called"))
        self.assertEqual(source.calls, [4])

    def test_invalid_output_writer_is_not_retried(self):
        class BadWriter:
            def write(self, body): return 0
            def flush(self): raise AssertionError("must not flush failed output")
        calls = []
        def sender(request): calls.append(request); return raw(response())
        with self.assertRaises(ValueError):
            p.serve(io.BytesIO(frame(PROMPT)), BadWriter(), model=MODEL, max_output_tokens=TOKENS,
                    send_json=sender, record=lambda value: None)
        self.assertEqual(len(calls), 1)

    def test_real_generated_child_bridge_integrates_with_runner(self):
        with tempfile.TemporaryDirectory(prefix="generated-neural077-provider-") as tmp:
            root = Path(tmp).resolve()
            client = root / "fake-provider-client.py"
            client.write_text('''import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('generated_provider', ''' + repr(str(HERE / "provider_bridge.py")) + ''')
p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
calls=[]
def sender(body):
    request=json.loads(body)
    assert request['input']==''' + repr([{"role": "user", "content": [{"type": "input_text", "text": PROMPT}]}]) + '''
    assert request['tools']==[] and request['tool_choice']=='none'
    calls.append(body)
    assert len(calls)==1
    return ''' + repr(raw(response())) + '''
def sink(receipt):
    assert receipt['status']=='complete_unscored_answer'
    assert receipt['sender_calls_attempted']==1
p.serve(sys.stdin.buffer,sys.stdout.buffer,model=''' + repr(MODEL) + ''',max_output_tokens=''' + repr(TOKENS) + ''',send_json=sender,record=sink)
''')
            row = {"ordinal": 0, "trial_id": QUERY_ID, "prompt": PROMPT,
                   "context_sha256": hashlib.sha256(PROMPT.encode()).hexdigest()}
            output = root / "episode"
            envelope, receipt = t.run_episode(row, "legacy_waveform_no_tools", output,
                                              client, sys.executable, sandbox="protocol_only")
            self.assertEqual(envelope["status"], "ok")
            self.assertEqual(envelope["response"], ANSWER)
            self.assertEqual((output / "INPUT.bin").read_bytes(), frame(PROMPT))
            self.assertEqual((output / "OUTPUT.bin").read_bytes(), frame(ANSWER))
            written = sum(path.stat().st_size for path in root.rglob("*")
                          if path.is_file() and not path.is_symlink())
            print("GENERATED_PROVIDER_CHILD_FIXTURE_BYTES " + str(written))


if __name__ == "__main__":
    unittest.main()
