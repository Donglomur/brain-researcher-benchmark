"""Generated review-identity controls; no neural data or native preparation."""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
# Overrides are trusted test-runner source paths, never participant input.
SOURCE = Path(os.environ.get("N041_SOURCE_ROOT", str(
    HERE.parent / "registered-runtime" / "runtime" / "source")))
PREPARATION = Path(os.environ.get("N041_PREPARATION", str(HERE / "preparation.py")))
sys.path.insert(0, str(SOURCE))
from core import Refusal
from schema import AUTHOR_REVISION, DATASET

spec = importlib.util.spec_from_file_location("n041_review_identity_control", PREPARATION)
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)


def generated_review():
    """Complete declared 44-session roster; all decisions are synthetic."""
    assets = []
    sessions = []
    for i in range(44):
        asset = {"asset_id": "generated-asset-" + str(i),
                 "patient_id": "generated-person-" + str(i % 36),
                 "session_id": "generated-session-" + str(i),
                 "path": "generated-" + str(i) + ".nwb",
                 "pin": {"bytes": 1, "sha256": "0" * 64}}
        assets.append(asset)
        sessions.append({
            "asset_id": asset["asset_id"],
            "source_session_id": asset["session_id"],
            "source_pin": dict(asset["pin"]),
            "preprocessing": dict.fromkeys(("bundle_spike_interpolation", "local_reference",
                "lowpass_175Hz", "downsample_400Hz", "notch_60_120Hz"), True),
            "lfp": [], "units": [],
            "trials": [{"row0": j, "eligible": False,
                        "reason": "generated decision only"} for j in range(140)],
            "evidence": "generated review metadata, never clinical evidence",
            "eligibility_basis": "clinical_and_signal_artifact_only_blind_to_load_correctness_order",
            "clock_evidence": dict.fromkeys(("trial_seconds", "spike_seconds",
                "lfp_start_seconds", "upstream_temporal_support_reviewed"), True),
        })
    roster = {"schema": "n041_roster_v1", "dataset": DATASET,
              "assets": assets, "provenance": "generated roster only"}
    review = {"schema": "n041_clinical_review_v1", "dataset": DATASET,
              "author_revision": AUTHOR_REVISION,
              "regions": ["Amy", "Hippo", "dACC", "preSMA", "vmPFC"],
              "sessions": sessions, "provenance": "generated decisions only"}
    return roster, review


class ReviewIdentityTests(unittest.TestCase):
    def test_complete_unique_review_retains_every_session(self):
        roster, review = generated_review()
        actual = preparation.validate_review(review, roster)
        self.assertEqual(len(actual), 44)
        self.assertEqual(set(actual), {a["asset_id"] for a in roster["assets"]})
        for row in review["sessions"]:
            self.assertEqual(actual[row["asset_id"]], row)

    def test_extra_conflicting_review_cannot_be_silently_overwritten(self):
        roster, review = generated_review()
        conflicting = copy.deepcopy(review["sessions"][0])
        conflicting["eligibility_basis"] = "generated prohibited load-dependent decision"
        review["sessions"].insert(0, conflicting)
        with self.assertRaisesRegex(Refusal, "one clinical review per source session"):
            preparation.validate_review(review, roster)

    def test_extra_malformed_review_cannot_disappear_before_validation(self):
        roster, review = generated_review()
        review["sessions"].insert(0, {"asset_id": review["sessions"][0]["asset_id"]})
        with self.assertRaisesRegex(Refusal, "one clinical review per source session"):
            preparation.validate_review(review, roster)

    def test_duplicate_replacing_a_required_session_remains_rejected(self):
        roster, review = generated_review()
        review["sessions"][-1] = copy.deepcopy(review["sessions"][0])
        with self.assertRaisesRegex(Refusal, "all source sessions reviewed"):
            preparation.validate_review(review, roster)


if __name__ == "__main__":
    unittest.main(verbosity=2)
