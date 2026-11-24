"""Generated complete-roster controls; no neural observations or model fitting."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("condition_comparison", HERE / "compare.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
PD = cc.draw_module()
SCORING = PD.scorer_module()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def fixture(animal="jc233", date="170220"):
    vectors, train, test, train_draw, test_draw = [], [], [], [], []
    for group, (context, condition) in enumerate((("A", "left"), ("A", "right"),
                                               ("B", "left"), ("B", "right"))):
        ids = [f"pv-{group}-{i}" for i in range(5)]
        vectors.extend({"pv_id": key, "context": context, "condition": condition} for key in ids)
        count = 3 if group % 2 == 0 else 4
        train.extend(ids[:count]); test.extend(ids[count:])
        train_draw.extend([ids[0]] * count); test_draw.extend([ids[count]] * (5 - count))
    source = {"schema": "hierarchy-figure4d-pv-metadata/v1", "animal": animal, "date": date,
              "context_labels": ["A", "B"], "condition_labels": ["left", "right"],
              "preparation_receipt_sha256": "a" * 64, "vectors": vectors}
    sha = hashlib.sha256(encode(source)).hexdigest()
    ledger = {"schema": "hierarchy-figure4d-draw-ledger/v1", "source_sha256": sha,
              "generation": {"kind": "regenerated_original_protocol", "receipt_sha256": "b" * 64,
                             "sample_fraction": 1},
              "repeats": [{"repeat": rep, "train_partition": list(train), "test_partition": list(test),
                           "train_draw": list(train_draw), "test_draw": list(test_draw)}
                          for rep in range(PD.REPEATS)]}
    by_id = {v["pv_id"]: v for v in vectors}
    rows = [{"Boot_rep": str(rep), "Draw_occurrence": str(i), "PV_id": key,
             "Real_label": by_id[key]["context"], "Pred_label": by_id[key]["context"],
             "Condition": by_id[key]["condition"]}
            for rep in range(PD.REPEATS) for i, key in enumerate(test_draw)]
    reference = {arm: deepcopy(rows) for arm in SCORING.ARMS}
    submissions = {outcome: {condition: deepcopy(reference) for condition in cc.CONDITIONS}
                   for outcome in cc.OUTCOMES}
    return source, ledger, sha, reference, submissions


def csv_body(rows):
    fields = sorted(PD.FIELDS)
    return (",".join(fields) + "\n" + "\n".join(
        ",".join(row[field] for field in fields) for row in rows) + "\n").encode()


def panel_fixture():
    members, sessions = {}, []
    for animal, dates in SCORING.ROSTER.items():
        for date in dates:
            source, ledger, _, reference, _ = fixture(animal, date)
            prefix = f"{animal}-{date}"
            def store(name, body):
                name = prefix + "-" + name
                members[name] = body
                return {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            csv = csv_body(reference[SCORING.ARMS[0]])
            sessions.append({
                "animal": animal, "date": date, "source": store("source", encode(source)),
                "ledger": store("ledger", encode(ledger)),
                "reference": {arm: store("reference-" + arm, csv) for arm in SCORING.ARMS},
                "submissions": {outcome: {condition: {
                    arm: store(outcome + "-" + condition + "-" + arm, csv) for arm in SCORING.ARMS}
                    for condition in cc.CONDITIONS} for outcome in cc.OUTCOMES},
            })
    return {"schema": "hierarchy-figure4d-condition-comparison/v1", "sessions": sessions}, members


class ComparisonChecks(unittest.TestCase):
    def setUp(self):
        self.source, self.ledger, self.sha, self.reference, self.submissions = fixture()

    def score(self):
        return cc.score_session(self.source, self.ledger, self.sha, self.reference,
                                self.submissions, PD, SCORING)

    def test_signed_condition_deltas_keep_outcomes_and_source_weighting_separate(self):
        for arm in SCORING.ARMS:
            paper = self.submissions["reproduction"]["paper_data"][arm]
            code = self.submissions["reproduction"]["paper_data_author_code"][arm]
            for i in (0, 1):
                paper[i]["Pred_label"] = "B"
            code[0]["Pred_label"] = "B"
            code.reverse()  # identity binding, not row-order pairing
            self.submissions["improvement"]["paper_data_author_code"][arm][2]["Pred_label"] = "B"
        report = self.score()
        reproduction = report["outcomes"]["reproduction"]
        conditional = reproduction["author_code_minus_paper_data"]["conditional"]
        self.assertEqual(conditional["repetitions"][0]["normalized_absolute_error"], -0.125)
        self.assertEqual(conditional["repetitions"][0]["exact_match_accuracy"], 0.125)
        self.assertAlmostEqual(conditional["repeat_summary"]["normalized_absolute_error"], -0.00125)
        global_delta = reproduction["author_code_minus_paper_data"]["global"]["repetitions"][0]
        self.assertAlmostEqual(global_delta["normalized_absolute_error"], -1 / 6)
        improvement = report["outcomes"]["improvement"]["author_code_minus_paper_data"]["conditional"]
        self.assertEqual(improvement["repetitions"][0]["normalized_absolute_error"], 0.25)
        self.assertEqual(report["outcomes"]["improvement"]["scientific_outcome"], "unknown")
        self.assertFalse(report["information_exposure_verified"])
        self.assertEqual(report["reference"]["conditional"]["repeat_summary"]["exact_match_accuracy"], 1)

    def test_missing_condition_remains_undefined_in_both_metric_deltas(self):
        for rep in self.ledger["repeats"]:
            rep["test_draw"] = [rep["test_draw"][0]] * 6
        for exports in [self.reference] + [self.submissions[o][c] for o in cc.OUTCOMES for c in cc.CONDITIONS]:
            for rows in exports.values():
                for row in rows:
                    row.update(PV_id="pv-0-3", Real_label="A", Pred_label="A", Condition="left")
        report = self.score()
        deltas = report["outcomes"]["reproduction"]["author_code_minus_paper_data"]
        self.assertIsNone(deltas["conditional"]["repeat_summary"]["exact_match_accuracy"])
        self.assertIsNone(deltas["conditional"]["repetitions"][0]["normalized_absolute_error"])
        self.assertIsNone(deltas["conditional"]["repetitions"][0]["conditions"][1]["normalized_absolute_error"])
        self.assertEqual(deltas["global"]["repetitions"][0]["normalized_absolute_error"], 0)

    def test_every_submission_is_bound_to_operator_targets_and_occurrences(self):
        for outcome in cc.OUTCOMES:
            for condition in cc.CONDITIONS:
                with self.subTest(outcome=outcome, condition=condition):
                    row = self.submissions[outcome][condition]["conditional_position_shuffle"][0]
                    row["PV_id"] = "pv-0-4"  # matching labels, different source identity
                    with self.assertRaisesRegex(PD.DrawError, "substituted another PV"):
                        self.score()
                    row["PV_id"] = "pv-0-3"
        self.submissions["improvement"]["paper_data"]["global"][0]["Real_label"] = "B"
        with self.assertRaisesRegex(PD.DrawError, "operator metadata"):
            self.score()

    def test_missing_outcome_condition_arm_and_occurrence_are_rejected(self):
        del self.submissions["improvement"]["paper_data_author_code"]
        with self.assertRaisesRegex(PD.DrawError, "information conditions"):
            self.score()
        self.setUp()
        del self.submissions["reproduction"]
        with self.assertRaisesRegex(PD.DrawError, "submission outcomes"):
            self.score()
        self.setUp()
        del self.submissions["improvement"]["paper_data"]["global_context_shuffle"]
        with self.assertRaisesRegex(PD.DrawError, "submission arms"):
            self.score()
        self.setUp()
        self.submissions["reproduction"]["paper_data_author_code"]["conditional"].pop()
        with self.assertRaisesRegex(PD.DrawError, "omits shared draw"):
            self.score()

    def test_complete_roster_runs_original_dependency_and_retains_input_pins(self):
        panel, members = panel_fixture()
        # Use the real bounded hash reader for the first session; generate the rest in memory.
        first = panel["sessions"][0]
        prefix = first["animal"] + "-" + first["date"]
        original = PD.pinned_body
        with tempfile.TemporaryDirectory() as tmp:
            for name, body in members.items():
                if name.startswith(prefix):
                    (Path(tmp) / name).write_bytes(body)
            def read(base, desc):
                return original(base, desc) if desc["path"].startswith(prefix) else members[desc["path"]]
            with patch.object(cc, "draw_module", return_value=PD), patch.object(PD, "pinned_body", side_effect=read):
                report = cc.score_panel(panel, tmp)
        self.assertEqual((report["session_count"], report["animal_count"]), (25, 5))
        self.assertIsNone(report["cross_session_aggregate"])
        self.assertIsNone(report["biological_uncertainty"])
        self.assertIsNone(report["paper_win"])
        for session in report["sessions"]:
            self.assertEqual(set(session["outcomes"]), set(cc.OUTCOMES))
            self.assertEqual(len(session["draw_support"]), 100)
            for outcome in cc.OUTCOMES:
                self.assertEqual(set(session["outcomes"][outcome]["conditions"]), set(cc.CONDITIONS))
        self.assertEqual(report["sessions"][0]["input_sha256"]["ledger"], first["ledger"]["sha256"])

    def test_partial_roster_and_reused_export_fail_without_comparing(self):
        panel, members = panel_fixture()
        with patch.object(cc, "draw_module", return_value=PD), patch.object(PD, "pinned_body", side_effect=lambda b, d: members[d["path"]]):
            first = panel["sessions"][0]
            first["submissions"]["reproduction"]["paper_data"]["global"] = first["reference"]["global"]
            with self.assertRaisesRegex(PD.DrawError, "same prediction export"):
                cc.score_panel(panel, ".")
            panel["sessions"].pop()
            with self.assertRaisesRegex(PD.DrawError, "25-session"):
                cc.score_panel(panel, ".")


if __name__ == "__main__":
    unittest.main(verbosity=2)
