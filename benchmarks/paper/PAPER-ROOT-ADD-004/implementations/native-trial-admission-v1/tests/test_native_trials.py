import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "native_trials.py"
spec = importlib.util.spec_from_file_location("native_trials", MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def behavior(codes=((1, 1, 1), (1, 0, 0), (1, -1, 0), (0, 1, 1))):
    lines = ["\t".join(native.FIELDS)]
    for i, (old, exemplar, recognition) in enumerate(codes, 1):
        values = [2, 1, "ret", 1, i, 1.0, "verb", "image", 1, old, "old", 0.5,
                  recognition, "answer", exemplar, 1.0, 2.0, 3.0, "12:00"]
        lines.append("\t".join(map(str, values)))
    return "\n".join(lines) + "\n"


def markers(samples=(1001, 2003, 3002, 4001)):
    return "Brain Vision Data Exchange Marker File, Version 1.0\n[Marker Infos]\n" + "\n".join(
        f"Mk{i}=Stimulus,S 41,{sample},1,0" for i, sample in enumerate(samples, 1)) + "\n"


class NativeSourceControls(unittest.TestCase):
    def session(self):
        return native.join_session(native.read_behavior(behavior()),
                                   native.read_cue_markers(markers()), "P02", "object", "ret1", 200)

    def test_exact_source_masks_keep_recognition_miss_but_not_unknown_outcome(self):
        rows = self.session()["records"]
        self.assertEqual([r["label_group"] for r in rows],
                         ["remembered", "not_remembered", None, None])
        self.assertEqual(rows[2]["source_metadata"]["ExemplarAccuracy"], -1)
        self.assertEqual(rows[3]["label_exclusion"], "OldNew_not_equal_to_1")
        self.assertEqual(self.session()["all_rows"], 4)

    def test_label_mask_exhaustive_against_explicit_native_truth_table(self):
        for old in (-1, 0, 1, 2):
            for exemplar in (-1, 0, 1, 2):
                for recognition in (-1, 0, 1, 2):
                    expected = {(1, 1): "remembered", (1, 0): "not_remembered"}.get((old, exemplar))
                    self.assertEqual(native.label_group({"OldNew": old, "ExemplarAccuracy": exemplar,
                                                         "Answer1Accuracy": recognition}), expected)

    def test_native_rounding_and_original_marker_identity(self):
        rows = self.session()["records"]
        self.assertEqual([r["source_cue_sample_at_recording_rate"] for r in rows], [200, 401, 600, 800])
        self.assertEqual(rows[0]["cue"]["sample_1000hz_one_based"], 1001)
        self.assertEqual(rows[0]["trial_id"], "P02/object/ret1/run-1/trial-1")

    def test_session_and_run_qualify_identity(self):
        rows = native.read_behavior(behavior())
        cues = native.read_cue_markers(markers())
        a = native.join_session(rows, cues, "P02", "object", "ret1", 200)
        b = native.join_session(rows, cues, "P02", "scene", "ret2", 200)
        self.assertTrue(set(r["trial_id"] for r in a["records"]).isdisjoint(
            r["trial_id"] for r in b["records"]))

    def test_declared_recording_rate_and_matlab_half_rounding(self):
        rows, cues = native.read_behavior(behavior()), native.read_cue_markers(markers())
        result = native.join_session(rows, cues, "P02", "object", "ret1", 500)
        self.assertEqual(result["records"][0]["source_cue_sample_at_recording_rate"], 501)
        for invalid in (0, -200, True, 200.0):
            with self.assertRaisesRegex(ValueError, "fsample"):
                native.join_session(rows, cues, "P02", "object", "ret1", invalid)

    def test_mismatched_counts_duplicate_ids_and_wrong_participant_fail(self):
        rows, cues = native.read_behavior(behavior()), native.read_cue_markers(markers())
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            native.join_session(rows, cues[:-1], "P02", "object", "ret1", 200)
        with self.assertRaisesRegex(ValueError, "SubjectNumber"):
            native.join_session(rows, cues, "P05", "object", "ret1", 200)
        rows[1]["TrialNumber"] = 1
        with self.assertRaisesRegex(ValueError, "duplicate native"):
            native.join_session(rows, cues, "P02", "object", "ret1", 200)

    def test_source_header_and_numeric_corruption_fail(self):
        for corrupted in (behavior().replace("OldNew", "old"),
                          behavior().replace("\t0.5\t", "\tbroken\t"),
                          behavior().replace("\t-1\t", "\tFalse\t")):
            with self.assertRaises(ValueError):
                native.read_behavior(corrupted)

    def test_missing_response_timing_is_preserved_without_label_exclusion(self):
        rows = native.read_behavior(behavior().replace("\t0.5\t", "\tNaN\t"))
        self.assertEqual(rows[0]["RT1"], "NaN")
        self.assertEqual(native.label_group(rows[0]), "remembered")

    def test_marker_join_is_literal_and_rejects_reordering(self):
        mixed = markers() + "Mk9=Stimulus,S 410,5000,1,0\nMk10=Comment,S\\141,6000,1,0\n"
        self.assertEqual(len(native.read_cue_markers(mixed)), 4)
        with self.assertRaisesRegex(ValueError, "increase strictly"):
            native.read_cue_markers(markers((2000, 1000)))
        with self.assertRaisesRegex(ValueError, "duplicate BrainVision"):
            native.read_cue_markers(markers() + "Mk1=Stimulus,S 41,9999,1,0\n")

    def test_cli_preserves_census_and_never_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "behavior.txt").write_text(behavior())
            (root / "markers.vmrk").write_text(markers())
            output = root / "admission.json"
            command = [sys.executable, str(MODULE), str(root / "behavior.txt"),
                       str(root / "markers.vmrk"), str(output), "--participant", "P02",
                       "--category", "object", "--block", "ret1", "--recording-sample-rate-hz", "200", "--data-kind",
                       "generated_engineering_control"]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            parsed = json.loads(output.read_text())
            self.assertEqual(parsed["session"]["label_counts"],
                             {"remembered": 1, "not_remembered": 1, "excluded_by_labels": 2})
            saved = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
