"""Generated software controls; these never load native recordings or fit a model."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoothing", ROOT / "smoothing.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def fixture():
    header = list(s.META) + [str(f) for f in s.FREQUENCIES]
    rows, expected = [], []
    for pid, age, region, base in [("p1", 8, "Precentral_gyrus", 1),
                                    ("p1", 8, "Middle_frontal_gyrus", 101),
                                    ("p2", 16, "Precentral_gyrus", 201)]:
        for time in [.5, .75, 1]:
            rows.append([pid, str(age), region, str(time)] + [str(base)] * 200)
        expected.append(dict(ID=pid, region=region, row_count=3, age=age,
                             start_time=.5, end_time=1))
    packet = dict(task_id=s.TASK_ID, source_commit=s.SOURCE_COMMIT,
                  assessment_kind="generated_engineering_control",
                  expected_participants=["p1", "p2"], expected_groups=expected)
    return header, rows, packet


def encode(header, rows, packet):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    data = buffer.getvalue().encode()
    packet["table_sha256"] = hashlib.sha256(data).hexdigest()
    return data


def decode(payload):
    rows = list(csv.reader(io.StringIO(payload.decode())))
    return rows[0], rows[1:], np.array([r[4:] for r in rows[1:]], dtype=float)


class SmoothingTests(unittest.TestCase):
    def test_boundary_counterexample_preserves_literal_companion(self):
        header, rows, packet = fixture()
        output, report = s.prepare(encode(header, rows, packet), packet)
        _, _, literal = decode(output["source_literal_smoothed.csv"])
        _, _, grouped = decode(output["grouped_sensitivity_smoothed.csv"])
        # Last window in group one mixes two of five rows from the next region.
        self.assertAlmostEqual(literal[2, 0], 41)
        self.assertAlmostEqual(grouped[2, 0], 1)
        self.assertEqual(report["lineage"][2]["source_cross_boundary_rows"], [3, 4])
        self.assertEqual(report["lineage"][2]["grouped_neighbor_rows"], [0, 1, 2, 2, 2])
        # The next boundary mixes different participants, not only regions.
        self.assertAlmostEqual(literal[5, 0], 141)
        self.assertAlmostEqual(grouped[5, 0], 101)
        self.assertEqual(report["lineage"][5]["source_cross_boundary_rows"], [6, 7])
        self.assertEqual(report["source_rows_touching_other_groups"], 7)
        np.testing.assert_array_equal(grouped[:, 0], [1]*3 + [101]*3 + [201]*3)

    def test_independent_two_axis_nearest_reference(self):
        header, rows, packet = fixture()
        for i, row in enumerate(rows):
            row[4:] = [str(1 + i*i + j*j/100) for j in range(200)]
        output, _ = s.prepare(encode(header, rows, packet), packet)
        _, _, actual = decode(output["source_literal_smoothed.csv"])
        for i, j in [(0, 0), (2, 87), (4, 199), (8, 199)]:
            expected = sum(float(rows[min(max(i+a, 0), 8)][4+min(max(j+b, 0), 199)])
                           for a in [-2, -1, 0, 1, 2] for b in [-1, 0, 1]) / 15
            self.assertAlmostEqual(actual[i, j], expected, places=11)

    def test_grouped_order_invariance_and_original_output_identity(self):
        header, rows, packet = fixture()
        for i, row in enumerate(rows):
            row[4:] = [str(i + 1)] * 200
        first, _ = s.prepare(encode(header, rows, packet), packet)
        rows = [rows[i] for i in [8, 1, 4, 0, 7, 3, 6, 2, 5]]
        second, report = s.prepare(encode(header, rows, packet), packet)
        def by_key(blob):
            _, table, _ = decode(blob)
            return {tuple(row[:4]): row[4:] for row in table}
        self.assertEqual(by_key(first["grouped_sensitivity_smoothed.csv"]),
                         by_key(second["grouped_sensitivity_smoothed.csv"]))
        self.assertNotEqual(by_key(first["source_literal_smoothed.csv"]),
                            by_key(second["source_literal_smoothed.csv"]))
        for blob in second.values():
            _, output_rows, _ = decode(blob)
            self.assertEqual([row[:4] for row in output_rows], [row[:4] for row in rows])
        self.assertEqual([item["row_index"] for item in report["lineage"]], list(range(9)))

    def test_invalid_identity_grid_and_coverage_rejected(self):
        for mutation in ["wrong_pin", "wrong_hash", "missing_participant", "missing_group",
                         "missing_window", "duplicate_window", "inconsistent_age", "bad_count",
                         "changed_bounds", "irregular_time", "frequency_order", "duplicate_header",
                         "negative", "nonfinite", "public_small_cohort", "duplicate_expected_group"]:
            with self.subTest(mutation=mutation):
                header, rows, packet = fixture()
                if mutation == "wrong_pin": packet["source_commit"] = "0"*40
                if mutation == "missing_participant": rows = rows[:-3]
                if mutation == "missing_group": rows = rows[:3] + rows[6:]
                if mutation == "missing_window": rows.pop(1)
                if mutation == "duplicate_window": rows[1] = rows[0][:]
                if mutation == "inconsistent_age": rows[1][1] = "9"
                if mutation == "bad_count": packet["expected_groups"][0]["row_count"] = 2
                if mutation == "changed_bounds": packet["expected_groups"][0]["end_time"] = 2
                if mutation == "irregular_time": rows[1][3] = ".8"
                if mutation == "frequency_order": header[4], header[5] = header[5], header[4]
                if mutation == "duplicate_header": header[5] = header[4]
                if mutation == "negative": rows[1][50] = "-1"
                if mutation == "nonfinite": rows[1][50] = "nan"
                if mutation == "public_small_cohort": packet["assessment_kind"] = "unqualified_public_spectral_table"
                if mutation == "duplicate_expected_group": packet["expected_groups"].append(copy.deepcopy(packet["expected_groups"][0]))
                data = encode(header, rows, packet)
                if mutation == "wrong_hash": packet["table_sha256"] = "0"*64
                with self.assertRaises(s.InputError):
                    s.prepare(data, packet)

    def test_zero_power_and_single_row_group_remain_supported(self):
        header, rows, packet = fixture()
        rows = [rows[0]]
        rows[0][4:] = ["0"] * 200
        packet["expected_participants"] = ["p1"]
        packet["expected_groups"] = [dict(ID="p1", region="Precentral_gyrus", row_count=1,
                                          age=8, start_time=.5, end_time=.5)]
        output, report = s.prepare(encode(header, rows, packet), packet)
        for blob in output.values():
            np.testing.assert_array_equal(decode(blob)[2], np.zeros((1, 200)))
        self.assertEqual(report["source_rows_touching_other_groups"], 0)

    def test_cli_emits_both_arms_and_receipts_without_overwriting(self):
        header, rows, packet = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.csv").write_bytes(encode(header, rows, packet))
            (root / "packet.json").write_text(json.dumps(packet))
            command = [sys.executable, "-B", str(ROOT / "smoothing.py"), "--spectra", str(root / "input.csv"),
                       "--packet", str(root / "packet.json"), "--output-directory", str(root / "out")]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            report = json.loads((root / "out/report.json").read_text())
            for name, pin in report["outputs"].items():
                blob = (root / "out" / name).read_bytes()
                self.assertEqual(len(blob), pin["bytes"])
                self.assertEqual(hashlib.sha256(blob).hexdigest(), pin["sha256"])
            before = (root / "out/report.json").read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertIn("already exists", second.stderr)
            self.assertEqual((root / "out/report.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
