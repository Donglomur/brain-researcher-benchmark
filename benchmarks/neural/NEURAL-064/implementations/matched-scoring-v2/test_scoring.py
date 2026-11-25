"""Generated arithmetic and adversarial software controls; no scientific data."""
import copy
import importlib.util
import itertools
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


class BehaviorPlaneIdentityTests(unittest.TestCase):
    """Generated metadata only: two imaging planes are one behavioral event."""

    @staticmethod
    def support_module():
        path = HERE.parent / "neural-064" / "programme"
        name = "neural064_support_identity"
        spec = importlib.util.spec_from_file_location(
            name, path / "__init__.py", submodule_search_locations=[str(path)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        spec.loader.exec_module(package)
        return importlib.import_module(name + ".support")

    @staticmethod
    def plane_fixture():
        records, events = [], []
        for plane in range(2):
            experiment, container = "plane" + str(plane), "container" + str(plane)
            common = {"experiment": experiment, "mouse": "generated-mouse",
                      "session": "generated-session", "container": container,
                      "condition": "Novel 1"}
            records.append({**common, "status": "complete",
                            "source_event_observations": 1,
                            "retained_event_observations": 1,
                            "excluded_event_observations": 0})
            events.append({**common, "event": experiment + ":event",
                           "behavior_event": "generated-session:event",
                           "image": "generated-image", "native_image_novel": True,
                           "lifetime_count_status": "known", "lifetime_image_count": 0,
                           "session_order": 1, "change": 0, "within_session_history": 0,
                           "pre_running_bin": 0, "pre_pupil_bin": 0,
                           "outcome_status": "known", "outcome_flags": [0] * 8,
                           "neural_support": "supported"})
        return ({"population": "catalogue", "membership_status": "admitted",
                 "source_membership_binding": "generated-binding-not-admission",
                 "experiments": records}, events)

    def test_matching_planes_keep_two_observations_and_one_behavior_event(self):
        membership, events = self.plane_fixture()
        table = self.support_module().support_tables(membership, events, [])
        self.assertEqual(table["unique_behavior_events"], 1)
        self.assertEqual(table["event_denominator_summary"]["source_event_observations"], 2)
        self.assertTrue(table["complete_quantitative_support"])

    def test_change_disagreement_rejected_in_either_plane_order(self):
        membership, events = self.plane_fixture()
        events[1]["change"] = 1
        for ordered in (events, list(reversed(events))):
            with self.assertRaisesRegex(ValueError, "session-plane"):
                self.support_module().support_tables(membership, ordered, [])

    def test_session_order_disagreement_rejected(self):
        membership, events = self.plane_fixture()
        events[1]["session_order"] = 2
        with self.assertRaisesRegex(ValueError, "session-plane"):
            self.support_module().support_tables(membership, events, [])

    def test_outcome_availability_disagreement_rejected(self):
        membership, events = self.plane_fixture()
        events[1]["outcome_status"] = "unavailable"
        with self.assertRaisesRegex(ValueError, "session-plane"):
            self.support_module().support_tables(membership, events, [])

    def test_missing_session_order_stays_unknown(self):
        membership, events = self.plane_fixture()
        for event in events:
            event["session_order"] = None
        table = self.support_module().support_tables(membership, events, [])
        row = next(r for r in table["overlap"]
                   if r["contrast"] == "Familiar_vs_Novel1"
                   and r["constraints"] == "image_animal_session_order")
        self.assertEqual(row["status"], "unavailable_required_fields")
        self.assertEqual(row["unavailable_by_field"], {"session_order": 1})

    def test_plane_specific_neural_support_may_differ(self):
        membership, events = self.plane_fixture()
        events[1]["neural_support"] = "unavailable_clock_or_registered_cells"
        table = self.support_module().support_tables(membership, events, [])
        self.assertEqual(table["unique_behavior_events"], 1)
        self.assertEqual(len(table["joint_support"]), 2)


class PopulationMembershipTests(unittest.TestCase):
    """Full declared-count generated metadata; never source admission or signals."""

    @staticmethod
    def programme_module(leaf):
        path = HERE.parent / "neural-064" / "programme"
        name = "neural064_population_membership"
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                name, path / "__init__.py", submodule_search_locations=[str(path)])
            package = importlib.util.module_from_spec(spec)
            sys.modules[name] = package
            spec.loader.exec_module(package)
        return importlib.import_module(name + "." + leaf)

    @staticmethod
    def populations():
        # 204 containers, 80 mice, 475 selected planes; roles are 55/11/14.
        # Within a container, every plane belongs to the same generated mouse.
        secondary_rows = []
        assignments = {str(m): "fit" if m < 55 else "validation" if m < 66 else "query"
                       for m in range(80)}
        for i in range(475):
            container, visit = i % 204, i // 204
            mouse = container % 80
            secondary_rows.append({
                "ophys_experiment_id": i, "mouse_id": mouse,
                "ophys_session_id": "selected-session-" + str(mouse) + "-" + str(visit),
                "ophys_container_id": "selected-container-" + str(container),
                "experience_level": "Novel 1" if visit == 0 else "Novel >1",
                "split": assignments[str(mouse)]})
        # The selected rows use 227 sessions. Another 476 gives all 703 catalogue
        # sessions, and another 27 mice gives all 107 catalogue mice.
        catalogue_rows = [{k: v for k, v in r.items() if k != "split"}
                          for r in secondary_rows]
        for i in range(1936 - 475):
            session = i % 476
            catalogue_rows.append({
                "ophys_experiment_id": i + 475, "mouse_id": 80 + session % 27,
                "ophys_session_id": "catalogue-session-" + str(session),
                "ophys_container_id": "catalogue-container-" + str(i),
                "experience_level": "Familiar"})
        return ({"records": catalogue_rows, "source_membership_binding": "generated-catalogue"},
                {"records": secondary_rows, "source_membership_binding": "generated-secondary",
                 "mouse_assignments": assignments})

    def test_complete_generated_memberships_and_order_independence(self):
        catalogue, secondary = self.populations()
        before = copy.deepcopy((catalogue, secondary))
        contract = self.programme_module("membership_contract")
        self.assertTrue(contract.require_population_shape(catalogue, secondary))
        self.assertEqual((catalogue, secondary), before)
        catalogue["records"].reverse()
        secondary["records"].reverse()
        self.assertTrue(contract.require_population_shape(catalogue, secondary))

    def test_count_preserving_biological_and_condition_reassignments_fail(self):
        for field, indices in (("mouse_id", (0, 1)), ("ophys_session_id", (0, 1)),
                               ("ophys_container_id", (0, 1)), ("experience_level", (0, 204))):
            with self.subTest(field=field):
                catalogue, secondary = self.populations()
                rows = secondary["records"]
                a, b = indices
                rows[a][field], rows[b][field] = rows[b][field], rows[a][field]
                with self.assertRaisesRegex(ValueError, "catalogue/secondary experiment identity"):
                    self.programme_module("membership_contract").require_population_shape(catalogue, secondary)

    def test_source_identifier_string_normalization_is_preserved(self):
        catalogue, secondary = self.populations()
        for row in secondary["records"]:
            for field in ("ophys_experiment_id", "mouse_id"):
                row[field] = str(row[field])
        self.assertTrue(self.programme_module("membership_contract").require_population_shape(catalogue, secondary))

    def test_missing_selected_experiment_and_role_drift_remain_invalid(self):
        for mutation in ("outside_catalogue", "role_drift"):
            catalogue, secondary = self.populations()
            if mutation == "outside_catalogue":
                secondary["records"][0]["ophys_experiment_id"] = "not-in-catalogue"
            else:
                secondary["records"][0]["split"] = "query"
            with self.assertRaises(ValueError):
                self.programme_module("membership_contract").require_population_shape(catalogue, secondary)

    def test_preparation_rejects_join_before_source_access(self):
        catalogue, secondary = self.populations()
        rows = secondary["records"]
        rows[0]["ophys_container_id"], rows[1]["ophys_container_id"] = (
            rows[1]["ophys_container_id"], rows[0]["ophys_container_id"])
        # Empty source mapping would fail with KeyError if preparation reached
        # source projection. The membership join must fail before that access.
        with self.assertRaisesRegex(ValueError, "catalogue/secondary experiment identity"):
            self.programme_module("native_pipeline")._prepare_admitted(
                catalogue, secondary, {}, None, None)
        with self.assertRaises(RuntimeError):
            self.programme_module("native_pipeline").main()


class MeanCancellationTests(unittest.TestCase):
    """Generated complete-policy contrasts and finite arithmetic boundaries."""

    def test_complete_policy_keeps_small_signed_equal_mouse_contrast(self):
        for policy in core.POLICIES:
            candidate, targets, reference = fixture(policy)
            first = [1e308, -1e308, 1e-20] + [0.0] * 11
            for row in targets["cases"]:
                if row["subset"] == "new_image":
                    index = int(row["mouse"].removeprefix("query"))
                    row["target"] = first[index] if row["phase"] == "FIRST" else 0.0
            values = {row["id"]: row["target"] for row in targets["cases"]}
            for row in candidate["predictions"]:
                for arm in core.ARMS:
                    row[arm] = values[row["id"]]
            for family in core.FAMILIES:
                for arm in core.ARMS:
                    reference["predictions"][family][arm] = dict(values)
            result = score(candidate, targets, reference, policy)
            self.assertTrue(result["complete_primary_support"])
            self.assertEqual(result["primary_prediction_error"], 0.0)
            self.assertEqual(result["primary_fixed_reference_gain"], 0.0)
            contrast = result["celltypes"]["new_image/" + core.CELL_TYPES[0]]
            self.assertEqual(len(contrast["mice"]), 14)
            self.assertEqual(contrast["supported_case_count"], 28)
            self.assertEqual(contrast["observed_equal_mouse"], 1e-20 / 14)
            self.assertEqual(contrast["predicted_equal_mouse"], 1e-20 / 14)
            self.assertEqual(contrast["contrast_absolute_error_equal_mouse"], 0.0)

    def test_finite_mean_cancellation_permutation_and_representable_boundaries(self):
        for values in itertools.permutations((1e308, -1e308, 1e-20)):
            self.assertEqual(core.mean(values), 1e-20 / 3)
            self.assertEqual(core.mean(-value for value in values), -1e-20 / 3)
        self.assertEqual(core.mean([1e308] * 14), 1e308)
        self.assertEqual(core.mean([math.ulp(0.0)] * 14), math.ulp(0.0))
        self.assertEqual(core.mean([1.0, 2.0, 3.0]), 2.0)
        self.assertEqual(core.mean([0.0] * 14), 0.0)

    def test_mean_keeps_existing_invalid_input_rejections(self):
        for values in ([], [True], [float("nan")], [float("inf")], ["1"]):
            with self.assertRaises(core.ScoringError):
                core.mean(values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
