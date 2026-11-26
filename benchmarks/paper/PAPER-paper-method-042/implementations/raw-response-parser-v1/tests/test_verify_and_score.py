"""Generated custody controls; no authentic responses, annotations or model calls."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("umbrae_custody_under_test", HERE / "verify_and_score.py")
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def body(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()


def write(path, value):
    data = body(value)
    path.write_bytes(data)
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class CustodyControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g, cls.raw, cls.vector, _ = c.load_kernels()

    def setUp(self):
        # With UMBRAE_CONTROL_ROOT, retain fixtures for source evidence. Ordinary
        # local users may run the same suite with automatic temporary cleanup.
        root = os.environ.get("UMBRAE_CONTROL_ROOT")
        if root:
            Path(root).mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=root))
        else:
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.fixture()

    def fixture(self, n=2, *, paper=False, empty_after=None):
        self.bundle = self.root / ("bundle-" + str(len(list(self.root.iterdir()))))
        self.bundle.mkdir()
        self.roster = {str(i): (["person"] if empty_after is None or i < empty_after else []) for i in range(n)}
        self.annotations = {i: {category: [[0, 0, 1, 1]] for category in cats} for i, cats in self.roster.items()}
        if paper:
            self.annotations["0"]["person"] *= 5829 - sum(len(v) for k, v in self.annotations.items() if k != "0")
        self.order = {str(i): "generated-stimulus-" + str(i) for i in range(n)}
        self.raw_packet = {
            "schema": self.raw.SCHEMA, "task_id": self.g.TASK,
            "profile": "paper_population" if paper else "engineering_controls",
            "query_roster_sha256": self.raw.canonical_sha256(self.roster),
            "responses": {role: {subject: {i: {cat: "[0,0,0.1,0.1]" for cat in cats}
                                            for i, cats in self.roster.items()}
                                 for subject in c.SUBJECTS} for role in c.ROLES},
        }
        self.raw_path = self.bundle / "raw.json"
        self.roster_path = self.bundle / "roster.json"
        self.conversion_path = self.bundle / "conversion.json"
        self.contract_path = self.bundle / "contract.json"
        self.annotations_path = self.bundle / "annotations.json"
        self.order_path = self.bundle / "order.json"
        self.output = self.bundle / "score.json"
        ann_pin = write(self.annotations_path, self.annotations)
        order_pin = write(self.order_path, self.order)
        exposure = {key: "a" * 64 for key in ("training_neural_sha256", "pretrained_language_sha256", "pretrained_image_sha256", "prompt_sha256")}
        exposure.update(training_subjects=list(c.SUBJECTS), training_stimulus_ids=["generated-training-only"], training_presentations=1)
        self.contract = {"task_id": self.g.TASK, "profile": self.raw_packet["profile"],
                         "subject_design": "shared_subjects_1_2_5_7", "brainhub_revision": self.g.BRAINHUB_REVISION,
                         "all_images_sha256": self.g.IMAGE_TENSOR_SHA256,
                         "annotations_sha256": ann_pin["sha256"], "image_order_sha256": order_pin["sha256"],
                         "exposure": exposure, "runs": {}}
        for role in c.ROLES:
            self.contract["runs"][role] = {"model_id": "generated-only", "checkpoint_sha256": "b" * 64,
                "exposure": exposure, "neural_condition": "none" if role == "neural_free" else "permuted" if role == "shuffled_neural" else "observed",
                "responses": {s: f"{role}-{s}.json" for s in c.SUBJECTS}}
        for role in ("neural_free", "shuffled_neural"):
            self.contract["runs"][role]["control_of"] = "candidate"
        self.contract["runs"]["shuffled_neural"]["source_image_by_target"] = {
            subject: {str(i): str((i + 1) % n) for i in range(n)} for subject in c.SUBJECTS}
        write(self.contract_path, self.contract)
        self.convert()

    def convert(self):
        self.raw_pin = write(self.raw_path, self.raw_packet)
        self.roster_pin = write(self.roster_path, self.roster)
        converted = self.raw.convert_panel(self.raw_packet, self.roster)
        self.extracted = converted.pop("responses")
        converted["input_pins"] = {"raw_panel": self.raw_pin, "query_roster": self.roster_pin}
        converted["extracted_files"] = {}
        for role in c.ROLES:
            converted["extracted_files"][role] = {}
            for subject in c.SUBJECTS:
                name = f"{role}-{subject}.json"
                pin = write(self.bundle / name, self.extracted[role][subject])
                converted["extracted_files"][role][subject] = {"path": name, **pin}
        converted["raw_panel_value_sha256"] = self.raw.canonical_sha256(self.raw_packet)
        converted["complete"] = True
        self.conversion = converted
        write(self.conversion_path, converted)

    def run_score(self, **kwargs):
        options = dict(expected_raw=self.raw_pin, expected_roster=self.roster_pin, draws=0)
        options.update(kwargs)
        return c.verify_and_score(self.raw_path, self.roster_path, self.conversion_path,
                                  self.contract_path, self.annotations_path, self.order_path, **options)

    def reject(self, **kwargs):
        with self.assertRaises((ValueError, OSError, TypeError, KeyError)):
            self.run_score(output_path=self.output, **kwargs)
        self.assertFalse(self.output.exists())

    def rewrite_extracted(self, value, *, update_pin=False, role="candidate", subject="S1"):
        name = f"{role}-{subject}.json"
        pin = write(self.bundle / name, value)
        if update_pin:
            self.conversion["extracted_files"][role][subject] = {"path": name, **pin}
            write(self.conversion_path, self.conversion)

    def test_valid_bundle_matches_original_kernels(self):
        result = self.run_score(draws=23, seed=7, output_path=self.output)
        original = self.g.evaluate(self.contract_path, self.annotations_path, self.order_path, bootstrap_draws=0, seed=7)
        expected = self.vector.compare_vectors(original["row_scores"], list(self.order), draws=23, seed=7)
        self.assertEqual(result["row_scores"], original["row_scores"])
        self.assertEqual(result["scores"], original["scores"])
        self.assertEqual(result["endpoint_vector"], expected)
        self.assertEqual(result["custody"]["streams"], 16)
        self.assertFalse(result["custody"]["historical_converter_exit_observed"])
        self.assertTrue(json.loads(self.output.read_bytes())["complete"])

    def test_first_box_tamper_rejected_even_with_updated_file_pin(self):
        modified = copy.deepcopy(self.extracted["candidate"]["S1"])
        modified["0"]["person"] = [[[0.0, 0.0, 1.0, 1.0]]]
        for update_pin in (False, True):
            with self.subTest(update_pin=update_pin):
                self.rewrite_extracted(modified, update_pin=update_pin)
                self.reject()
        # Demonstrate the original seam's actual effect using generated boxes.
        old = self.g.evaluate(self.contract_path, self.annotations_path, self.order_path, bootstrap_draws=0)
        self.assertEqual(old["scores"]["candidate"]["S1"]["All"]["accuracy"]["0.5"], 0.5)

    def test_independent_raw_and_roster_commitments(self):
        accepted_raw = dict(self.raw_pin)
        self.raw_packet["responses"]["candidate"]["S1"]["0"]["person"] = "[0,0,1,1]"
        self.convert()  # Coherent rewritten raw, manifest and extracted bundle.
        self.reject(expected_raw=accepted_raw)
        self.reject(expected_roster={**self.roster_pin, "sha256": "0" * 64})
        with self.assertRaises(ValueError):
            self.run_score(expected_raw={**self.raw_pin, "bytes": True})

    def test_complete_manifest_and_all_streams_required(self):
        original = copy.deepcopy(self.conversion)
        changes = [lambda m: m.pop("complete"), lambda m: m.update(complete=False),
                   lambda m: m.update(complete=1), lambda m: m["extracted_files"].pop("neural_free"),
                   lambda m: m["extracted_files"]["candidate"].pop("S7"),
                   lambda m: m["extracted_files"]["candidate"]["S1"].update(path="other.json"),
                   lambda m: m["input_pins"]["raw_panel"].update(sha256="0" * 64)]
        for change in changes:
            self.conversion = copy.deepcopy(original)
            change(self.conversion)
            write(self.conversion_path, self.conversion)
            self.reject()
        self.conversion_path.unlink()
        self.reject()

    def test_missing_file_and_subject_swap(self):
        self.raw_packet["responses"]["candidate"]["S1"]["0"]["person"] = "[0,0,1,1]"
        self.convert()
        for role, subject in (("candidate", "S2"), ("official_baseline", "S1")):
            self.rewrite_extracted(self.extracted[role][subject], update_pin=True)
            self.reject()
        (self.bundle / "shuffled_neural-S7.json").unlink()
        self.reject()

    def test_roster_reference_join_includes_empty_images(self):
        self.fixture(n=12, empty_after=2)
        self.run_score()
        self.roster["2"] = ["person"]
        for role in c.ROLES:
            for subject in c.SUBJECTS:
                self.raw_packet["responses"][role][subject]["2"] = {"person": None}
        self.raw_packet["query_roster_sha256"] = self.raw.canonical_sha256(self.roster)
        self.convert()
        self.reject()

    def test_incomplete_raw_query_cannot_reduce_denominator(self):
        self.raw_packet["responses"]["candidate"]["S1"]["0"].pop("person")
        self.raw_pin = write(self.raw_path, self.raw_packet)
        self.reject()

    def test_exact_numeric_image_and_category_order(self):
        self.fixture(n=12, empty_after=2)
        before = self.run_score()
        reordered = {key: self.extracted["candidate"]["S1"][key] for key in sorted(self.roster)}
        self.assertNotEqual(list(reordered), list(self.extracted["candidate"]["S1"]))
        self.rewrite_extracted(reordered, update_pin=True)
        self.reject()
        self.assertEqual(before["endpoint_vector"]["empty_query_image_count"], 10)
        # A same-value representation change also is not original converter bytes.
        self.convert()
        self.extracted["candidate"]["S1"]["0"]["person"][0][0][0] = 0
        self.rewrite_extracted(self.extracted["candidate"]["S1"], update_pin=True)
        self.reject()

    def test_missing_empty_invalid_first_and_strict_threshold(self):
        self.fixture(n=8)
        answers = [None, "[0, 0, 1, 1]", "[9,0,1,1;0,0,1,1]", "[0,0,0.5,1]",
                   "[0,0,1,1;9,0,1,1]", "text [0,0,1,1] tail", "[0,0,0.1,0.1]", "[0,0,1,1][9,0,1,1]"]
        for i, answer in enumerate(answers):
            self.raw_packet["responses"]["candidate"]["S1"][str(i)]["person"] = answer
        self.convert()
        result = self.run_score()
        rows = result["row_scores"]["candidate"]["S1"]
        self.assertEqual([r["prediction_status"] for r in rows[:3]], ["missing", "empty_extraction", "invalid_extraction"])
        self.assertEqual(rows[3]["iou"], 0.5)
        self.assertEqual(result["endpoint_vector"]["scores_percent"]["candidate"]["S1"], 37.5)
        original = self.g.evaluate(self.contract_path, self.annotations_path, self.order_path, bootstrap_draws=0)
        self.assertEqual(rows, original["row_scores"]["candidate"]["S1"])

    def test_full_generated_982_image_paper_geometry(self):
        self.fixture(n=982, paper=True, empty_after=2)
        result = self.run_score()
        self.assertEqual(result["population"]["shared_images"], 982)
        self.assertEqual(result["endpoint_vector"]["empty_query_image_count"], 980)
        self.assertEqual(set(result["scores"]), set(c.ROLES))
        self.assertEqual(result["qualification"], "not_established")

    def test_duplicate_nonfinite_and_invalid_unicode_inputs(self):
        valid = self.contract_path.read_bytes()
        for malformed in (b'{"profile":1,"profile":2}', b'{"extra":NaN}',
                          b'{"extra":1e400}', b'{"extra":"\\ud800"}'):
            with self.subTest(malformed=malformed):
                self.contract_path.write_bytes(malformed)
                self.reject()
        self.contract_path.write_bytes(valid)
        self.run_score()

    def test_input_and_output_aliases_rejected_before_capture(self):
        with mock.patch.object(c, "_capture", side_effect=AssertionError("payload read")) as capture:
            for alias in (self.raw_path, self.raw_path.parent / "." / self.raw_path.name):
                with self.assertRaises(ValueError):
                    self.run_score(output_path=alias)
            original = self.roster_path.read_bytes()
            self.roster_path.unlink()
            os.link(self.raw_path, self.roster_path)
            self.reject()
            self.roster_path.unlink()
            self.roster_path.symlink_to(self.raw_path)
            self.reject()
            self.roster_path.unlink()
            self.roster_path.write_bytes(original)
            capture.assert_not_called()
        self.run_score()

    def test_fifo_and_aggregate_size_refused_before_capture(self):
        self.roster_path.unlink()
        os.mkfifo(self.roster_path)
        with mock.patch.object(c, "_capture", side_effect=AssertionError("payload read")) as capture:
            self.reject()
            capture.assert_not_called()
        self.roster_path.unlink()
        write(self.roster_path, self.roster)
        with mock.patch.object(c, "MAX_TOTAL_BYTES", 1), mock.patch.object(c, "_capture") as capture:
            self.reject()
            capture.assert_not_called()

    def test_scoring_uses_captured_values_after_path_replacement(self):
        original_capture = c._capture
        consumed = []
        original_pin = dict(self.conversion["extracted_files"]["candidate"]["S1"])
        def capture(path, identity, limit):
            result = original_capture(path, identity, limit)
            consumed.append(path)
            if len(consumed) == 22:
                replacement = copy.deepcopy(self.extracted["candidate"]["S1"])
                replacement["0"]["person"] = [[[0.0, 0.0, 1.0, 1.0]]]
                self.rewrite_extracted(replacement)
            return result
        with mock.patch.object(c, "_capture", side_effect=capture):
            result = self.run_score()
        self.assertEqual(len(consumed), len(set(consumed)))
        self.assertEqual(len(consumed), 22)
        self.assertEqual(result["endpoint_vector"]["scores_percent"]["candidate"]["S1"], 0)
        self.assertEqual(result["input_pins"]["response/candidate/S1"]["sha256"], original_pin["sha256"])

    def test_dependency_snapshots_and_pin_fail_closed(self):
        opened = []
        original_open = Path.open
        def record_open(path, *args, **kwargs):
            opened.append(path)
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", record_open):
            g, raw, vector, pins = c.load_kernels()
        self.assertEqual(len(opened), 3)
        self.assertIs(raw.g, g)
        self.assertIs(vector.g, g)
        altered = dict(c.DEPENDENCIES)
        relative, size, digest = altered["raw"]
        altered["raw"] = (relative, size, "0" * 64)
        with mock.patch.object(c, "DEPENDENCIES", altered):
            self.reject()
        self.assertEqual(pins["grounding"]["sha256"], raw.CORE_SHA256)

    def test_contract_cannot_select_other_output(self):
        self.contract["runs"]["candidate"]["responses"]["S1"] = "official_baseline-S1.json"
        write(self.contract_path, self.contract)
        self.reject()

    def test_output_failures_leave_no_complete_final_artifact(self):
        for operation in ("fsync", "link"):
            with self.subTest(operation=operation):
                with mock.patch.object(c.os, operation, side_effect=OSError("generated write failure")):
                    self.reject()
                self.assertFalse(list(self.bundle.glob(".score.json.*.pending")))
        self.output.write_bytes(b"existing result")
        with self.assertRaises(ValueError):
            self.run_score(output_path=self.output)
        self.assertEqual(self.output.read_bytes(), b"existing result")

    def test_competing_output_writer_is_not_overwritten(self):
        original_link = os.link
        def competing(source, destination):
            Path(destination).write_bytes(b"other writer")
            original_link(source, destination)
        with mock.patch.object(c.os, "link", side_effect=competing):
            with self.assertRaises(FileExistsError):
                self.run_score(output_path=self.output)
        self.assertEqual(self.output.read_bytes(), b"other writer")
        self.assertFalse(list(self.bundle.glob(".score.json.*.pending")))

    def test_optional_comparison_metadata_is_not_attested(self):
        self.conversion["input_pins"]["comparison_extracted_panel"] = {"bytes": 10, "sha256": "c" * 64}
        self.conversion["extraction_comparison"] = {"status": "extraction_disagreement", "mismatch_count": 1}
        write(self.conversion_path, self.conversion)
        result = self.run_score()
        self.assertFalse(result["custody"]["optional_comparison_diagnostic_consumed"])
        self.assertEqual(result["custody"]["raw_replay"]["mismatch_count"], 0)

    def test_real_converter_and_verifier_cli(self):
        cli_bundle = self.bundle / "cli-conversion"
        converted = subprocess.run([sys.executable, "-I", "-B", str(HERE / "raw_response.py"),
                                   "--raw-panel", str(self.raw_path), "--query-roster", str(self.roster_path),
                                   "--output-directory", str(cli_bundle)], capture_output=True, text=True, timeout=10)
        self.assertEqual(converted.returncode, 0, converted.stderr)
        for role in c.ROLES:
            for subject in c.SUBJECTS:
                self.contract["runs"][role]["responses"][subject] = str(cli_bundle / f"{role}-{subject}.json")
        write(self.contract_path, self.contract)
        arguments = [sys.executable, "-I", "-B", str(HERE / "verify_and_score.py"),
                     "--raw-panel", str(self.raw_path), "--query-roster", str(self.roster_path),
                     "--conversion", str(cli_bundle / "conversion.json"), "--contract", str(self.contract_path),
                     "--annotations", str(self.annotations_path), "--image-order", str(self.order_path),
                     "--expected-raw-bytes", str(self.raw_pin["bytes"]), "--expected-raw-sha256", self.raw_pin["sha256"],
                     "--expected-roster-bytes", str(self.roster_pin["bytes"]), "--expected-roster-sha256", self.roster_pin["sha256"],
                     "--output", str(self.output), "--draws", "0"]
        verified = subprocess.run(arguments, capture_output=True, text=True, timeout=10)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        report = json.loads(self.output.read_bytes())
        self.assertTrue(report["complete"])
        self.assertEqual(report["custody"]["streams"], 16)
        rejected = subprocess.run(arguments, capture_output=True, text=True, timeout=10)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("custody rejected", rejected.stderr)
        self.assertEqual(json.loads(self.output.read_bytes()), report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
