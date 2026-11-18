"""Generated full-support controls; no empirical RSA or native models."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("selected_main_compare", HERE / "compare_main.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = Path(os.environ.get("BENCHMARK_REPOSITORY_ROOT", str(HERE.parents[4])))
LEGACY = ROOT / ("benchmarks/paper/PAPER-paper-method-replacement-016/implementations/"
                 "original-panel-comparison-v1/compare.py")
PROTOCOL = ROOT / ("benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/"
                   "authoring/delivery-20261105/common/remaining-builds-wave38/"
                   "hundred-models-complete-design/implementation-v1/successor-v2/"
                   "source-donors/metadata/PROTOCOL.json")


def fixtures():
    source = MODULE.load_legacy(LEGACY)
    axes = source.source_axes(PROTOCOL)
    support = {k: copy.deepcopy(axes[k]) for k in ("subjects", "stimuli", "repetitions")}
    support.update(brain_rdms_sha256="1" * 64, video_inputs_sha256="2" * 64)
    conditions = ["test:pca:" + model for model in axes["models"]]
    layers = ["generated_layer_a", "generated_layer_b"]
    reference = {"schema": MODULE.REFERENCE_SCHEMA, "test_support": support,
                 "run_sha256": "3" * 64, "origin": "published_author_outputs",
                 "noise_ceilings": [{"roi": roi, "lower": 0.4, "upper": 0.6} for roi in axes["rois"]],
                 "layer_catalog": {condition: layers[:] for condition in conditions},
                 "rsa": [{"condition": condition, "roi": roi, "layers": layers[:],
                          "values": [[-0.5] * 10, [0.2] * 10]}
                         for condition in conditions for roi in axes["rois"]]}
    candidate = {"schema": MODULE.CANDIDATE_SCHEMA, "test_support": copy.deepcopy(support),
                 "run_sha256": "4" * 64, "freeze_sha256": "5" * 64,
                 "layers": ["new_architecture_layer"],
                 "rsa": [{"roi": roi, "layers": ["new_architecture_layer"], "values": [[0.3] * 10]}
                         for roi in axes["rois"]]}
    reproduction = copy.deepcopy(reference)
    reproduction.pop("origin")
    reproduction.update(schema=MODULE.REPRODUCTION_SCHEMA, run_sha256="6" * 64)
    return source, axes, reference, candidate, reproduction


class SelectedMainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.axes, cls.reference, cls.candidate, cls.reproduction = fixtures()

    def candidate_result(self, reference=None, candidate=None):
        return MODULE.compare_candidate(PROTOCOL, self.reference if reference is None else reference,
                                        self.candidate if candidate is None else candidate, legacy_path=LEGACY)

    def reproduction_result(self, reproduction=None):
        return MODULE.compare_reproduction(PROTOCOL, self.reference,
                                           self.reproduction if reproduction is None else reproduction,
                                           legacy_path=LEGACY)

    def test_complete_main_is_independent_of_separate_companions(self):
        result = self.candidate_result()
        self.assertEqual(result["counts"]["reference_rows"], 1683)
        self.assertEqual(len(result["reference_conditions"]), 1683)
        self.assertEqual(len(result["per_reference_comparisons"]), 1683)
        self.assertEqual(len(result["roi_profile"]), 17)
        self.assertEqual(result["noise_ceilings"], self.reference["noise_ceilings"])
        self.assertNotIn("train_support", result)
        self.assertEqual(result["reference_origin"], "published_author_outputs")
        self.assertIsNone(result["inference"]["paper_win"])
        self.assertIsNone(result["inference"]["across_roi_decision"])
        self.assertFalse(result["qualification"]["scientific_improvement"])

    def test_main_outputs_match_broader_predecessor_without_modifying_it(self):
        reference = copy.deepcopy(self.reference)
        reference["schema"] = "hundred_models_original_reference_v1"
        reference["noise_ceilings"] = {"test": self.reference["noise_ceilings"],
                                        "train": self.reference["noise_ceilings"]}
        reference["train_support"] = {"subjects": self.axes["subjects"], "repetitions": 3,
                                        "stimuli": ["generated_training_" + str(i) for i in range(1000)],
                                        "brain_rdms_sha256": "7" * 64, "video_inputs_sha256": "8" * 64}
        for condition, role in self.axes["conditions"]:
            if role == "main":
                continue
            reference["layer_catalog"][condition] = ["generated_layer_a", "generated_layer_b"]
            for roi in self.axes["rois"]:
                reference["rsa"].append({"condition": condition, "roi": roi,
                                          "layers": ["generated_layer_a", "generated_layer_b"],
                                          "values": [[-0.5] * 10, [0.2] * 10]})
        broader = self.source.compare(PROTOCOL, reference, self.candidate)
        selected = self.candidate_result()
        self.assertEqual(selected["roi_profile"], broader["roi_profile"])
        self.assertEqual(selected["per_reference_comparisons"], broader["per_reference_comparisons"])
        main = [{k: v for k, v in row.items() if k != "role"}
                for row in broader["reference_conditions"] if row["role"] == "main"]
        self.assertEqual(selected["reference_conditions"], main)

    def test_no_weaker_reference_or_defined_subset_substitution(self):
        reference = copy.deepcopy(self.reference)
        reference["rsa"][17]["values"][1] = [0.8] * 10
        result = self.candidate_result(reference)
        self.assertEqual(result["roi_profile"][0]["strongest_reference_model"], self.axes["models"][1])
        self.assertAlmostEqual(result["roi_profile"][0]["delta_to_strongest"], -0.5)
        reference["rsa"][0]["values"][0][0] = None
        result = self.candidate_result(reference)
        self.assertIsNone(result["roi_profile"][0]["strongest_reference_model"])
        self.assertIsNone(result["roi_profile"][0]["delta_to_strongest"])
        self.assertEqual(result["reference_conditions"][0]["subject_values"][0][0], None)
        self.assertEqual(len(result["per_reference_comparisons"]), 1683)

    def test_incomplete_extra_and_reordered_reference_support_refused(self):
        changes = [lambda r: r["rsa"].pop(),
                   lambda r: r["rsa"].reverse(),
                   lambda r: r["layer_catalog"].update({"train:pca:invented": ["a"]}),
                   lambda r: r["noise_ceilings"].pop(),
                   lambda r: r.update(train_support={})]
        for change in changes:
            reference = copy.deepcopy(self.reference)
            change(reference)
            with self.assertRaises(ValueError):
                self.candidate_result(reference)

    def test_candidate_identity_and_layer_subsetting_refused(self):
        changes = [lambda c: c["test_support"]["subjects"].reverse(),
                   lambda c: c["test_support"].update(brain_rdms_sha256="9" * 64),
                   lambda c: c["rsa"][0].update(layers=["roi_specific_layer"]),
                   lambda c: c["rsa"][0]["values"][0].__setitem__(0, True)]
        for change in changes:
            candidate = copy.deepcopy(self.candidate)
            change(candidate)
            with self.assertRaises(ValueError):
                self.candidate_result(candidate=candidate)

    def test_complete_reproduction_differences_and_ceiling_companions(self):
        reproduction = copy.deepcopy(self.reproduction)
        reproduction["rsa"][17]["values"][1][3] = 0.4
        reproduction["noise_ceilings"][0]["upper"] = 0.7
        result = self.reproduction_result(reproduction)
        self.assertEqual(len(result["per_source_row_comparisons"]), 1683)
        row = result["per_source_row_comparisons"][17]
        self.assertAlmostEqual(row["participant_deltas"][1][3], 0.2)
        self.assertAlmostEqual(row["profile_delta"], 0.02)
        self.assertAlmostEqual(result["noise_ceilings"]["deltas"][0]["upper"], 0.1)
        self.assertEqual(result["noise_ceilings"]["reference"], self.reference["noise_ceilings"])
        self.assertIsNone(result["inference"]["reproduction_pass"])
        self.assertIsNone(result["inference"]["equivalence_tolerance"])
        self.assertFalse(result["qualification"]["scientific_reproduction"])

    def test_reproduction_undefined_values_remain_explicit_and_catalogs_match(self):
        reproduction = copy.deepcopy(self.reproduction)
        reproduction["rsa"][0]["values"][0][0] = None
        reproduction["noise_ceilings"][0]["lower"] = None
        result = self.reproduction_result(reproduction)
        self.assertIsNone(result["per_source_row_comparisons"][0]["participant_deltas"][0][0])
        self.assertIsNone(result["per_source_row_comparisons"][0]["profile_delta"])
        self.assertIsNone(result["noise_ceilings"]["deltas"][0]["lower"])
        condition = reproduction["rsa"][0]["condition"]
        reproduction["layer_catalog"][condition] = ["different_a", "different_b"]
        for row in reproduction["rsa"]:
            if row["condition"] == condition:
                row["layers"] = ["different_a", "different_b"]
        with self.assertRaises(ValueError):
            self.reproduction_result(reproduction)

    def test_input_immutability_and_source_identity_refusal(self):
        before = [self.source.digest(value) for value in (self.reference, self.candidate, self.reproduction)]
        self.candidate_result()
        self.reproduction_result()
        self.assertEqual(before, [self.source.digest(value)
                                  for value in (self.reference, self.candidate, self.reproduction)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "untrusted.py"
            path.write_text("raise AssertionError('must never execute')\n")
            with self.assertRaises(ValueError):
                MODULE.load_legacy(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
