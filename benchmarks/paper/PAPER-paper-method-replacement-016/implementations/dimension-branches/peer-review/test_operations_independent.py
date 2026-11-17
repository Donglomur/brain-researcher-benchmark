"""Independent literal-operation checks on invented metadata, without arrays."""
import dataclasses as dc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tracemalloc
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "kernel-work/operation_contracts.py"
spec = importlib.util.spec_from_file_location("peer_dimension_operations", SOURCE)
o = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = o
spec.loader.exec_module(o)
REAL_DUMPS = json.dumps
ACTUAL_BYTES = 0
ACTUAL_CALLS = 0
ADMISSION = "c" * 64
BUDGET = o.SerializationBudget(5_000_000)


def counted_dumps(*args, **kwargs):
    global ACTUAL_BYTES, ACTUAL_CALLS
    text = REAL_DUMPS(*args, **kwargs)
    ACTUAL_BYTES += len(text.encode("utf8"))
    ACTUAL_CALLS += 1
    return text


def support(split):
    ids = o.TEST_STIMULI if split == o.TEST_SPLIT else tuple("invented_train_" + str(i) for i in range(1000))
    stimuli = o.StimulusSupport(ids, o.canonical_digest(ids, BUDGET), ADMISSION)
    keys = (o.LayerShape("layer10", (1, 200, 1)), o.LayerShape("layer2", (2, 100)))
    files = tuple(o.FeatureFile(name + ".npz", name, keys) for name in reversed(ids))
    return o.FeatureSupport("invented_model", stimuli, ("layer10", "layer2"), files, ADMISSION)


def admission(reduction):
    return o.RunAdmission(o.canonical_digest(reduction, BUDGET), ADMISSION, "prospective")


def operation(layer, name):
    return next(x for x in layer.operations if x.name == name)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test = support(o.TEST_SPLIT)
        cls.train = support(o.TRAIN_SPLIT)

    def test_01_json_boundaries_and_precharge_before_encoding(self):
        values = [chr(i) for i in range(130)] + ["\ud800", "\U0001f9e0", "a\n\t\\\"z", {"x": (False, 103, None)}]
        for value in values:
            expected = counted_dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            exact = o.SerializationBudget(len(expected))
            self.assertEqual(o.canonical_size(value), len(expected))
            self.assertEqual(o.canonical_bytes(value, exact), expected)
            self.assertEqual(exact.used_bytes, len(expected))
            calls_before = ACTUAL_CALLS
            with self.assertRaises(o.SerializationLimitError):
                o.canonical_bytes(value, o.SerializationBudget(len(expected) - 1))
            self.assertEqual(ACTUAL_CALLS, calls_before)

    def test_02_literal_pca_test_natural_order_and_constructor_omissions(self):
        result = o.compile_model_contract(o.TEST_SPLIT, self.test, o.literal_script_pca(), budget=BUDGET)
        self.assertEqual(result.source_axis_layer_order, ("layer10", "layer2"))
        self.assertEqual(result.execution_layer_order, ("layer2", "layer10"))
        self.assertEqual(result.stimulus_order, o.TEST_STIMULI)
        for layer in result.layer_contracts:
            self.assertEqual(layer.constructor.name, "PCA")
            self.assertEqual(layer.constructor.arguments, (("n_components", 100),))
            self.assertEqual(dict(operation(layer, "fill_estimator_prefix").arguments)["natural_stimulus_prefix_length"], 102)
            self.assertEqual(dict(operation(layer, "transform_every_stimulus").arguments)["stimulus_count"], 102)
            self.assertEqual(dict(operation(layer, "reshape_estimator").arguments)["shape"], (102, -1))
            self.assertEqual(dict(operation(layer, "flatten_features").arguments)["start_dim"], 1)
            self.assertFalse(result.native_executed)
            self.assertFalse(result.historical_runtime_equivalence)

    def test_03_train_thousand_is_transformed_but_only_first102_estimate(self):
        result = o.compile_model_contract(o.TRAIN_SPLIT, self.train, o.literal_script_pca(), budget=BUDGET)
        for layer in result.layer_contracts:
            self.assertEqual(dict(operation(layer, "fill_estimator_prefix").arguments)["natural_stimulus_prefix_length"], 102)
            self.assertEqual(dict(operation(layer, "transform_every_stimulus").arguments)["output_shape"], (1000, 100))
        brain = o.BrainSupport(self.train.stimuli, tuple(o.BrainRecord(subject, roi, (1000, 3, 4), self.train.stimuli.order_sha256, ADMISSION) for subject in o.SUBJECTS for roi in o.ROIS), ADMISSION)
        compiled = o.compile_brain_contract(o.TRAIN_SPLIT, brain, budget=BUDGET)
        ops = {x.name: dict(x.arguments) for x in compiled.operations}
        self.assertEqual(ops["mean_repetitions"]["axis"], 1)
        self.assertEqual(ops["mean_repetitions"]["input_count_per_stimulus"], 3)
        self.assertEqual(ops["brain_pearson_distance"]["expression"], "1 - np.corrcoef(raw)")
        self.assertEqual(ops["stack_subject_rdms_per_roi"]["output_shape_per_roi"], (10, 1000, 1000))
        self.assertFalse(ops["retain_subject_axis"]["average_external"])
        with self.assertRaises(o.ContractError):
            o.compile_brain_contract(o.TRAIN_SPLIT, dc.replace(brain, records=brain.records[:-1]), budget=BUDGET)
        with self.assertRaises(o.ContractError):
            o.compile_brain_contract(o.TEST_SPLIT, brain, budget=BUDGET)

    def test_04_no_reduction_omits_all_iterator_parameters(self):
        reduction = o.ReductionSpec("explicit_run_spec", None, 9999, 3, 1)
        result = o.compile_model_contract(o.TEST_SPLIT, self.test, reduction, budget=BUDGET, run_admission=admission(reduction))
        self.assertEqual(result.iterator_kwargs, ())
        self.assertEqual(result.run_spec.n_samples_estim, 9999)
        for layer in result.layer_contracts:
            self.assertFalse(layer.reduction_applied)
            self.assertIsNone(layer.components_before)
            self.assertIsNone(layer.constructor)
            self.assertNotIn("fit", [x.name for x in layer.operations])

    def test_05_automatic_srp_resolution_persists_across_layers(self):
        reduction = o.ReductionSpec("explicit_run_spec", "srp", 102, None)
        run = admission(reduction)
        witness = o.EstimationWitness(self.test.model_id, "layer2", run.run_spec_sha256, o.canonical_digest(self.test, BUDGET), o.canonical_digest(o.TEST_STIMULI, BUDGET), 7, "d" * 64, ADMISSION)
        result = o.compile_model_contract(o.TEST_SPLIT, self.test, reduction, budget=BUDGET, run_admission=run, estimation_witnesses=(witness,))
        first, second = result.layer_contracts
        self.assertEqual(first.constructor.arguments, ())
        self.assertEqual((first.components_before, first.components_after), (None, 7))
        self.assertIn("fit_transform", [x.name for x in first.operations])
        self.assertEqual(second.constructor.arguments, (("n_components", 7),))
        self.assertEqual((second.components_before, second.components_after), (7, 7))
        self.assertIn("fit", [x.name for x in second.operations])
        self.assertNotIn("fit_transform", [x.name for x in second.operations])
        with self.assertRaises(o.ContractError):
            o.compile_model_contract(o.TEST_SPLIT, self.test, reduction, budget=BUDGET, run_admission=run)
        with self.assertRaises(o.ContractError):
            o.compile_model_contract(o.TEST_SPLIT, self.test, reduction, budget=BUDGET, run_admission=run, estimation_witnesses=(dc.replace(witness, estimation_prefix_sha256="e" * 64),))

    def test_06_complete_keys_shapes_sort_ties_and_uninitialized_prefix_refuse(self):
        original = self.test.files[0]
        wrong_shape = dc.replace(original, layers=(o.LayerShape("layer10", (201,)), o.LayerShape("layer2", (2, 100))))
        candidates = [dc.replace(self.test, files=self.test.files[:-1]), dc.replace(self.test, files=(wrong_shape,) + self.test.files[1:])]
        tie_keys = (o.LayerShape("x1", (200,)), o.LayerShape("x01", (200,)))
        candidates.append(dc.replace(self.test, expected_layer_order=("x1", "x01"), files=tuple(dc.replace(f, layers=tie_keys) for f in self.test.files)))
        for candidate in candidates:
            with self.assertRaises(o.ContractError):
                o.compile_model_contract(o.TEST_SPLIT, candidate, o.literal_script_pca(), budget=BUDGET)
        reduction = o.ReductionSpec("explicit_run_spec", "pca", 103, 100)
        with self.assertRaisesRegex(o.ContractError, "uninitialized"):
            o.compile_model_contract(o.TEST_SPLIT, self.test, reduction, budget=BUDGET, run_admission=admission(reduction))


if __name__ == "__main__":
    before = SOURCE.read_bytes()
    tracemalloc.start()
    with patch.object(o.json, "dumps", counted_dumps):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    live, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert SOURCE.read_bytes() == before
    print(REAL_DUMPS({"groups": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "runtime_bytes": len(before), "runtime_sha256": hashlib.sha256(before).hexdigest(), "actual_canonical_fixture_serialization_bytes": ACTUAL_BYTES, "actual_canonical_calls": ACTUAL_CALLS, "shared_compiler_budget_used": BUDGET.used_bytes, "traced_live_after_imports": live, "traced_peak_after_imports": peak, "physical_invented_fixture_bytes": 0}, sort_keys=True))
    sys.exit(not result.wasSuccessful())
