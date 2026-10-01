"""Safety regression only; no source fitting or replacement scientific bank."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_quarantined_source_fails_before_imports_download_or_analysis(tmp_path):
    task = Path(__file__).resolve().parents[1]
    # -S excludes site packages: failure must not require numpy, pynwb or DANDI.
    result = subprocess.run(
        [sys.executable, "-S", str(task / "solution/compute.py")],
        env={**os.environ, "OUTPUT_DIR": str(tmp_path)},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert "sampled at spike occurrence times" in result.stderr
    assert set(p.name for p in tmp_path.iterdir()) == {
        "run_metadata.json", "results.json", "findings.md"
    }
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    outcome = json.loads((tmp_path / "results.json").read_text())
    assert metadata["status"] == outcome["status"] == "failed_precondition"
    assert metadata["source_sha256"] == (
        "f35c398d7e266ed81a960e00e8fb623bc5992deaed6f70c85cee340f431b5950"
    )
    assert "independently_sampled_position" in metadata["scientific_precondition"]
    assert outcome["reason"] == metadata["reason"]
    assert metadata["reason"] in (tmp_path / "findings.md").read_text()
