"""Small source-parser controls. No private targets, arrays or model calls."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("voice_chronology", Path(__file__).parents[1] / "recover_chronology.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Numeric table facts transcribed independently from the published table.
# The day139 inconsistency is intentional and must survive recovery.
TABLE = """Cover page\f
Supplementary Table 1. Data used for training the brain-to-voice decoder
Evaluation / training / reported interval / cumulative sentences / hours
 25
       25 0 180 0.5
 (1st session)
 109 104 5 4,140 17.4
 110 109 1 4,389 18.7
 125 123 2 4,648 20.1
 139 132 5 4,936 21.6
 165 153 12 5,921 26.9
 172 165 7 6,254 28.5
 174 172 2 6,552 30.1
 179 174 5 6,778 31.3
 181 179 2 7,077 32.8
 186 181 5 7,279 34.0
 188 186 2 7,589 35.3
 193 188 5 7,890 36.4
 195 193 2 8,315 37.8
\f"""


class RecoveryTests(unittest.TestCase):
    def test_complete_source_rows_and_units(self):
        rows = module.parse_table_text(TABLE)
        self.assertEqual(len(rows), 14)
        self.assertEqual([r["evaluation_day_post_implant"] for r in rows],
                         [25, 109, 110, 125, 139, 165, 172, 174, 179, 181, 186, 188, 193, 195])
        self.assertEqual(rows[-1]["cumulative_training_sentences"], 8315)
        self.assertEqual(rows[-1]["cumulative_training_hours_decimal"], "37.8")
        self.assertEqual(rows[5]["reported_days_between_training_and_evaluation"], 12)
        self.assertEqual(rows[0]["reported_days_between_training_and_evaluation"], 0)

    def test_source_inconsistency_is_preserved(self):
        conflicts = [r for r in module.parse_table_text(TABLE) if not r["reported_gap_matches_day_subtraction"]]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["evaluation_day_post_implant"], 139)
        self.assertEqual(conflicts[0]["most_recent_decoder_training_day_post_implant"], 132)
        self.assertEqual(conflicts[0]["reported_days_between_training_and_evaluation"], 5)
        self.assertEqual(conflicts[0]["arithmetic_days_between_training_and_evaluation"], 7)

    def test_partial_table_is_not_returned(self):
        with self.assertRaisesRegex(module.SourceError, "fourteen complete"):
            module.parse_table_text(TABLE.replace(" 195 193 2 8,315 37.8\n", ""))

    def test_bad_count_format_and_duplicate_rows_fail(self):
        for replacement in ("195 193 2 83,15 37.8", "193 193 2 8,315 37.8"):
            with self.subTest(replacement=replacement), self.assertRaises(module.SourceError):
                module.parse_table_text(TABLE.replace("195 193 2 8,315 37.8", replacement))

    def test_future_training_date_is_rejected(self):
        with self.assertRaisesRegex(module.SourceError, "after evaluation"):
            module.parse_table_text(TABLE.replace("195 193 2", "195 196 2"))

    def test_unknown_source_fails_before_pdf_process(self):
        with mock.patch.object(module, "extract_pdf_text") as extraction:
            with self.assertRaisesRegex(module.SourceError, "source hash mismatch"):
                module.recover({role: b"altered source" for role in module.PINS})
            extraction.assert_not_called()

    def test_pdf_extraction_rejects_unpinned_bytes(self):
        with mock.patch.object(module.subprocess, "run") as process:
            with self.assertRaisesRegex(module.SourceError, "source hash mismatch"):
                module.extract_pdf_text(b"%PDF-unpinned")
            process.assert_not_called()

    def test_configs_require_full_roster_and_named_fields(self):
        with self.assertRaises(module.SourceError):
            module.parse_demo_configs("  total_trials: 8184\n", "sessions: []")


if __name__ == "__main__":
    unittest.main()
