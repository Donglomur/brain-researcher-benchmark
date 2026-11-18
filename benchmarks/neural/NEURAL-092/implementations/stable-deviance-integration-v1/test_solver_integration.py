"""Generated consumer checks only; no data, fits, issuer, or source mutation."""
import ast
from decimal import Decimal, localcontext
import importlib.util
import math
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
TASK = Path(os.environ.get("N092_BASE_TASK", str(HERE.parent.parent)))
BASE = TASK / "implementations/registered-runtime/programme"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType("_n092_integrated_candidate")
package.__path__ = [str(HERE / "gain")]
sys.modules[package.__name__] = package
solver = load(package.__name__ + ".solver", HERE / "gain/solver.py")
cost = load(package.__name__ + ".cost", HERE / "gain/cost.py")


def oracle(y, mu):
    with localcontext() as context:
        context.prec = 150
        a, b = Decimal(y), Decimal.from_float(mu)
        return float(2 * (b if y == 0 else a * (a / b).ln() - a + b))


class ForbiddenReads:
    def __getitem__(self, item):
        raise AssertionError("input touched before authority check")


class IntegrationTests(unittest.TestCase):
    def test_other_solver_functions_and_live_guards_preserved(self):
        def definitions(path):
            return {node.name: ast.dump(node, include_attributes=False)
                    for node in ast.parse(path.read_text()).body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        before = definitions(BASE / "gain/solver.py")
        after = definitions(HERE / "gain/solver.py")
        self.assertEqual(set(before), set(after))
        for name in before.keys() - {"deviance_term"}:
            self.assertEqual(before[name], after[name], name)
        for name in ("authority.py", "constants.py", "__init__.py"):
            self.assertEqual((HERE / "gain" / name).read_bytes(),
                             (BASE / "gain" / name).read_bytes())

    def test_stable_primitive_is_existing_reviewed_component(self):
        original = TASK / "implementations/stable-deviance-v1/poisson_deviance.py"
        self.assertEqual((HERE / "gain/poisson_deviance.py").read_bytes(),
                         original.read_bytes())

    def test_validation_consumer_preserves_near_equal_loss(self):
        # Only the gate and prediction producer are test doubles. The actual
        # candidate validation consumer, scalar kernel and call ledger execute.
        means = [math.nextafter(1.0, math.inf), 1e-320]
        calls = cost.Calls()
        seen = []
        with patch.object(solver, "require_live", side_effect=lambda *x: seen.append(x)), \
             patch.object(solver, "predicted_mean", side_effect=means):
            result = solver.prediction_deviance(None, 1, [7, 9], lambda i: 1,
                                               None, 0.0, object(), calls)
        expected = sum(oracle(1, mu) for mu in means) / 2
        self.assertTrue(math.isclose(result, expected, rel_tol=2e-13))
        self.assertEqual(len(seen), 1)
        self.assertEqual(calls.counts["validation_deviance"], 1)
        self.assertEqual(calls.counts["deviance_row"], 2)

    def test_query_consumer_keeps_complete_strided_axis(self):
        maximum = 2**63 - 1
        # Unit1 only: sentinel values in the other unit would change the answer.
        counts = [999, maximum, 999, 1, 999, 0]
        means = [999.0, float(2**63), 999.0, math.nextafter(1.0, math.inf), 999.0, 0.25]
        calls = cost.Calls()
        with patch.object(solver, "require_live", return_value=None):
            result = solver.frozen_deviance(counts, means, 3, 2, 1, object(), calls)
        expected = sum(oracle(counts[i], means[i]) for i in (1, 3, 5)) / 3
        self.assertTrue(math.isclose(result, expected, rel_tol=2e-13))
        self.assertEqual(calls.counts["query_deviance"], 1)
        self.assertEqual(calls.counts["deviance_row"], 3)

    def test_candidate_reference_order_survives_query_path(self):
        candidate = math.nextafter(1.0, math.inf)
        reference = math.nextafter(candidate, math.inf)
        with patch.object(solver, "require_live", return_value=None):
            candidate_loss = solver.frozen_deviance([1], [candidate], 1, 1, 0, object(), cost.Calls())
            reference_loss = solver.frozen_deviance([1], [reference], 1, 1, 0, object(), cost.Calls())
        self.assertGreater(reference_loss - candidate_loss, 0)
        self.assertTrue(math.isclose(reference_loss - candidate_loss,
                                    oracle(1, reference) - oracle(1, candidate), rel_tol=2e-13))

    def test_true_arithmetic_failure_preserves_solver_exception_and_cause(self):
        calls = cost.Calls()
        with self.assertRaises(solver.FitFailure) as caught:
            solver.deviance_term(0, sys.float_info.max, calls)
        self.assertIs(type(caught.exception.__cause__), ArithmeticError)
        self.assertEqual(calls.counts["deviance_row"], 1)

    def test_invalid_domains_remain_value_errors_not_fit_failures(self):
        for y, mu in [(True, 1.0), (-1, 1.0), (2**63, 1.0),
                      (1, 1), (1, 0.0), (1, math.nan)]:
            with self.subTest(y=y, mu=mu):
                with self.assertRaises(ValueError):
                    solver.deviance_term(y, mu, cost.Calls())

    def test_real_unissued_custody_rejects_both_consumers_before_inputs(self):
        # Load the unchanged actual custody module, but NEVER call issue().
        host_package = types.ModuleType("host092")
        host_package.__path__ = [str(BASE / "host092")]
        with patch.dict(sys.modules, {"host092": host_package}):
            custody = load("host092.custody", BASE / "host092/custody.py")
            try:
                class Host:
                    pass
                host = Host()
                self.assertEqual(len(custody._LIVE), 0)
                calls = cost.Calls()
                with self.assertRaises(solver.ScientificAuthorityUnavailable if hasattr(solver, "ScientificAuthorityUnavailable") else RuntimeError):
                    solver.prediction_deviance(ForbiddenReads(), 1, [0], ForbiddenReads(),
                                               ForbiddenReads(), 0.0, host, calls)
                with self.assertRaises(RuntimeError):
                    solver.frozen_deviance(ForbiddenReads(), ForbiddenReads(), 1, 1, 0, host, calls)
                self.assertEqual(calls.counts, {})
                self.assertEqual(len(custody._LIVE), 0)
            finally:
                sys.modules.pop("host092.custody", None)

    def test_series_plan_covers_both_consumers_without_inventing_flop_bound(self):
        plan = cost.session_plan(3, 2, 4, 5, 2)
        work = plan["deviance_workload"]
        rows = 5 * (45 * 2 + 6 * 4)
        self.assertEqual(work["rows_max"], rows)
        self.assertEqual(work["validation_rows_max"] + work["query_rows_max"], rows)
        self.assertEqual(work["series_iterations_max"], 32 * rows)
        self.assertEqual(work["fsum_input_terms_max"], sum(range(2, 34)) * rows)
        self.assertEqual(work["log_calls_max"], 2 * rows)
        self.assertIsNone(plan["conservative_scalar_arithmetic_bound"])
        self.assertFalse(work["scalar_operation_bound_qualified"])
        self.assertFalse(plan["physical_memory_qualified"])
        self.assertEqual(plan["grid_fits"], 45 * 5)
        self.assertEqual(plan["refits"], 5 * 5)

    def test_actual_generated_calls_fit_new_per_kind_structural_bounds(self):
        values = [(1, 1.1), (1, math.nextafter(1.0, math.inf)),
                  (2**63 - 1, math.ulp(0.0)), (0, 0.5)]
        calls = cost.Calls()
        for y, mu in values:
            solver.deviance_term(y, mu, calls)
        self.assertEqual(calls.counts["deviance_row"], len(values))
        self.assertLessEqual(calls.counts.get("deviance_series_term", 0), 32 * len(values))
        self.assertLessEqual(calls.counts.get("log_scalar", 0), 2 * len(values))


if __name__ == "__main__":
    unittest.main(verbosity=1)
