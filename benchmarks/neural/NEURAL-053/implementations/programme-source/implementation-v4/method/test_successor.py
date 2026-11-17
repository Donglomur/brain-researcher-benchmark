"""Focused I5/C2 controls only. All numerical values are invented engineering data.

Direct execution avoids importing the parent's concurrently revised admission
module. No broad prior suite, authentic dataset or scientific model is executed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent
V2 = HERE.parent
V1_PLAN = V2.parent / "implementation-v1" / "method" / "plan.py"
FILES = {"v1_evaluator": V1_PLAN, "v2_evaluator": HERE / "plan.py",
         "reference_models": V2 / "reference" / "models.py",
         "successor_test": Path(__file__).resolve()}
OBSERVATIONS = {}
SOURCE_BYTES_READ = 0


def pin(path):
    global SOURCE_BYTES_READ
    size = path.stat().st_size
    if size > 40000:
        raise AssertionError("unexpected source extent")
    body = path.read_bytes()
    SOURCE_BYTES_READ += len(body)
    if len(body) != size:
        raise AssertionError("source changed while reading")
    return {"bytes": size, "sha256": hashlib.sha256(body).hexdigest()}


def module_at(name, path):
    if path.stat().st_size > 40000:
        raise AssertionError("unexpected source extent before import")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def array_extent(value, seen=None):
    """Observed retained ndarray payload, not allocator/RSS telemetry."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    if isinstance(value, np.ndarray):
        return value.nbytes
    if isinstance(value, dict):
        return sum(array_extent(v, seen) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(array_extent(v, seen) for v in value)
    return 0


def softmax_document():
    return {"schema": "neural053_row_plan_v1", "input_dim": 3, "class_count": 3,
            "constants": {}, "nodes": [{"id": "prob", "op": "softmax", "input": "input", "axis": "classes"}],
            "output": "prob"}


class SuccessorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = {name: pin(path) for name, path in FILES.items()}
        if cls.before["v1_evaluator"] != {"bytes": 13516, "sha256": "0cbe60d42265b4660a27bb4a2578e6bef8fda3ad40dac27acccb445573ecb333"}:
            raise AssertionError("frozen current V1 identity mismatch")
        cls.old = module_at("neural053_I5_frozen_v1", V1_PLAN)
        cls.new = module_at("neural053_I5_successor_v2", HERE / "plan.py")
        cls.reference = module_at("neural053_C2_reference", V2 / "reference" / "models.py")
        OBSERVATIONS["source_before"] = cls.before

    def test_01_softmax_underflow_and_error_disposition(self):
        logits = np.array([[0., 0., -745.], [0., 0., -746.], [745., 745., 0.]])
        old_plan = self.old.load_plan(softmax_document())
        with self.assertRaises(self.old.PlanError) as caught:
            self.old.evaluate(old_plan, logits[:1], backend="vectorized")
        new_plan = self.new.load_plan(softmax_document())
        expected = np.array([[0.5, 0.5, 0.], [0.5, 0.5, 0.], [0.5, 0.5, 0.]])
        backends = {}
        for backend in ("scalar", "vectorized"):
            actual = self.new.evaluate(new_plan, logits, backend=backend)
            np.testing.assert_array_equal(actual, expected)
            self.assertTrue(np.all(np.isfinite(actual)))
            np.testing.assert_array_equal(actual.sum(axis=1), np.ones(3))
            backends[backend] = {"rows": 3, "exact_expected_probabilities": True,
                                 "finite_and_unit_rows": True, "zero_probability_preserved": True}
        # Finite input subtraction overflow still refuses; invalid/nonfinite
        # values and zero-division graphs are not rescued by the narrow change.
        refused = []
        for label, values in [("overflow", [[-1e308, 1e308, 0.]]),
                              ("nonfinite_nan", [[float("nan"), 0., 1.]]),
                              ("nonfinite_inf", [[float("inf"), 0., 1.]])]:
            with self.assertRaises(self.new.PlanError):
                self.new.evaluate(new_plan, np.array(values), backend="vectorized")
            refused.append(label)
        zero = softmax_document()
        zero["constants"] = {"denominator": {"dtype": "float64", "shape": [], "values": [0.]}}
        zero["nodes"].insert(0, {"id": "scaled", "op": "div_const", "input": "input", "constant": "denominator"})
        zero["nodes"][-1]["input"] = "scaled"
        with self.assertRaises(self.new.PlanError): self.new.load_plan(zero)
        invalid = softmax_document()
        invalid["nodes"].insert(0, {"id": "logged", "op": "log", "input": "input"})
        invalid["nodes"][-1]["input"] = "logged"
        with self.assertRaises(self.new.PlanError):
            self.new.evaluate(self.new.load_plan(invalid), np.array([[-1., 1., 1.]]))
        refused.extend(["divide_by_zero_constant", "invalid_log_domain"])
        OBSERVATIONS["I5"] = {"frozen_v1_failure_reproduced": str(caught.exception),
                              "witness_logits": [0, 0, -745], "v2_backends": backends,
                              "failure_dispositions_preserved": refused,
                              "invented_witness_input_bytes": logits.nbytes,
                              "invented_expected_output_bytes": expected.nbytes}

    def test_02_all_four_current_exporters_against_exact_v2(self):
        # Smallest balanced nondegenerate two-class fit for LDA (N>C). Full
        # specified 1,024 Fourier features remain; its small-N dual solve avoids
        # a fabricated 1,024-by-1,024 fixture allocation. Queries are invented.
        x = np.array([[0.], [1.], [3.], [4.]])
        y = np.array([1, 1, 2, 2], dtype=np.int64)
        q = np.array([[0.5], [2.5]])
        rows = []
        settings = [("ridge", {"alpha": 1.}), ("shrinkage_lda", {"gamma": 0.5}),
                    ("fourier_ridge", {"q": 1., "alpha": 0.01}), ("historical_centroid", {})]
        for family, params in settings:
            fit = self.reference.fit_reference(family, params, x, y, 2, 0, "ocular")
            document = self.reference.export_plan(fit, 1.)
            plan = self.new.load_plan(document)
            logits = self.reference.score_reference(fit, q)
            expected = np.exp(self.reference.log_probabilities(logits, 1.))
            expected_packed = self.reference.calibrated_probabilities(logits, 1.)
            maximum = {}
            for backend in ("scalar", "vectorized"):
                actual = self.new.evaluate(plan, q, backend=backend)
                np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
                np.testing.assert_array_equal(actual.astype(np.float32), expected_packed)
                maximum[backend] = float(np.max(np.abs(actual - expected)))
            record = {"family": family, "parameters": params, "training_shape": [4, 1],
                      "query_shape": [2, 1], "classes": 2, "temperature": 1.,
                      "max_abs_probability_difference": maximum,
                      "fitted_array_payload_bytes": array_extent(fit),
                      "encoded_plan_bytes": len(plan.encoded),
                      "plan_sha256": plan.digest, "matched": True,
                      "float32_packing_matches_reference": True}
            if family == "fourier_ridge":
                self.assertEqual(fit["fourier_features"], 1024)
                self.assertEqual(fit["solve"]["system"], "dual_ridge")
                self.assertIsNone(fit["fallback"])
                record.update({"fourier_features": 1024, "nonconstant_fourier_path": True,
                               "solver": fit["solve"]["system"]})
            rows.append(record)
            del fit, document, plan, expected, expected_packed, logits, actual
        OBSERVATIONS["C2"] = {"historical_reference_exporter_parity": {
            "bytes": 13399, "sha256": "dd3c23812c9b6898091ae6782c77628cc5bfb7a2806115e424a4816f1aee4a0d",
            "meaning": "Historical receipt only; not evidence for later V1 or repaired V2."},
            "all_four_current_v2_exports": rows,
            "invented_explicit_training_label_query_bytes": x.nbytes + y.nbytes + q.nbytes}

    @classmethod
    def tearDownClass(cls):
        after = {name: pin(path) for name, path in FILES.items()}
        OBSERVATIONS["source_after"] = after
        if cls.before != after:
            raise AssertionError("evaluator/reference/test source changed during focused controls")
        OBSERVATIONS["exact_source_before_after_match"] = True


if __name__ == "__main__":
    output = HERE / "SUCCESSOR_CONTROL_RESULTS.json"
    history = []
    if output.exists():
        if sys.argv[1:] != ["--append-authorized-retry"]:
            raise RuntimeError("existing result preserved; explicit independently authorized retry flag required")
        if output.stat().st_size > 30000:
            raise RuntimeError("unexpected history extent")
        old = json.loads(output.read_bytes())
        history = old["attempts"] if old.get("schema") == "neural053_method_successor_control_history_v1" else [old]
    elif sys.argv[1:]:
        raise RuntimeError("unknown control arguments")
    suite = (unittest.TestSuite([SuccessorControls("test_02_all_four_current_exporters_against_exact_v2")])
             if history else unittest.defaultTestLoader.loadTestsFromTestCase(SuccessorControls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    OBSERVATIONS.update({"schema": "neural053_method_successor_controls_v1", "source_only_engineering": True,
                         "tests_run": result.testsRun, "successful": result.wasSuccessful(),
                         "failures": len(result.failures), "errors": len(result.errors),
                         "physical_IO_or_RSS_certified": False,
                         "explicit_source_pin_read_bytes": SOURCE_BYTES_READ,
                         "controls_scope": ("Authorized retry of C2 all4 exporter/evaluator parity only; prior passing I5 is not replayed."
                                            if history else "Focused I5 regression and all4 actual exporter/evaluator parity only; no broad unchanged-suite replay."),
                         "additional_invented_fixture_grant_bytes": {"cumulative": 1048576, "retained": 262144, "live": 2097152},
                         "conservative_additional_fixture_charge_bytes": {"cumulative": 1048576, "retained": 32768, "live": 1048576},
                         "fixture_accounting_limit": "Known tiny input/output/state and encoded-plan extents reported above; cumulative/live charges conservatively include transient numerical and serialization payloads, not independently metered allocator or process RSS. No numerical fixture files retained; retained provision covers source literals and this control receipt.",
                         "actual_neural_data_model_provider_or_scientific_runs": 0,
                         "runtime_or_scientific_qualification": False,
                         "api_changed": False})
    if history:
        # Preserve the complete first failed result without relabeling its
        # charge or claiming its earlier scalar/float32 comparison was valid.
        report = {"schema": "neural053_method_successor_control_history_v1",
                  "attempts": history + [OBSERVATIONS],
                  "retry_reason": "First C2 control compared float64 evaluator to stored float32 reference at1e-12. Successor compares exp(log_probabilities) atfloat64 precision and separately checks exactfloat32 packing.",
                  "historical_failure_tool": "62390d", "historical_failure_exit_code": 1,
                  "prior_conservative_fixture_debit_preserved": True,
                  "retry_fixture_authority": "Separate prospective parent authorization required; command flag is not authority.",
                  "latest_successful": result.wasSuccessful(),
                  "additional_cumulative_fixture_charge_bytes": sum(a["conservative_additional_fixture_charge_bytes"]["cumulative"] for a in history + [OBSERVATIONS])}
    else:
        report = OBSERVATIONS
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
