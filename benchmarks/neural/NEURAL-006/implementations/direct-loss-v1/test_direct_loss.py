"""Generated operator controls; no original observations, fits or model calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import direct_loss as grader


def fixture():
    adapter = grader._ADAPTER
    held_person = adapter.ACTIVE[0]

    def features(trial):
        return dict(offer=2.0, rp=1.5, exp_valence=-1.0, ep_valence=0.5,
                    exp_arousal=0.2, ep_arousal=0.3, trialLocal=(trial - 1) % 5 + 1,
                    trialGlobal=trial, abs_R=0.5, abs_V=1.5,
                    abs_A=abs(0.2 - 0.3))

    clusters = [{"fit_id": "cluster_%02d" % i, "original_participant": person}
                for i, person in enumerate(adapter.ACTIVE) if person != held_person]
    training = []
    for index, cluster in enumerate(clusters, 1):
        for trial, frn in ((1, 0.0), (2, 2.0)) if index == 1 else ((1, 3.0),):
            training.append(dict(features(trial), source_row=index * 180 + trial,
                                 participant=cluster["fit_id"],
                                 original_participant=cluster["original_participant"],
                                 FRN_N2_offer=frn, P3b_offer=2 * frn))
    held = [dict(features(trial), source_row=trial, participant=held_person,
                 FRN_N2_offer=3.0, P3b_offer=6.0) for trial in range(1, 181)]
    held[0]["FRN_N2_offer"] = None
    held[1]["P3b_offer"] = None
    held[2]["rp"] = None
    held[3].update(FRN_N2_offer=1.0, P3b_offer=2.0)
    case = {"schema": "neural006-case-v1", "participant": held_person,
            "clusters": clusters, "training": training,
            "query": [{k: row[k] for k in adapter.FEATURES + ("source_row",)}
                      for row in held if all(row[k] is not None for k in adapter.FEATURES)]}
    _, binding = adapter.prepare_case(case)
    response = {"schema": "neural006-static-numeric-response-v1",
                "packet_sha256": binding["packet_sha256"],
                "predictions": [[token, 0.0, 0.0] for token, _ in binding["query_source_rows"]]}
    keys = [row["source_row"] for row in case["query"]]
    reference = {"schema": "neural006-reference-v1", "participant": held_person,
                 "status": "complete", "source_rows": keys, "results": {}}
    for target, mean, variance in (("FRN_N2_offer", 47 / 16, 39 / 256),
                                   ("P3b_offer", 47 / 8, 39 / 64)):
        reference["results"][target] = {
            "normalizer": {"training_equal_person_mean": mean,
                           "training_equal_person_variance": variance},
            "arms": {arm: {"status": "fit_completed",
                           "prediction": [mean if arm == "mean" else 0.0] * len(keys)}
                     for arm in grader._ARITHMETIC.ARMS}}
    return case, binding, adapter.canonical(response), held, reference


class DirectLossTests(unittest.TestCase):
    def test_hand_calculated_paired_loss_and_training_cluster_weighting(self):
        args = fixture()
        result = grader.score_response(*args)
        self.assertEqual(result["paired_scored_rows"], 177)
        self.assertEqual(result["condition"], grader.CONDITION)
        self.assertEqual(result["scope"], "one_observed_development_lopo33_case")
        self.assertEqual(result["scientific_qualification"], "not_established")
        frn = result["components"]["FRN_N2_offer"][grader.CONDITION]
        p3 = result["components"]["P3b_offer"][grader.CONDITION]
        self.assertAlmostEqual(frn["mse"], 1585 / 177)
        self.assertAlmostEqual(frn["mae"], 529 / 177)
        self.assertAlmostEqual(frn["normalized_mse"], (1585 / 177) / (39 / 256))
        self.assertAlmostEqual(p3["mse"], 4 * frn["mse"])
        self.assertAlmostEqual(p3["normalized_mse"], frn["normalized_mse"])
        for target in grader._ARITHMETIC.TARGETS:
            self.assertEqual(set(result["components"][target]),
                             set(grader._ARITHMETIC.ARMS) | {grader.CONDITION})
        self.assertEqual(result["response_sha256"], hashlib.sha256(args[2]).hexdigest())

    def test_response_order_restores_query_ids(self):
        args = list(fixture())
        original = grader.score_response(*args)
        response = json.loads(args[2])
        response["predictions"].reverse()
        args[2] = grader._ADAPTER.canonical(response)
        result = grader.score_response(*args)
        self.assertEqual(result["components"], original["components"])
        self.assertEqual(result["prediction_sha256"], original["prediction_sha256"])
        self.assertNotEqual(result["response_sha256"], original["response_sha256"])

    def test_legacy_api_retains_two_exact_modes_and_same_arithmetic(self):
        case, binding, body, held, reference = fixture()
        candidate = grader._ADAPTER.collect(case, binding, body)["candidate"]
        both = {mode: candidate for mode in grader._ARITHMETIC.MODES}
        old = grader._ARITHMETIC.score_case(case, held, reference, both)
        direct = grader.score_response(case, binding, body, held, reference)
        for target in grader._ARITHMETIC.TARGETS:
            self.assertEqual(old["components"][target]["frozen_program"],
                             direct["components"][target][grader.CONDITION])
        with self.assertRaisesRegex(grader._ARITHMETIC.InvalidScoreInput, "matched_modes"):
            grader._ARITHMETIC.score_case(case, held, reference, {grader.CONDITION: candidate})

    def test_unscored_queries_still_require_predictions_before_private_arithmetic(self):
        args = list(fixture())
        response = json.loads(args[2])
        response["predictions"].pop(0)  # Missing FRN target does not excuse a response.
        args[2] = grader._ADAPTER.canonical(response)
        with mock.patch.object(grader._ARITHMETIC, "_score_modes") as private:
            with self.assertRaises(grader._ADAPTER.InvalidDirectResponse):
                grader.score_response(*args)
            private.assert_not_called()

    def test_changed_case_binding_and_response_packet_refused(self):
        for change in ("case", "binding", "response"):
            args = list(fixture())
            if change == "case":
                args[0]["training"][0]["FRN_N2_offer"] += 1
            elif change == "binding":
                args[1]["query_source_rows"][0][1] = 999
            else:
                response = json.loads(args[2]); response["packet_sha256"] = "0" * 64
                args[2] = grader._ADAPTER.canonical(response)
            with self.subTest(change=change), self.assertRaises(grader._ADAPTER.InvalidDirectResponse):
                grader.score_response(*args)

    def test_complete_private_trajectory_and_reconstructed_mask_required(self):
        for change in ("truncate", "query_change"):
            args = list(fixture())
            if change == "truncate":
                args[3].pop()
            else:
                args[3][3]["rp"] = None
            with self.subTest(change=change), self.assertRaises(grader._ARITHMETIC.InvalidScoreInput):
                grader.score_response(*args)

    def test_reference_normalizer_and_arm_completeness_refused(self):
        for change in ("normalizer", "arm"):
            args = list(fixture()); entry = args[4]["results"]["P3b_offer"]
            if change == "normalizer":
                entry["normalizer"]["training_equal_person_variance"] *= 2
            else:
                entry["arms"].pop("V")
            with self.subTest(change=change), self.assertRaises(grader._ARITHMETIC.InvalidScoreInput):
                grader.score_response(*args)

    def test_source_pin_checked_before_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / grader._SOURCES["adapter"][0]
            path.parent.mkdir()
            path.write_text("raise RuntimeError('must not execute')\n")
            with mock.patch.object(grader, "_ROOT", root):
                with self.assertRaisesRegex(ValueError, "direct_loss_source_changed"):
                    grader._load("adapter")

    def test_input_objects_unchanged(self):
        args = fixture(); before = copy.deepcopy(args)
        grader.score_response(*args)
        self.assertEqual(args, before)


if __name__ == "__main__":
    unittest.main()
