"""Generated investigator-message controls; no provider or scientific execution."""
import base64
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch
import zlib


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "programme-source/implementation-v1/central-integration/successor-v3/effective-parent"


def generated_png():
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x20\x40\x60")) + chunk(b"IEND", b""))


class CapturedRequest(Exception):
    """Stop the generated dialogue after its next request was inspected."""


class MixedEvidenceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package_name = "_n004_mixed_evidence_control"
        spec = importlib.util.spec_from_file_location(cls.package_name, PARENT / "__init__.py",
                                                     submodule_search_locations=[str(PARENT)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        cls.actor = importlib.import_module(cls.package_name + ".investigator")
        cls.common = importlib.import_module(cls.package_name + ".common")

    @classmethod
    def tearDownClass(cls):
        for name in list(sys.modules):
            if name == cls.package_name or name.startswith(cls.package_name + "."):
                del sys.modules[name]

    def message_from_analysis(self, evidence, *, output_limit=8192, image_byte_limit=512):
        """Exercise the real loop with in-memory process/provider doubles.

        The generated analysis payload substitutes for a process result. The
        real history, serialization, image conversion and message branch run;
        neither generated Python nor a model/provider is executed.
        """
        actor, common = self.actor, self.common
        original = copy.deepcopy(evidence)
        captures = []
        failures = []
        ticks = iter(range(10000))
        ledger = types.SimpleNamespace(
            limits={"provider_calls": 3}, tick=lambda *args: next(ticks),
            clock=lambda: next(ticks), reserve=lambda *args, **kwargs: None,
            fail=lambda key, error: failures.append((key, type(error).__name__)))

        class MemoryBodies:
            def put(self, name, raw):
                return {"path": name, **common.body_pin(raw)}

        record = {"outputs_closed": True, "generated_control_only": True}

        class GeneratedProcess:
            def run(self, job, context, files, view, argv, action):
                request_body = files["/request/job.json"]
                request = common.decode(request_body, 8192)
                self_case.assertEqual(action, "analyze")
                execution = {key: request[key] for key in (
                    "job_id", "action", "code_pin", "training_pin", "query_pin", "state_pin")}
                execution.update(request_pin=common.body_pin(request_body), candidate_status="returned")
                return {"outputs": {"EXECUTION.json": common.encode(execution, 8192),
                                    "RESULT.json": common.encode(evidence, 8192)}, "record": record}

        self_case = self
        investigator = actor.Investigator.__new__(actor.Investigator)
        investigator.transport = GeneratedProcess()
        investigator.bodies = MemoryBodies()
        investigator.ledger = ledger
        investigator.worker_source = b"# generated control; never executed\n"
        investigator.python = "/generated/no-process-python"
        limits = {"provider_calls": 3, "tools": 4, "source_bytes": 1024,
                  "state_bytes": 1024, "view_bytes": 8192, "output_bytes": output_limit,
                  "request_bytes": 8192}
        body = b"{}"
        context = {"mode": "I", "view": "E", "context": "generated-context",
                   "training_pin": common.body_pin(body), "held_pin": common.body_pin(body),
                   "training_ids": ["generated-train"], "held_ids": ["generated-query"]}
        packet = {"private_context": context, "training_body": body, "held_body": body}
        instructions = b"Generated software control only."
        policy = {"source": common.body_pin(instructions), "limits": limits,
                  "wire_limits": {"max_response_bytes": 8192, "max_image_bytes": image_byte_limit,
                                  "max_image_pixels": 16},
                  "question": "generated message delivery", "capabilities": {}, "provider": {}}

        def fake_build(provider, messages, tools, wire_limits, *, image_sources):
            captures.append({"messages": copy.deepcopy(messages), "images": copy.deepcopy(image_sources)})
            if len(captures) == 2:
                raise CapturedRequest("second request captured; no provider")
            return {"body": b"{}"}

        def fake_send(*args):
            return {"raw_response": common.encode({"choices": [{"message": {
                "role": "assistant", "content": None}}]}, 8192), "usage": {},
                "actions": [{"id": "generated-revision", "name": "revise",
                             "arguments": {"source": "# generated method, not executed\n"}},
                            {"id": "generated-analysis", "name": "execute",
                             "arguments": {"action": "analyze"}}]}

        with patch.object(actor, "build_request", fake_build), patch.object(actor, "send_https", fake_send):
            with self.assertRaises(CapturedRequest):
                investigator.run(packet, policy, instructions, None, None, None, common.pin({"generated": True}))
        self.assertEqual(evidence, original)
        self.assertEqual(failures, [("generated-context/actor", "CapturedRequest")])
        message = captures[-1]["messages"][-1]
        self.assertEqual(message["role"], "tool")
        self.assertEqual(message["tool_call_id"], "generated-analysis")
        return message["content"], captures[-1]["images"], common.pin(record)

    def test_retained_predecessor_demonstrates_lost_sibling_evidence(self):
        predecessor = HERE.parent / "programme-source/implementation-v1/successor-v3/investigator.py"
        name = self.package_name + ".retained_investigator"
        spec = importlib.util.spec_from_file_location(name, predecessor)
        old = importlib.util.module_from_spec(spec)
        sys.modules[name] = old
        spec.loader.exec_module(old)
        current = self.actor
        try:
            self.actor = old
            parts, _, _ = self.message_from_analysis({"summary": "This was lost.", "images": []})
            self.assertNotIn("evidence", json.loads(parts[0]["text"]))
        finally:
            self.actor = current
            sys.modules.pop(name, None)

    def test_mixed_numeric_and_text_evidence_reaches_next_request(self):
        png = generated_png()
        image = {"mime": "image/png", "base64": base64.b64encode(png).decode("ascii")}
        evidence = {"summary": "Generated means differ.", "difference": -0.125,
                    "counts": [2, 3], "nested": {"note": "preserve me"}, "images": [image]}
        parts, inventory, provenance = self.message_from_analysis(evidence)
        text = json.loads(parts[0]["text"])
        self.assertEqual(text["evidence"], {key: value for key, value in evidence.items() if key != "images"})
        self.assertEqual(text["status"], "analysis")
        self.assertEqual(text["provenance_pin"], provenance)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[1]["image_url"]["url"], "data:image/png;base64," + image["base64"])
        source = self.common.body_pin(png)
        self.assertEqual(inventory, {source["sha256"]: {"source_pin": source, "provenance_pin": provenance}})

    def test_empty_image_list_preserves_evidence(self):
        parts, inventory, _ = self.message_from_analysis({"summary": "No figure needed.", "images": []})
        self.assertEqual(json.loads(parts[0]["text"])["evidence"], {"summary": "No figure needed."})
        self.assertEqual(len(parts), 1)
        self.assertEqual(inventory, {})

    def test_image_only_evidence_and_image_order(self):
        encoded = base64.b64encode(generated_png()).decode("ascii")
        parts, inventory, _ = self.message_from_analysis({"images": [
            {"mime": "image/png", "base64": encoded}, {"mime": "image/png", "base64": encoded}]})
        self.assertEqual(json.loads(parts[0]["text"])["evidence"], {})
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[1], parts[2])
        self.assertEqual(len(inventory), 1)

    def test_plain_analysis_stays_complete(self):
        for evidence in ({"summary": "Plain result", "value": 0.5}, [1, 2], "analysis text"):
            with self.subTest(evidence=evidence):
                content, inventory, _ = self.message_from_analysis(evidence)
                self.assertIsInstance(content, str)
                self.assertEqual(json.loads(content)["evidence"], evidence)
                self.assertEqual(inventory, {})

    def test_retained_text_obeys_existing_output_limit(self):
        with self.assertRaisesRegex(ValueError, "bound|cap"):
            self.message_from_analysis({"summary": "x" * 990, "images": []}, output_limit=1024)

    def test_image_bounds_remain_enforced(self):
        encoded = base64.b64encode(generated_png()).decode("ascii")
        with self.assertRaisesRegex(ValueError, "image encoded extent"):
            self.message_from_analysis({"images": [{"mime": "image/png", "base64": encoded}]},
                                       image_byte_limit=16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
