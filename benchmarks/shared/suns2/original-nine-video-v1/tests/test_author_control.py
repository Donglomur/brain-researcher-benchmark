"""Generated control producer tests, without authenticated source payloads."""
from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import test_grade as fixture_module
from qualify_author_control import execute_control


class AuthorControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.GradingControls()
        self.fixture.setUp()
        self.destination = self.fixture.root / "author-replay"
        self.output = self.fixture.root / "replay-report.json"
        self.copy_bytes = sum(row["author_prediction"]["bytes"]
                              for row in self.fixture.spec["cases"])

    def tearDown(self):
        self.fixture.tearDown()

    def execute(self):
        return execute_control(self.fixture.spec_path, self.fixture.digest,
                               self.destination, self.output, self.copy_bytes,
                               "d" * 64)

    def test_generated_full_replay_has_zero_exact_deltas(self):
        result = self.execute()
        self.assertTrue(self.output.is_file())
        self.assertEqual(result["fixed_control"]["source_MAT_bytes_copied"], self.copy_bytes)
        self.assertFalse(result["scores"]["descriptive_outcome"][
            "same_panel_geometry_improvement"])
        self.assertEqual(result["scores"]["descriptive_outcome"][
            "audit_mean_delta_exact"]["numerator"], "0")
        for row in self.fixture.spec["cases"]:
            copied = self.destination / "masks" / (row["video_id"] + ".mat")
            self.assertEqual(copied.read_bytes(), Path(row["author_prediction"]["path"]).read_bytes())

    def test_changed_source_refuses_without_success_report(self):
        source = Path(self.fixture.spec["cases"][2]["author_prediction"]["path"])
        source.write_bytes(source.read_bytes()[:-1] + b"x")
        with self.assertRaisesRegex(ValueError, "trusted pin"):
            self.execute()
        self.assertFalse(self.output.exists())
        self.assertEqual(len(list((self.destination / "masks").glob("*.mat"))), 2)

    def test_preexisting_output_refuses_before_copy(self):
        self.output.write_text("preserved")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.execute()
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.output.read_text(), "preserved")

    def test_panel_zero_cannot_hide_per_video_order_or_count_error(self):
        valid = self.execute()
        for index, kind in enumerate(("order", "counts")):
            bad = copy.deepcopy(valid)
            row = bad["scores"]["cases"][0]
            if kind == "order":
                row["geometry"]["raw_instance_order_equal"] = False
            else:
                row["original"]["candidate"]["matches"] += 1
            destination = self.fixture.root / f"bad-{index}"
            output = self.fixture.root / f"bad-{index}.json"
            with patch("suns2_benchmark.grade.grade_submission", return_value=bad):
                with self.assertRaisesRegex(ValueError, "per-video"):
                    execute_control(self.fixture.spec_path, self.fixture.digest,
                                    destination, output, self.copy_bytes, "d" * 64)
            self.assertFalse(output.exists())

    def test_fixed_report_bound_refuses_before_write(self):
        valid = self.execute()
        valid["oversized_annotation"] = "x" * 65536
        output = self.fixture.root / "large-report.json"
        with patch("suns2_benchmark.grade.grade_submission", return_value=valid):
            with self.assertRaisesRegex(ValueError, "exceeds65536B"):
                execute_control(self.fixture.spec_path, self.fixture.digest,
                                self.fixture.root / "large-replay", output,
                                self.copy_bytes, "d" * 64)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
