"""Generated full-panel reporting controls; no authentic scientific observations."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "fig3_score.py"
SPEC = importlib.util.spec_from_file_location("fig3_reporting", MODULE)
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


def fixture():
    # Shared immutable operands keep the complete in-memory fixture small.
    models = {}
    for model in s.MODELS:
        side = "all" if model == "random" else model[-1]
        folds = [{"sample_ids": [f"{side}-{i}-{j}" for j in range(2 if i == 0 else 1)],
                  "actual": [0.0] * (2 if i == 0 else 1),
                  "predicted": [0.0 if i == 0 else math.pi] * (2 if i == 0 else 1)}
                 for i in range(10)]
        models[model] = {"folds": folds,
                         "shuffle_scores": [[(repeat - 50) / 100] * 10 for repeat in range(100)]}
    rows = [dict(animal=a, day=d, cell_type=c, model=m, **models[m])
            for a in s.ANIMALS for d in s.DAYS for c in s.CELL_TYPES for m in s.MODELS]
    return {"schema": s.SCHEMA, "source_commit": s.COMMIT,
            "preparation_sha256": "1" * 64, "fold_receipt_sha256": "2" * 64, "rows": rows}


class SourceReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = fixture()

    def test_source_table_preserves_all_real_shuffle_records_and_original_keys(self):
        result = s.score_panel(self.panel)
        records = result["figure3b_source_table"]
        self.assertEqual(len(records), 924)
        expected_keys = {"mouse", "switch", "day", "ct", "model", "score_type", "score", "sess_id"}
        expected_ids = {(f"{a}_{d}", c, m, kind)
                        for a in s.ANIMALS for d in s.DAYS for c in s.CELL_TYPES
                        for m in s.MODELS[:2] for kind in ("real", "shuffle")}
        self.assertEqual({(r["sess_id"], r["ct"], r["model"], r["score_type"]) for r in records}, expected_ids)
        for row in records:
            self.assertEqual(set(row), expected_keys)
            self.assertEqual(row["switch"], s.DAYS.index(row["day"]) + 1)
            self.assertEqual(row["sess_id"], f'{row["mouse"]}_{row["day"]}')
            self.assertAlmostEqual(row["score"], -0.8 if row["score_type"] == "real" else -0.005)
        self.assertEqual(records[0]["day"], 3)
        self.assertEqual(records[-1]["day"], 14)
        self.assertEqual(len(result["rows"]), 1155)

    def test_reporting_is_independent_of_input_row_order_but_requires_all_controls(self):
        expected = s.score_panel(self.panel)["figure3b_source_table"]
        reordered = dict(self.panel, rows=list(reversed(self.panel["rows"])))
        self.assertEqual(s.score_panel(reordered)["figure3b_source_table"], expected)
        incomplete = dict(self.panel, rows=self.panel["rows"][:-1])
        with self.assertRaisesRegex(s.InputError, "all 77 sessions"):
            s.score_panel(incomplete)

    def test_comparison_marks_original_targets_and_control_gains_without_a_win(self):
        candidate = copy.deepcopy(self.panel)
        # Improvement only on after-trained/random controls, and on every null
        # distribution: neither can count as a published real-score gain.
        for row in candidate["rows"]:
            row["shuffle_scores"] = [[0.9] * 10 for _ in range(100)]
            if row["model"] not in s.MODELS[:2]:
                row["folds"] = copy.deepcopy(row["folds"])
                for fold in row["folds"]:
                    fold["predicted"] = list(fold["actual"])
        result = s.compare(candidate, self.panel)
        targets = [r for r in result["session_conditions"] if r["score_role"] == "directional_performance_target"]
        controls = [r for r in result["session_conditions"] if r["score_role"] == "native_condition_control"]
        self.assertEqual(len(targets), 462)
        self.assertEqual(len(controls), 693)
        self.assertTrue(all(r["figure3b"] and r["paired_gain"] == 0.0 for r in targets))
        self.assertTrue(all(not r["figure3b"] and abs(r["paired_gain"] - 1.8) < 1e-12 for r in controls))
        self.assertTrue(all(r["candidate_shuffle_mean"] > r["author_shuffle_mean"] for r in targets))
        self.assertEqual(sum(r["figure3b"] for r in result["mouse_conditions"]), 66)
        self.assertTrue(all(r["sessions"] == 7 for r in result["mouse_conditions"]))
        self.assertEqual(result["endpoint_roles"]["shuffle_scores"], "fidelity_and_protection_only")
        self.assertIsNone(result["paper_win"])


if __name__ == "__main__":
    unittest.main()
