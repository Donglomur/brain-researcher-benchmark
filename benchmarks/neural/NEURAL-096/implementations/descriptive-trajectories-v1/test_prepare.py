"""Generated operator-bundle controls; original-packet loading is mocked only here."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from packet import PacketError, RECEIPT_SHA256, SOURCE_SHA256
import prepare
from score import expected_answer
from test_support import generated_metadata
from test_trajectory import generated_arrays
from trajectory import TrajectoryError


class PreparationTests(unittest.TestCase):
    def fixture(self):
        metadata = generated_metadata()
        binding = {"receipt_sha256": RECEIPT_SHA256, "source_sha256": SOURCE_SHA256,
                   "files": {}, "verification_scope": "GENERATED TEST DOUBLE; no authentic packet read"}
        return metadata, generated_arrays(metadata), binding

    def test_generated_closed_bundle_grade_and_external_freeze(self):
        # This authentic-loader double belongs only to the test. The production
        # API has no generated mode and still requires the pinned original receipt.
        # Keep operator output outside a checkout, including on hosted CI.
        with tempfile.TemporaryDirectory(prefix="neural096-generated-prepare-") as temp:
            folder = Path(temp)
            delivery = folder / "delivery"
            with patch.object(prepare, "load_original_packet", return_value=self.fixture()) as loader:
                result = prepare.prepare(folder / "not-a-recording", delivery)
            self.assertEqual(loader.call_count, 1)
            self.assertLess(result["bytes_written"], prepare.MAX_DELIVERY_BYTES)
            frozen = result["completion"]["sha256"]
            reference = prepare.load_reference(delivery, frozen)
            participant = json.loads((delivery / "participant/observations.json").read_text())
            self.assertTrue(all("difference_hz" not in row and "summary" not in row
                                for row in participant["cells"]))
            submission = folder / "answer.json"
            submission.write_bytes(prepare.encoded(expected_answer(reference)))
            report = prepare.grade_submission(delivery, frozen, submission, folder / "grade.json")
            self.assertEqual(report["numeric_status"], "complete")
            self.assertTrue(report["uncertainty_qualification_correct"])
            self.assertEqual(report["numeric_errors"]["quarter_signed_mean_hz"]["mean_absolute_error_hz"], 0)
            complete = delivery / "COMPLETE.json"
            complete.write_bytes(complete.read_bytes() + b" ")
            with self.assertRaisesRegex(TrajectoryError, "operator-frozen identity"):
                prepare.load_reference(delivery, frozen)

    def test_authentication_failure_creates_no_delivery(self):
        with tempfile.TemporaryDirectory(prefix="neural096-generated-auth-refusal-") as temp:
            delivery = Path(temp) / "delivery"
            with patch.object(prepare, "load_original_packet", side_effect=PacketError("pin mismatch")):
                with self.assertRaisesRegex(PacketError, "pin mismatch"):
                    prepare.prepare(Path(temp) / "missing-packet", delivery)
            self.assertFalse(delivery.exists())

    def test_existing_output_is_never_overwritten_or_opened(self):
        with tempfile.TemporaryDirectory(prefix="neural096-generated-existing-") as temp:
            delivery = Path(temp) / "delivery"
            delivery.mkdir()
            marker = delivery / "existing"
            marker.write_bytes(b"preserve")
            with patch.object(prepare, "load_original_packet") as loader:
                with self.assertRaisesRegex(TrajectoryError, "fresh output"):
                    prepare.prepare(Path(temp) / "missing-packet", delivery)
            loader.assert_not_called()
            self.assertEqual(marker.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
