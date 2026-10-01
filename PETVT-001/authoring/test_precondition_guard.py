"""Safety-only fixtures: no dataset acquisition, fit or scientific bank creation."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


TASK = Path(__file__).resolve().parents[1]
SUBJECTS = ("sf02", "sf05", "sf06", "sf07", "sf08", "sf09", "sf10")


@pytest.mark.parametrize("receipt_kind", ["absent", "malformed", "weak", "unknown", "forged"])
def test_unapproved_receipt_fails_before_imports_or_network(tmp_path, receipt_kind):
    receipt = tmp_path/"unapproved_decay_receipt.json"
    if receipt_kind == "malformed":
        receipt.write_text("{this is not JSON")
    elif receipt_kind == "weak":
        receipt.write_text(json.dumps({subject: {
            "source": "https://pubmed.ncbi.nlm.nih.gov/16513622/",
            "blood_activity_reference": "pet_time_zero",
        } for subject in SUBJECTS}))
    elif receipt_kind == "unknown":
        receipt.write_text(json.dumps({subject: {
            "source": "arbitrary nonempty string", "blood_activity_reference": "unknown",
        } for subject in SUBJECTS}))
    elif receipt_kind == "forged":
        receipt.write_text(json.dumps({subject: {
            "source": "https://example.invalid/claimed-exporter-receipt",
            "blood_activity_reference": "draw_time",
            "source_snapshot_commit": "358a370c010a792484585b80d28adb699ec28927",
            "approved": True,
        } for subject in SUBJECTS}))
    output = tmp_path/"output"
    # -S removes site packages. The audit hook additionally proves the oracle
    # never attempts a numeric import or a network operation before its guard.
    driver = """
import json, runpy, sys
blocked = []
def guard(event, args):
    numeric = event == 'import' and args[0].split('.')[0] in {'numpy', 'input_contract'}
    network = event == 'urllib.Request' or event.startswith('socket.')
    if numeric or network:
        blocked.append(event + ':' + str(args[0]))
        raise AssertionError('forbidden precondition-side effect')
sys.addaudithook(guard)
try:
    runpy.run_path(sys.argv[1], run_name='__main__')
finally:
    print(json.dumps({'forbidden_events': blocked,
                      'numpy_imported': 'numpy' in sys.modules,
                      'http_imported': 'urllib.request' in sys.modules}))
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", driver, str(TASK/"solution"/"compute.py")],
        env={**os.environ, "OUTPUT_DIR": str(output), "BLOOD_DECAY_RECEIPT": str(receipt)},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1
    assert "No supplied decay receipt is currently approved" in result.stderr
    audit = json.loads(result.stdout.strip().splitlines()[-1])
    assert audit == {"forbidden_events": [], "numpy_imported": False, "http_imported": False}
    assert set(path.name for path in output.iterdir()) == {
        "run_metadata.json", "vt_estimates.csv", "findings.md"
    }
    metadata = json.loads((output/"run_metadata.json").read_text())
    assert metadata["status"] == "failed_precondition"
    assert metadata["dataset"] == "ds005619" and metadata["snapshot"] == "1.1.0"
    assert metadata["source_snapshot_commit"] == "358a370c010a792484585b80d28adb699ec28927"
    assert metadata["scientific_precondition"] == "released_blood_activity_decay_reference_unverified"
    assert metadata["reason"] in (output/"findings.md").read_text()
    assert (output/"vt_estimates.csv").read_text() == "subject,session,target,input,model,VT\n"
