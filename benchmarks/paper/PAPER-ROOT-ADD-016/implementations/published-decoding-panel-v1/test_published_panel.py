"""Generated controls; no source scores, recordings or private targets."""
import csv
import importlib.util
import io
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("tested_published_panel", HERE / "published_panel.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def generated_rows():
    return [[str(i + 20*c + 60*d), str(i), device, condition, str((i+20*c+60*d)/200)]
            for d, device in enumerate(P.DEVICES)
            for c, condition in enumerate(P.CONDITIONS)
            for i in range(20)]


def encoded(rows, header=P.HEADER):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode()


class PublishedPanelControls(unittest.TestCase):
    def test_complete_panel_and_known_arithmetic(self):
        result = P.report(P._parse(encoded(generated_rows())))
        self.assertEqual(result["n_rows"], 120)
        self.assertEqual(result["n_participants"], 20)
        self.assertEqual(len(result["cells"]), 6)
        for index, cell in enumerate(result["cells"]):
            self.assertEqual(cell["n_participants"], 20)
            self.assertAlmostEqual(cell["arithmetic_mean_r"], (9.5 + 20*index)/200)
            self.assertAlmostEqual(cell["sample_sd_r"], math.sqrt(35)/200)
        self.assertNotIn("score", result)
        self.assertNotIn("confidence_interval", result)

    def test_row_permutation_preserves_paired_cells(self):
        original = P.report(P._parse(encoded(generated_rows())))
        shuffled = P.report(P._parse(encoded(list(reversed(generated_rows())))))
        self.assertEqual(original, shuffled)

    def test_missing_cell_rejected(self):
        with self.assertRaisesRegex(P.SourceError, "six"):
            P._parse(encoded(generated_rows()[:-1]))

    def test_missing_subject_rejected(self):
        with self.assertRaisesRegex(P.SourceError, "20-participant"):
            P._parse(encoded([r for r in generated_rows() if r[1] != "19"]))

    def test_duplicate_cell_rejected_even_at_right_row_count(self):
        rows = generated_rows()
        rows[-1] = rows[0].copy()
        with self.assertRaisesRegex(P.SourceError, "Duplicate"):
            P._parse(encoded(rows))

    def test_same_count_different_participant_panel_rejected(self):
        rows = generated_rows()
        for row in rows:
            if row[1] == "19":
                row[1] = "replacement"
        with self.assertRaisesRegex(P.SourceError, "participant"):
            P._parse(encoded(rows))

    def test_participant_mismatch_between_cells_rejected(self):
        rows = generated_rows()
        rows[-1][1] = "replacement"
        with self.assertRaises(P.SourceError):
            P._parse(encoded(rows))

    def test_nonfinite_and_out_of_range_scores_rejected(self):
        for invalid in ("nan", "inf", "-inf", "1.00001", "-1.00001", "", " 0.5"):
            with self.subTest(value=invalid):
                rows = generated_rows()
                rows[0][-1] = invalid
                with self.assertRaises(P.SourceError):
                    P._parse(encoded(rows))

    def test_unknown_modality_and_condition_rejected(self):
        for column, value in ((2, "combined"), (3, "ECG_unknown")):
            rows = generated_rows()
            rows[0][column] = value
            with self.assertRaises(P.SourceError):
                P._parse(encoded(rows))

    def test_extra_column_and_header_changes_rejected(self):
        rows = generated_rows()
        rows[0].append("unreported")
        with self.assertRaises(P.SourceError):
            P._parse(encoded(rows))
        with self.assertRaises(P.SourceError):
            P._parse(encoded(generated_rows(), header=P.HEADER[::-1]))

    def test_published_loader_rejects_unauthenticated_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "generated.csv"
            for value in (b"x" * P.SOURCE_BYTES, b"x" * (P.SOURCE_BYTES + 1)):
                source.write_bytes(value)
                with self.assertRaises(P.SourceError):
                    P.load_published(source)


if __name__ == "__main__":
    unittest.main()
