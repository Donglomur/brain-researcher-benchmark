"""Generated audit controls; no authentic neurons, fits or paper-result claims."""
import copy
from datetime import date
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
SPEC = importlib.util.spec_from_file_location("pair_audit_scorer", MODULE)
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def packet(n=1):
    first = [4, 4, 6, 6] * 750
    second = [5-.5-math.sqrt(.75), 5-.5+math.sqrt(.75),
              5+.5-math.sqrt(.75), 5+.5+math.sqrt(.75)] * 750
    units, assignments = [], []
    for track in range(n):
        for session, vector in ((1, first), (2, second)):
            uid = track * 2 + session - 1
            units.append(dict(dataset="A", unit_id=uid, session_id=session,
                              shank=0, recording_date=f"2020-01-0{session}",
                              peth=vector, mean_rate_hz=5))
            assignments.append(dict(dataset="A", unit_id=uid, track_id=track+1))
    return dict(schema_version="figure5-peth/v2", source_kind="generated_engineering_control",
                peth_schema="press_release_poke_3x1000_bins_1ms_plus_minus_500ms",
                rate_unit="Hz", rate_measurement_provenance="generated fixture Hz",
                population_provenance="generated audit fixture",
                units=units, methods={name: dict(peth_excluded_from_matching_and_selection=True,
                execution_provenance="generated assignments", assignments=copy.deepcopy(assignments))
                for name in scorer.BASELINES})


class PairAuditControls(unittest.TestCase):
    def test_complete_retained_population_preserves_original_numerical_result(self):
        fixture = packet(100)
        expected = scorer.score(fixture)
        result = scorer.score(fixture, include_pair_audit=True)
        audit = result.pop("pair_audit")
        self.assertEqual(result, expected)
        self.assertEqual(result["original_method_common_support"], ["A"])
        self.assertEqual(len(audit["population"]), 200)
        for method in audit["methods"].values():
            self.assertEqual(len(method["tracks"]), 100)
            self.assertEqual(len(method["consecutive_day_pairs"]), 100)
            self.assertEqual(method["unmatched_units"], [])
            for pair in method["consecutive_day_pairs"]:
                self.assertEqual(pair["outcome"], "valid")
                self.assertAlmostEqual(pair["fisher_z"], math.log(3)/2)

    def test_full_membership_reconstructs_nonconsecutive_and_same_day_pairs(self):
        fixture = packet()
        # Four sessions on days1,1,2,4. Independent combinations give six
        # total unordered pairs, two consecutive-day pairs and four others.
        fixture["units"][1]["recording_date"] = "2020-01-01"
        for uid, session, day in ((2, 3, "2020-01-02"), (3, 4, "2020-01-04")):
            row = copy.deepcopy(fixture["units"][0])
            row.update(unit_id=uid, session_id=session, recording_date=day)
            fixture["units"].append(row)
            for method in fixture["methods"].values():
                method["assignments"].append(dict(dataset="A", unit_id=uid, track_id=1))
        result = scorer.score(fixture, include_pair_audit=True)
        audit = result["pair_audit"]
        population = {(r["dataset"], r["unit_id"]): r for r in audit["population"]}
        for name, method in audit["methods"].items():
            track, = method["tracks"]
            expected = set()
            other = 0
            for a, b in itertools.combinations(track["unit_ids"], 2):
                rows = sorted((population[("A", a)], population[("A", b)]),
                              key=lambda r: r["recording_date"])
                delta = (date.fromisoformat(rows[1]["recording_date"]) -
                         date.fromisoformat(rows[0]["recording_date"])).days
                if delta == 1:
                    expected.add((rows[0]["unit_id"], rows[1]["unit_id"]))
                else:
                    other += 1
            actual = {(r["earlier_unit_id"], r["later_unit_id"])
                      for r in method["consecutive_day_pairs"]}
            self.assertEqual(actual, expected)
            self.assertEqual(actual, {(0, 2), (1, 2)})
            self.assertEqual(track["not_consecutive_day_pairs"], other)
            self.assertEqual(other, 4)
            self.assertEqual(track["all_track_pairs"], 6)
            self.assertEqual(result["methods"][name]["A"]["not_consecutive_day_pairs"], other)

    def test_rate_constant_and_valid_outcomes_are_disjoint(self):
        fixture = packet(3)
        fixture["units"][0].update(mean_rate_hz=.5, peth=[5]*3000)
        fixture["units"][2]["peth"] = [5]*3000
        result = scorer.score(fixture, include_pair_audit=True)
        rows = result["pair_audit"]["methods"]["DANT"]["consecutive_day_pairs"]
        self.assertEqual([r["outcome"] for r in rows],
                         ["rate_ineligible", "constant_peth", "valid"])
        self.assertIsNone(rows[0]["fisher_z"])
        self.assertIsNone(rows[1]["fisher_z"])
        self.assertAlmostEqual(rows[2]["fisher_z"], math.log(3)/2)
        counts = result["methods"]["DANT"]["A"]
        self.assertEqual((counts["rate_ineligible_pairs"], counts["constant_peth_pairs"],
                          counts["valid_pairs"]), (1, 1, 1))

    def test_unmatched_and_positive_singleton_remain_distinct(self):
        fixture = packet()
        for method in fixture["methods"].values():
            method["assignments"][1]["track_id"] = -1
        audit = scorer.score(fixture, include_pair_audit=True)["pair_audit"]
        for method in audit["methods"].values():
            self.assertEqual(method["unmatched_units"], [dict(dataset="A", unit_id=1)])
            self.assertEqual(method["tracks"], [dict(dataset="A", track_id=1,
                             unit_ids=[0], all_track_pairs=0, not_consecutive_day_pairs=0)])
            self.assertEqual(method["consecutive_day_pairs"], [])

    def test_audit_order_invariant_and_candidate_does_not_mutate_baseline(self):
        fixture = packet(2)
        expected = scorer.score(fixture, include_pair_audit=True)["pair_audit"]
        fixture["units"].reverse()
        for method in fixture["methods"].values():
            method["assignments"].reverse()
        shuffled = scorer.score(fixture, include_pair_audit=True)["pair_audit"]
        self.assertEqual(shuffled, expected)
        candidate = copy.deepcopy(fixture["methods"]["DANT"])
        for row in candidate["assignments"]:
            row["track_id"] = -1
        fixture["methods"]["candidate"] = candidate
        audit = scorer.score(fixture, include_pair_audit=True)["pair_audit"]
        self.assertEqual(audit["methods"].pop("candidate")["tracks"], [])
        self.assertEqual(audit, expected)

    def test_vector_hash_is_normalized_operand_binding_not_only_score(self):
        fixture = packet()
        before = scorer.score(fixture, include_pair_audit=True)
        row = before["pair_audit"]["population"][0]
        raw = json.dumps([float(x) for x in fixture["units"][0]["peth"]],
                         separators=(",", ":"), allow_nan=False).encode()
        expected = hashlib.sha256(b"figure5-peth/validated-float-json/v1\n"+raw).hexdigest()
        self.assertEqual(row["peth_sha256"], expected)
        fixture["units"][0]["peth"] = [2*x for x in fixture["units"][0]["peth"]]
        after = scorer.score(fixture, include_pair_audit=True)
        self.assertNotEqual(after["pair_audit"]["population"][0]["peth_sha256"], expected)
        self.assertAlmostEqual(before["methods"]["DANT"]["A"]["median_fisher_z"],
                               after["methods"]["DANT"]["A"]["median_fisher_z"])

    def test_default_path_never_hashes_vectors_and_flag_is_not_truthy_coerced(self):
        fixture = packet()
        with patch.object(scorer.hashlib, "sha256", side_effect=AssertionError("unexpected audit hash")):
            self.assertNotIn("pair_audit", scorer.score(fixture))
        for value in (1, "yes", None):
            with self.subTest(value=value), self.assertRaises(scorer.InputError):
                scorer.score(fixture, include_pair_audit=value)

    def test_audit_cli_binds_input_and_preserves_infinity_without_overwrite(self):
        fixture = packet()
        fixture["units"][1]["peth"] = fixture["units"][0]["peth"]
        raw = json.dumps(fixture).encode()
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"in.json", Path(directory)/"out.json"
            source.write_bytes(raw)
            argv = [str(MODULE), str(source), str(output), "--pair-audit"]
            with patch.object(sys, "argv", argv):
                scorer.main()
            result = json.loads(output.read_bytes())
            self.assertEqual(result["input_sha256"], hashlib.sha256(raw).hexdigest())
            pair, = result["pair_audit"]["methods"]["DANT"]["consecutive_day_pairs"]
            self.assertEqual(pair["fisher_z"], "positive_infinity")
            original = output.read_bytes()
            with patch.object(sys, "argv", argv), self.assertRaises(FileExistsError):
                scorer.main()
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
