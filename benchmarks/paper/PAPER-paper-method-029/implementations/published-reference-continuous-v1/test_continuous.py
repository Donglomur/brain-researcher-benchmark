"""Generated complete-panel controls; no authentic replay or model execution."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("continuous", Path(__file__).with_name("continuous.py"))
continuous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(continuous)
api = continuous.reference_api


def panel():
    # Construct support independently of EXPECTED_KEYS.
    reference = {}
    rows = []
    for source in range(1, 6):
        for target in range(1, 6):
            if source == target:
                continue
            for roi in ("VC", "V1", "V2", "V3", "V4", "HVC"):
                for method in ("brain_loss", "content_loss"):
                    for axis in ("pattern", "profile"):
                        key = (f"sub{source:02d}", f"sub{target:02d}", roi, method, axis)
                        reference[key] = (source - target) / 16
                        rows.append(dict(zip(("source", "target", "roi", "method", "axis"), key),
                                         mean_r=reference[key], eligible_count=50 if axis == "pattern" else 7,
                                         total_count=50 if axis == "pattern" else 9, undefined_count=0))
    replay = {"task_id": "PAPER-paper-method-029", "source_commit": api.SOURCE_COMMIT,
              "population": "public_deeprecon", "images": 50, "repeats": 24, "source_pairs": 20,
              "methods": ["brain_loss", "content_loss"], "rois": ["VC", "V1", "V2", "V3", "V4", "HVC"],
              "normalized": {"pair_rows": rows}}
    return reference, replay


class ContinuousControls(unittest.TestCase):
    def test_complete_exact_report_has_no_binary_decision(self):
        ref, replay = panel()
        report = continuous.compare_continuous(ref, replay)
        self.assertEqual((len(report["rows"]), len(report["summaries"])), (480, 24))
        self.assertEqual(report["decision"], "not_made")
        self.assertEqual(report["reference_authentication"], "not_established_by_pure_function")
        self.assertEqual(report["scientific_improvement"], "not_evaluated")
        for row in report["rows"]:
            self.assertEqual(row["absolute_error"], 0)
            self.assertNotIn("within_tolerance", row)
        for row in report["summaries"]:
            self.assertEqual(row["root_mean_square_pair_error"], 0)
            self.assertNotIn("pairs_within_tolerance", row)
        self.assertNotIn("supplied_absolute_tolerance", report)

    def test_cancelling_errors_remain_visible_in_complete_panel(self):
        ref, replay = panel()
        rows = [row for row in replay["normalized"]["pair_rows"]
                if (row["roi"], row["method"], row["axis"]) == ("VC", "brain_loss", "pattern")]
        rows[0]["mean_r"] += .125
        rows[1]["mean_r"] -= .125
        report = continuous.compare_continuous(ref, replay)
        group = report["summaries"][0]
        self.assertEqual(group["mean_signed_error"], 0)
        self.assertEqual(group["mean_absolute_pair_error"], .0125)
        self.assertEqual(group["maximum_absolute_pair_error"], .125)
        self.assertAlmostEqual(group["root_mean_square_pair_error"], .125 / math.sqrt(10))
        self.assertEqual(sum(row["absolute_error"] != 0 for row in report["rows"]), 2)

    def test_no_subset_raw_score_or_wrong_source_substitution(self):
        for kind in ("missing", "duplicate", "undefined", "raw", "revision", "generated", "axis"):
            ref, replay = panel()
            rows = replay["normalized"]["pair_rows"]
            if kind == "missing": rows.pop()
            elif kind == "duplicate": rows[-1] = rows[0]
            elif kind == "undefined": rows[0]["undefined_count"] = 1
            elif kind == "raw": replay["raw"] = replay.pop("normalized")
            elif kind == "revision": replay["source_commit"] = "other"
            elif kind == "generated": replay["population"] = "generated_engineering_control"
            else: rows[0]["axis"] = "different_endpoint"
            with self.subTest(kind=kind), self.assertRaises(api.ReferenceError):
                continuous.compare_continuous(ref, replay)

    def test_reference_and_replay_preserve_clipped_source_domain(self):
        for invalid in (float("nan"), float("inf"), True, 1.01, -1.01):
            ref, replay = panel()
            key = next(iter(ref))
            bad_ref = dict(ref, **{})
            bad_ref[key] = invalid
            with self.subTest(side="reference", value=invalid), self.assertRaises(api.ReferenceError):
                continuous.compare_continuous(bad_ref, replay)
            replay["normalized"]["pair_rows"][0]["mean_r"] = invalid
            with self.subTest(side="replay", value=invalid), self.assertRaises(api.ReferenceError):
                continuous.compare_continuous(ref, replay)

    def test_order_invariance_and_no_input_mutation(self):
        ref, replay = panel()
        original_ref, original_replay = copy.deepcopy((ref, replay))
        first = continuous.compare_continuous(ref, replay)
        self.assertEqual((ref, replay), (original_ref, original_replay))
        reverse = copy.deepcopy(replay)
        reverse["normalized"]["pair_rows"].reverse()
        self.assertEqual(first, continuous.compare_continuous(dict(reversed(list(ref.items()))), reverse))

    def test_cli_uses_authenticated_reader_and_strict_json_without_margin(self):
        ref, replay = panel()
        with tempfile.TemporaryDirectory() as folder:
            source, operand, output = (Path(folder) / name for name in ("source.csv", "replay.json", "report.json"))
            source.write_text("generated fixture, not publisher bytes")
            operand.write_text(json.dumps(replay))
            args = [str(source), "--replay", str(operand), "--output", str(output)]
            with self.assertRaisesRegex(api.ReferenceError, "byte identity"):
                continuous.main(args)
            self.assertFalse(output.exists())
            # Generated CLI plumbing only: actual publisher authentication is not claimed by this fixture.
            with mock.patch.object(api, "load_reference", return_value=ref) as reader:
                self.assertEqual(continuous.main(args), 0)
                reader.assert_called_once_with(str(source))
            saved = output.read_bytes()
            self.assertEqual(len(json.loads(saved)["rows"]), 480)
            with self.assertRaisesRegex(api.ReferenceError, "overwrite"):
                continuous.main(args)
            self.assertEqual(output.read_bytes(), saved)
            for invalid in (b'{"a":1,"a":2}', b'{"nested":{"k":1,"k":2}}', b'{"a":NaN}'):
                with self.subTest(invalid=invalid), self.assertRaises(api.ReferenceError):
                    continuous._strict_json(invalid)

    def test_predecessor_change_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / "reader.py"
            wrong.write_text("raise RuntimeError('must not execute')")
            with mock.patch.object(continuous, "PREDECESSOR", wrong):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    continuous._load_predecessor()


if __name__ == "__main__":
    unittest.main()
