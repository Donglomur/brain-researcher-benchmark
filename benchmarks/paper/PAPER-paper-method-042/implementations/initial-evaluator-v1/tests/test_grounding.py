import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grounding as g
from make_control import build


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "control"
        self.contract_path = build(self.root)
        self.contract = g.read_json(self.contract_path)
        self.annotations = g.read_json(self.root / "annotations.json")
        self.order = g.read_json(self.root / "image_order.json")
        self.targets = g.prepare_reference(self.annotations, self.order, "engineering_controls")

    def tearDown(self):
        self.tmp.cleanup()

    def save_contract(self):
        self.contract_path.write_text(json.dumps(self.contract))

    def evaluate(self):
        return g.evaluate(self.contract_path, self.root / "annotations.json", self.root / "image_order.json", bootstrap_draws=50, seed=7)

    def test_complete_cli_inputs_and_hand_computed_metrics(self):
        result = self.evaluate()
        self.assertEqual(result["population"]["shared_images"], 4)
        self.assertEqual(result["population"]["queries_per_subject"], 4)
        self.assertEqual(result["population"]["all_annotation_boxes"], 5)
        for subject in g.SUBJECTS:
            score = result["scores"]["candidate"][subject]["All"]
            self.assertEqual(score["accuracy"], {"0.3": 1, "0.5": .75, "0.7": .75})
            self.assertEqual(score["mean_iou"], .875)
        self.assertEqual(result["paired_comparisons"]["official_baseline"]["delta_accuracy_at_0.5"], .5)
        self.assertFalse(result["authentic_reference_run"])
        self.assertEqual(result["qualification"], "unknown")

    def test_strict_iou_threshold_and_scale(self):
        a = g.box([0, 0, 1, .5], reference=False)
        b = g.box([0, 0, 1, 1], reference=True)
        self.assertEqual(g.intersection_over_union(a, b), .5)
        self.assertEqual(g.intersection_over_union(tuple(x * 1000 for x in a), tuple(x * 1000 for x in b)), .5)
        rows = [{"category": "person", "iou": .5, "prediction_status": "valid"}]
        self.assertEqual(g.summarize(rows)["All"]["accuracy"], {"0.3": 1, "0.5": 0, "0.7": 0})

    def test_first_box_only_no_best_overlap_selection(self):
        predictions = {"0": {"car": [[[.5, .5, 1, 1], [0, 0, .25, .25]]]}}
        rows = g.score_subject(self.targets, set(self.order), predictions)
        self.assertEqual(next(r for r in rows if r["category"] == "car")["iou"], 0)
        self.assertEqual(len(rows), 4)

    def test_pairing_ignores_insertion_order(self):
        expected = self.evaluate()
        for run in self.contract["runs"].values():
            for name in run["responses"].values():
                path = self.root / name
                response = g.read_json(path)
                response = {i: dict(reversed(list(c.items()))) for i, c in reversed(list(response.items()))}
                path.write_text(json.dumps(response))
        actual = self.evaluate()
        self.assertEqual(actual["scores"], expected["scores"])
        self.assertEqual(actual["paired_comparisons"], expected["paired_comparisons"])

    def test_missing_images_and_malformed_boxes_keep_denominator(self):
        response = {"0": {"person": [[[-1, 0, 1, 1]]], "car": [[[True, 0, 1, 1]]]}, "1": {"bottle": [[[0, 0, float("nan"), 1]]]}}
        rows = g.score_subject(self.targets, set(self.order), response)
        score = g.summarize(rows)["All"]
        self.assertEqual(score["query_count"], 4)
        self.assertEqual(score["mean_iou"], 0)
        self.assertEqual(score["missing_or_invalid"], 4)

    def test_reference_degenerate_and_empty_query_rejected(self):
        for bad in (None, [], [[0, 0, 0, 0]], [[0, 0, 2, 1]], [[0, 0, 1e-200, 1e-200]], [[0, 0, 10**1000, 1]]):
            annotations = copy.deepcopy(self.annotations)
            annotations["0"]["person"] = bad
            with self.assertRaises(g.ContractError):
                g.prepare_reference(annotations, self.order, "engineering_controls")
        with self.assertRaises(g.ContractError):
            g.prepare_reference({"0": {}}, {"0": "one"}, "engineering_controls")

    def test_unexpected_images_and_categories_rejected(self):
        for responses in ({"wrong": {}}, {"0": {"bird": []}}, {"2": {"person": []}}):
            with self.assertRaises(g.ContractError):
                g.score_subject(self.targets, set(self.order), responses)

    def test_unequal_query_counts_not_image_macro_average(self):
        rows = [{"image_id": "0", "category": "person", "iou": 1, "prediction_status": "valid"}]
        rows += [{"image_id": "1", "category": cat, "iou": 0, "prediction_status": "valid"} for cat in ("car", "dog", "bottle")]
        self.assertEqual(g.summarize(rows)["All"]["accuracy"]["0.5"], .25)
        subject_rows = {s: rows for s in g.SUBJECTS}
        result = g.paired_image_bootstrap(subject_rows, subject_rows, ["0", "1"], 100, 0)
        self.assertEqual(result["delta_accuracy_at_0.5"], 0)
        self.assertEqual(result["image_cluster_percentile_95_interval"], [0, 0])

    def test_group_counts_and_partition(self):
        self.assertEqual([len(v) for v in g.GROUPS.values()], [80, 28, 11, 17, 52])
        self.assertFalse(g.GROUPS["Salient"] & g.GROUPS["Inconspicuous"])
        self.assertEqual(g.GROUPS["All"], g.GROUPS["Salient"] | g.GROUPS["Inconspicuous"])

    def test_population_and_no_subject_holdout_claim(self):
        with self.assertRaises(g.ContractError):
            g.prepare_reference(self.annotations, self.order, "paper_population")
        for field, value in (("subject_design", "held_out_subject"), ("brainhub_revision", "main"), ("all_images_sha256", "0" * 64)):
            contract = copy.deepcopy(self.contract)
            contract[field] = value
            with self.assertRaises(g.ContractError):
                g.validate_design(contract, self.order)

    def test_native_cardinality_does_not_invent_per_class_minima(self):
        order = {str(i): f"generated-{i}" for i in range(982)}
        annotations = {i: {} for i in order}
        annotations["0"] = {"person": [[0, 0, 1, 1]] * 5829}
        targets = g.prepare_reference(annotations, order, "paper_population")
        self.assertEqual(len(targets), 1)
        annotations["0"]["person"].pop()
        with self.assertRaises(g.ContractError):
            g.prepare_reference(annotations, order, "paper_population")

    def test_exposure_mismatch_leakage_and_subject_omission(self):
        contract = copy.deepcopy(self.contract)
        contract["runs"]["candidate"]["exposure"]["pretrained_language_sha256"] = "5" * 64
        with self.assertRaises(g.ContractError):
            g.validate_design(contract, self.order)
        self.contract["exposure"]["training_stimulus_ids"] = ["generated-stimulus-0"]
        with self.assertRaises(g.ContractError):
            g.validate_design(self.contract, self.order)
        contract = g.read_json(self.contract_path)
        del contract["runs"]["candidate"]["responses"]["S7"]
        with self.assertRaises(g.ContractError):
            g.validate_design(contract, self.order)

    def test_shuffle_must_be_complete_bijection_without_fixed_images(self):
        for mapping in ({"0": "0", "1": "1", "2": "2", "3": "3"}, {"0": "1", "1": "2", "2": "3", "3": "1"}, {"0": "1"}):
            contract = copy.deepcopy(self.contract)
            contract["runs"]["shuffled_neural"]["source_image_by_target"]["S1"] = mapping
            with self.assertRaises(g.ContractError):
                g.validate_design(contract, self.order)

    def test_controls_are_paired_to_candidate_checkpoint(self):
        for field, value in (("control_of", "official_baseline"), ("checkpoint_sha256", "9" * 64)):
            contract = copy.deepcopy(self.contract)
            contract["runs"]["neural_free"][field] = value
            with self.assertRaises(g.ContractError):
                g.validate_design(contract, self.order)

    def test_hash_mismatch_rejected(self):
        self.contract["annotations_sha256"] = "0" * 64
        self.save_contract()
        with self.assertRaises(g.ContractError):
            self.evaluate()

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        path = self.root / "bad.json"
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            path.write_text(text)
            with self.assertRaises(g.ContractError):
                g.read_json(path)


if __name__ == "__main__":
    unittest.main()
