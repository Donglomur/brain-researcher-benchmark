"""Generated controls; no authentic recordings, model, fit, or native imports."""
import contextlib
import copy
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("generation_roster", HERE / "generation_roster.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Mask(list):
    def __and__(self, other):
        return Mask(a and b for a, b in zip(self, other))


class Series(list):
    @property
    def values(self):
        return self

    def __eq__(self, other):
        return Mask(value == other for value in self)


class Frame:
    """Small explicit DataFrame double for the exact captured metric helpers."""
    def __init__(self, rows, columns):
        self.rows = list(rows)
        self.columns = list(columns)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, key):
        if isinstance(key, str):
            return Series(row[key] for row in self.rows)
        if isinstance(key, Mask):
            return Frame([row for row, keep in zip(self.rows, key) if keep], self.columns)
        return Frame([{column: row[column] for column in key} for row in self.rows], key)

    def drop_duplicates(self):
        seen, rows = set(), []
        for row in self.rows:
            key = tuple(row[column] for column in self.columns)
            if key not in seen:
                rows.append(row)
                seen.add(key)
        return Frame(rows, self.columns)

    def reset_index(self, drop):
        assert drop is True
        return self

    @property
    def iloc(self):
        return [[row[column] for column in self.columns] for row in self.rows]


def weighted_boolean_prf(true, pred, *, average, zero_division):
    """Named generated-only stand-in, not a scikit-learn parity certificate."""
    assert average == "weighted" and zero_division == 0
    metrics = [0., 0., 0.]
    for label in (False, True):
        tp = sum(a == label and b == label for a, b in zip(true, pred))
        fp = sum(a != label and b == label for a, b in zip(true, pred))
        fn = sum(a == label and b != label for a, b in zip(true, pred))
        support = sum(a == label for a in true)
        precision = tp / (tp + fp) if tp + fp else 0.
        recall = tp / (tp + fn) if tp + fn else 0.
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
        for index, value in enumerate((precision, recall, f1)):
            metrics[index] += support * value / len(true) if true else 0.
    return (*metrics, None)


def runtime_double():
    return SimpleNamespace(pd=SimpleNamespace(DataFrame=Frame),
        np=SimpleNamespace(union1d=lambda a, b: sorted(set(a) | set(b)), array=list),
        precision_recall_fscore_support=weighted_boolean_prf)


def fixture():
    def pin(name):
        return {"path": name + ".json", "bytes": 1, "sha256": "0" * 64}
    def row(name, tick):
        return {"id": name, "recording": "generated-lateral", "end_tick": tick, "recording_ticks": 1000}
    support = {"train": [row("train", 10)], "selection": [row("validation", 100)],
               "evaluation": [row("evaluation0", 200), row("evaluation1", 205)]}
    runs, pairs, packets = [], [], []
    for arm in M.ARMS:
        pair = {"pair_id": arm}
        for role in M.ROLES:
            run_id = arm + ":" + role
            pair[role] = run_id
            runs.append({"run_id": run_id, "case_id": "lateral--neural_ablation--current--100",
                "condition": "protected_support_source_amended_10ms", "arm": arm, "role": role,
                "seed": 19, "source_run": pin(run_id.replace(":", "-")), "support": copy.deepcopy(support)})
            ids = [0, 0] if role == "source_reference" else [2, 0]
            intervals = [M._float32(2.), M._float32(2.)] if role == "source_reference" else [M._float32(2.), M._float32(2.05)]
            packets.append({"run_id": run_id, "prediction": {"ID": ids, "dt": [0., .01],
                "Trial": [0, 0], "Interval": intervals}})
        pairs.append(pair)
    study = {"schema": M.SCHEMA, "study_identity": pin("generated-study"), "runs": runs, "pairs": pairs,
        "limits": {"max_runs": 4, "max_support_rows": 16, "max_windows": 8,
            "max_prediction_events": 16, "max_truth_events": 16}}
    def truth(run):
        return tuple({"interval": M._float32(row["end_tick"] * .01), "trial": 0,
                      "ids": (0, 0, 1) if i == 0 else ()}
                     for i, row in enumerate(run["support"]["evaluation"]))
    return packets, study, truth


class GenerationRosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        implementations = Path(os.environ.get("NEUROFORMER_TEST_IMPLEMENTATIONS", str(HERE.parent)))
        cls.path_patch = patch.object(M, "BEHAVIOR_PATH", implementations / "native-behavior-truth-v1" / "behavior_truth.py")
        cls.path_patch.start()
        cls.source_owner = M.source_context()
        cls.loaded = cls.source_owner.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.source_owner.__exit__(None, None, None)
        cls.path_patch.stop()

    def setUp(self):
        @contextlib.contextmanager
        def borrowed():
            yield self.loaded
        self.borrow = patch.object(M, "source_context", borrowed)
        self.borrow.start()
        self.addCleanup(self.borrow.stop)
        self.packets, self.study, self.truth = fixture()
        self.calls = []

    def loader(self, run):
        self.calls.append(("truth", run["run_id"]))
        return self.truth(run)

    def runtime(self):
        self.calls.append(("runtime", None))
        return runtime_double()

    def run_assess(self):
        return M.assess(self.packets, self.study, self.loader, self.runtime)

    def assert_admission_refuses(self):
        with self.assertRaises(ValueError):
            self.run_assess()
        self.assertEqual(self.calls, [])

    def test_full_roster_and_both_unchanged_original_branches(self):
        report = self.run_assess()
        self.assertEqual(len(report["runs"]), 4)
        self.assertEqual(len(report["comparisons"]), 2)
        self.assertEqual([kind for kind, _ in self.calls], ["truth"] * 4 + ["runtime"])
        reference = report["runs"][0]["diagnostics"]
        self.assertEqual(reference["branches"]["compute_scores"]["recall"], 1.)  # Retain original FP==0 shortcut.
        self.assertEqual(reference["true_present_windows"], 1)
        self.assertEqual(reference["complete_windows"], 2)
        self.assertEqual(reference["predicted_present_windows"], 1)
        self.assertEqual(report["comparisons"][0]["candidate_minus_reference"]["compute_scores"]["F1"], -1.)
        self.assertFalse(report["scientifically_qualified"])
        self.assertIsNone(report["selected_paper_figure6_metric"])
        self.assertIsNone(report["paper_win"])
        self.assertNotIn("ids", repr(report))

    def test_last_bad_packet_blocks_every_target_and_runtime(self):
        self.packets[-1]["prediction"]["ID"][-1] = True
        self.assert_admission_refuses()

    def test_missing_and_reordered_run_rosters_refuse(self):
        self.packets.pop()
        self.assert_admission_refuses()
        self.packets, self.study, self.truth = fixture()
        self.packets.reverse()
        self.assert_admission_refuses()

    def test_out_of_population_and_out_of_window_refuse_early(self):
        self.packets[-1]["prediction"]["ID"][-1] = 2022
        self.assert_admission_refuses()
        self.packets, self.study, self.truth = fixture()
        self.packets[-1]["prediction"]["Interval"][-1] = 999.
        self.assert_admission_refuses()

    def test_aggregate_prediction_bound_is_not_per_run_only(self):
        self.study["limits"]["max_prediction_events"] = 7
        self.assert_admission_refuses()

    def test_pair_cannot_change_arm_seed_support_or_condition(self):
        for key, value in (("arm", "paper_data_author_code"), ("seed", 20),
                           ("condition", "released_computational_path_10ms")):
            self.packets, self.study, self.truth = fixture()
            self.study["runs"][1][key] = value
            self.assert_admission_refuses()
        self.packets, self.study, self.truth = fixture()
        self.study["runs"][1]["support"]["evaluation"].reverse()
        self.assert_admission_refuses()

    def test_orphan_and_duplicate_pairing_refuse(self):
        self.study["pairs"][1] = copy.deepcopy(self.study["pairs"][0])
        self.assert_admission_refuses()

    def test_prospective_and_behavior_cells_cannot_enter_neural_diagnostic(self):
        for case in ("lateral--blocked_neural--improved--100", "lateral--speed_regression--neuroformer--100"):
            self.packets, self.study, self.truth = fixture()
            self.study["runs"][0]["case_id"] = case
            self.assert_admission_refuses()

    def test_historical_neural_split_is_not_replaced_with_behavior_test_support(self):
        for run in self.study["runs"]:
            run["condition"] = "released_computational_path_10ms"
            run["support"]["selection"] = copy.deepcopy(run["support"]["evaluation"])
        self.assert_admission_refuses()

    def test_float32_endpoint_collision_refuses(self):
        for run in self.study["runs"]:
            for rows in run["support"].values():
                for row in rows:
                    row["recording_ticks"] = 2_000_000_000
            run["support"]["evaluation"][0]["end_tick"] = 1_677_721_600
            run["support"]["evaluation"][1]["end_tick"] = 1_677_721_605
        self.assert_admission_refuses()

    def test_missing_or_reordered_truth_blocks_runtime(self):
        original = self.truth
        for replacement in (lambda run: original(run)[:-1], lambda run: original(run)[::-1]):
            self.calls.clear()
            self.truth = replacement
            with self.assertRaises(ValueError):
                self.run_assess()
            self.assertFalse(any(kind == "runtime" for kind, _ in self.calls))

    def test_paired_truth_mismatch_blocks_runtime(self):
        original = self.truth
        def altered(run):
            windows = list(original(run))
            if run["role"] == "candidate":
                windows[0] = {**windows[0], "ids": (0,)}
            return tuple(windows)
        self.truth = altered
        with self.assertRaisesRegex(ValueError, "paired private truth"):
            self.run_assess()
        self.assertEqual(len(self.calls), 4)

    def test_truth_event_capacity_counts_all_runs(self):
        self.study["limits"]["max_truth_events"] = 11
        with self.assertRaisesRegex(ValueError, "aggregate truth"):
            self.run_assess()
        self.assertFalse(any(kind == "runtime" for kind, _ in self.calls))

    def test_post_admission_mutation_cannot_change_predictions(self):
        original = self.truth
        def mutate(run):
            for packet in self.packets:
                packet["prediction"]["ID"][:] = [100, 100]
            self.study["runs"].clear()
            return original(run)
        self.truth = mutate
        report = self.run_assess()
        self.assertEqual(report["runs"][0]["diagnostics"]["branches"]["compute_scores"]["F1"], 1.)
        self.assertEqual(len(report["runs"]), 4)

    def test_empty_source_branches_remain_empty_with_null_effect(self):
        for packet in self.packets:
            packet["prediction"] = {key: [] for key in ("ID", "dt", "Trial", "Interval")}
        original = self.truth
        self.truth = lambda run: tuple({**window, "ids": ()} for window in original(run))
        report = self.run_assess()
        self.assertEqual(report["runs"][0]["diagnostics"]["branches"], {branch: {} for branch in M.BRANCHES})
        self.assertTrue(all(value is None for branch in report["comparisons"][0]["candidate_minus_reference"].values()
                            for value in branch.values()))

    def test_embedded_generator_truth_is_not_read(self):
        class DoNotRead:
            def __iter__(self):
                raise AssertionError("embedded truth must not be consumed")
        for packet in self.packets:
            packet["prediction"]["true"] = DoNotRead()
            packet["prediction"]["time"] = DoNotRead()
        self.assertTrue(self.run_assess()["all_predictions_admitted_before_targets_and_runtime"])


if __name__ == "__main__":
    unittest.main()
