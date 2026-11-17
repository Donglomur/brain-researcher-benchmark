"""Generated arithmetic controls; never reads authentic data or old predictions."""
from decimal import Decimal, localcontext
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "neural-095-four-cell"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


paired = module("exact_dmfc_paired", HERE / "paired.py")


def oracle(cue, neural, truth, selected):
    # Independent decimal arithmetic; 1200 digits cover every binary64 value,
    # exact finite differences and means well beyond final binary64 precision.
    with localcontext() as context:
        context.prec = 1200
        rows = [abs(Decimal.from_float(cue[i]) - Decimal.from_float(truth[i]))
                - abs(Decimal.from_float(neural[i]) - Decimal.from_float(truth[i]))
                for i in selected]
        return sum(rows, Decimal()) / len(rows)


class PairedControls(unittest.TestCase):
    def setUp(self):
        self.condition = [i % 40 for i in range(258)]
        self.context = [k // 5 for k in self.condition]
        self.truth = [1000.] * 258

    def evaluate(self, cue, neural, truth=None):
        return paired.pair_difference(cue, neural, self.truth if truth is None else truth,
                                      self.condition, self.context)

    def test_loss_rounding_counterexample(self):
        cue, neural = [0.] * 258, [1e-14] * 258
        self.assertEqual(abs(cue[0] - 1000.) - abs(neural[0] - 1000.), 0.)
        result = self.evaluate(cue, neural)
        self.assertEqual(result["cue_minus_neural_mae_ms"], 1e-14)
        self.assertEqual(result["cue_minus_neural_eight_context_macro_mae_ms"], 1e-14)
        self.assertTrue(all(row["cue_minus_neural_mae_ms"] == 1e-14
                            for name in ("by_condition", "by_context") for row in result[name].values()))

    def test_subnormal_increment_survives_aggregation(self):
        tiny = math.ulp(0.)
        result = self.evaluate([0.] * 258, [tiny] * 258)
        self.assertEqual(result["cue_minus_neural_mae_ms"], tiny)
        self.assertEqual(result["cue_minus_neural_eight_context_macro_mae_ms"], tiny)
        self.assertEqual(math.fsum(tiny / 258 for _ in range(258)), 0.)

    def test_independent_decimal_oracle_and_unequal_group_sizes(self):
        rng = random.Random(95)
        values = [-1e300, -1200., -1e-12, -math.ulp(0.), 0., math.ulp(0.),
                  1e-14, 500., 1000., 1200., 1e300]
        cue = [rng.choice(values) for _ in range(258)]
        neural = [rng.choice(values) for _ in range(258)]
        result = self.evaluate(cue, neural)
        self.assertEqual(result["cue_minus_neural_mae_ms"], float(oracle(cue, neural, self.truth, range(258))))
        context_means = []
        for name, assignment, size in (("by_condition", self.condition, 40), ("by_context", self.context, 8)):
            for key in range(size):
                selected = [i for i, group in enumerate(assignment) if group == key]
                expected = oracle(cue, neural, self.truth, selected)
                self.assertEqual(result[name][str(key)], {"n": len(selected), "cue_minus_neural_mae_ms": float(expected)})
                if name == "by_context":
                    context_means.append(expected)
        with localcontext() as context:
            context.prec = 1200
            self.assertEqual(result["cue_minus_neural_eight_context_macro_mae_ms"],
                             float(sum(context_means, Decimal()) / 8))

    def test_arm_swap_sign_and_zero(self):
        cue, neural = [0.] * 258, [1e-14] * 258
        self.assertEqual(self.evaluate(neural, cue)["cue_minus_neural_mae_ms"], -1e-14)
        self.assertEqual(self.evaluate(cue, cue)["cue_minus_neural_mae_ms"], 0.)

    def test_refusal_preserves_complete_panel_and_overflow_policy(self):
        good = [0.] * 258
        cases = [([0.] * 257, good, self.truth, self.condition, self.context),
                 (good, [math.nan] * 258, self.truth, self.condition, self.context),
                 (good, good, [0.] * 258, self.condition, self.context),
                 (good, good, self.truth, [0] * 258, self.context),
                 (good, good, self.truth, self.condition, self.context[::-1]),
                 ([-sys.float_info.max] * 258, good, [sys.float_info.max] * 258, self.condition, self.context)]
        for case in cases:
            with self.subTest(case=cases.index(case)):
                with self.assertRaises(ValueError):
                    paired.pair_difference(*case)

    def test_generated_complete_four_cell_scorer(self):
        import numpy as np
        sys.path.insert(0, str(PRIOR))
        legacy = module("dmfc_existing_scorer", PRIOR / "score.py")
        old_paired = module("dmfc_prior_pair", PRIOR / "paired.py")
        condition = np.asarray(self.condition, dtype=np.int64)
        truth = np.asarray(self.truth)
        ids = [f"dmfc-{i:06d}" for i in range(258)]
        private = {"case_id": np.asarray(ids), "tp_ms": truth,
                   "condition": condition, "context": condition // 5}
        groups = {"by_condition": self.condition, "by_context": self.context}
        reference = legacy.metrics._candidate((truth + 3).tolist(), self.truth, groups)
        references = {"scores": {name: reference for name in legacy.metrics.METHODS}}
        self.assertEqual(old_paired.pair_difference(np.zeros(258), np.full(258, 1e-14), truth,
                                                    condition, condition // 5)["cue_minus_neural_mae_ms"], 0.)
        legacy.paired = paired
        with tempfile.TemporaryDirectory(prefix="dmfc-generated-paired-") as directory:
            root = Path(directory).resolve()
            paths = {}
            for cell in legacy.CELLS:
                paths[cell] = root / (cell + ".npz")
                predictions = np.full(258, 0. if cell.endswith("cue_only") else 1e-14)
                np.savez(paths[cell], case_id=np.asarray(ids[::-1]), prediction_ms=predictions[::-1])
            calls = []
            def labels():
                calls.append("targets")
                return private
            def refs():
                calls.append("references")
                return references
            result = legacy.evaluate(paths, ids, labels, refs)
            self.assertEqual(calls, ["references", "targets"])
            self.assertEqual(result["private_loader_calls"], 1)
            for mode in legacy.MODES:
                self.assertEqual(result["modes"][mode]["paired"]["cue_minus_neural_mae_ms"], 1e-14)
                self.assertEqual(result["modes"][mode]["paired_arithmetic_checks"], 50)
                for arm in result["modes"][mode]["arms"].values():
                    self.assertEqual(arm["candidate"]["mae_ms"], 1000.)
            json.dumps(result, allow_nan=False)
            calls.clear()
            np.savez(paths[legacy.CELLS[-1]], case_id=np.asarray(ids), prediction_ms=np.full(258, np.nan))
            with self.assertRaises(ValueError):
                legacy.evaluate(paths, ids, labels, refs)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
