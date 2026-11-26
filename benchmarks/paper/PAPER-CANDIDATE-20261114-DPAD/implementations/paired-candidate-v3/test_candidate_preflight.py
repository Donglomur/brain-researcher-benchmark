"""Generated DPAD candidate input checks; no targets or author fit is required."""
import copy
from io import StringIO
import json
import unittest
from unittest.mock import patch

import paired as p
from test_stable_pearson import full_fixture


class CandidatePreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The established generated fixture supplies valid plan/configuration
        # identities; protected arrays and author predictions are discarded.
        _, _, _, cls.plan, cls.predictions = full_fixture()

    def check(self, plan=None, predictions=None, digest=None):
        plan = self.plan if plan is None else plan
        return p.preflight(plan, self.predictions if predictions is None else predictions,
                           p.e.digest(plan) if digest is None else digest)

    def test_complete_candidate_preflight_never_calls_scoring(self):
        with patch.object(p.e, "channel_cc", side_effect=AssertionError("scoring not permitted")):
            result = self.check()
        self.assertEqual(result["status"], "structurally_valid_candidate_submission")
        self.assertEqual((result["session_count"], result["session_fold_count"],
                          result["dimension_count"], result["prediction_case_count"]), (7, 35, 8, 280))
        self.assertEqual(result["predictions_sha256"], p.e.digest(self.predictions))
        self.assertFalse(result["protected_targets_read"])
        self.assertEqual(result["scientific_improvement"], "not_assessed")
        self.assertNotIn("score", result)

    def test_constant_predictions_are_structural_not_correlation_acceptance(self):
        predictions = copy.deepcopy(self.predictions)
        for row in predictions["cases"]:
            for role in ("neural", "behavior"):
                row[role] = [[0.0] * len(row[role][0]) for _ in row[role]]
        self.assertEqual(self.check(predictions=predictions)["status"],
                         "structurally_valid_candidate_submission")

    def test_rejects_incomplete_duplicate_or_unknown_grid(self):
        mutations = [lambda x: x["cases"].pop(),
                     lambda x: x["cases"].append(copy.deepcopy(x["cases"][0])),
                     lambda x: x["cases"][0].update(dimension=3),
                     lambda x: x["cases"][0].update(fold=True),
                     lambda x: x["cases"][0].update(session_id="different-session")]
        for mutate in mutations:
            predictions = copy.deepcopy(self.predictions)
            mutate(predictions)
            with self.subTest(mutation=mutate), self.assertRaises(p.e.ContractError):
                self.check(predictions=predictions)

    def test_rejects_candidate_and_configuration_identity_changes(self):
        for field, value in (("selection_plan_sha256", "0" * 64),
                             ("candidate_id", "different-candidate"), ("code_sha256", "b" * 64)):
            predictions = copy.deepcopy(self.predictions)
            predictions[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(p.e.ContractError, "binding"):
                self.check(predictions=predictions)
        predictions = copy.deepcopy(self.predictions)
        predictions["cases"][0]["configuration_sha256"] = "f" * 64
        with self.assertRaisesRegex(p.e.ContractError, "configuration changed"):
            self.check(predictions=predictions)
        with self.assertRaisesRegex(p.e.ContractError, "selection plan changed"):
            self.check(digest="0" * 64)

    def test_rejects_row_channel_shape_and_finite_value_changes(self):
        mutations = [lambda r: r["sample_ids"].reverse(),
                     lambda r: r["neural_channel_ids"].reverse(),
                     lambda r: r["behavior_channel_ids"].reverse(),
                     lambda r: r["neural"].pop(),
                     lambda r: r["behavior"][0].pop(),
                     lambda r: r["neural"][0].__setitem__(0, float("inf")),
                     lambda r: r["neural"][0].__setitem__(0, True)]
        for mutate in mutations:
            predictions = copy.deepcopy(self.predictions)
            mutate(predictions["cases"][0])
            with self.subTest(mutation=mutate), self.assertRaises(p.e.ContractError):
                self.check(predictions=predictions)

    def test_rejects_rehashed_invalid_plan(self):
        mutations = [lambda x: x.update(schema="dpad-candidate-plan-v2"),
                     lambda x: x.update(numerical_policy="unknown"),
                     lambda x: x["cases"].pop(),
                     lambda x: x["cases"].append(copy.deepcopy(x["cases"][0])),
                     lambda x: x["cases"][0].update(selected_dimension=8),
                     lambda x: x["cases"][0]["dimensions"].pop("128"),
                     lambda x: x["cases"][0]["dimensions"]["1"].update(configuration_sha256="bad")]
        for mutate in mutations:
            plan, predictions = copy.deepcopy(self.plan), copy.deepcopy(self.predictions)
            mutate(plan)
            digest = p.e.digest(plan)
            predictions["selection_plan_sha256"] = digest
            with self.subTest(mutation=mutate), self.assertRaises(p.e.ContractError):
                self.check(plan, predictions, digest)

    def test_compare_retains_independent_target_protocol_type_validation(self):
        training, targets, author, plan, predictions = full_fixture()
        reference = p.freeze_reference(training, targets, author)
        targets = copy.deepcopy(targets)
        targets["protocol"]["neural_lag_samples"] = True
        # A matching owner hash does not make a malformed protocol valid.
        reference["targets_sha256"] = p.e.digest(targets)
        reference["source_grid_results"]["targets_sha256"] = reference["targets_sha256"]
        with self.assertRaisesRegex(p.e.ContractError, "one-step-ahead"):
            p.compare(targets, reference, plan, predictions, p.e.digest(reference), p.e.digest(plan))

    def test_cli_reads_only_plan_and_predictions(self):
        inputs = {"candidate-plan.json": self.plan, "candidate-predictions.json": self.predictions}
        written = []
        argv = ["paired.py", "preflight", "--plan", "candidate-plan.json", "--predictions",
                "candidate-predictions.json", "--plan-sha256", p.e.digest(self.plan), "--output", "check.json"]
        with patch("sys.argv", argv), patch.object(p.e, "read_json", side_effect=inputs.__getitem__) as read, \
                patch.object(p, "_new_output_path", return_value=p.Path("check.json")), \
                patch.object(p, "_publish_output", side_effect=lambda path, value: written.append(value)), \
                patch("sys.stdout", new_callable=StringIO) as output:
            p.main()
        self.assertEqual([call.args[0] for call in read.call_args_list], list(inputs))
        self.assertEqual(len(written), 1)
        result = json.loads(written[0])
        self.assertEqual(result["prediction_case_count"], 280)
        self.assertEqual(json.loads(output.getvalue())["canonical_sha256"], p.e.digest(result))


if __name__ == "__main__":
    unittest.main()
