"""Bounded metadata-only controls; no arrays, native imports, or fixture files."""

from dataclasses import replace
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


path = Path(__file__).with_name("operation_contracts.py")
spec = importlib.util.spec_from_file_location("dimension_contracts_tested", path)
k = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = k
spec.loader.exec_module(k)

# Initial author serializer probe used77 actual bytes, including its retained
# five-byte DEL undercharge. Later targeted reruns must carry their predecessor.
BUDGET = k.SerializationBudget(8 * 1024 * 1024,
                              int(os.environ.get("DIMENSION_TEST_PRIOR_SERIALIZED_BYTES", "77")))
PIN = "1" * 64


def stimuli(ids):
    return k.StimulusSupport(ids, k.canonical_digest(ids, BUDGET), PIN)


def support(ids=None, layer_shapes=None):
    ids = k.TEST_STIMULI if ids is None else ids
    layer_shapes = (k.LayerShape("layer10", (1, 128)), k.LayerShape("layer2", (2, 64))) if layer_shapes is None else layer_shapes
    order = tuple(layer.layer for layer in layer_shapes)
    return k.FeatureSupport("invented_model", stimuli(ids), order,
                            tuple(k.FeatureFile(identity + ".npz", identity, layer_shapes) for identity in reversed(ids)), PIN)


def admitted(spec):
    return k.RunAdmission(k.canonical_digest(spec, BUDGET), PIN, "prospective")


class OperationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exactly one full1000 feature metadata fixture and one full170 brain
        # shape fixture, shared by success/failure controls; no feature values.
        cls.train = support(tuple("training-example-" + str(i).zfill(4) for i in range(1, 1001)))
        cls.brain = k.BrainSupport(cls.train.stimuli, tuple(
            k.BrainRecord(subject, roi, (1000, 3, 1), cls.train.stimuli.order_sha256, PIN)
            for subject in k.SUBJECTS for roi in k.ROIS), PIN)

    def test_01_single_full_train_and_brain_contract(self):
        contract = k.compile_model_contract(k.TRAIN_SPLIT, self.train, k.literal_script_pca(), budget=BUDGET)
        self.assertEqual(contract.execution_layer_order, ("layer2", "layer10"))
        self.assertEqual(contract.source_axis_layer_order, ("layer10", "layer2"))
        self.assertEqual(len(contract.stimulus_order), 1000)
        self.assertEqual(dict(contract.iterator_kwargs)["n_samples_estim"], 102)
        for layer in contract.layer_contracts:
            self.assertEqual(layer.constructor.arguments, (("n_components", 100),))
            operations = {op.name: dict(op.arguments) for op in layer.operations}
            self.assertEqual(operations["fill_estimator_prefix"]["natural_stimulus_prefix_length"], 102)
            self.assertEqual(operations["transform_every_stimulus"]["stimulus_count"], 1000)
            self.assertEqual(operations["emit_layer_rdm"]["shape"], (1000, 1000))
            self.assertEqual(operations["model_pearson_distance"]["standardize_on_dim"], None)
            self.assertFalse(set(dict(layer.constructor.arguments)) & {"random_state", "svd_solver", "eps"})
        brain = k.compile_brain_contract(k.TRAIN_SPLIT, self.brain, budget=BUDGET)
        operations = {op.name: dict(op.arguments) for op in brain.operations}
        self.assertEqual(operations["mean_repetitions"]["axis"], 1)
        self.assertEqual(operations["brain_pearson_distance"]["dim"], None)
        self.assertEqual(operations["retain_subject_axis"]["average_external"], False)
        self.assertEqual(operations["stack_subject_rdms_per_roi"]["output_shape_per_roi"], (10, 1000, 1000))
        self.assertEqual(brain.roi_order, k.ROIS)
        self.assertEqual(brain.subject_order, k.SUBJECTS)
        summary = k.summarize_contract(contract, budget=BUDGET)
        self.assertEqual(summary.layer_order, self.train.expected_layer_order)
        self.assertEqual(summary.stimulus_order_sha256, self.train.stimuli.order_sha256)
        for result in (contract, brain, summary):
            self.assertFalse(result.metadata_authenticity_verified)
            self.assertFalse(result.native_executed)
            self.assertFalse(result.historical_runtime_equivalence)
            self.assertFalse(result.scientific_qualified)

    def test_02_literal_test_parameters_exact_and_separate_support(self):
        data = support()
        contract = k.compile_model_contract(k.TEST_SPLIT, data, k.literal_script_pca(), budget=BUDGET)
        self.assertEqual(contract.stimulus_order, k.TEST_STIMULI)
        self.assertEqual(contract.split.repetitions, 10)
        self.assertEqual(dict(contract.iterator_kwargs), {"dim_reduction": "pca", "n_samples_estim": 102,
                                                        "n_components": 100, "max_dim_allowed": None})
        with self.assertRaisesRegex(k.ContractError, "full_split_stimulus_count"):
            k.compile_model_contract(k.TRAIN_SPLIT, data, k.literal_script_pca(), budget=BUDGET)
        with self.assertRaisesRegex(k.ContractError, "literal_script_is_exact"):
            k.compile_model_contract(k.TEST_SPLIT, data, replace(k.literal_script_pca(), n_samples_estim=100), budget=BUDGET)

    def test_03_natural_order_complete_axis_and_tie_refusal(self):
        data = support()
        result = k.compile_model_contract(k.TEST_SPLIT, data, k.literal_script_pca(), budget=BUDGET)
        self.assertEqual(result.execution_layer_order, ("layer2", "layer10"))
        tied = support(layer_shapes=(k.LayerShape("layer1", (128,)), k.LayerShape("layer01", (128,))))
        with self.assertRaisesRegex(k.ContractError, "natural_sort_tie"):
            k.compile_model_contract(k.TEST_SPLIT, tied, k.literal_script_pca(), budget=BUDGET)
        mixed = replace(data, files=(replace(data.files[0], layers=data.files[0].layers[:1]),) + data.files[1:])
        with self.assertRaisesRegex(k.ContractError, "complete_exact_layer_support"):
            k.compile_model_contract(k.TEST_SPLIT, mixed, k.literal_script_pca(), budget=BUDGET)

    def test_04_threshold_strict_greater_and_truthy_zero(self):
        data = support(layer_shapes=(k.LayerShape("a", (128,)), k.LayerShape("b", (129,))))
        spec = k.ReductionSpec("explicit_run_spec", "pca", 102, 50, 128)
        result = k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET, run_admission=admitted(spec))
        self.assertEqual([layer.reduction_applied for layer in result.layer_contracts], [False, True])
        zero = replace(spec, max_dim_allowed=0)
        result = k.compile_model_contract(k.TEST_SPLIT, data, zero, budget=BUDGET, run_admission=admitted(zero))
        self.assertTrue(all(layer.reduction_applied for layer in result.layer_contracts))

    def test_05_no_reduction_ignores_every_reduction_argument(self):
        spec = k.ReductionSpec("explicit_run_spec", None, 999999, 999999, 1)
        data = support(layer_shapes=(k.LayerShape("scalar", ()), k.LayerShape("tensor", (1, 2, 1, 3))))
        result = k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET, run_admission=admitted(spec))
        self.assertEqual(result.iterator_kwargs, ())
        self.assertTrue(all(layer.constructor is None and not layer.reduction_applied for layer in result.layer_contracts))
        scalar, tensor = result.layer_contracts
        self.assertEqual((scalar.squeezed_feature_shape, tensor.squeezed_feature_shape), ((1,), (2, 3)))
        self.assertEqual((scalar.flattened_width, tensor.flattened_width), (1, 6))
        self.assertEqual({op.name for op in scalar.operations}, {"sample_squeeze", "load_every_stimulus_without_reduction",
                         "torch_from_numpy_and_device", "flatten_features", "model_pearson_distance", "emit_layer_rdm"})

    def test_06_srp_automatic_constructor_omission_and_state_carry(self):
        data = support()
        spec = k.ReductionSpec("explicit_run_spec", "srp", 102, None, None)
        admission = admitted(spec)
        witness = k.EstimationWitness(data.model_id, "layer2", admission.run_spec_sha256,
                    k.canonical_digest(data, BUDGET), k.canonical_digest(data.stimuli.ordered_ids[:102], BUDGET), 7, PIN, PIN)
        result = k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET,
                                         run_admission=admission, estimation_witnesses=(witness,))
        first, later = result.layer_contracts
        self.assertEqual(first.constructor.name, "SparseRandomProjection")
        self.assertEqual(first.constructor.arguments, ())
        self.assertEqual(later.constructor.arguments, (("n_components", 7),))
        self.assertEqual((first.components_before, first.components_after, later.components_before), (None, 7, 7))
        self.assertIn("fit_transform", {op.name for op in first.operations})
        self.assertIn("fit", {op.name for op in later.operations})
        self.assertIsNone(later.estimation_witness_sha256)

    def test_07_pca_automatic_mle_and_zero_falsy_witness(self):
        data = support()
        spec = k.ReductionSpec("explicit_run_spec", "pca", 102, 0, None)
        admission = admitted(spec)
        with self.assertRaisesRegex(k.ContractError, "automatic_component_resolution"):
            k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET, run_admission=admission)
        witness = k.EstimationWitness(data.model_id, "layer2", admission.run_spec_sha256,
                    k.canonical_digest(data, BUDGET), k.canonical_digest(data.stimuli.ordered_ids, BUDGET), 9, PIN, PIN)
        result = k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET,
                                         run_admission=admission, estimation_witnesses=(witness,))
        self.assertEqual(result.layer_contracts[0].constructor.arguments, (("n_components", "mle"),))
        self.assertEqual(result.layer_contracts[1].constructor.arguments, (("n_components", 9),))
        broken = replace(witness, input_metadata_sha256="2" * 64)
        with self.assertRaisesRegex(k.ContractError, "estimation_witness_model_run_input_prefix_binding"):
            k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET,
                                     run_admission=admission, estimation_witnesses=(broken,))

    def test_08_automatic_state_starts_at_first_reduced_layer(self):
        data = support(layer_shapes=(k.LayerShape("a", (4,)), k.LayerShape("b", (128,)), k.LayerShape("c", (4,)), k.LayerShape("d", (128,))))
        spec = k.ReductionSpec("explicit_run_spec", "srp", 102, None, 64)
        admission = admitted(spec)
        witness = k.EstimationWitness(data.model_id, "b", admission.run_spec_sha256, k.canonical_digest(data, BUDGET),
                                     k.canonical_digest(data.stimuli.ordered_ids, BUDGET), 5, PIN, PIN)
        result = k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET,
                                         run_admission=admission, estimation_witnesses=(witness,))
        self.assertEqual([(layer.components_before, layer.components_after) for layer in result.layer_contracts],
                         [(None, None), (None, 5), (5, 5), (5, 5)])
        self.assertEqual(result.layer_contracts[3].constructor.arguments, (("n_components", 5),))
        with self.assertRaisesRegex(k.ContractError, "unused_or_nonautomatic"):
            k.compile_model_contract(k.TEST_SPLIT, data, spec, budget=BUDGET, run_admission=admission,
                                     estimation_witnesses=(witness, replace(witness, layer="d")))

    def test_09_undefined_estimator_support_and_unbound_srp_refuse(self):
        data = support()
        unknown = k.ReductionSpec("explicit_run_spec", "srp", 102, None, None)
        with self.assertRaisesRegex(k.ContractError, "historical_parameters_unbound"):
            k.compile_model_contract(k.TEST_SPLIT, data, unknown, budget=BUDGET)
        too_many = k.ReductionSpec("explicit_run_spec", "pca", 103, 100, None)
        with self.assertRaisesRegex(k.ContractError, "source_uninitialized_estimator_rows"):
            k.compile_model_contract(k.TEST_SPLIT, data, too_many, budget=BUDGET, run_admission=admitted(too_many))
        malformed = replace(admitted(unknown), run_spec_sha256="2" * 64)
        with self.assertRaisesRegex(k.ContractError, "run_admission_spec_mismatch"):
            k.compile_model_contract(k.TEST_SPLIT, data, unknown, budget=BUDGET, run_admission=malformed)

    def test_10_complete_support_metadata_refusals(self):
        data = support()
        cases = (
            replace(data, files=data.files[:-1]),
            replace(data, files=(replace(data.files[0], basename="extraneous.txt"),) + data.files[1:]),
            replace(data, files=(replace(data.files[0], layers=(k.LayerShape("layer10", (129,)), k.LayerShape("layer2", (2, 64)))),) + data.files[1:]),
            replace(data, files=(replace(data.files[0], stimulus_id="changed"),) + data.files[1:]),
            replace(data, feature_format="NPZ_CONSOLIDATED"),
            replace(data, root_path="consolidated_features"),
            replace(data, stimuli=replace(data.stimuli, admission_record_sha256="")),
            replace(data, stimuli=replace(data.stimuli, ordered_ids=tuple(reversed(data.stimuli.ordered_ids)))),
        )
        for case in cases:
            with self.subTest(kind=case.feature_format), self.assertRaises(k.ContractError):
                k.compile_model_contract(k.TEST_SPLIT, case, k.literal_script_pca(), budget=BUDGET)

    def test_11_brain_axes_coordinates_and_full_scope_refuse(self):
        first = self.brain.records[0]
        for changed in (replace(first, shape=(1000, 10, 1)), replace(first, shape=(1000, 3)),
                        replace(first, stimulus_order_sha256="2" * 64), replace(first, coordinate_admission_sha256="")):
            bad = replace(self.brain, records=(changed,) + self.brain.records[1:])
            with self.assertRaises(k.ContractError):
                k.compile_brain_contract(k.TRAIN_SPLIT, bad, budget=BUDGET)
        with self.assertRaisesRegex(k.ContractError, "complete_10_subject_17_roi"):
            k.compile_brain_contract(k.TRAIN_SPLIT, replace(self.brain, records=self.brain.records[:-1]), budget=BUDGET)
        with self.assertRaisesRegex(k.ContractError, "identity_or_duplicate"):
            k.compile_brain_contract(k.TRAIN_SPLIT, replace(self.brain, records=(first,) + self.brain.records[:-1]), budget=BUDGET)

    def test_12_canonical_precharge_exact_escape_boundaries_and_fail_before_encoding(self):
        for value in ("~", "\x7f", "\x80", "\ud800", "😀", "é", '"\\\b\f\n\r\t',
                      tuple(chr(i) for i in range(128)), {"z": (0, -1, True, False, None), "a": "value"}):
            before = BUDGET.used_bytes
            raw = k.canonical_bytes(value, BUDGET)
            self.assertEqual(len(raw), k.canonical_size(value))
            self.assertEqual(BUDGET.used_bytes - before, len(raw))
        boundary = k.SerializationBudget(7)
        with patch.object(k.json, "dumps", side_effect=AssertionError("encoding must not happen")):
            with self.assertRaises(k.SerializationLimitError):
                k.canonical_bytes("\x7f", boundary)
        self.assertEqual(boundary.used_bytes, 0)
        before = BUDGET.used_bytes
        with self.assertRaises(k.ContractError):
            k.canonical_bytes(float("nan"), BUDGET)
        self.assertEqual(BUDGET.used_bytes, before)


if __name__ == "__main__":
    unittest.main()
