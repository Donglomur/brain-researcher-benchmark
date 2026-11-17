"""Generated arithmetic and adversarial software controls; no scientific data."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural064_scoring_v2", HERE / "scoring.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def pair(mouse, container, ident, first, repeat, *, split="query", subset="new_image"):
    return [{"id": ident + ":" + phase, "mouse": mouse, "container": container, "pair": ident,
             "phase": phase, "target": value, "split": split, "subset": subset,
             "cre_line": core.CELL_TYPES[0], "image": "invented-image"}
            for phase, value in zip(core.PHASES, (first, repeat))]


def unbalanced():
    return (pair("a", "a1", "a1p1", 6, 4) +
            sum((pair("a", "a2", "a2p" + str(i), 0, 4) for i in range(3)), []) +
            pair("b", "b1", "b1p1", -1, 2))


def fixture(policy=core.POLICIES[0]):
    roster, rows = [], []
    for role, count in core.ROLES.items():
        for i in range(count):
            mouse = role + str(i)
            roster.append({"mouse": mouse, "split": role, "status": "complete_supported"})
            if role == "query":
                rows += pair(mouse, mouse + "container", mouse + "new", 2 if i % 2 else -2, 0)
                rows += pair(mouse, mouse + "container", mouse + "familiar", 100, 101,
                             subset="already_familiar_image_control")
    targets = {"cases": rows, "mouse_support": roster, "complete_primary_support": True,
               "training_target_sd": 1.0}
    candidate = {"query_binding": "generated-binding", "predictions": [
        {"id": r["id"], "JOINT": r["target"], "NUISANCE": r["target"] + 50} for r in rows]}
    selection = {arm: {"hierarchical_validation_loss": 0.5, "hgb_grid_validation_losses": [1, 2, 3, 4],
                      "hgb_grid_index": 0, "validation_only_selected": "hierarchical_mean",
                      "fit_refit_on_validation": False} for arm in core.ARMS}
    reference = {"predictions": {family: {arm: {r["id"]: r["target"] + delta for r in rows}
                                           for arm in core.ARMS}
                                 for family, delta in zip(core.FAMILIES, (2, 3))},
                 "frozen_selection": {"policy": policy, "training_target_sd": 1.0,
                                      "primary_nuisance": "hierarchical_mean", "selection": selection}}
    return candidate, targets, reference


def score(candidate, targets, reference, policy=core.POLICIES[0]):
    return core.score_policy(policy, candidate, targets, reference, "generated-binding")


class ArithmeticTests(unittest.TestCase):
    def test_exact_nested_weights_and_population_scale(self):
        rows = unbalanced()
        w = core.weights(rows)
        self.assertAlmostEqual(sum(w.values()), 1)
        self.assertEqual(w["a1p1:FIRST"], 1 / 8)
        self.assertEqual(w["a2p0:REPEAT"], 1 / 24)
        self.assertEqual(w["b1p1:FIRST"], 1 / 4)
        # Hand moments: weighted E[Y]=2, E[Y^2]=9.75, hence Var=5.75.
        for r in rows:
            r["split"] = "fit"
        self.assertAlmostEqual(core.training_scale(rows), math.sqrt(5.75))

    def test_macro_rmse_is_mean_of_mouse_roots(self):
        rows = unbalanced()
        pp = {r["id"]: r["target"] + (2 if r["phase"] == "REPEAT" else 0)
              if r["container"] == "a1" else r["target"] + (4 if r["container"] == "a2" else 0)
              for r in rows}
        # Mouse a: sqrt((mean(0^2,2^2)+mean(4^2,4^2))/2)=3;
        # mouse b: 0. Average of roots is 1.5, not sqrt(mean MSE).
        self.assertAlmostEqual(core.macro_error(pp, rows, 1), 1.5)
        self.assertAlmostEqual(core.macro_error(pp, rows, 2), 0.75)
        self.assertNotAlmostEqual(core.macro_error(pp, rows, 1), math.sqrt(4.5))

    def test_signed_contrast_and_nested_replication_invariance(self):
        rows = unbalanced()
        truth = {r["id"]: r["target"] for r in rows}
        self.assertEqual(core.contrasts(truth, rows), {"a": -1, "b": -3})
        self.assertEqual(core.contrasts({k: -v for k, v in truth.items()}, rows), {"a": 1, "b": 3})
        replicated = copy.deepcopy(rows)
        for r in rows:
            if r["container"] == "a2":
                replicated.append({**r, "id": r["id"] + "copy", "pair": r["pair"] + "copy"})
        got = core.contrasts({r["id"]: r["target"] for r in replicated}, replicated)
        self.assertEqual(got, {"a": -1, "b": -3})

    def test_constant_scale_null_and_role_protection(self):
        rows = pair("m", "c", "p", 1, 1, split="fit")
        self.assertIsNone(core.training_scale(rows))
        rows[0]["split"] = rows[1]["split"] = "query"
        with self.assertRaises(core.ScoringError):
            core.training_scale(rows)
        for r in rows:
            r["split"], r["subset"] = "fit", "already_familiar_image_control"
        with self.assertRaises(core.ScoringError):
            core.training_scale(rows)

    def test_pair_and_parent_integrity(self):
        for mutate in (
                lambda rr: rr.pop(),
                lambda rr: rr.append(copy.deepcopy(rr[0])),
                lambda rr: rr[0].update(phase="REPEAT"),
                lambda rr: rr[0].update(subset="already_familiar_image_control"),
                lambda rr: rr[-1].update(container="a1"),
                lambda rr: rr[-1].update(split="fit")):
            rows = unbalanced()
            mutate(rows)
            with self.assertRaises(core.ScoringError):
                core.weights(rows)

    def test_large_finite_residuals_do_not_overflow_before_scaling(self):
        rows = pair("m", "c", "p", -1e308, -1e308)
        pp = {r["id"]: 1e308 for r in rows}
        self.assertEqual(core.macro_error(pp, rows, 1e308), 2)
        with self.assertRaises(core.ScoringError):
            core.macro_error(pp, rows, 1e-308)


class PolicyTests(unittest.TestCase):
    def test_fixed_reference_gain_and_familiar_controls(self):
        candidate, targets, reference = fixture()
        got = score(candidate, targets, reference)
        self.assertEqual(got["primary_prediction_error"], 0)
        self.assertEqual(got["primary_fixed_reference_gain"], 2)
        self.assertEqual(got["candidate_nuisance_error_descriptive"], 50)
        key = "already_familiar_image_control/" + core.CELL_TYPES[0]
        self.assertEqual(got["celltypes"][key]["observed_equal_mouse"], -1)
        for r in candidate["predictions"]:
            r["NUISANCE"] *= 100000
        self.assertEqual(score(candidate, targets, reference)["primary_fixed_reference_gain"], 2)

    def test_validation_selection_cannot_be_reversed_by_query(self):
        candidate, targets, reference = fixture()
        frozen = reference["frozen_selection"]
        frozen["selection"]["NUISANCE"]["hgb_grid_validation_losses"] = [0.25, 2, 3, 4]
        frozen["selection"]["NUISANCE"]["validation_only_selected"] = "hist_gradient_boosting"
        frozen["primary_nuisance"] = "hist_gradient_boosting"
        # HGB has worse generated query error (3 versus 2), but validation owns selection.
        self.assertEqual(score(candidate, targets, reference)["primary_fixed_reference_gain"], 3)
        frozen["primary_nuisance"] = "hierarchical_mean"
        with self.assertRaises(core.ScoringError):
            score(candidate, targets, reference)

    def test_both_policies_separate_and_reference_tie_is_fixed(self):
        for policy in core.POLICIES:
            candidate, targets, reference = fixture(policy)
            item = reference["frozen_selection"]["selection"]["NUISANCE"]
            item["hgb_grid_validation_losses"] = [0.5, 0.5, 1, 2]
            self.assertEqual(score(candidate, targets, reference, policy)["primary_fixed_reference_gain"], 2)
            item["hgb_grid_index"] = 1
            with self.assertRaises(core.ScoringError):
                score(candidate, targets, reference, policy)

    def test_missing_support_scale_or_reference_stays_null(self):
        for mutate in (
                lambda t: t.update(complete_primary_support=False),
                lambda t: t["mouse_support"][0].update(status="incomplete_source"),
                lambda t: t.update(training_target_sd=None),
                lambda t: t.update(training_target_sd=0),
                lambda t: t.update(training_target_sd=float("nan"))):
            candidate, targets, reference = fixture()
            mutate(targets)
            got = score(candidate, targets, reference)
            self.assertFalse(got["complete_primary_support"])
            self.assertIsNone(got["primary_prediction_error"])
            self.assertIsNone(got["primary_fixed_reference_gain"])
        candidate, targets, _ = fixture()
        self.assertIn("unavailable_frozen_evaluator_reference", score(candidate, targets, None)["unsupported_primary_reasons"])

    def test_omitted_mouse_and_unknown_novelty_cannot_reduce_denominator(self):
        candidate, targets, reference = fixture()
        removed = {r["id"] for r in targets["cases"] if r["mouse"] == "query0"}
        targets["cases"] = [r for r in targets["cases"] if r["id"] not in removed]
        candidate["predictions"] = [r for r in candidate["predictions"] if r["id"] not in removed]
        got = score(candidate, targets, reference)
        self.assertIn("incomplete_query_new_image_denominator", got["unsupported_primary_reasons"])
        candidate, targets, reference = fixture()
        for r in targets["cases"]:
            if r["mouse"] == "query0" and r["subset"] == "new_image":
                r["subset"] = "unknown_first_image_status"
        self.assertIn("unknown_new_image_denominator", score(candidate, targets, reference)["unsupported_primary_reasons"])

    def test_prediction_denominator_and_values_are_exact(self):
        for mutate in (
                lambda c: c["predictions"].pop(),
                lambda c: c["predictions"].__setitem__(0, copy.deepcopy(c["predictions"][1])),
                lambda c: c["predictions"][0].update(JOINT=True),
                lambda c: c["predictions"][0].update(NUISANCE=float("inf")),
                lambda c: c.update(query_binding="other")):
            candidate, targets, reference = fixture()
            mutate(candidate)
            with self.assertRaises(core.ScoringError):
                score(candidate, targets, reference)
        candidate, targets, reference = fixture()
        reference["predictions"]["hist_gradient_boosting"]["NUISANCE"].pop(targets["cases"][-1]["id"])
        with self.assertRaises(core.ScoringError):
            score(candidate, targets, reference)

    def test_full_original_roles_required(self):
        candidate, targets, reference = fixture()
        targets["mouse_support"].pop(0)
        with self.assertRaises(core.ScoringError):
            score(candidate, targets, reference)
        candidate, targets, reference = fixture()
        for r in targets["cases"][:4]:
            r["split"] = "fit"
        with self.assertRaises(core.ScoringError):
            score(candidate, targets, reference)

    def test_preserved_consumer_accepts_numeric_core_without_native_activation(self):
        path = HERE.parent / "neural-064" / "programme"
        spec = importlib.util.spec_from_file_location("neural064_preserved", path / "__init__.py",
                                                      submodule_search_locations=[str(path)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        evidence = importlib.import_module("neural064_preserved.evidence")
        candidate, targets, reference = fixture()
        old = evidence._evaluate_policy(core.POLICIES[0], candidate, targets, reference,
                                        "generated-binding", core)
        new = score(candidate, targets, reference)
        for key in ("primary_prediction_error", "primary_fixed_reference_gain", "references"):
            self.assertEqual(old[key], new[key])
        with self.assertRaises(RuntimeError):
            evidence.evaluate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
