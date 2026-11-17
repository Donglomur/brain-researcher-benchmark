"""Evidence-capture regression tests use synthetic files, never scientific claims."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from record_neuro_trial import capture
from validate_neuro_tasks import Audit


@pytest.fixture
def case(tmp_path):
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


def test_capture_preserves_controls_and_raw_files(case):
    capture(**case)
    q = json.loads((case["authoring"] / "evidence/qualification.json").read_text())
    assert q["local_controls"] == ["retained"]
    assert q["runs"]["oracle"]["status"] == "recorded"
    assert (case["authoring"] / q["runs"]["oracle"]["result_path"]).read_bytes() == (case["trial"] / "result.json").read_bytes()


def test_changed_task_rejected(case):
    (case["task"] / "instruction.md").write_text("Edited after execution")
    with pytest.raises(ValueError, match="changed"):
        capture(**case)


def test_job_aggregate_rejected(case):
    (case["trial"] / "result.json").write_text('{"stats": {}}')
    with pytest.raises(ValueError, match="single trial"):
        capture(**case)


def test_missing_behavioral_evidence_rejected(case):
    (case["trial"] / "verifier/ctrf.json").unlink()
    with pytest.raises(ValueError, match="Missing regular ctrf"):
        capture(**case)


def test_capture_never_overwrites(case):
    capture(**case)
    with pytest.raises(ValueError, match="overwrite"):
        capture(**case)


def test_path_traversal_rejected(case):
    case["run_id"] = "../outside"
    with pytest.raises(ValueError, match="simple directory"):
        capture(**case)
