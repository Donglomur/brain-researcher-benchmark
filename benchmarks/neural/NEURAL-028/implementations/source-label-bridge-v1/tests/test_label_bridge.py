"""Generated label-contract controls; no recordings, NPY decoding or fitting."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neural028_label_bridge", HERE / "label_bridge.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def projection():
    return {"schema": b.INPUT_SCHEMA, "task_id": "NEURAL-028", "source_revision": b.SOURCE_REVISION,
            "source_asset_sha256": "a" * 64, "session_id": "generated-before",
            "trial_index_base": 0, "neural_frame_count": 8,
            "behavior": {"UniqWalls": [91, 17], "stim_id": [2, 0],
                         "WallName": [17, 91, 91, 17], "ntrials": 4,
                         "ft_WallID": [17, 17, 91, 91, 91, 91, 17, 17],
                         "ft_trInd": [0, 0, 1, 1, 2, 2, 3, 3]}}


class LabelBridgeTests(unittest.TestCase):
    def test_noncategory_wall_ids_use_declared_lookup(self):
        source = projection()
        result = b.project_labels(source)
        self.assertEqual(result["evaluator_fields"], {
            "trial_id": [0, 0, 1, 1, 2, 2, 3, 3],
            "stimulus_id": [0, 0, 2, 2, 2, 2, 0, 0],
            "trial_stimulus_id": [0, 2, 2, 0]})
        self.assertEqual(result["discarded_frames"], 0)
        self.assertFalse(result["source_payload_authenticated"])
        self.assertEqual(source, projection())

    def test_reordering_wall_mapping_does_not_change_labels(self):
        source = projection()
        for key in ("UniqWalls", "stim_id"):
            source["behavior"][key].reverse()
        self.assertEqual(b.project_labels(source)["evaluator_fields"],
                         b.project_labels(projection())["evaluator_fields"])

    def test_string_wall_identity_is_not_numeric_category(self):
        source = projection()
        names = {17: "circle1", 91: "leaf1"}
        for key in ("UniqWalls", "WallName", "ft_WallID"):
            source["behavior"][key] = [names[value] for value in source["behavior"][key]]
        self.assertEqual(b.project_labels(source)["evaluator_fields"]["trial_stimulus_id"], [0, 2, 2, 0])

    def test_explicit_one_based_conversion_preserves_all_indices(self):
        source = projection()
        source["trial_index_base"] = 1
        source["behavior"]["ft_trInd"] = [float(x + 1) for x in source["behavior"]["ft_trInd"]]
        self.assertEqual(b.project_labels(source)["evaluator_fields"]["trial_id"],
                         projection()["behavior"]["ft_trInd"])
        source["trial_index_base"] = 0
        with self.assertRaisesRegex(b.LabelError, "outside"):
            b.project_labels(source)

    def test_ambiguous_and_unknown_mapping_rejected(self):
        for field, value in (("UniqWalls", [17, 17]), ("stim_id", [2, 2]),
                             ("stim_id", [0, 7]), ("stim_id", [False, 2]),
                             ("stim_id", [0, 1])):
            source = projection()
            source["behavior"][field] = value
            with self.assertRaises(b.LabelError):
                b.project_labels(source)
        source = projection()
        source["behavior"]["ft_WallID"][0] = 999
        with self.assertRaisesRegex(b.LabelError, "absent"):
            b.project_labels(source)

    def test_no_truncation_missing_trial_or_frame_selection(self):
        for mutate in (
            lambda p: p["behavior"]["ft_WallID"].pop(),
            lambda p: p["behavior"]["ft_trInd"].append(3),
            lambda p: p["behavior"].update(ft_trInd=[0, 0, 1, 1, 1, 1, 3, 3]),
            lambda p: p["behavior"]["WallName"].pop(),
        ):
            source = projection()
            mutate(source)
            with self.assertRaises(b.LabelError):
                b.project_labels(source)

    def test_source_frame_trial_disagreement_rejected(self):
        source = projection()
        source["behavior"]["ft_WallID"][0] = 91
        with self.assertRaisesRegex(b.LabelError, "disagreement"):
            b.project_labels(source)

    def test_missing_outside_behavior_indices_are_not_dropped(self):
        for value in (None, float("nan"), float("inf"), -1, 0.25, True):
            source = projection()
            source["behavior"]["ft_trInd"][0] = value
            with self.assertRaises(b.LabelError):
                b.project_labels(source)

    def test_metadata_commitment_and_answer_injection_fail_closed(self):
        for field, value in (("task_id", "NEURAL-027"), ("source_revision", "main"),
                             ("source_asset_sha256", "not-a-hash"), ("trial_index_base", True)):
            source = projection()
            source[field] = value
            with self.assertRaises(b.LabelError):
                b.project_labels(source)
        for where in ("top", "behavior"):
            source = projection()
            (source if where == "top" else source["behavior"])["answers"] = {"effect": 1}
            with self.assertRaisesRegex(b.LabelError, "exact fields"):
                b.project_labels(source)

    def test_projection_hash_changes_with_declared_source(self):
        source = projection()
        first = b.project_labels(source)
        source["source_asset_sha256"] = "b" * 64
        second = b.project_labels(source)
        self.assertNotEqual(first["source_projection_sha256"], second["source_projection_sha256"])
        self.assertEqual(first["evaluator_fields"], second["evaluator_fields"])

    def test_bounded_json_and_exclusive_cli_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.json", root / "output.json"
            source.write_text(json.dumps(projection()))
            with self.assertRaisesRegex(b.LabelError, "byte bound"):
                b.read_json(source, 10)
            args = [sys.executable, "-I", "-S", "-B", str(HERE / "label_bridge.py"),
                    "--input", str(source), "--output", str(output)]
            first = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            saved = output.read_bytes()
            second = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), saved)
            for raw in ('{"x": 1, "x": 2}', '{"x": NaN}'):
                source.write_text(raw)
                with self.assertRaises(b.LabelError):
                    b.read_json(source)


if __name__ == "__main__":
    unittest.main()
