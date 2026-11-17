"""Generated controls only: no authentic signals, labels, fits or numerical imports."""
import contextlib
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scorer
from roster import ROSTER
import evaluate as cli

PIN = "1" * 64


def invented_intake():
    records = []
    for rid, animal, system, n, days in ROSTER:
        trials = []
        for i in range(n):
            sid = "INVENTED:" + rid + ":" + str(i)
            trials.append({"source_trial_id": sid, "source_order": i,
                           "disposition": "eligible", "query_id": "q_" + hashlib.sha256(sid.encode()).hexdigest()[:32],
                           "direction": i % 8, "exclusion_reason": None, "adjudication_sha256": None,
                           "timing": {"baseline_start": -2.0, "baseline_end": -1.0,
                                      "cue": 0.0, "memory_start": 1.0, "memory_end": 3.0,
                                      "go": 3.0, "acquisition_start": 2.0, "acquisition_end": 3.0}})
        records.append({"record_id": rid, "native_hz": 1 if n else None,
                        "reconciliation_sha256": PIN, "clock_mapping_sha256": PIN if n else None,
                        "representation_sha256": PIN if n else None, "trials": trials})
    return {"schema": "fus_adjudicated_intake_v1", "contract_sha256": scorer.CONTRACT_SHA256,
            "source_roster_sha256": scorer.ROSTER_SHA256, "source_archive_sha256": PIN,
            "intake_review_sha256": PIN, "records": records}


def predictions(intake, shift=0, animal=None):
    rows = []
    for record in intake["records"]:
        for t in record["trials"][8:]:
            offset = shift if animal is None or record["record_id"].startswith(animal + "-") else 0
            p = [0.0] * 8
            p[(t["direction"] + offset) % 8] = 1.0
            rows.append({"query_id": t["query_id"], "probabilities": p})
    return rows


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intake = invented_intake()
        cls.perfect = predictions(cls.intake)
        cls.report = scorer.evaluate(cls.intake, cls.perfect, condition="program_B")

    def test_complete_roster_and_perfect(self):
        r = self.report
        self.assertEqual((len(ROSTER), sum(x[3] for x in ROSTER), r["queries"]), (49, 20622, 20238))
        self.assertEqual(r["primary"], 1)
        self.assertEqual(r["overall"]["equal_animal_mean"]["brier"], 0)
        self.assertEqual([x for x in r["source_census"] if x["source_trials"] == 0],
                         [{"record_id": "L-S45-R1", "source_trials": 0, "calibration": 0,
                           "queries": 0, "adjudicated_excluded": 0}])
        self.assertEqual({a: x["sessions"] for a, x in r["overall"]["animals"].items()}, {"L": 26, "P": 22})

    def test_equal_animals_not_pooled_sessions(self):
        r = scorer.evaluate(self.intake, predictions(self.intake, shift=4, animal="P"), condition="native_A")
        self.assertEqual(r["primary"], .5)
        self.assertNotEqual(r["primary"], 26 / 48)
        self.assertEqual(r["overall"]["equal_animal_mean"]["angular_error_deg"], 90)
        self.assertEqual(r["overall"]["equal_animal_mean"]["brier"], 1)
        delta = scorer.paired_delta(self.report, r)
        self.assertEqual(delta["overall"]["equal_animal_mean"]["balanced_accuracy"], .5)
        self.assertEqual(delta["overall"]["equal_animal_mean"]["brier"], -1)

    def test_scalar_hand_anchors_and_reliability(self):
        queries = [{"query_id": str(i), "direction": i} for i in range(8)]
        values = {str(i): [.125] * 8 for i in range(8)}
        r = scorer.session_score(queries, values, False)
        self.assertEqual((r["balanced_accuracy"], r["accuracy"], r["brier"], r["angular_error_deg"]), (.125, .125, .875, 90))
        self.assertEqual(r["reliability_bins"][1], {"count": 8, "confidence_sum": 1.0, "correct": 1})
        values.pop("7")
        r = scorer.session_score(queries, values, False)
        self.assertEqual((r["invalid_by_class"][7], r["reliability_invalid"]), (1, 1))
        self.assertEqual(sum(b["count"] for b in r["reliability_bins"]) + r["reliability_invalid"], 8)

    def test_saved_pair_retains_evidence_conditions_and_intake(self):
        reference = copy.deepcopy(self.report)
        reference["condition"] = "augmented_tools_C"
        delta = scorer.paired_delta(self.report, reference)
        self.assertEqual((delta["candidate_condition"], delta["reference_condition"]),
                         ("program_B", "augmented_tools_C"))
        self.assertEqual(delta["intake_sha256"], self.report["intake_sha256"])
        self.assertFalse(delta["information_matched_by_scorer"])
        reference["condition"] = "undeclared"
        with self.assertRaises(scorer.ConstructionError):
            scorer.paired_delta(self.report, reference)

    def test_known_missing_and_duplicate_keep_denominator(self):
        broken = self.perfect[1:] + [copy.deepcopy(self.perfect[1])]
        r = scorer.evaluate(self.intake, broken, condition="tools_C")
        self.assertEqual(r["queries"], self.report["queries"])
        first = r["sessions"][0]
        self.assertEqual(sum(first["invalid_by_class"]), 2)
        loss = (1 / first["class_support"][0] + 1 / first["class_support"][1]) / 8 / 26 / 2
        self.assertAlmostEqual(r["primary"], 1 - loss)
        self.assertFalse(r["whole_submission_invalid"])

    def test_extra_or_calibration_id_penalizes_whole_report(self):
        row = {"query_id": self.intake["records"][0]["trials"][0]["query_id"], "probabilities": [1] + [0] * 7}
        r = scorer.evaluate(self.intake, self.perfect + [row], condition="program_B")
        self.assertEqual((r["primary"], r["queries"], r["whole_submission_invalid"]), (0, 20238, True))
        self.assertEqual(r["overall"]["equal_animal_mean"]["brier"], 2)
        self.assertEqual(r["overall"]["equal_animal_mean"]["angular_error_deg"], 180)

    def test_invalid_probability_boundaries(self):
        for bad in (None, [0]*8, [True]+[0]*7, [math.nan]+[0]*7, [math.inf]+[0]*7,
                    [10**1000]+[0]*7, [-.1,1.1]+[0]*6, [1]*7, [1.0000001]+[0]*7):
            self.assertIsNone(scorer.probabilities(bad))
        self.assertEqual(scorer.probabilities([.9999999]+[0]*7), [1]+[0]*7)
        self.assertIsNone(scorer.probabilities([.999]+[0]*7))

    def test_full_missing_predictions_penalized(self):
        for pred in ([], None):
            r = scorer.evaluate(self.intake, pred, condition="augmented_program_B")
            self.assertEqual((r["primary"], r["queries"]), (0, 20238))
            self.assertEqual(r["overall"]["equal_animal_mean"]["brier"], 2)

    def test_construction_invalid_all_class_support(self):
        d = copy.deepcopy(self.intake)
        for t in d["records"][0]["trials"][8:]:
            if t["direction"] == 7:
                t["direction"] = 6
        with self.assertRaisesRegex(scorer.ConstructionError, "post-calibration"):
            scorer.evaluate(d, [], condition="native_A")

    def test_early_acquisition_and_nonfinite_clock_refuse(self):
        d = copy.deepcopy(self.intake)
        t = d["records"][0]["trials"][0]["timing"]
        for key, value in (("acquisition_start", .9), ("acquisition_end", 3.1), ("cue", True), ("go", math.inf)):
            old = t[key]; t[key] = value
            with self.assertRaises(scorer.ConstructionError):
                scorer.evaluate(d, [], condition="program_B")
            t[key] = old

    def test_complete_census_and_trial_lineage(self):
        d = copy.deepcopy(self.intake)
        d["records"][1]["trials"][0]["source_trial_id"] = d["records"][0]["trials"][0]["source_trial_id"]
        with self.assertRaisesRegex(scorer.ConstructionError, "globally unique"):
            scorer.evaluate(d, [], condition="tools_C")
        d["records"].pop()
        with self.assertRaisesRegex(scorer.ConstructionError, "complete intake"):
            scorer.evaluate(d, [], condition="tools_C")

    def test_earliest_calibration_recomputed_and_exclusion_review_required(self):
        d = copy.deepcopy(self.intake)
        t = d["records"][0]["trials"][0]
        t.update({"disposition": "adjudicated_excluded", "query_id": None, "timing": None,
                  "exclusion_reason": "missing_timing", "adjudication_sha256": "2"*64})
        with self.assertRaisesRegex(scorer.ConstructionError, "eligibility exclusion"):
            scorer.evaluate(d, [], condition="program_B")
        t["adjudication_sha256"] = PIN
        partitions = scorer.validate_intake(d)
        self.assertEqual(partitions[0][2][0]["source_order"], 9)
        self.assertEqual(sum(len(row[2]) for row in partitions), 20237)

    def test_paired_support_and_explicit_condition(self):
        changed = copy.deepcopy(self.report)
        changed["intake_sha256"] = "2"*64
        with self.assertRaises(scorer.ConstructionError):
            scorer.paired_delta(self.report, changed)
        with self.assertRaises(scorer.ConstructionError):
            scorer.evaluate({}, [], condition="undeclared")

    def test_strict_json_and_fifo_before_open(self):
        for raw in (b'{"x":1,"x":2}', b'[NaN]', b'[Infinity]'):
            with self.assertRaises(ValueError):
                cli.strict_json(raw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"fifo"; os.mkfifo(path)
            with patch.object(cli.os, "open", side_effect=AssertionError("must not open FIFO")):
                with self.assertRaises(ValueError): cli.read_pinned(path, PIN, 100)

    def test_complete_cli_and_invalid_json_penalty(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, p = Path(tmp)/"intake.json", Path(tmp)/"prediction.json"
            a.write_text(json.dumps(self.intake)); p.write_text('{"query_id":')
            args = ["--intake",str(a),"--intake-sha256",hashlib.sha256(a.read_bytes()).hexdigest(),
                    "--predictions",str(p),"--predictions-sha256",hashlib.sha256(p.read_bytes()).hexdigest(),
                    "--condition","program_B"]
            output = io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(cli.main(args), 0)
            r = json.loads(output.getvalue())
            self.assertEqual((r["primary"],r["queries"],r["prediction_json_invalid"]), (0,20238,True))
            self.assertNotIn('source_trial_id', output.getvalue())
            self.assertNotIn('q_', output.getvalue())


if __name__ == "__main__":
    unittest.main()
