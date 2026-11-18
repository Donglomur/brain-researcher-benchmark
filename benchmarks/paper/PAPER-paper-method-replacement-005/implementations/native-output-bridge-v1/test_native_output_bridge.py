"""Generated controls only; no real observations, native model, training or fit."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("native_output_bridge", HERE / "native_output_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
DEPENDENCY_DIRECTORY = HERE.parent / "initial-evaluator-v1"


def fixture(evaluator):
    roster = evaluator.load_roster()
    sessions, exports = [], []
    ordered = roster["training_eids"] + roster["heldout_eids"]
    for k, eid in enumerate(ordered):
        session = {"eid": eid, "animal_id": "animal-" + str(0 if k == 1 else k),
                   "bin_width_seconds": 0.02, "unit_ids": ["u-right", "u-left"],
                   "source_identity": {"kind": "generated_control_not_observed_IBL"}}
        for split, n in (("train", 3), ("validation", 2), ("test", 3)):
            session[split] = {
                "trial_ids": [f"{eid}:{split}:{i}" for i in range(n)],
                "spike": [[[1 + i % 2, (t + i) % 3] for t in range(100)] for i in range(n)],
                "choice": [-1, 1, -1][:n], "block": [0.2, 0.5, 0.8][:n],
                "wheel": [[i + t / 100 for t in range(100)] for i in range(n)],
                "whisker": [[2 * i - t / 100 for t in range(100)] for i in range(n)],
            }
        sessions.append(session)
        for method in ("source_method", "candidate"):
            # The two methods intentionally have different class outcomes.
            native = {key: {"expected_counts_per_bin": copy.deepcopy(session["test"]["spike"])}
                      for key in bridge.ENCODING}
            native["eval_behavior"] = {
                "choice_class_index": [1, 0, 1] if method == "source_method" else [0, 1, 0],
                "block_class_index": [2, 0, 1] if method == "source_method" else [0, 1, 2],
                "wheel": copy.deepcopy(session["test"]["wheel"]),
                "whisker": copy.deepcopy(session["test"]["whisker"]),
            }
            metadata = evaluator.make_receipt(session, method, {}, "same-declared-budget",
                                               roster["training_eids"])
            del metadata["predictions"]
            metadata["native_outputs"] = native
            exports.append(metadata)
    return ({"schema": "neds-binned-panel-v1", "source_commit": bridge.COMMIT,
             "evidence_kind": "generated_engineering", "sessions": sessions},
            {"schema": "neds-native-prediction-export/v1", "source_commit": bridge.COMMIT,
             "evidence_kind": "generated_engineering", "methods": ["source_method", "candidate"],
             "records": exports})


class NativeOutputBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = bridge.load_evaluator(DEPENDENCY_DIRECTORY)
        cls.bundle, cls.export = fixture(cls.evaluator)
        cls.methods = ("source_method", "candidate")

    def assemble(self, bundle=None, export=None):
        return bridge.assemble(self.bundle if bundle is None else bundle,
                               self.export if export is None else export, self.methods,
                               evaluator_directory=DEPENDENCY_DIRECTORY)

    def mutated_export(self, mutate):
        export = copy.deepcopy(self.export)
        mutate(export)
        return export

    def test_complete84_pair_and_exact_class_mapping(self):
        result = self.assemble()
        self.assertEqual(len(result["receipts"]), 168)
        self.assertEqual(result["coverage"]["endpoint_count_per_record"], 9)
        first, second = result["receipts"][:2]
        self.assertEqual(first["predictions"]["decode_all"]["choice"], [1, -1, 1])
        self.assertEqual(first["predictions"]["decode_all"]["block"], [0.8, 0.2, 0.5])
        self.assertEqual(second["predictions"]["decode_all"]["choice"], [-1, 1, -1])
        self.assertEqual(second["predictions"]["decode_all"]["block"], [0.2, 0.5, 0.8])
        self.assertEqual(first["predictions"]["encode_all"]["spike"], self.bundle["sessions"][0]["test"]["spike"])
        self.assertFalse(result["readiness_promoted"])

    def test_full_bridge_reaches_existing_scorer_and_all_nine_endpoints(self):
        result = bridge.evaluate_export(self.bundle, self.export, self.methods,
                                         evaluator_directory=DEPENDENCY_DIRECTORY, draws=8, seed=4)
        report = result["evaluation"]
        self.assertEqual(len(report["session_results"]), 84)
        self.assertEqual(report["summaries"]["training"]["sessions"], 74)
        self.assertEqual(report["summaries"]["heldout"]["sessions"], 10)
        for row in report["session_results"]:
            for method in self.methods:
                self.assertEqual(len(row["scores"][method]["endpoints"]), 9)
            self.assertEqual(row["scores"]["source_method"]["endpoints"]["choice:accuracy"], 0.0)
            self.assertEqual(row["scores"]["candidate"]["endpoints"]["choice:accuracy"], 1.0)
            self.assertEqual(row["scores"]["candidate"]["endpoints"]["block:accuracy"], 1.0)
            self.assertEqual(row["scores"]["candidate"]["endpoints"]["wheel:r2"], 1.0)
            self.assertEqual(row["scores"]["candidate"]["endpoints"]["whisker:r2"], 1.0)
        self.assertEqual(report["scientific_qualification"], "unknown")

    def test_method_order_cannot_be_chosen_by_export(self):
        bad = self.mutated_export(lambda x: x["methods"].reverse())
        with self.assertRaisesRegex(bridge.BridgeError, "operator selection"):
            self.assemble(export=bad)

    def test_missing_and_duplicate_pairs_refused(self):
        with self.assertRaisesRegex(bridge.BridgeError, "record count"):
            self.assemble(export=self.mutated_export(lambda x: x["records"].pop()))
        bad = self.mutated_export(lambda x: x["records"].__setitem__(1, copy.deepcopy(x["records"][0])))
        with self.assertRaisesRegex(bridge.BridgeError, "duplicate"):
            self.assemble(export=bad)

    def test_last_batch_and_reordered_trial_ids_refused(self):
        bad = self.mutated_export(lambda x: x["records"][0]["native_outputs"]["eval_spike"]["expected_counts_per_bin"].pop())
        with self.assertRaisesRegex(bridge.BridgeError, "complete trial"):
            self.assemble(export=bad)
        bad = self.mutated_export(lambda x: x["records"][0]["trial_ids"].reverse())
        with self.assertRaisesRegex(ValueError, "trial_ids"):
            self.assemble(export=bad)

    def test_reordered_units_and_wrong_masks_refused(self):
        bad = self.mutated_export(lambda x: x["records"][0]["unit_ids"].reverse())
        with self.assertRaisesRegex(ValueError, "unit_ids"):
            self.assemble(export=bad)
        bad = self.mutated_export(lambda x: x["records"][0]["native_outputs"].pop("eval_spike_choice"))
        with self.assertRaisesRegex(bridge.BridgeError, "native_outputs"):
            self.assemble(export=bad)

    def test_target_bearing_extra_fields_and_units_refused(self):
        bad = self.mutated_export(lambda x: x["records"][0]["native_outputs"]["eval_spike"].update(gt=[1]))
        with self.assertRaisesRegex(bridge.BridgeError, "exact fields"):
            self.assemble(export=bad)
        bad = self.mutated_export(lambda x: x["records"][0]["native_outputs"]["eval_spike"].update(hertz=[[1]]))
        with self.assertRaisesRegex(bridge.BridgeError, "exact fields"):
            self.assemble(export=bad)

    def test_raw_labels_probabilities_and_boolean_indices_refused(self):
        for indices in ([0.2, 0.5, 0.8], [0.0, 1.0, 2.0], [True, 0, 1], [0, 1, 3], [[1, 0, 0]] * 3):
            with self.subTest(indices=indices), self.assertRaises(bridge.BridgeError):
                bridge.decode_classes(indices, "block", 3)

    def test_negative_rates_coercible_numbers_nonfinite_refused(self):
        for number in (-1, "1", True, float("nan")):
            def mutate(x):
                x["records"][0]["native_outputs"]["eval_spike"]["expected_counts_per_bin"][0][0][0] = number
            with self.subTest(number=number), self.assertRaises(bridge.BridgeError):
                self.assemble(export=self.mutated_export(mutate))

    def test_exposure_budget_and_packet_disagreements_refused(self):
        mutations = [lambda x: x["records"][1].__setitem__("budget_contract", "different-budget"),
                     lambda x: x["records"][1]["pretrained_eids"].pop(),
                     lambda x: x["records"][0]["packet_sha256"].__setitem__("encode_all", "0" * 64)]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises((bridge.BridgeError, ValueError)):
                self.assemble(export=self.mutated_export(mutate))

    def test_no_authentic_subset_escape(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["sessions"].pop()
        with self.assertRaisesRegex(ValueError, "complete 74"):
            self.assemble(bundle=bundle)

    def test_output_is_detached_from_export(self):
        result = self.assemble()
        result["receipts"][0]["predictions"]["decode_all"]["wheel"][0][0] = 999
        self.assertNotEqual(self.export["records"][0]["native_outputs"]["eval_behavior"]["wheel"][0][0], 999)

    def test_dependency_change_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "neds_evaluator.py").write_text("raise RuntimeError('must not execute')\n")
            with self.assertRaisesRegex(bridge.BridgeError, "dependency changed"):
                bridge.load_evaluator(directory)

    def test_duplicate_json_keys_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text('{"records": [], "records": []}')
            with self.assertRaisesRegex(bridge.BridgeError, "duplicate JSON"):
                bridge.read_json(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluator-directory", type=Path, default=DEPENDENCY_DIRECTORY)
    args, remainder = parser.parse_known_args()
    DEPENDENCY_DIRECTORY = args.evaluator_directory
    unittest.main(argv=[__file__, *remainder])
