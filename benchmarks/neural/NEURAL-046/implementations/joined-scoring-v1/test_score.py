"""Generated controls only. No source observations, fitted models, or private targets."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("joined_score", Path(__file__).with_name("score.py"))
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def fixture(opaque=False, cell_id=None):
    hidden, query = [], []
    for i, target in enumerate((1., 2., 4., 8.)):
        animal = "A" if i < 3 else "B"
        hidden.append({"id": "native-" + str(i), "animal": animal, "session": animal + "-day1",
            "condition": "test-condition", "endpoint": "cue", "domain": "appetitive",
            "target": target, "features": {"sex": "F", "hardware": "test"},
            "outcome_stratum": "delivered", "trial_ordinal": i + 1})
        query.append({k: hidden[-1][k] for k in ("id", "animal", "session", "condition")})
        if opaque:
            query[-1].update(id="opaque-" + str(i), animal="opaque-" + animal,
                             session="opaque-" + animal + "-day1")
    public = {"task": "NEURAL-046", "cell_id": cell_id or
        ("F_X_opaque_ID" if opaque else "F_X_full_permitted"), "endpoint": "cue",
        "query": query, "synthetic": True,
        "endpoint_support": {"schema": "endpoint_eligibility_summary_v1", "endpoint": "cue"}}
    predictions = {name: {q["id"]: h["target"] + offset for q, h in zip(query, hidden)}
                   for name, offset in (("ME", 1.), ("MN", 2.), ("MEN", 0.))}
    predictions["M0"] = {q["id"]: 0. for q in query}
    submission = {"schema": "sealed_neural_predictions_v1", "task": "NEURAL-046",
        "cell_id": public["cell_id"], "input_digest": scorer.digest(public),
        "predictions": predictions, "model_artifact_digests": {k: "0" * 64 for k in predictions}}
    sensitivity = {"MEN_independently_tuned": {q["id"]: h["target"] + residual
        for q, h, residual in zip(query, hidden, (0., 0., 3., 1.))}}
    binding = {q["id"]: {k: h[k] for k in scorer.IDENTITY} for q, h in zip(query, hidden)}
    return public, submission, sensitivity, binding, hidden


def seal(public, submission, sensitivity, binding):
    return {"all_required_producers_closed": True, "all_required_artifacts_sealed": True,
        "private_targets_opened_before_closure": False, "public_digest": scorer.digest(public),
        "submission_digest": scorer.digest(submission), "sensitivity_digest": scorer.digest(sensitivity),
        "binding_digest": scorer.digest(binding)}


class JoinTests(unittest.TestCase):
    def run_score(self, values, hidden=None, closure=None):
        p, s, z, b, h = values
        return scorer.score_joined(p, s, z, b, closure or seal(p, s, z, b),
                                   lambda: h if hidden is None else hidden)

    def assert_before_read(self, values, closure=None):
        p, s, z, b, _ = values
        def forbidden():
            self.fail("invalid public artifact opened private targets")
        with self.assertRaises(ValueError):
            scorer.score_joined(p, s, z, b, closure or seal(p, s, z, b), forbidden)

    def test_hand_computed_animal_macro_and_signed_contrasts(self):
        result = self.run_score(fixture())
        metrics = result["metrics"]
        self.assertEqual(metrics["models"]["M0"]["animal_macro_mse"], 35.5)
        self.assertEqual(metrics["contrasts"]["Delta"], 3.)
        self.assertEqual(metrics["contrasts"]["G_E"], 4.)
        self.assertEqual(metrics["contrasts"]["G_N"], 1.)
        sensitivity = result["mandatory_sensitivity"]["MEN_independently_tuned"]
        self.assertEqual(sensitivity, {"animals": {"A": 3., "B": 1.}, "animal_macro_mse": 2.})
        self.assertEqual(result["paired_join"]["query_cases"], 4)
        self.assertFalse(result["scientific_qualification"])

    def test_arbitrary_private_order_is_aligned_without_changing_scores(self):
        values = fixture()
        self.assertEqual(self.run_score(values), self.run_score(values, list(reversed(values[-1]))))

    def test_predecessor_counterexample_truncates_sensitivity(self):
        p, _, z, _, h = fixture()
        old = scorer.shared.score_sensitivities(z, p, h[:-1])
        self.assertEqual(set(old["MEN_independently_tuned"]["animals"]), {"A"})
        self.assertEqual(old["MEN_independently_tuned"]["animal_macro_mse"], 3.)
        with self.assertRaisesRegex(ValueError, "private_case_count"):
            self.run_score(fixture(), h[:-1])

    def test_predecessor_counterexample_reorders_opaque_targets(self):
        values = fixture(opaque=True)
        p, _, z, _, h = values
        old = scorer.shared.score_sensitivities(z, p, list(reversed(h)))
        self.assertNotEqual(old["MEN_independently_tuned"]["animal_macro_mse"], 2.)
        self.assertEqual(self.run_score(values), self.run_score(values, list(reversed(h))))

    def test_duplicate_unknown_private_case_and_endpoint_changes_fail(self):
        values = fixture()
        for mutation in ("duplicate", "unknown", "endpoint", "animal", "session", "domain"):
            with self.subTest(mutation=mutation):
                hidden = deepcopy(values[-1])
                if mutation == "duplicate": hidden[-1] = deepcopy(hidden[0])
                elif mutation == "unknown": hidden[-1]["id"] = "unexpected"
                else: hidden[-1][mutation] = "changed"
                with self.assertRaises(ValueError):
                    self.run_score(values, hidden)

    def test_invalid_sensitivity_is_rejected_before_private_read(self):
        for value in (True, None, float("inf"), float("nan")):
            values = fixture()
            closure = seal(*values[:4])
            values[2]["MEN_independently_tuned"]["native-0"] = value
            # Nonfinite changes cannot even be rehashed by the scoring API.
            if isinstance(value, float):
                self.assert_before_read(values, closure)
            else: self.assert_before_read(values)
        for mutation in ("missing", "unknown", "model"):
            values = fixture()
            if mutation == "missing": del values[2]["MEN_independently_tuned"]["native-0"]
            elif mutation == "unknown": values[2]["MEN_independently_tuned"]["unknown"] = 0.
            else: values[2]["extra_model"] = {}
            self.assert_before_read(values)

    def test_invalid_primary_fails_before_private_read(self):
        values = fixture()
        values[1]["predictions"]["ME"]["native-0"] = True
        self.assert_before_read(values)
        values = fixture()
        del values[1]["predictions"]["MN"]
        self.assert_before_read(values)

    def test_closure_changes_fail_before_private_read(self):
        for field in ("public_digest", "submission_digest", "sensitivity_digest", "binding_digest",
                      "all_required_producers_closed", "all_required_artifacts_sealed"):
            values = fixture()
            closure = seal(*values[:4]); closure[field] = False
            self.assert_before_read(values, closure)
        values = fixture(); closure = seal(*values[:4])
        closure["private_targets_opened_before_closure"] = True
        self.assert_before_read(values, closure)

    def test_binding_cannot_alias_animals_or_cases(self):
        for mutation in ("case", "animal", "session", "condition", "endpoint"):
            values = fixture(opaque=True)
            binding = values[3]
            if mutation == "case": binding["opaque-3"]["id"] = binding["opaque-0"]["id"]
            elif mutation == "animal": binding["opaque-3"]["animal"] = "A"
            elif mutation == "session": binding["opaque-3"]["session"] = "A-day1"
            else: binding["opaque-3"][mutation] = "changed"
            self.assert_before_read(values)

    def test_no_sensitivity_backfill_when_joint_model_unavailable(self):
        values = fixture(cell_id="F_X_neural_trained_nuisance_only")
        p, s, z, b, _ = values
        s["predictions"] = {"M0": s["predictions"]["M0"]}
        s["model_artifact_digests"] = {"M0": "0" * 64}
        self.assert_before_read(values)
        z.clear()
        result = self.run_score(values)
        self.assertEqual(result["mandatory_sensitivity"], {})
        self.assertEqual(result["metrics"]["contrasts"], {})

    def test_input_mutation_inside_callback_cannot_change_sealed_predictions(self):
        values = fixture()
        p, s, z, b, h = values
        def load():
            s["predictions"]["ME"]["native-0"] = 999.
            z["MEN_independently_tuned"]["native-0"] = 999.
            return h
        result = scorer.score_joined(p, s, z, b, seal(p, s, z, b), load)
        self.assertEqual(result["metrics"]["contrasts"]["Delta"], 3.)
        self.assertEqual(result["mandatory_sensitivity"]["MEN_independently_tuned"]["animal_macro_mse"], 2.)


if __name__ == "__main__":
    unittest.main(verbosity=2)
