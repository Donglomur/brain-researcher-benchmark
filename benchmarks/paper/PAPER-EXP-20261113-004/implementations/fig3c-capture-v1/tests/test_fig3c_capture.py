import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fig3c_capture", ROOT / "fig3c_capture.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture(profiles):
    """Full declared cohort, tiny in-memory vectors; never serialize this fixture."""
    lengths = [2] + [1] * 9
    model_values = {}
    support_models = {}
    for model in profiles.MODELS:
        after = model == "train0_test1"
        actual = [[0.0 if after else -1.0] * n for n in lengths]
        opposite = [[math.atan2(math.sin(x + math.pi), math.cos(x + math.pi))
                     for x in fold] for fold in actual]
        real = copy.deepcopy(actual if after else opposite)
        predicted = {str(r): copy.deepcopy(actual if r % 2 == 0 else opposite) for r in range(100)}
        targets = {str(r): copy.deepcopy(actual) for r in range(100)}
        model_values[model] = {"pred": real, "actual": actual,
                               "pred_shuffle": predicted, "actual_shuffle": targets}
        side = "after" if after else "before"
        support_models[model] = [[f"{side}-fold{f}-sample{i}" for i in range(n)]
                                 for f, n in enumerate(lengths)]
    capture = {"schema": m.CAPTURE_SCHEMA, "source_commit": m.COMMIT}
    for field in m.FIELDS:
        capture[field] = {
            str(day): {animal: {cell: {model: model_values[model][field]
                                      for model in profiles.MODELS}
                               for cell in profiles.CELL_TYPES}
                       for animal in profiles.ANIMALS}
            for day in profiles.DAYS}
    support = {"schema": m.SUPPORT_SCHEMA, "source_commit": m.COMMIT,
               "preparation_sha256": "a" * 64, "fold_receipt_sha256": "b" * 64,
               "sample_ids": {str(day): {animal: copy.deepcopy(support_models)
                                        for animal in profiles.ANIMALS}
                              for day in profiles.DAYS}}
    return capture, support


def first(capture, field, model="train0_test1"):
    return capture[field]["3"]["GCAMP3"]["rr"][model]


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = m.CaptureAdapter()

    def setUp(self):
        self.capture, self.support = fixture(self.adapter.profiles)

    def test_full_composition_maps_directions_repeats_missingness_and_original_ids(self):
        # Distinct signs in the two directions reveal swapped model mappings.
        # Preserve one missing observation in all corresponding real/shuffle targets.
        first(self.capture, "actual")[0][0] = None
        first(self.capture, "pred")[0][0] = None
        for repeat in range(100):
            first(self.capture, "actual_shuffle")[str(repeat)][0][0] = None
            first(self.capture, "pred_shuffle")[str(repeat)][0][0] = None
        result = self.adapter.score(self.capture, self.support)
        self.assertEqual(len(result["rows"]), 462)
        self.assertEqual(len(result["cohort_profiles"]), 42)
        self.assertEqual(len(result["figure3c_source_export"]), 66)
        for row in result["rows"]:
            after = row["model"] == "train0_test1"
            index = 22 if after else 14
            self.assertAlmostEqual(row["zscore"][index]["value"], 1.0 if after else -1.0)
            self.assertEqual(row["shuffle_repeat_valid_fold_counts"][0][index], 10)
            self.assertEqual(row["real_fold_missing_actual"][0], 1 if after else 0)
        panel = self.adapter._panel(self.capture, self.support)
        row = panel["rows"][0]
        self.assertEqual(row["folds"][0]["sample_ids"], ["after-fold0-sample0", "after-fold0-sample1"])
        self.assertIsNone(row["shuffles"][99][0]["actual"][0])
        self.assertEqual(result["capture_binding"]["accepted_profile_module_sha256"], m.PROFILE_SHA256)
        self.assertFalse(result["capture_binding"]["native_serialization_loaded"])
        self.assertFalse(result["capture_binding"]["observation_custody_authenticated"])
        self.assertIsNone(result["paper_win"])

    def test_no_missing_day_or_animal_can_shrink_the_capture(self):
        for field, level in (("pred", "day"), ("actual_shuffle", "animal")):
            with self.subTest(field=field):
                capture = copy.deepcopy(self.capture)
                if level == "day":
                    del capture[field]["14"]
                else:
                    del capture[field]["14"]["GCAMP19"]
                with self.assertRaisesRegex(m.CaptureError, "exact keys"):
                    self.adapter.score(capture, self.support)

    def test_wrong_population_and_same_set_model_cannot_replace_cross_switch(self):
        del self.capture["pred"]["3"]["GCAMP3"]["track"]
        with self.assertRaisesRegex(m.CaptureError, "populations"):
            self.adapter.score(self.capture, self.support)
        self.capture, self.support = fixture(self.adapter.profiles)
        models = self.capture["actual"]["3"]["GCAMP3"]["rr"]
        models["train0_test0"] = models.pop("train0_test1")
        with self.assertRaisesRegex(m.CaptureError, "cross-switch"):
            self.adapter.score(self.capture, self.support)

    def test_repeat_indices_are_complete_and_cannot_be_list_or_padded_aliases(self):
        for change in ("missing", "list", "padded"):
            with self.subTest(change=change):
                capture = copy.deepcopy(self.capture)
                branch = capture["pred_shuffle"]["3"]["GCAMP3"]["rr"]
                repeats = branch["train0_test1"]
                if change == "missing":
                    del repeats["99"]
                elif change == "padded":
                    repeats["00"] = repeats.pop("0")
                else:
                    branch["train0_test1"] = list(repeats.values())
                with self.assertRaisesRegex(m.CaptureError, "shuffle prediction repeats"):
                    self.adapter.score(capture, self.support)

    def test_missing_actual_shuffle_is_not_filled_from_real_targets(self):
        del self.capture["actual_shuffle"]
        with self.assertRaisesRegex(m.CaptureError, "capture"):
            self.adapter.score(self.capture, self.support)

    def test_aggregate_scores_cannot_replace_per_sample_predictions(self):
        self.capture["scores_shuffle"] = self.capture.pop("pred_shuffle")
        with self.assertRaisesRegex(m.CaptureError, "capture"):
            self.adapter.score(self.capture, self.support)

    def test_wrong_fold_axis_and_vector_lengths_reject(self):
        first(self.capture, "pred_shuffle")["0"] = [[0.0] for _ in range(100)]
        with self.assertRaisesRegex(m.CaptureError, "ten ordered fold"):
            self.adapter.score(self.capture, self.support)
        self.capture, self.support = fixture(self.adapter.profiles)
        first(self.capture, "pred")[0].pop()
        with self.assertRaisesRegex(m.CaptureError, "lengths differ"):
            self.adapter.score(self.capture, self.support)

    def test_real_shuffle_target_mismatch_rejects(self):
        first(self.capture, "actual_shuffle")["0"][0][0] = 0.2
        with self.assertRaisesRegex(m.CaptureError, "shuffle changed"):
            self.adapter.score(self.capture, self.support)

    def test_population_support_target_mismatch_rejects(self):
        branch = self.capture["actual"]["3"]["GCAMP3"]["track"]
        branch["train0_test1"] = copy.deepcopy(branch["train0_test1"])
        branch["train0_test1"][0][0] = 0.2
        # Keep the shuffle targets internally matched; across-class comparison must reject.
        repeats = {str(r): copy.deepcopy(branch["train0_test1"]) for r in range(100)}
        self.capture["actual_shuffle"]["3"]["GCAMP3"]["track"]["train0_test1"] = repeats
        with self.assertRaisesRegex(m.CaptureError, "across cell populations"):
            self.adapter.score(self.capture, self.support)

    def test_ids_are_not_synthesized_and_duplicate_fold_support_rejects(self):
        del self.support["sample_ids"]["3"]["GCAMP3"]["train1_test0"]
        with self.assertRaisesRegex(m.CaptureError, "support models"):
            self.adapter.score(self.capture, self.support)
        self.capture, self.support = fixture(self.adapter.profiles)
        ids = self.support["sample_ids"]["3"]["GCAMP3"]["train0_test1"]
        ids[1] = ids[0]
        with self.assertRaisesRegex(m.CaptureError, "duplicate sample"):
            self.adapter.score(self.capture, self.support)

    def test_wrong_projection_and_source_revision_reject(self):
        self.capture["schema"] = "dill-native"
        with self.assertRaisesRegex(m.CaptureError, "projection/source"):
            self.adapter.score(self.capture, self.support)
        self.capture["schema"] = m.CAPTURE_SCHEMA
        self.support["source_commit"] = "0" * 40
        with self.assertRaisesRegex(m.CaptureError, "support projection/source"):
            self.adapter.score(self.capture, self.support)

    def test_source_null_survives_but_boolean_and_infinity_do_not(self):
        for bad in (True, math.inf, -math.inf):
            with self.subTest(bad=bad):
                first(self.capture, "pred")[0][0] = bad
                with self.assertRaises(m.CaptureError):
                    self.adapter.score(self.capture, self.support)

    def test_small_file_hash_cap_and_strict_json_boundaries(self):
        # All disk fixtures combined are under256 bytes; full cohort stays in memory.
        bodies = (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'not JSON')
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "capture.json"
            for body in bodies:
                path.write_bytes(body)
                with self.assertRaises(m.CaptureError):
                    m.read_bound_json(path, hashlib.sha256(body).hexdigest(), 128)
            body = b'{"x":1}'
            path.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            self.assertEqual(m.read_bound_json(path, digest, len(body)), {"x": 1})
            self.assertEqual(m.read_bound_json(path, digest, 2**63 - 1), {"x": 1})
            with self.assertRaisesRegex(m.CaptureError, "digest"):
                m.read_bound_json(path, "0" * 64, 128)
            with self.assertRaisesRegex(m.CaptureError, "bounded"):
                m.read_bound_json(path, digest, len(body) - 1)

    def test_missing_or_changed_scorer_dependency_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "fig3c_profiles.py"
            with self.assertRaises(OSError):
                m.CaptureAdapter(path)
            path.write_bytes(b'raise RuntimeError("must not execute")\n')
            with self.assertRaisesRegex(m.CaptureError, "dependency pin"):
                m.CaptureAdapter(path)


if __name__ == "__main__":
    unittest.main()
