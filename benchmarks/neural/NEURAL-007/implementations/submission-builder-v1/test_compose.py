"""Generated-only submission construction controls; no EEG, targets or Docker."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--adapter-source")
options, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]


def encoded(rows):
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode()


class SubmissionBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = compose.load_adapter(options.adapter_source)
        cls.rows = [list(compose.HEADER)]
        for case, epochs in compose.CASES:
            for i in range(epochs):
                p = 0.12345678901234567 + i * 0.000001
                cls.rows.append([f"{case}/{i:05d}", repr(p), ".2", ".3", ".15", repr(.35 - p)])
        cls.raw = encoded(cls.rows)
        cls.temp = tempfile.TemporaryDirectory(prefix="sleep007-csv-generated-")
        cls.root = Path(cls.temp.name).resolve()
        cls.input = cls.root / "probabilities.csv"
        cls.input.write_bytes(cls.raw)
        cls.fixture_writes = len(cls.raw)

    @classmethod
    def tearDownClass(cls):
        retained = sum(p.stat().st_size for p in cls.root.iterdir() if not p.is_symlink())
        cls.temp.cleanup()
        assert not cls.root.exists()
        assert cls.fixture_writes < 2 * 2**20
        print("GENERATED_FIXTURE_ACCOUNTING=" + json.dumps({
            "cumulative_file_bytes": cls.fixture_writes,
            "retained_bytes_before_cleanup": retained,
            "owned_directory_removed": True,
            "authentic_data": False}, sort_keys=True))

    def copy_rows(self):
        return [list(row) for row in self.rows]

    def test_complete_cli_archive_passes_original_validator_and_preserves_values(self):
        output = self.root / "complete.npz"
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["--csv", str(self.input), "--output", str(output)]
        if options.adapter_source:
            argv += ["--adapter-source", options.adapter_source]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(compose.main(argv), 0)
        self.assertEqual(stderr.getvalue(), "")
        report = json.loads(stdout.getvalue())
        self.assertEqual((report["people"], report["epochs"]), (2, 5450))
        self.assertEqual(report["status"], "valid_prediction_contract")
        self.assertFalse(report["scientific_score_computed"])
        self.assertFalse(report["targets_read"])
        self.assertFalse(report["programme_provenance_verified"])
        self.assertEqual(report["source_csv"], compose.pin(self.raw))
        body = output.read_bytes()
        self.__class__.fixture_writes += len(body)
        self.assertEqual(report["submission"], compose.pin(body))
        self.assertEqual(output.stat().st_mode & 0o222, 0)
        spec = self.adapter.Specification(tuple(self.adapter.Case(*c) for c in compose.CASES), ("YASA", "RF"))
        validated = self.adapter.validate_submission(output, report["submission"], spec)
        start = 1
        for case, epochs in compose.CASES:
            probabilities = validated["people"][case]["probabilities"]
            expected = self.adapter.np.asarray([r[1:] for r in self.rows[start:start + epochs]], dtype="float64")
            self.adapter.np.testing.assert_array_equal(probabilities, expected)
            self.assertEqual(probabilities.dtype, self.adapter.np.dtype("float64"))
            self.assertEqual(validated["people"][case]["epoch_id"][-1], f"{case}/{epochs - 1:05d}")
            start += epochs

    def test_missing_final_epoch_rejected(self):
        with self.assertRaisesRegex(ValueError, "development-002/02669"):
            compose.arrays_from_csv(encoded(self.rows[:-1]), self.adapter)

    def test_duplicate_or_reordered_epochs_rejected(self):
        for indices in ((12, 13), (2780, 2781)):
            rows = self.copy_rows()
            rows[indices[1]] = list(rows[indices[0]])
            with self.subTest(kind="duplicate", indices=indices), self.assertRaisesRegex(ValueError, "identity/order"):
                compose.arrays_from_csv(encoded(rows), self.adapter)
            rows = self.copy_rows()
            rows[indices[0]], rows[indices[1]] = rows[indices[1]], rows[indices[0]]
            with self.subTest(kind="reordered", indices=indices), self.assertRaisesRegex(ValueError, "identity/order"):
                compose.arrays_from_csv(encoded(rows), self.adapter)

    def test_other_person_or_abbreviated_epoch_identity_rejected(self):
        for bad_id in ("development-003/00000", "development-001/0", "development-001/00001"):
            rows = self.copy_rows()
            rows[1][0] = bad_id
            with self.subTest(bad_id=bad_id), self.assertRaisesRegex(ValueError, "identity/order"):
                compose.arrays_from_csv(encoded(rows), self.adapter)

    def test_reordered_duplicate_or_extended_header_rejected(self):
        for header in (("epoch_id", "N1", "W", "N2", "N3", "R"),
                       ("epoch_id", "W", "N1", "N2", "N3", "N3"),
                       (*compose.HEADER, "score_mask")):
            with self.subTest(header=header), self.assertRaisesRegex(ValueError, "Exact header"):
                compose.arrays_from_csv(encoded([header, *self.rows[1:]]), self.adapter)

    def test_extra_rows_and_extra_or_missing_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "Extra CSV rows"):
            compose.arrays_from_csv(encoded([*self.rows, self.rows[-1]]), self.adapter)
        for row in (self.rows[-1][:-1], [*self.rows[-1], "unused"], []):
            with self.subTest(fields=len(row)), self.assertRaisesRegex(ValueError, "Six CSV fields"):
                compose.arrays_from_csv(encoded([*self.rows[:-1], row]), self.adapter)

    def test_nonfinite_range_and_nonnumeric_probabilities_rejected(self):
        for bad in ("nan", "inf", "-inf", "1e9999", "-0.01", "1.01", "N2", ""):
            rows = self.copy_rows()
            rows[-1][1] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                compose.arrays_from_csv(encoded(rows), self.adapter)

    def test_row_sum_tolerance_preserved_without_normalization(self):
        rows = self.copy_rows()
        rows[-1][1:] = ["0.2000001", ".2", ".2", ".2", ".2"]
        values = compose.arrays_from_csv(encoded(rows), self.adapter)
        self.assertEqual(values["development-002__probabilities"][-1, 0], .2000001)
        rows[-1][1] = "0.200002"
        with self.assertRaisesRegex(ValueError, "row-sum tolerance"):
            compose.arrays_from_csv(encoded(rows), self.adapter)

    def test_existing_output_preserved_before_input_or_source_reads(self):
        output = self.root / "existing.npz"
        output.write_bytes(b"preserve existing file")
        self.__class__.fixture_writes += output.stat().st_size
        with mock.patch.object(compose, "read_source", side_effect=AssertionError("must not read")):
            with self.assertRaises(FileExistsError):
                compose.build("absent-input", output)
        self.assertEqual(output.read_bytes(), b"preserve existing file")

    def test_bad_csv_never_creates_output(self):
        output = self.root / "invalid.npz"
        with mock.patch.object(compose, "read_source", return_value=b"wrong-header\n"), \
                mock.patch.object(compose, "load_adapter", return_value=self.adapter):
            with self.assertRaisesRegex(ValueError, "Exact header"):
                compose.build(self.input, output)
        self.assertFalse(output.exists())

    def test_substituted_validator_source_rejected_before_execution(self):
        source = self.root / "substituted.py"
        source.write_bytes(b"raise RuntimeError('source must not execute')\n")
        self.__class__.fixture_writes += source.stat().st_size
        with self.assertRaisesRegex(ValueError, "validator source changed"):
            compose.load_adapter(source)

    def test_explicit_npz_suffix_and_unlinked_input_required(self):
        with self.assertRaisesRegex(ValueError, "Explicit .npz"):
            compose.build(self.input, self.root / "ambiguous")
        linked = self.root / "linked.csv"
        linked.symlink_to(self.input)
        with self.assertRaisesRegex(ValueError, "Linked path"):
            compose.build(linked, self.root / "linked.npz")
        self.assertFalse((self.root / "linked.npz").exists())


if __name__ == "__main__":
    unittest.main()
