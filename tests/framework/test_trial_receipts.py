"""Evidence-capture regression tests use synthetic files, never scientific claims."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from neurobench.trials import capture
from neurobench.task_validation import Audit


def make_case(tmp_path):
    task = tmp_path / "sample"
    task.mkdir()
    (task / "instruction.md").write_text("Synthetic fixture")
    authoring = tmp_path / "authoring"
    (authoring / "evidence").mkdir(parents=True)
    (authoring / "evidence/qualification.json").write_text(json.dumps({"schema_version": 1, "local_controls": ["retained"]}))
    trial = tmp_path / "trial"
    (trial / "verifier").mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({
        "agent_info": {"name": "oracle"}, "task_name": "terminal-bench-science/sample",
        "finished_at": "2026-10-29T00:00:00Z", "task_checksum": "0" * 64,
        "verifier_result": {"rewards": {"reward": 1}}, "exception_info": None,
    }))
    (trial / "verifier/reward.txt").write_text("1\n")
    (trial / "verifier/ctrf.json").write_text("{}\n")
    return dict(task=task, authoring=authoring, trial=trial, kind="oracle",
                expected_fingerprint=Audit(task, authoring).fingerprint(),
                command=["harbor", "run", "-a", "oracle"], harbor_version="fixture",
                run_id="fixture-only")


class TrialReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.case = make_case(Path(temporary.name))

    def test_capture_preserves_controls_and_raw_files(self):
        case = self.case
        capture(**case)
        q = json.loads((case["authoring"] / "evidence/qualification.json").read_text())
        self.assertEqual(q["local_controls"], ["retained"])
        self.assertEqual(q["runs"]["oracle"]["status"], "recorded")
        self.assertEqual(
            (case["authoring"] / q["runs"]["oracle"]["result_path"]).read_bytes(),
            (case["trial"] / "result.json").read_bytes())

    def test_changed_task_rejected(self):
        (self.case["task"] / "instruction.md").write_text("Edited after execution")
        with self.assertRaisesRegex(ValueError, "changed"):
            capture(**self.case)

    def test_job_aggregate_rejected(self):
        (self.case["trial"] / "result.json").write_text('{"stats": {}}')
        with self.assertRaisesRegex(ValueError, "single trial"):
            capture(**self.case)

    def test_missing_behavioral_evidence_rejected(self):
        (self.case["trial"] / "verifier/ctrf.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing regular ctrf"):
            capture(**self.case)

    def test_capture_never_overwrites(self):
        capture(**self.case)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            capture(**self.case)

    def test_path_traversal_rejected(self):
        self.case["run_id"] = "../outside"
        with self.assertRaisesRegex(ValueError, "simple directory"):
            capture(**self.case)


if __name__ == "__main__":
    unittest.main()
