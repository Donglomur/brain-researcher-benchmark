"""Generated-only controls; no authentic exports, fit, subprocess or network."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

import paired_loss as scorer


def fixture():
    def row(source_row, person, trial, frn, p3):
        value = {name: 0.0 for name in scorer.FEATURES}
        value.update(source_row=source_row, participant=person, trialGlobal=trial,
                     trialLocal=(trial - 1) % 5 + 1, FRN_N2_offer=frn, P3b_offer=p3)
        return value
    held = [row(i, "202", i, 3.0, 6.0) for i in range(1, 181)]
    held[0]["FRN_N2_offer"] = None
    held[1]["P3b_offer"] = None
    held[2]["rp"] = None
    held[3].update(FRN_N2_offer=1.0, P3b_offer=2.0)
    training = []
    for source_row, person, cluster, trial, value in (
            (181, "203", "cluster_a", 1, 0.0),
            (182, "203", "cluster_a", 2, 2.0),
            (183, "204", "cluster_b", 1, 10.0)):
        item = row(source_row, cluster, trial, value, 2 * value)
        item["original_participant"] = person
        training.append(item)
    case = {"participant": "202", "training": training,
            "clusters": [{"fit_id": "cluster_a", "original_participant": "203"},
                         {"fit_id": "cluster_b", "original_participant": "204"}],
            "query": [{name: item[name] for name in scorer.FEATURES + ("source_row",)}
                      for item in held if all(item[name] is not None for name in scorer.FEATURES)]}
    keys = [item["source_row"] for item in case["query"]]
    reference = {"schema": "neural006-reference-v1", "participant": "202", "status": "complete",
                 "source_rows": keys, "results": {}}
    for target, mean, variance in (("FRN_N2_offer", 5.5, 20.75), ("P3b_offer", 11.0, 83.0)):
        reference["results"][target] = {
            "normalizer": {"training_equal_person_mean": mean,
                           "training_equal_person_variance": variance},
            "arms": {arm: {"status": "fit_completed",
                           "prediction": [mean if arm == "mean" else 0.0] * len(keys)}
                     for arm in scorer.ARMS}}
    candidates = {mode: {"status": "complete", "predictions": [[key, 0.0, 0.0] for key in keys]}
                  for mode in scorer.MODES}
    return case, held, reference, candidates


class PairedLossTests(unittest.TestCase):
    def test_independent_unequal_person_arithmetic_and_units(self):
        result = scorer.score_case(*fixture())
        self.assertEqual(result["paired_scored_rows"], 177)
        frn = result["components"]["FRN_N2_offer"]["frozen_program"]
        p3 = result["components"]["P3b_offer"]["frozen_program"]
        self.assertAlmostEqual(frn["mse"], 1585 / 177)
        self.assertAlmostEqual(frn["mae"], 529 / 177)
        self.assertAlmostEqual(frn["normalized_mse"], (1585 / 177) / 20.75)
        self.assertAlmostEqual(p3["mse"], 4 * frn["mse"])
        self.assertAlmostEqual(p3["mae"], 2 * frn["mae"])
        self.assertAlmostEqual(p3["normalized_mse"], frn["normalized_mse"])

    def test_matches_predecessor_on_valid_projection(self):
        # Definition-only imports; this does not execute the effectful runtime.
        runtime = Path(__file__).resolve().parents[1] / "neural-006/broker-controls-v4/runtime"
        saved = sys.modules.get("protocol")
        try:
            for name in ("protocol", "analysis"):
                spec = importlib.util.spec_from_file_location(name, runtime / (name + ".py"))
                module = importlib.util.module_from_spec(spec)
                if name == "protocol":
                    sys.modules["protocol"] = module
                spec.loader.exec_module(module)
            case, held, reference, candidates = fixture()
            truth = {row["source_row"]: {target: row[target] for target in scorer.TARGETS}
                     for row in held if all(row[name] is not None for name in scorer.FEATURES + scorer.TARGETS)}
            self.assertEqual(scorer.score_case(case, held, reference, candidates),
                             module.score_case(case, truth, reference, candidates))
            # The old API accepts an eligible-row omission. The new API rebuilds
            # that mask from all 180 rows instead of accepting this truth dict.
            truth.pop(4)
            old_subset = module.score_case(case, truth, reference, candidates)
            self.assertEqual(old_subset["paired_scored_rows"], 176)
            self.assertNotEqual(old_subset, scorer.score_case(case, held, reference, candidates))
        finally:
            if saved is None:
                sys.modules.pop("protocol", None)
            else:
                sys.modules["protocol"] = saved

    def test_unscored_behavior_rows_still_require_predictions(self):
        case, held, reference, candidates = fixture()
        candidates["frozen_program"]["predictions"].pop(0)
        with self.assertRaisesRegex(scorer.InvalidScoreInput, "complete_candidate_queries"):
            scorer.score_case(case, held, reference, candidates)

    def test_target_missingness_stays_paired(self):
        case, held, reference, candidates = fixture()
        held[0]["P3b_offer"] = 1e100  # FRN missing: neither component is scored here.
        held[1]["FRN_N2_offer"] = 1e100  # P3 missing: neither component is scored here.
        self.assertEqual(scorer.score_case(case, held, reference, candidates), scorer.score_case(*fixture()))

    def test_candidate_order_is_identity_joined(self):
        case, held, reference, candidates = fixture()
        candidates["adaptive_investigation"]["predictions"].reverse()
        self.assertEqual(scorer.score_case(case, held, reference, candidates), scorer.score_case(*fixture()))

    def test_complete_private_trajectory_required(self):
        case, held, reference, candidates = fixture()
        with self.assertRaisesRegex(scorer.InvalidScoreInput, "complete_held_trajectory"):
            scorer.score_case(case, held[:-1], reference, candidates)

    def test_omitted_or_reordered_eligible_query_refused(self):
        for reorder in (False, True):
            with self.subTest(reorder=reorder):
                case, held, reference, candidates = fixture()
                if reorder:
                    case["query"].reverse()
                else:
                    case["query"].pop()
                with self.assertRaises(scorer.InvalidScoreInput):
                    scorer.score_case(case, held, reference, candidates)

    def test_boolean_source_aliases_refused(self):
        for location in ("held", "query", "candidate", "reference"):
            with self.subTest(location=location):
                case, held, reference, candidates = fixture()
                if location == "held": held[0]["source_row"] = True
                if location == "query": case["query"][0]["source_row"] = True
                if location == "candidate": candidates["frozen_program"]["predictions"][0][0] = True
                if location == "reference": reference["source_rows"][0] = True
                with self.assertRaises(scorer.InvalidScoreInput):
                    scorer.score_case(case, held, reference, candidates)

    def test_changed_training_normalizer_refused(self):
        case, held, reference, candidates = fixture()
        reference["results"]["FRN_N2_offer"]["normalizer"]["training_equal_person_variance"] = 1.0
        with self.assertRaisesRegex(scorer.InvalidScoreInput, "independent_training_variance"):
            scorer.score_case(case, held, reference, candidates)

    def test_training_source_leakage_and_duplicate_refused(self):
        for defect in ("held_row", "held_person", "duplicate"):
            with self.subTest(defect=defect):
                case, held, reference, candidates = fixture()
                if defect == "held_row": case["training"][0]["source_row"] = 1
                if defect == "held_person": case["clusters"][0]["original_participant"] = "202"
                if defect == "duplicate": case["training"].append(copy.deepcopy(case["training"][0]))
                with self.assertRaises(scorer.InvalidScoreInput):
                    scorer.score_case(case, held, reference, candidates)

    def test_bootstrap_copy_has_equal_cluster_mass(self):
        case, held, reference, candidates = fixture()
        case["clusters"].append({"fit_id": "cluster_c", "original_participant": "204"})
        duplicate = dict(case["training"][-1], participant="cluster_c")
        case["training"].append(duplicate)
        for target, mean, variance in (("FRN_N2_offer", 7.0, 55 / 3), ("P3b_offer", 14.0, 220 / 3)):
            entry = reference["results"][target]
            entry["normalizer"].update(training_equal_person_mean=mean, training_equal_person_variance=variance)
            entry["arms"]["mean"]["prediction"] = [mean] * len(case["query"])
        score = scorer.score_case(case, held, reference, candidates)
        self.assertAlmostEqual(score["components"]["FRN_N2_offer"]["frozen_program"]["normalized_mse"],
                               (1585 / 177) / (55 / 3))
        duplicate["FRN_N2_offer"] = 11.0
        with self.assertRaisesRegex(scorer.InvalidScoreInput, "inconsistent_training_source_copy"):
            scorer.score_case(case, held, reference, candidates)

    def test_frozen_reserve_uses_separate_training_case(self):
        case, held, reference, candidates = fixture()
        training = {"training": case.pop("training"), "clusters": case.pop("clusters")}
        self.assertEqual(scorer.score_case(case, held, reference, candidates, training_case=training),
                         scorer.score_case(*fixture()))

    def test_incomplete_bootstrap_copy_refused(self):
        case, held, reference, candidates = fixture()
        case["clusters"].append({"fit_id": "cluster_c", "original_participant": "203"})
        case["training"].append(dict(case["training"][0], participant="cluster_c"))
        with self.assertRaisesRegex(scorer.InvalidScoreInput, "inconsistent_training_copy_support"):
            scorer.score_case(case, held, reference, candidates)

    def test_nonfinite_unpaired_targets_and_reference_predictions_refused(self):
        for location in ("held", "candidate", "reference"):
            with self.subTest(location=location):
                case, held, reference, candidates = fixture()
                if location == "held": held[0]["P3b_offer"] = float("inf")
                if location == "candidate": candidates["frozen_program"]["predictions"][0][1] = float("nan")
                if location == "reference": reference["results"]["FRN_N2_offer"]["arms"]["J"]["prediction"][0] = float("inf")
                with self.assertRaises(scorer.InvalidScoreInput):
                    scorer.score_case(case, held, reference, candidates)

    def test_incomplete_mode_arm_and_empty_paired_support_refused(self):
        for defect in ("mode", "arm", "support"):
            with self.subTest(defect=defect):
                case, held, reference, candidates = fixture()
                if defect == "mode": candidates.pop("adaptive_investigation")
                if defect == "arm": reference["results"]["P3b_offer"]["arms"]["J"]["status"] = "fit_error"
                if defect == "support":
                    for row in held: row["FRN_N2_offer"] = None
                with self.assertRaises(scorer.InvalidScoreInput):
                    scorer.score_case(case, held, reference, candidates)


if __name__ == "__main__":
    unittest.main()
