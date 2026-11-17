"""Generated scalar controls only; no neural data, source parsing or model work."""
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


HERE = Path(__file__).resolve().parent
P = load("primary", HERE / "primary.py")
F = load("original_generated_report", HERE.parent / "investigation-claims-v1" / "test_claims.py")


def variant(candidate_control_delta=0.0, candidate_neural_delta=0.0):
    """Perturb whole arms coherently across every report section and condition.

    The original generated report has unequal per-person query-row counts.
    These coherent counterexamples expose the old control-gain ranking error.
    """
    def delta(row):
        if row.get("track", "candidate") != "candidate":
            return 0.0
        return candidate_neural_delta if row["arm"] == "neural" else candidate_control_delta

    def chapters():
        for row in F.chapters():
            yield dict(row, log_loss=row["log_loss"] + delta(row))

    def vectors():
        for row in F.vectors():
            d = delta(row)
            yield dict(row, log_loss=row["log_loss"] + d,
                       people=[dict(person, log_loss=person["log_loss"] + d) for person in row["people"]])

    def averages():
        for row in F.averages():
            yield dict(row, log_loss=row["log_loss"] + delta(row))

    def paired():
        for row in F.paired():
            d = candidate_control_delta - candidate_neural_delta if row["track"] == "candidate" else 0.0
            yield dict(row, positive_improvement=row["positive_improvement"] + d)

    def candidate():
        for row in F.candidate():
            yield dict(row, positive_improvement=row["positive_improvement"] - candidate_neural_delta)

    result = F.report()
    result.update(chapter_seed_distribution=chapters(), person_seed_vectors=vectors(),
                  ten_seed_averages=averages(), all_four_paired_control_contrasts=paired(),
                  candidate_neural_improvement=candidate())
    return result


class PrimaryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = P.endpoints(variant())

    def test_exact_eight_strata_and_independent_closed_form(self):
        rows = self.baseline["primary"]
        expected = {(axis, budget, mode) for axis, budget in P.PRIMARY_STRATA for mode in P.MODES}
        self.assertEqual({(r["axis"], r["budget"], r["mode"]) for r in rows}, expected)
        self.assertEqual(len(rows), 8)
        self.assertEqual(self.baseline["denominator"]["invocations"], 76800)
        # Analytic fixture expectation: average seeds 0..9, people 0..31 and
        # chapters 0..1. Query-row counts 1..32 must not reweight people.
        expected_loss = 1 + .003 * 4.5 + .0001 * 15.5 + .00001 * .5
        self.assertAlmostEqual(rows[0]["value"], expected_loss, places=12)
        self.assertAlmostEqual(rows[0]["independent_reference"]["reference_minus_candidate"], .005, places=12)
        self.assertEqual(rows[0]["direction"], "lower")
        self.assertTrue(all(r["unit"] == "nats_per_prediction" for r in rows))
        self.assertTrue(all(r["ranked"] is False for r in self.baseline["descriptive_claims"]))
        self.assertEqual(len(self.baseline["descriptive_claims"]), 348)

    def test_weaker_candidate_controls_cannot_improve_any_primary(self):
        attacked = P.endpoints(variant(candidate_control_delta=4.0))
        self.assertEqual(attacked["primary"], self.baseline["primary"])
        key = "neural_gain/held_chapter/full/frozen_program/candidate/timing"
        old = next(r["value"] for r in self.baseline["descriptive_claims"] if r["id"] == key)
        new = next(r["value"] for r in attacked["descriptive_claims"] if r["id"] == key)
        self.assertAlmostEqual(new - old, 4.0, places=12)

    def test_worse_neural_predictions_lose_even_when_self_gain_increases(self):
        worse = P.endpoints(variant(candidate_control_delta=4.0, candidate_neural_delta=.25))
        for old, new in zip(self.baseline["primary"], worse["primary"]):
            self.assertAlmostEqual(new["value"] - old["value"], .25, places=12)
            ref = new["independent_reference"]
            self.assertLess(ref["reference_minus_candidate"], 0)
            self.assertAlmostEqual(ref["timing_minus_neural"], .002, places=12)
            self.assertAlmostEqual(ref["time_shifted_neural_minus_neural"], .001, places=12)

    def test_missing_exposed_rows_still_refused_before_primary_output(self):
        report = variant()
        report["chapter_seed_distribution"] = (
            row for row in report["chapter_seed_distribution"] if row["axis"] != "exposed_person")
        with self.assertRaisesRegex(ValueError, "missing"):
            P.endpoints(report)

    def test_incomplete_companions_and_tampered_means_refused(self):
        report = variant()
        report["candidate_neural_improvement"] = itertools.islice(report["candidate_neural_improvement"], 7679)
        with self.assertRaisesRegex(ValueError, "missing"):
            P.endpoints(report)
        report = variant()
        rows = report["ten_seed_averages"]
        first = dict(next(rows), log_loss=0.0)
        report["ten_seed_averages"] = itertools.chain([first], rows)
        with self.assertRaisesRegex(ValueError, "all ten seeds"):
            P.endpoints(report)

    def test_duplicate_and_nonfinite_json_and_failed_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "report.json"
            output = Path(root) / "endpoints.json"
            for body in ('{"schema":"a","schema":"b"}', '{"x":NaN}', '{"x":Infinity}'):
                source.write_text(body)
                with self.assertRaises(ValueError):
                    P.main(["--report", str(source), "--output", str(output)])
                self.assertFalse(output.exists())
            source.write_text('{}')
            with self.assertRaises(ValueError):
                P.main(["--report", str(source), "--output", str(output)])
            self.assertFalse(output.exists())

    def test_complete_generated_cli_route_without_overwrite(self):
        # Inject complete streaming scalar reports at the file-reader boundary;
        # keep fixtures small instead of serializing 76,800 redundant test rows.
        # JSON syntax rejection is separately exercised through the real reader.
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "report.json"
            output = Path(root) / "endpoints.json"
            source.write_text('{"small":[1,2.5,null]}')
            self.assertEqual(P.read_report(source), {"small": [1, 2.5, None]})
            with mock.patch.object(P, "read_report", return_value=variant()):
                P.main(["--report", str(source), "--output", str(output)])
            actual = json.loads(output.read_text())
            self.assertEqual(actual, self.baseline)
            with mock.patch.object(P, "read_report", return_value=variant()):
                with self.assertRaises(FileExistsError):
                    P.main(["--report", str(source), "--output", str(output)])
            self.assertEqual(json.loads(output.read_text()), self.baseline)

    def test_changed_validator_source_pin_refused(self):
        with mock.patch.object(P, "CLAIMS_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "source pin"):
                P.endpoints(variant())


if __name__ == "__main__":
    unittest.main()
