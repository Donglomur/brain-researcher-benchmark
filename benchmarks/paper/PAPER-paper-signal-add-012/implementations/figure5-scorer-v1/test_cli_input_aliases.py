"""Generated CLI controls: output aliases must never truncate frozen inputs."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCORER_PATH = Path(__file__).with_name("scorer.py")


def fixture(directory):
    roster = [f"generated-{index:02}" for index in range(19)]
    observations = [{"participant_id": person, "window_id": f"window-{label}",
                     "awake": label} for person in roster for label in (0, 1)]
    targets = {"schema_version": 1, "task_id": "PAPER-paper-signal-add-012",
               "panel": "figure5_dataset1_loso", "participant_ids": roster,
               "source_binding_sha256": "a" * 64, "observations": observations}
    target_blob = json.dumps(targets).encode()
    digest = hashlib.sha256(target_blob).hexdigest()
    author = {"schema_version": 1, "access_condition": "author_reference",
              "target_manifest_sha256": digest,
              "observations": [{"participant_id": row["participant_id"],
                                "held_out_participant_id": row["participant_id"],
                                "window_id": row["window_id"],
                                "predicted_awake": row["awake"],
                                "score_awake": float(row["awake"])}
                               for row in observations]}
    candidate = copy.deepcopy(author)
    candidate["access_condition"] = "paper_data"
    paths = [directory / name for name in ("targets.json", "author.json", "candidate.json")]
    blobs = [target_blob, json.dumps(author).encode(), json.dumps(candidate).encode()]
    for path, blob in zip(paths, blobs):
        path.write_bytes(blob)
    return paths, blobs, digest


def invoke(paths, digest, output):
    return subprocess.run(
        [sys.executable, "-I", "-B", str(SCORER_PATH), "--targets", str(paths[0]),
         "--expected-target-sha256", digest, "--author", str(paths[1]),
         "--candidate", str(paths[2]), "--output", str(output)],
        capture_output=True, text=True, timeout=10)


class InputAliasControls(unittest.TestCase):
    def test_hardlink_of_each_input_is_rejected_without_mutation(self):
        for index in range(3):
            with self.subTest(input_index=index), tempfile.TemporaryDirectory() as temp:
                paths, blobs, digest = fixture(Path(temp))
                output = Path(temp) / "output.json"
                os.link(paths[index], output)
                result = invoke(paths, digest, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("output must not overwrite a source input", result.stderr)
                self.assertEqual([path.read_bytes() for path in paths], blobs)
                self.assertEqual(output.read_bytes(), blobs[index])

    def test_direct_and_symlink_aliases_remain_rejected(self):
        for kind in ("direct", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                paths, blobs, digest = fixture(Path(temp))
                output = paths[0]
                if kind == "symlink":
                    output = Path(temp) / "output.json"
                    output.symlink_to(paths[0].name)
                result = invoke(paths, digest, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual([path.read_bytes() for path in paths], blobs)

    def test_distinct_existing_output_preserves_inputs_and_scores(self):
        with tempfile.TemporaryDirectory() as temp:
            paths, blobs, digest = fixture(Path(temp))
            output = Path(temp) / "output.json"
            output.write_text("previous output")
            result = invoke(paths, digest, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([path.read_bytes() for path in paths], blobs)
            report = json.loads(output.read_text())
            self.assertEqual(report["participant_count"], 19)
            self.assertEqual(report["observation_count"], 38)
            for arm in ("author", "candidate"):
                for metric in ("balanced_accuracy", "roc_auc"):
                    self.assertEqual(report["arms"][arm]["summary"][metric]["mean"], 1)
            self.assertEqual(report["mean_paired_difference"],
                             {"balanced_accuracy": 0.0, "roc_auc": 0.0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
