"""Four checks against measured, immutable-source total-power receipts."""
import os
from pathlib import Path
import proof_of_work as q

OUT=Path(os.environ.get("OUTPUT_DIR","/app/output"))


def test_complete_original_event_membership():
    q.read_events(OUT,q.load_reference())


def test_full_mean_power_and_trial_windows():
    q.validate_power_receipts(OUT,q.load_reference())


def test_complete_curve_recomputes():
    reference=q.load_reference()
    q.read_curve(OUT,reference,q.validate_power_receipts(OUT,reference))


def test_endpoint_metadata_and_findings():
    q.validate_output_directory(OUT,q.load_reference())
