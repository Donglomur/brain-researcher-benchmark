import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "native_cohort.py"
sys.path.insert(0, str(MODULE.parent))
spec = importlib.util.spec_from_file_location("native_cohort", MODULE)
cohort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cohort)


def fixture(root):
    entries = []
    for participant, category, block in cohort.CELLS:
        stem = f"{participant}_{category}_{block}"
        lines = ["\t".join(cohort.native.FIELDS)]
        for i, (old, exemplar, recognition) in enumerate(((1, 1, 1), (1, 0, 0), (1, -1, 0), (0, 1, 1)), 1):
            values = [int(participant[1:]), 1, "ret", 1, i, 1.0, "verb", "image", 1,
                      old, "old", "NaN", recognition, "answer", exemplar, 1.0, 2.0, 3.0, "12:00"]
            lines.append("\t".join(map(str, values)))
        (root / f"{stem}.txt").write_text("\n".join(lines) + "\n")
        (root / f"{stem}.vmrk").write_text("[Marker Infos]\n" + "\n".join(
            f"Mk{i}=Stimulus,S 41,{i * 1000 + 1},1,0" for i in range(1, 5)) + "\n")
        entries.append({
            "participant_id": participant, "category": category, "block": block,
            "recording_sample_rate_hz": 500 if block == "ret2" else 200,
            "behavior": f"{stem}.txt", "markers": f"{stem}.vmrk",
        })
    return {"schema": cohort.SCHEMA, "data_kind": "generated_engineering_control", "sessions": entries}


class FullCohortPreparationControls(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = fixture(self.root)

    def test_full_census_retains_all_rows_masks_and_source_clocks(self):
        self.manifest["sessions"].reverse()
        result = cohort.prepare(self.manifest, self.root)
        self.assertEqual(result["participant_ids"], list(cohort.native.PARTICIPANTS))
        self.assertEqual(result["session_count"], 72)
        self.assertEqual(result["all_rows"], 288)
        self.assertEqual(result["label_counts"], {"remembered": 72, "not_remembered": 72,
                                                  "excluded_by_labels": 144})
        self.assertFalse(result["scientifically_qualified"])
        ids = []
        for item in result["sessions"]:
            session = item["session"]
            ids.extend(row["trial_id"] for row in session["records"])
            self.assertEqual([row["label_group"] for row in session["records"]],
                             ["remembered", "not_remembered", None, None])
            first = session["records"][0]
            self.assertEqual(first["source_metadata"]["RT1"], "NaN")
            self.assertEqual(first["cue"]["sample_1000hz_one_based"], 1001)
            self.assertEqual(first["source_cue_sample_at_recording_rate"],
                             501 if session["block"] == "ret2" else 200)
            for kind in ("behavior", "markers"):
                receipt = item["inputs"][kind]
                raw = (self.root / receipt["filename"]).read_bytes()
                self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(receipt["bytes"], len(raw))
        self.assertEqual(len(set(ids)), 288)
        self.assertTrue(all(p["all_rows"] == 16 and p["session_count"] == 4
                            for p in result["participants"]))

    def test_missing_or_duplicate_cells_fail_before_source_reads(self):
        missing = {**self.manifest, "sessions": self.manifest["sessions"][:-1]}
        duplicate = {**self.manifest, "sessions": self.manifest["sessions"] + [self.manifest["sessions"][0]]}
        with patch.object(Path, "read_bytes", side_effect=AssertionError("source was opened")):
            for manifest, message in ((missing, "incomplete source cohort"), (duplicate, "duplicate source cell")):
                with self.assertRaisesRegex(ValueError, message):
                    cohort.prepare(manifest, self.root)

    def test_substitute_participant_is_not_a_complete_original_cohort(self):
        self.manifest["sessions"][-1]["participant_id"] = "P99"
        with self.assertRaisesRegex(ValueError, "unexpected source cell"):
            cohort.prepare(self.manifest, self.root)

    def test_wrong_native_subject_and_count_mismatch_propagate(self):
        first = self.manifest["sessions"][0]
        wrong = self.manifest["sessions"][4]
        first["behavior"] = wrong["behavior"]
        with self.assertRaisesRegex(ValueError, "SubjectNumber"):
            cohort.prepare(self.manifest, self.root)
        first["behavior"] = "P02_object_ret1.txt"
        path = self.root / first["markers"]
        path.write_text(path.read_text().replace("Mk4=Stimulus,S 41,4001,1,0\n", ""))
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            cohort.prepare(self.manifest, self.root)

    def test_cli_relative_inputs_complete_receipt_and_evidence_protection(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        output = self.root / "cohort.json"
        command = [sys.executable, str(MODULE), str(manifest), str(output)]
        first = subprocess.run(command, cwd=self.root.parent, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        saved = output.read_bytes()
        result = json.loads(saved)
        self.assertEqual(result["all_rows"], 288)
        self.assertEqual(result["input_manifest"]["sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("output already exists", second.stderr)
        self.assertEqual(output.read_bytes(), saved)
        source = self.root / self.manifest["sessions"][0]["behavior"]
        source_saved = source.read_bytes()
        overwrite = subprocess.run(command[:-1] + [str(source)], capture_output=True, text=True)
        self.assertNotEqual(overwrite.returncode, 0)
        self.assertIn("must not overwrite", overwrite.stderr)
        self.assertEqual(source.read_bytes(), source_saved)

    def test_failed_session_does_not_write_partial_cohort(self):
        source = self.root / self.manifest["sessions"][-1]["markers"]
        source.write_text("[Marker Infos]\n")
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        output = self.root / "cohort.json"
        result = subprocess.run([sys.executable, str(MODULE), str(manifest), str(output)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no literal S 41", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
