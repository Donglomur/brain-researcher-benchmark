"""Generated interface and adversarial correspondence checks; no paper data."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("paired", HERE / "paired.py")
paired = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paired)
GENERATED_WRITTEN_BYTES = 0


def record_write(path, text):
    global GENERATED_WRITTEN_BYTES
    raw = text.encode("utf-8")
    path.write_bytes(raw)
    GENERATED_WRITTEN_BYTES += len(raw)


def fixture():
    units = []
    for epoch in ("sample", "delay", "reward"):
        rows = []
        for index in range(2):
            rows.append({"trial_id": "generated-trial-" + str(index), "frame_id": "generated-frame",
                         "fold_id": index + 1, "trial_type": index + 1, "activity": 0.5 + index,
                         "npvc": {"log_joint_grid": [0.0] * 200,
                                  "log_joint_observed": -1.0, "log_marginal_observed": -3.0},
                         "glm": {"mean": 0.8 + index * 0.3, "null_mean": 1.0}})
        units.append({"identity": {"animal_id": "generated-animal", "session_id": "generated-session",
                                   "neuron_id": "generated-neuron", "projection": "generated-projection", "epoch": epoch},
                      "activity_bounds": [0.0, 2.0], "observations": rows})
    author = {"schema": "npvc-fde-operands-v1", "units": units}
    support = {"schema": "npvc-declared-support-v1", "units": [
        {**copy.deepcopy(unit), "observations": [{k: row[k] for k in paired.ROW_FIELDS} for row in unit["observations"]]}
        for unit in units]}
    return support, author, copy.deepcopy(author)


class PairingTests(unittest.TestCase):
    def reject(self, support, author, candidate, text=None):
        with self.assertRaisesRegex(ValueError, text or "."):
            paired.compare(support, author, candidate)

    def test_reorders_without_changing_correspondence_or_full_vector(self):
        support, author, candidate = fixture()
        candidate["units"].reverse()
        for unit in candidate["units"]:
            unit["observations"].reverse()
        result = paired.compare(support, author, candidate)
        self.assertEqual([u["identity"]["epoch"] for u in result["units"]], ["sample", "delay", "reward"])
        self.assertEqual(result["recomputed_author"], result["recomputed_candidate"])
        self.assertTrue(all(u["models"][m]["candidate_minus_author_fde"] == 0 for u in result["units"] for m in ("npvc", "glm")))
        # A perfect match to a deliberately partial generated declaration does
        # not certify the original five-epoch, animal/session population.
        self.assertIsNone(result["complete_source_cohort"])
        self.assertIsNone(result["paper_win"])
        self.assertFalse(result["source_membership_authenticated"])

    def test_rejects_candidate_unit_dropout(self):
        support, author, candidate = fixture()
        candidate["units"].pop()
        self.reject(support, author, candidate, "missing or extra neuron/epoch")

    def test_rejects_reference_dropout_too(self):
        support, author, candidate = fixture()
        author["units"].pop()
        self.reject(support, author, candidate, "author has missing")

    def test_rejects_missing_observation(self):
        support, author, candidate = fixture()
        candidate["units"][0]["observations"].pop()
        self.reject(support, author, candidate, "missing or extra trial/frame")

    def test_rejects_same_count_but_different_observation(self):
        support, author, candidate = fixture()
        candidate["units"][0]["observations"][0]["frame_id"] = "substitute"
        self.reject(support, author, candidate, "missing or extra trial/frame")

    def test_rejects_target_or_fold_or_condition_change(self):
        for field, changed in (("activity", 0.6), ("fold_id", 5), ("trial_type", 8)):
            with self.subTest(field=field):
                support, author, candidate = fixture()
                candidate["units"][0]["observations"][0][field] = changed
                self.reject(support, author, candidate, "changes held-out")

    def test_rejects_activity_coordinate_change(self):
        support, author, candidate = fixture()
        for unit in candidate["units"]:
            unit["activity_bounds"] = [0.0, 3.0]
        self.reject(support, author, candidate, "changes activity coordinates")

    def test_rejects_duplicate_support_unit_or_observation(self):
        support, author, candidate = fixture()
        support["units"].append(copy.deepcopy(support["units"][0]))
        self.reject(support, author, candidate, "duplicate unit")
        support, author, candidate = fixture()
        support["units"][0]["observations"].append(copy.deepcopy(support["units"][0]["observations"][0]))
        self.reject(support, author, candidate, "duplicate trial/frame")

    def test_undefined_denominators_are_retained_without_differences(self):
        support, author, candidate = fixture()
        fde = paired.equations()
        saturated = fde.npvc_point([0.0, 2.0], [0.0] * 200, 0.0, 0.0)["saturated"]
        for bundle in (author, candidate):
            for unit in bundle["units"]:
                for row in unit["observations"]:
                    row["npvc"]["log_marginal_observed"] = saturated
                    row["glm"]["null_mean"] = row["activity"]
        result = paired.compare(support, author, candidate)
        self.assertEqual(len(result["units"]), 3)
        for unit in result["units"]:
            for model in unit["models"].values():
                self.assertEqual(model["author"]["denominator_state"], "zero")
                self.assertIsNone(model["candidate_minus_author_fde"])
                self.assertEqual(model["difference_state"], "undefined_operand")

    def test_negative_and_above_one_values_are_not_clamped_or_called_wins(self):
        support, author, candidate = fixture()
        for unit in author["units"]:
            for row in unit["observations"]:
                row["npvc"]["log_joint_observed"] = -10.0
        for unit in candidate["units"]:
            for row in unit["observations"]:
                row["npvc"]["log_joint_observed"] = 2.0
        result = paired.compare(support, author, candidate)
        self.assertLess(result["units"][0]["models"]["npvc"]["author"]["fde"], 0)
        self.assertGreater(result["units"][0]["models"]["npvc"]["candidate"]["fde"], 1)
        self.assertIsNone(result["paper_win"])
        self.assertEqual(result["density_admissibility"], "unresolved")

    def test_model_specific_null_change_is_exposed_not_silently_shared(self):
        support, author, candidate = fixture()
        candidate["units"][0]["observations"][0]["npvc"]["log_marginal_observed"] = -4.0
        result = paired.compare(support, author, candidate)
        self.assertTrue(result["units"][0]["models"]["npvc"]["null_log_likelihood_total_differs"])
        self.assertFalse(result["units"][0]["models"]["glm"]["null_log_likelihood_total_differs"])
        self.assertEqual(result["scientific_outcome"], "unknown")

    def test_invalid_numeric_and_extra_fields_rejected(self):
        for field, value in (("fold_id", True), ("activity", float("nan"))):
            with self.subTest(field=field):
                support, author, candidate = fixture()
                candidate["units"][0]["observations"][0][field] = value
                self.reject(support, author, candidate)
        support, author, candidate = fixture()
        candidate["units"][0]["observations"][0]["computed_fde"] = 1.0
        self.reject(support, author, candidate, "incorrect fields")

    def test_file_interface_binds_three_inputs_and_refuses_output_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for name, doc in zip(("support", "author", "candidate"), fixture()):
                path = root / (name + ".json")
                record_write(path, json.dumps(doc))
                paths.append(path)
            out = root / "out.json"
            paired.run(*paths, out)
            global GENERATED_WRITTEN_BYTES
            GENERATED_WRITTEN_BYTES += out.stat().st_size
            report = json.loads(out.read_text())
            self.assertEqual(set(report["input_pins"]), {"support", "author", "candidate"})
            self.assertEqual(report["input_pins"]["candidate"]["bytes"], paths[2].stat().st_size)
            with self.assertRaisesRegex(ValueError, "fresh output"):
                paired.run(*paths, out)
            self.assertFalse(report["readiness_promoted"])

    def test_duplicate_json_fields_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            record_write(path, '{"schema":"x","schema":"npvc-declared-support-v1","units":[]}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON"):
                paired.read_json(path)

    def test_changed_equation_binding_refuses(self):
        original = paired.EQUATIONS_SHA256
        try:
            paired.EQUATIONS_SHA256 = "0" * 64
            with self.assertRaisesRegex(ValueError, "dependency changed"):
                paired.compare(*fixture())
        finally:
            paired.EQUATIONS_SHA256 = original

    def test_equation_loader_does_not_reopen_after_hash_check(self):
        with patch("importlib.machinery.SourceFileLoader.exec_module", side_effect=AssertionError("unbound reopen")):
            bound = paired.equations()
            self.assertEqual(bound.GRID_SIZE, 200)
            self.assertEqual(bound.poisson_log_likelihood(0, 0), 0.0)

    def test_distinct_large_integer_targets_do_not_collapse(self):
        support, author, candidate = fixture()
        for bundle in (support, author, candidate):
            for unit in bundle["units"]:
                unit["activity_bounds"] = [0, 2**53 + 4]
            bundle["units"][0]["observations"][0]["activity"] = 2**53 + 1
        candidate["units"][0]["observations"][0]["activity"] = 2**53
        self.assertEqual(float(2**53 + 1), float(2**53))
        self.reject(support, author, candidate, "changes held-out")
        support, author, candidate = fixture()
        for bundle in (support, author, candidate):
            for unit in bundle["units"]:
                unit["activity_bounds"] = [0, 2**53]
        candidate["units"][0]["observations"][0]["activity"] = 2**53 + 1
        self.reject(support, author, candidate, "activity outside source bounds")

    def test_distinct_large_integer_bounds_do_not_collapse(self):
        support, author, candidate = fixture()
        for bundle in (support, author):
            for unit in bundle["units"]:
                unit["activity_bounds"] = [0, 2**53 + 1]
        for unit in candidate["units"]:
            unit["activity_bounds"] = [0, 2**53]
        self.reject(support, author, candidate, "changes activity coordinates")


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        print("generated_written_bytes=" + str(GENERATED_WRITTEN_BYTES))
