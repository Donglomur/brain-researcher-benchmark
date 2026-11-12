"""Invented arithmetic and actual numerical-tail parity; no real data or runner."""
import ast
import copy
import importlib.util
import math
from pathlib import Path
import unittest

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probability_diagnostics", D / "probability_diagnostics.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def accumulator(nights):
    a = p.ProbabilityAccumulator()
    for number, rows in enumerate(nights):
        a.begin_night(number, len(rows))
        for probability, stage in rows:
            a.update(probability, stage)
        a.end_night()
    return a


def matrix(count, truth=0, predicted=0):
    out = [[0]*5 for _ in range(5)]
    out[truth][predicted] = count
    return out


def numerical_functions(reader):
    # Accepted pure science functions execute; the sole common import is replaced
    # by explicit constants/ValueError. No reference, transport or file reader runs.
    source = (D / "predecessor/science.py").read_text()
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not
                 (isinstance(node, ast.ImportFrom) and node.module == "common")]
    namespace = {"CLASSES": p.CLASSES, "need": p.need}
    exec(compile(tree, "accepted_science_pure_definitions", "exec"), namespace)
    original = (D / "predecessor/scorer.py").read_text()
    cut = original.index("    panels={}\n", original.index("def score("))
    legacy = "def legacy(got, graph, prepared, grant, meter):\n" + original[cut:]
    namespace.update(array_rows=reader, ProbabilityAccumulator=p.ProbabilityAccumulator,
                     panel_macro=p.panel_macro)
    exec(compile(legacy, "actual_original_numeric_tail", "exec"), namespace)
    current = ast.parse((D / "scorer_with_probability_diagnostics.py").read_text())
    node = next(n for n in current.body if isinstance(n, ast.FunctionDef)
                and n.name == "_score_admitted_panel")
    exec(compile(ast.Module(body=[node], type_ignores=[]), "actual_successor_numeric_tail", "exec"), namespace)
    return namespace["legacy"], namespace["_score_admitted_panel"]


def full_invented_panel(profile):
    panels = []
    for mode in ("frozen_program", "case_adaptive_equal_inputs_tools_compute"):
        selected = profile if mode == "frozen_program" else "current_person"
        panels.extend((mode, selected, v, "original") for v in ("C", "EC", "OC", "EOC"))
        panels.extend((mode, selected, v, "shifted") for v in ("EC", "EOC"))
    panels.append(("R0", "independent_reference", "C", "original"))
    for family in ("R1", "R2"):
        panels.extend((family, "independent_reference", v, "original") for v in ("C", "EC", "OC", "EOC"))
        panels.extend((family, "independent_reference", v, "shifted") for v in ("EC", "EOC"))
    panels.extend(("R2", "independent_reference", v, "association") for v in ("C", "EC"))
    values, prepared, got = {}, {}, {}
    for person in range(78):
        for night in range(2 if person < 75 else 1):
            name = f"invented:{person}:{night}"
            stages = [person % 5, -1, (person + night + 2) % 5]
            values[name+":stages"] = stages
            values[name+":mask"] = [stage >= 0 for stage in stages]
            prepared[person, night] = {"stages": {"id": name+":stages"}, "mask": {"id": name+":mask"}}
    for ordinal, key in enumerate(panels):
        for person in range(78):
            row = dict(zip(("mode", "profile", "view", "control"), key))
            row.update(subject=person, nights=[])
            for night in range(2 if person < 75 else 1):
                name = f"invented:{person}:{night}"
                probabilities = []
                for j, stage in enumerate(values[name+":stages"]):
                    rowp = [.1]*5
                    rowp[(person + ordinal + j) % 5] = .6
                    probabilities.append(rowp)
                probability_name = name+f":panel{ordinal}"
                values[probability_name] = probabilities
                row["nights"].append({"night": night, "epochs": 3, "probabilities": {"id": probability_name}})
            got[f"invented:{ordinal}:{person}"] = row
    def reader(artifact, epochs, columns, dtype, meter):
        rows = values[artifact["id"]]
        assert len(rows) == epochs
        yield from copy.deepcopy(rows)
    return got, prepared, reader


class DiagnosticsControls(unittest.TestCase):
    def test_perfect_and_uniform_known_values(self):
        perfect = accumulator([[([0, 0, 1, 0, 0], 2)]]).result()
        self.assertEqual(perfect["mean_multiclass_brier"], 0)
        self.assertEqual(perfect["mean_clipped_log_loss_nats"], 0)
        uniform = accumulator([[([.2]*5, 2)]]).result()
        self.assertAlmostEqual(uniform["mean_multiclass_brier"], .8)
        self.assertAlmostEqual(uniform["mean_clipped_log_loss_nats"], math.log(5))
        self.assertEqual(uniform["log_loss_clipped_epochs"], 0)

    def test_wrong_zero_probability_is_explicitly_clipped(self):
        r = accumulator([[([0, 1, 0, 0, 0], 0)]]).result()
        self.assertEqual(r["mean_multiclass_brier"], 2)
        self.assertAlmostEqual(r["mean_clipped_log_loss_nats"], -math.log(p.EPSILON))
        self.assertEqual(r["log_loss_clipped_epochs"], 1)

    def test_masked_rows_do_not_change_numerical_metrics(self):
        a = accumulator([[([1, 0, 0, 0, 0], 0), ([0, 1, 0, 0, 0], -1)]]).result()
        self.assertEqual((a["clock_epochs"], a["eligible_epochs"], a["masked_epochs"]), (2, 1, 1))
        self.assertEqual(a["mean_multiclass_brier"], 0)

    def test_same_argmax_can_have_different_probability_quality(self):
        a = accumulator([[([.6, .1, .1, .1, .1], 0)]]).result()
        b = accumulator([[([.8, .05, .05, .05, .05], 0)]]).result()
        self.assertLess(b["mean_multiclass_brier"], a["mean_multiclass_brier"])
        self.assertLess(b["mean_clipped_log_loss_nats"], a["mean_clipped_log_loss_nats"])

    def test_unequal_nights_pool_epochs_then_equal_people(self):
        a = accumulator([[([1, 0, 0, 0, 0], 0)]]).result()
        b = accumulator([[([1, 0, 0, 0, 0], 0)], [([0, 1, 0, 0, 0], 0)]*3]).result()
        cm = matrix(1); cm[0][1] = 3
        result = p.panel_macro({0: a, 1: b}, {0: matrix(1), 1: cm})
        self.assertEqual(b["mean_multiclass_brier"], 1.5)
        self.assertEqual(result["person_macro_brier"], .75)
        self.assertNotEqual(result["person_macro_brier"], 6/5)

    def test_marginal_calibration_does_not_imply_good_resolution(self):
        r = accumulator([[([.5, .5, 0, 0, 0], 0), ([.5, .5, 0, 0, 0], 1)]]).result()
        self.assertEqual(r["calibration_in_large_predicted_minus_observed"], [0]*5)
        self.assertEqual(r["mean_multiclass_brier"], .5)

    def test_empty_eligible_support_is_not_selected_away(self):
        a = accumulator([[([1, 0, 0, 0, 0], -1)]]).result()
        b = accumulator([[([1, 0, 0, 0, 0], 0)]]).result()
        r = p.panel_macro({0: a, 1: b}, {0: matrix(0), 1: matrix(1)})
        self.assertIsNone(r["person_macro_brier"])
        self.assertEqual(r["undefined_people"], [0])

    def test_bad_values_and_masks_refused_without_row_repair(self):
        for row, stage in [([True, 0, 0, 0, 0], 0), ([float('nan')]*5, 0),
                           ([1.01, 0, 0, 0, 0], 0), ([.3]*5, 0),
                           ([1, 0, 0, 0, 0], True), ([1, 0, 0, 0, 0], -2)]:
            with self.subTest(row=row, stage=stage), self.assertRaises(ValueError):
                accumulator([[(row, stage)]])

    def test_existing_simplex_tolerance_preserved_without_normalizing(self):
        row = [.2, .2, .2, .2, .2000005]
        r = accumulator([[(row, 4)]]).result()
        self.assertEqual(r["mean_predicted_probability"], row)

    def test_missing_extra_or_duplicate_nights_refused(self):
        a = p.ProbabilityAccumulator(); a.begin_night(1, 2)
        a.update([1, 0, 0, 0, 0], 0)
        with self.assertRaises(ValueError): a.end_night()
        with self.assertRaises(ValueError): a.result()
        a.update([1, 0, 0, 0, 0], 0)
        with self.assertRaises(ValueError): a.update([1, 0, 0, 0, 0], 0)
        a.end_night()
        with self.assertRaises(ValueError): a.begin_night(1, 2)

    def test_exact_confusion_support_and_detached_results(self):
        a = accumulator([[([1, 0, 0, 0, 0], 0)]]).result()
        with self.assertRaises(ValueError): p.panel_macro({0: a}, {1: matrix(1)})
        with self.assertRaises(ValueError): p.panel_macro({0: a}, {0: matrix(2)})
        result = p.panel_macro({0: a}, {0: matrix(1)})
        result["people"]["0"]["truth_counts"][0] = 999
        self.assertEqual(a["truth_counts"][0], 1)

    def test_original_admission_boundary_preserved(self):
        old = (D / "predecessor/scorer.py").read_text()
        new = (D / "scorer_with_probability_diagnostics.py").read_text()
        original_prefix = old[:old.index("    panels={}\n", old.index("def score("))]
        new_prefix = new[:new.index("    return _score_admitted_panel")]
        new_prefix = new_prefix.replace("from .probability_diagnostics import ProbabilityAccumulator, panel_macro\n", "")
        self.assertEqual(new_prefix, original_prefix)
        self.assertIn("Independent complete exposure/fit lineage audit", new_prefix)

    def test_actual_numeric_tail_exact_original_grade_for_both_profiles(self):
        for profile in ("generic_current_person", "training_only_reuse"):
            with self.subTest(profile=profile):
                got, prepared, reader = full_invented_panel(profile)
                self.assertEqual((len(got), len(prepared)), (2106, 153))
                legacy, successor = numerical_functions(reader)
                args = (got, {"profile": profile}, prepared,
                        {"predictions": {"bytes": 123, "sha256": "0"*64}}, None)
                expected = legacy(*args)
                result = successor(*args)
                self.assertEqual(result["grade"], expected)
                diagnostics = result["probability_diagnostics"]
                self.assertEqual(set(diagnostics["panels"]), set(expected["panels"]))
                self.assertEqual(len(diagnostics["panels"]), 27)
                for key, panel in diagnostics["panels"].items():
                    self.assertEqual(panel["required_people"], 78)
                    self.assertEqual(sum(x["clock_epochs"] for x in panel["people"].values()), 459)
                    self.assertEqual(sum(x["eligible_epochs"] for x in panel["people"].values()), 306)
                    for person, scores in panel["people"].items():
                        self.assertEqual(scores["truth_counts"], expected["panels"][key]["people"][int(person)]["support"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
