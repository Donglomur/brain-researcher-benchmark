"""Generated real-core final capture with a stub scientific-grader boundary.

This checks adapter-to-bridge compatibility, not scientific scoring accuracy.
The full48 fixture and full-size generated PNG come from the core test helper.
No authentic data, renderer, model or scientific dependency is opened/imported.
"""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import attempt
import attempt_grade as bridge
import test_attempt as fixtures


class CapturedAttemptGradeIntegration(unittest.TestCase):
    WRITE_CEILING = 1024 * 1024

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="n096-captured-grade-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name).resolve()
        cls.written_bytes = 0
        original_attempt_write, original_bridge_write = attempt.write_new, bridge.write_fresh

        def charge(body):
            cls.written_bytes += len(body)
            if cls.written_bytes > cls.WRITE_CEILING:
                raise AssertionError("generated integration cumulative write budget exceeded")

        def attempt_write(path, body):
            charge(body)
            original_attempt_write(path, body)

        def bridge_write(path, body, cap):
            charge(body)
            original_bridge_write(path, body, cap)

        for module, name, replacement in ((attempt, "write_new", attempt_write),
                                           (bridge, "write_fresh", bridge_write)):
            handle = patch.object(module, name, replacement)
            handle.start()
            cls.addClassCleanup(handle.stop)

        _, _, index_body, observation_body, cls.binding = fixtures.generated_inputs()
        cls.binding = dict(cls.binding)
        cls.observation_body = observation_body
        cls.png = fixtures.generated_png()
        cls.operator_bundle = cls.root / "operator-bundle"
        cls.operator_bundle.mkdir(mode=0o700)
        cls.prepared = cls.root / "private-preparation"
        cls.prepared.mkdir(mode=0o700)
        observation_pin = attempt.pin(observation_body)
        operator_manifest = {
            "schema": "neural096-observation-delivery-manifest/v1",
            "source_binding": {
                "preparation_completion_sha256": cls.binding["preparation_completion_sha256"],
                "preparation_receipt": attempt.pin(b"generated preparation receipt"),
                "observation": observation_pin,
            },
            "files": {"programme/observations.json": observation_pin},
        }
        manifest_body = bridge.encoded(operator_manifest)
        cls.manifest_path = cls.operator_bundle / "MANIFEST.json"
        attempt.write_new(cls.manifest_path, manifest_body)
        cls.binding["observation_manifest_sha256"] = attempt.pin(manifest_body)["sha256"]
        cls.png_source = cls.root / "source.png"
        attempt.write_new(cls.png_source, cls.png)
        sources = {identity: {"path": str(cls.png_source), **attempt.pin(cls.png)} for identity in attempt.IDS}
        cls.native = cls.root / "native-material"
        cls.programme = cls.root / "programme-material"
        cls.materials = {
            "native": attempt.materialize_native(index_body, sources,
                {**cls.binding, "renderer_manifest_sha256": "c" * 64}, cls.native),
            "programme": attempt.materialize_programme(index_body, observation_body,
                                                       cls.binding, cls.programme),
        }
        cls.sequence = 0

    def capture(self, arm):
        type(self).sequence += 1
        identity = "integration_" + str(self.sequence)
        folder = self.root / identity
        material = self.native if arm == "native" else self.programme
        made = attempt.create_attempt(material, self.materials[arm]["material_manifest"]["sha256"],
                                      fixtures.config(identity), folder)
        sha = made["attempt_manifest"]["sha256"]
        attempt.request_observation(material, folder, sha, {"kind": "index"})
        request = {"kind": "view", "cell_id": attempt.IDS[-1]} if arm == "native" else {"kind": "observations"}
        response = attempt.request_observation(material, folder, sha, request)
        self.assertEqual(response["body"], self.png if arm == "native" else self.observation_body)
        answer = b'{"generated_dispatch_answer":true}\n'
        captured = attempt.submit_final(folder, sha, answer)
        self.assertEqual(captured["receipt"]["status"], "captured")
        return folder, sha, answer, captured

    def invoke_bridge(self, folder, sha, final_sha, output):
        return bridge.grade_attempt(self.prepared, self.binding["preparation_completion_sha256"],
            self.manifest_path, self.binding["observation_manifest_sha256"], folder, sha,
            final_sha, output, (self.native, self.programme))

    def test_real_capture_for_each_arm_reaches_private_operator_bridge(self):
        calls = []
        def fake_grade(prepared, completion, submission, output):
            body = submission.read_bytes()
            calls.append((prepared, completion, body))
            result = {"submission": attempt.pin(body), "generated_dispatch_control": True}
            attempt.write_new(output, bridge.encoded(result))
            return result
        with patch.object(bridge, "_grader_module", return_value=SimpleNamespace(grade_submission=fake_grade)):
            for arm in ("native", "programme"):
                with self.subTest(arm=arm):
                    folder, sha, answer, captured = self.capture(arm)
                    output = self.root / ("private-grade-" + arm)
                    final_sha = captured["receipt_pin"]["sha256"]
                    result = self.invoke_bridge(folder, sha, final_sha, output)
                    self.assertEqual(result["status"], "graded")
                    receipt = bridge.strict_json((output / "RECEIPT.json").read_bytes())
                    self.assertEqual(receipt["final_receipt"], captured["receipt_pin"])
                    self.assertEqual(receipt["frozen_final_receipt_sha256"], final_sha)
                    self.assertEqual(receipt["submission"], attempt.pin(answer))
                    self.assertEqual(receipt["arm"], arm)
                    self.assertFalse(receipt["participant_feedback_delivered"])
                    self.assertFalse(receipt["native_tolerance_relaxed"])
                    self.assertLess(captured["receipt_pin"]["bytes"], bridge.MAX_RECEIPT_BYTES)
                    self.assertEqual(attempt.verify_final(folder, sha, final_sha)["answer_bytes"], answer)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][2], calls[1][2])

    def test_real_capture_tampering_is_rejected_before_grader_import(self):
        folder, sha, answer, captured = self.capture("programme")
        changed = b"x" + answer[1:]
        type(self).written_bytes += len(changed)
        self.assertLessEqual(self.written_bytes, self.WRITE_CEILING)
        (folder / "ANSWER.bin").write_bytes(changed)
        output = self.root / "must-not-exist"
        with patch.object(bridge, "_grader_module") as loader:
            with self.assertRaises(attempt.AttemptError):
                self.invoke_bridge(folder, sha, captured["receipt_pin"]["sha256"], output)
            loader.assert_not_called()
        self.assertFalse(output.exists())

    def test_coherent_answer_and_receipt_rewrite_cannot_replace_capture_time_pin(self):
        folder, sha, answer, captured = self.capture("native")
        changed = b"x" + answer[1:]
        revised = attempt.decode((folder / "FINAL.json").read_bytes())
        revised["answer"] = attempt.pin(changed)
        revised_body = attempt.encode(revised)
        type(self).written_bytes += len(changed) + len(revised_body)
        self.assertLessEqual(self.written_bytes, self.WRITE_CEILING)
        (folder / "ANSWER.bin").write_bytes(changed)
        (folder / "FINAL.json").write_bytes(revised_body)
        output = self.root / "coherent-rewrite-must-not-grade"
        with patch.object(bridge, "_grader_module") as loader:
            with self.assertRaises(attempt.AttemptError):
                self.invoke_bridge(folder, sha, captured["receipt_pin"]["sha256"], output)
            loader.assert_not_called()
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
