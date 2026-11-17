"""Generated engineering controls; no authentic neural data or candidate execution."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import evaluator as e


def fixture_roster():
    sessions = []
    for group, ids in e.SESSIONS.items():
        for index, sid in enumerate(ids):
            number = index // 2 if group == "SL_only_shaping" else min(index, 3)
            sessions.append({"session_id": sid, "mouse_id": f"{group}:mouse{number}",
                             "shaping_group": group,
                             "trials": [{"trial_id": f"trial{trial}", "context": e.CONTEXTS[trial % 3],
                                         "has_any_retained_event": True} for trial in range(30)]})
    return {"schema": "structured_experience_owner_roster_v1",
            "evidence_kind": "generated_engineering_control", "method_route": "prospective_pointwise_0p5s",
            "provenance": {name: "a" * 64 for name in e.PROVENANCE_FIELDS}, "sessions": sessions}


class OwnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = fixture_roster()
        assets = {s["mouse_id"]: "b" * 64 for s in cls.roster["sessions"]}
        cls.expected = e.build_expected(cls.roster, b"secret" * 8, "c" * 64, assets)

    def test_exact_fit_plan_and_full_universe(self):
        self.assertEqual(len(self.expected["fit_units"]), 390)
        self.assertEqual(len(self.expected["rows"]), 46800)
        for unit in self.expected["fit_units"]:
            self.assertEqual(len(unit["development_mouse_ids"]), 7)
            self.assertNotIn(unit["held_mouse_id"], unit["development_mouse_ids"])
            self.assertEqual(len(unit["calibration_trial_ids"]), 9)
            self.assertEqual(len(unit["query_trial_ids"]), 3)
            self.assertFalse(set(unit["calibration_trial_ids"]) & set(unit["query_trial_ids"]))

    def test_complete_roster_and_unresolved_methods_refuse(self):
        mutations = [
            lambda r: r["sessions"].pop(),
            lambda r: r["sessions"][0]["trials"][0].update(has_any_retained_event=False),
            lambda r: r.update(method_route="paper_only_nearest_1s"),
            lambda r: r["sessions"][0]["trials"][0].update(context="SS"),
            lambda r: r["sessions"][0].update(mouse_id="invented_fifth_mouse"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                roster = copy.deepcopy(self.roster)
                mutate(roster)
                with self.assertRaises(e.AdmissionError):
                    e.validate_roster(roster)

    def test_rehashed_target_omission_and_fit_leakage_still_refuse(self):
        for mutate in [lambda x: x["rows"].pop(),
                       lambda x: x["fit_units"][0]["development_mouse_ids"].append(x["fit_units"][0]["held_mouse_id"]),
                       lambda x: x.update(scientifically_qualified=True)]:
            malformed = copy.deepcopy(self.expected)
            mutate(malformed)
            malformed["expected_sha256"] = e.sha256({k: v for k, v in malformed.items() if k != "expected_sha256"})
            with self.assertRaises(e.AdmissionError):
                e.validate_expected(malformed)

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "source session t-test requires optional SciPy")
    def test_source_session_statistic_is_separate_and_abs_gap_retained(self):
        tables = {}
        for group, sessions in e.SESSIONS.items():
            for index, sid in enumerate(sessions):
                # Across=10, within=10+(index+1): the signed gap is negative.
                tables[sid] = {s: {t: 10 + index + 1 if s == t else 10 for t in e.CONTEXTS} for s in e.CONTEXTS}
        result = e.summarize_reproduction(self.roster, tables, method_route="source_concordance_0p5s")
        self.assertEqual(result["sessions"][0]["signed_across_minus_within_seconds2"], -1)
        self.assertEqual(result["sessions"][0]["absolute_gap_seconds2"], 1)
        expected_t = 1.5 / math.sqrt((52 / 11) * (1 / 8 + 1 / 5))
        self.assertAlmostEqual(result["published_session_test"]["statistic"], expected_t, places=14)
        self.assertEqual(result["published_session_test"]["df"], 11)
        self.assertFalse(result["published_session_test"]["independent_animal_inference"])
        self.assertFalse(result["paper_comprehension_score"])
        with self.assertRaises(e.AdmissionError):
            e.summarize_reproduction(self.roster, tables, method_route="paper_only_nearest_1s")

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "source session t-test requires optional SciPy")
    def test_source_summary_does_not_require_prospective_query_fold_support(self):
        roster = copy.deepcopy(self.roster)
        # Complete source session contexts can be grouped in source order; some
        # query folds then lack a context, unlike the prospective admission policy.
        for session in roster["sessions"]:
            session["trials"].sort(key=lambda trial: trial["context"])
        tables = {sid: {s: {t: 0 if s == t else index + 1 for t in e.CONTEXTS} for s in e.CONTEXTS}
                  for index, sid in enumerate(sid for group in e.SESSIONS.values() for sid in group)}
        with self.assertRaisesRegex(e.AdmissionError, "every query fold requires all three test contexts"):
            e.validate_roster(roster)
        roster.pop("method_route")
        result = e.summarize_reproduction(roster, tables, method_route="source_concordance_0p5s")
        self.assertEqual(len(result["sessions"]), 13)
        self.assertFalse(result["source_workflow_verified"])

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "reproduction CLI requires optional SciPy")
    def test_strict_json_and_exclusive_cli_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            bad = path / "bad.json"
            for data in ('{"x":1,"x":2}', '{"x":NaN}'):
                bad.write_text(data)
                with self.assertRaises(e.AdmissionError):
                    e._load(bad)
            tables = {sid: {s: {t: 0 if s == t else index + 1 for t in e.CONTEXTS} for s in e.CONTEXTS}
                      for index, sid in enumerate(sid for group in e.SESSIONS.values() for sid in group)}
            (path / "roster.json").write_text(json.dumps(self.roster))
            (path / "tables.json").write_text(json.dumps(tables))
            command = [sys.executable, str(ROOT / "evaluator.py"), "reproduction", str(path / "roster.json"),
                       str(path / "tables.json"), str(path / "output.json"), "--route", "source_concordance_0p5s"]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual((path / "output.json").stat().st_mode & 0o777, 0o600)
            original = (path / "output.json").read_bytes()
            duplicate = subprocess.run(command, capture_output=True)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertEqual((path / "output.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
