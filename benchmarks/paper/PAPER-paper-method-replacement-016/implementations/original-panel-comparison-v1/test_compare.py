"""Generated software controls only. No authentic RSA values or model calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("original_panel_comparison", HERE / "compare.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ROOT = HERE.parents[4]
PROTOCOL = ROOT / ("benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/"
                   "authoring/delivery-20261105/common/remaining-builds-wave38/"
                   "hundred-models-complete-design/implementation-v1/successor-v2/"
                   "source-donors/metadata/PROTOCOL.json")


def fixtures():
    axes = MODULE.source_axes(PROTOCOL)
    support = {k: axes[k] for k in ("subjects", "stimuli", "repetitions")}
    support.update(brain_rdms_sha256="1" * 64, video_inputs_sha256="2" * 64)
    layers = ["generated_layer_a", "generated_layer_b"]
    conditions = [key for key, _ in axes["conditions"]]
    source = {"schema": "hundred_models_original_reference_v1",
              "test_support": support, "run_sha256": "3" * 64,
              "origin": "reproduced_author_outputs",
              "train_support": {"subjects": axes["subjects"], "repetitions": 3,
                                "stimuli": ["generated_training_" + str(i) for i in range(1000)],
                                "brain_rdms_sha256": "4" * 64, "video_inputs_sha256": "5" * 64},
              "noise_ceilings": {panel: [{"roi": roi, "lower": 0.4, "upper": 0.6}
                                          for roi in axes["rois"]] for panel in ("test", "train")},
              "layer_catalog": {key: layers for key in conditions},
              "rsa": [{"condition": key, "roi": roi, "layers": layers,
                       "values": [[-0.5] * 10, [0.2] * 10]}
                      for key in conditions for roi in axes["rois"]]}
    candidate = {"schema": "hundred_models_original_candidate_v1", "test_support": support,
                 "run_sha256": "6" * 64, "freeze_sha256": "7" * 64,
                 "layers": ["different_candidate_architecture_layer"],
                 "rsa": [{"roi": roi, "layers": ["different_candidate_architecture_layer"],
                          "values": [[0.3] * 10]} for roi in axes["rois"]]}
    return axes, source, candidate


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.axes, cls.reference, cls.candidate = fixtures()

    def test_max_after_mean_counterexample(self):
        # Participant-specific max would report .9; correct max(mean) is .4.
        values = [[0.9] * 5 + [-0.9] * 5, [0.4] * 10]
        result = MODULE.select(["variable", "stable"], values)
        self.assertEqual(result["selected_layer"], "stable")
        self.assertAlmostEqual(result["score"], 0.4)

    def test_signed_scores_and_first_tie(self):
        result = MODULE.select(["negative", "first", "tied"],
                               [[-0.9] * 10, [0.2] * 10, [0.2] * 10])
        self.assertEqual(result["selected_layer"], "first")

    def test_undefined_is_not_dropped(self):
        result = MODULE.select(["complete", "undefined"], [[0.4] * 10, [None] + [0.8] * 9])
        self.assertIsNone(result["score"])
        self.assertEqual(result["subject_values"][1][0], None)

    def test_numeric_domains(self):
        for bad in (True, float("nan"), float("inf"), 1.01, "0.2"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MODULE.select(["a"], [[bad] + [0.2] * 9])
        with self.assertRaises(ValueError):
            MODULE.select(["a"], [[0.2] * 9])

    def test_complete_original_and_companion_profiles(self):
        result = MODULE.compare(PROTOCOL, self.reference, self.candidate)
        self.assertEqual(len(result["reference_conditions"]), 5695)
        self.assertEqual(len(result["per_reference_comparisons"]), 1683)
        self.assertEqual(len(result["roi_profile"]), 17)
        self.assertEqual({role: sum(row["role"] == role for row in result["reference_conditions"])
                          for role in ("main", "figure16", "figure17", "figure18")},
                         {"main": 1683, "figure16": 3128, "figure17": 867, "figure18": 17})
        self.assertAlmostEqual(result["roi_profile"][0]["delta_to_strongest"], 0.1)
        self.assertIsNone(result["inference"]["paper_win"])
        self.assertFalse(result["qualification"]["scientific_improvement"])
        self.assertEqual(result["noise_ceilings"], self.reference["noise_ceilings"])

    def test_strongest_reference_not_convenient_reference(self):
        source = copy.deepcopy(self.reference)
        source["rsa"][17]["values"][1] = [0.8] * 10
        result = MODULE.compare(PROTOCOL, source, self.candidate)
        self.assertEqual(result["roi_profile"][0]["strongest_reference_model"], self.axes["models"][1])
        self.assertAlmostEqual(result["roi_profile"][0]["delta_to_strongest"], -0.5)

    def test_missing_reference_prevents_strongest_subset(self):
        source = copy.deepcopy(self.reference)
        source["rsa"][0]["values"][0][0] = None
        result = MODULE.compare(PROTOCOL, source, self.candidate)
        self.assertIsNone(result["roi_profile"][0]["strongest_reference_model"])
        self.assertIsNone(result["roi_profile"][0]["delta_to_strongest"])
        self.assertEqual(len(result["per_reference_comparisons"]), 1683)

    def test_complete_support_refusals(self):
        changes = [
            lambda r, c: r["rsa"].pop(),
            lambda r, c: c["rsa"].reverse(),
            lambda r, c: c["test_support"]["subjects"].reverse(),
            lambda r, c: c["test_support"]["stimuli"].reverse(),
            lambda r, c: c["test_support"].update(brain_rdms_sha256="8" * 64),
            lambda r, c: r["train_support"].update(repetitions=10),
            lambda r, c: r["train_support"]["stimuli"].__setitem__(0, "vid1001"),
            lambda r, c: r["noise_ceilings"]["train"].pop(),
            lambda r, c: r["rsa"][0].update(layers=["omitted_layer"]),
            lambda r, c: c["rsa"][0].update(layers=["ROI_specific_layer"]),
        ]
        for index, change in enumerate(changes):
            r, c = copy.deepcopy(self.reference), copy.deepcopy(self.candidate)
            change(r, c)
            with self.subTest(index=index), self.assertRaises(ValueError):
                MODULE.compare(PROTOCOL, r, c)

    def test_source_pin_and_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for body in ('{"x":1,"x":2}', '{"x":NaN}'):
                path.write_text(body)
                with self.assertRaises(ValueError):
                    MODULE.read_json(path)
            path.write_text("{}")
            with self.assertRaises(ValueError):
                MODULE.source_axes(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
