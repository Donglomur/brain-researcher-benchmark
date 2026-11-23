"""Generated controls for source-shaped arithmetic; no empirical fits or labels."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "quantities.py"
SPEC = importlib.util.spec_from_file_location("find024_quantities", SOURCE)
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def participant(participant_id="p2"):
    return {
        "participant_id": participant_id,
        "electrode_ids": ["e3", "e1", "e2", "e4"],
        "slow_tied_width_sec": [.125, .375, .125, .125],
        "fast_tied_width_sec": [.125, .125, .375, .015625],
        "overall_width_sec": [.25, .5, .0625, 1.],
        "slow_logP_gaussfit": [2., 2., 6., -2.],
        "fast_logP_gaussfit": [4., 5., 2., 10.],
    }


def fixture():
    return {"schema": q.SCHEMA, "participants": [participant()]}


class QuantityTests(unittest.TestCase):
    def test_source_arithmetic_without_clipping(self):
        result = q.paired_quantities(fixture())
        self.assertEqual([r["source_fit_eligible"] for r in result["rows"]],
                         [False, True, True, True])
        for row, expected in zip(result["rows"], [0., 1., -1., 3. / math.log2(3)]):
            self.assertAlmostEqual(row["structure_yoking"], expected)
        self.assertFalse(result["native_parity_verified"])
        self.assertEqual(result["scientific_qualification"], "unknown")

    def test_strict_quality_boundary_retains_ineligible_rows(self):
        panel = fixture()
        p = panel["participants"][0]
        p["slow_logP_gaussfit"] = [3., math.nextafter(3., math.inf), 2., 4.]
        p["fast_logP_gaussfit"] = p["slow_logP_gaussfit"][:]
        rows = q.paired_quantities(panel)["rows"]
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["source_fit_eligible"] for r in rows], [False, True, False, True])

    def test_independent_overall_width_and_raw_quality_preserved(self):
        rows = q.paired_quantities(fixture())["rows"]
        self.assertEqual([r["overall_width_sec"] for r in rows], [.25, .5, .0625, 1.])
        self.assertEqual([r["log2_overall_width_sec"] for r in rows], [-2., -1., -4., 0.])
        self.assertEqual(rows[3]["slow_logP_gaussfit"], -2.)
        self.assertEqual(rows[3]["fast_logP_gaussfit"], 10.)
        self.assertNotEqual(rows[1]["overall_width_sec"],
                            (rows[1]["slow_tied_width_sec"] + rows[1]["fast_tied_width_sec"]) / 2)

    def test_source_order_and_participant_scoped_electrode_names(self):
        panel = fixture()
        panel["participants"].append(participant("p1"))
        before = copy.deepcopy(panel)
        result = q.paired_quantities(panel)
        self.assertEqual([(r["participant_id"], r["electrode_id"]) for r in result["rows"]],
                         [(p, e) for p in ("p2", "p1") for e in ("e3", "e1", "e2", "e4")])
        self.assertEqual(result["participant_count"], 2)
        self.assertEqual(result["electrode_count"], 8)
        self.assertEqual(panel, before)

    def test_extreme_finite_widths_use_log_difference(self):
        panel = fixture()
        p = panel["participants"][0]
        p["slow_tied_width_sec"][0] = 1e308
        p["fast_tied_width_sec"][0] = math.ulp(0.)
        p["slow_logP_gaussfit"][0] = 1e308
        p["fast_logP_gaussfit"][0] = 1e308
        row = q.paired_quantities(panel)["rows"][0]
        self.assertTrue(math.isfinite(row["structure_yoking"]))
        self.assertEqual(row["mean_rate_fit_quality"], 1e308)
        json.dumps(row, allow_nan=False)

    def test_nonfinite_or_nonpositive_width_rejects_complete_panel(self):
        for bad in (0., -1., None, True, "0.5", math.nan, math.inf):
            panel = fixture()
            panel["participants"][0]["overall_width_sec"][-1] = bad
            with self.subTest(bad=bad), self.assertRaises(q.QuantityError):
                q.paired_quantities(panel)

    def test_nonfinite_or_nonreal_quality_rejected(self):
        for bad in (None, False, "3", math.nan, math.inf, 10 ** 400):
            panel = fixture()
            panel["participants"][0]["slow_logP_gaussfit"][0] = bad
            with self.subTest(bad=bad), self.assertRaises(q.QuantityError):
                q.paired_quantities(panel)

    def test_duplicate_or_incomplete_identity_rejected(self):
        for mutation in ("participant", "electrode", "short", "long", "empty"):
            panel = fixture()
            p = panel["participants"][0]
            if mutation == "participant": panel["participants"].append(copy.deepcopy(p))
            if mutation == "electrode": p["electrode_ids"][1] = p["electrode_ids"][0]
            if mutation == "short": p["fast_tied_width_sec"].pop()
            if mutation == "long": p["fast_tied_width_sec"].append(1.)
            if mutation == "empty": panel["participants"] = []
            with self.subTest(mutation=mutation), self.assertRaises(q.QuantityError):
                q.paired_quantities(panel)

    def test_missing_or_unknown_fields_rejected(self):
        panel = fixture()
        panel["participants"][0]["overall_width_ms"] = [1] * 4
        with self.assertRaises(q.QuantityError): q.paired_quantities(panel)
        del panel["participants"][0]["overall_width_ms"]
        del panel["participants"][0]["overall_width_sec"]
        with self.assertRaises(q.QuantityError): q.paired_quantities(panel)

    def test_cli_captured_bytes_and_frozen_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path, output = Path(directory) / "panel.json", Path(directory) / "output.json"
            raw = json.dumps(fixture()).encode()
            path.write_bytes(raw)
            original_read = Path.read_bytes
            def capture_then_remove(selected):
                value = original_read(selected)
                if selected == path: selected.unlink()
                return value
            with patch.object(Path, "read_bytes", capture_then_remove):
                q.main([str(path), str(output), "--expected-sha256", hashlib.sha256(raw).hexdigest()])
            result = json.loads(output.read_text())
            self.assertEqual(result["input_bytes"], len(raw))
            self.assertEqual(result["input_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(result["electrode_count"], 4)
            path.write_bytes(raw)
            output.unlink()
            with self.assertRaisesRegex(q.QuantityError, "SHA256 mismatch"):
                q.main([str(path), str(output), "--expected-sha256", "0" * 64])
            self.assertFalse(output.exists())

    def test_cli_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, output = Path(directory) / "panel.json", Path(directory) / "output.json"
            raw = b'{"schema":"wrong","schema":"find024-paired-window-input/v1","participants":[]}'
            path.write_bytes(raw)
            with self.assertRaisesRegex(q.QuantityError, "duplicate JSON key"):
                q.main([str(path), str(output), "--expected-sha256", hashlib.sha256(raw).hexdigest()])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
