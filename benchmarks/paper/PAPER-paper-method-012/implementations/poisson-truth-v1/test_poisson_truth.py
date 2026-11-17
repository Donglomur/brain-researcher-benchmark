"""Small deterministic mathematical and admission controls; no simulation runs."""
import copy
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import itertools
import math
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("poisson_truth", Path(__file__).with_name("poisson_truth.py"))
truth = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(truth)


def packet():
    rows = []
    for n, repeat, method in itertools.product(range(1, 5), range(1, 26), truth.SOURCE_METHODS):
        rows.append({"n_neurons": n, "trials_per_stimulus": 20, "repeat": repeat,
                     "method": method, "estimate_bits": -repeat / 100,
                     "draw_sha256": hashlib.sha256(f"generated-control:{n}:{repeat}".encode()).hexdigest()})
    return {"branch": truth.BRANCH, "input_role": "generated_software_control",
            "trials_per_stimulus_grid": [20], "candidate_methods": [], "estimates": rows}


class AnalyticalControls(unittest.TestCase):
    def test_binned_against_high_precision_entropy_identity(self):
        # Independent H(R)-H(R|S) implementation with decimal arithmetic.
        with localcontext() as ctx:
            ctx.prec = 55
            half, ln2 = Decimal("0.5"), Decimal(2).ln()
            marginals = []
            for mean in (Decimal(1), Decimal(2)):
                probs = [(-mean).exp() * mean ** k / Decimal(math.factorial(k)) for k in range(4)]
                marginals.append(probs + [Decimal(1) - sum(probs)])
            entropy = lambda probabilities: -sum(x * x.ln() / ln2 for x in probabilities if x)
            for n in range(1, 5):
                first = [math.prod(marginals[0][x] for x in state)
                         for state in itertools.product(range(5), repeat=n)]
                second = [math.prod(marginals[1][x] for x in state)
                          for state in itertools.product(range(5), repeat=n)]
                expected = entropy([half * (a + b) for a, b in zip(first, second)]) - half * (entropy(first) + entropy(second))
                self.assertAlmostEqual(truth.binned_truth(n), float(expected), delta=2e-14)

    def test_unbinned_sufficient_statistic_against_full_two_neuron_sum(self):
        # Enumerate separate neuron counts, rather than the implementation's sum.
        conditional = [[math.exp(-mean) * mean ** k / math.factorial(k)
                        for k in range(31)] for mean in (1, 2)]
        expected = 0.0
        for a, b in itertools.product(range(31), repeat=2):
            p = conditional[0][a] * conditional[0][b]
            q = conditional[1][a] * conditional[1][b]
            mixture = (p + q) / 2
            expected += p / 2 * math.log2(p / mixture) + q / 2 * math.log2(q / mixture)
        result = truth.unbinned_truth(2, 1e-15)
        self.assertAlmostEqual(result["information_bits"], expected, delta=4e-14)

    def test_tail_bound_contains_difference_to_tighter_sum(self):
        for n in range(1, 5):
            loose = truth.unbinned_truth(n, 1e-6)
            tight = truth.unbinned_truth(n, 1e-15)
            omitted = tight["information_bits"] - loose["information_bits"]
            self.assertGreaterEqual(omitted, -1e-14)
            self.assertLessEqual(omitted, loose["truncation_bound_bits"] + 1e-14)
            self.assertLessEqual(tight["truncation_bound_bits"], 1e-15)

    def test_data_processing_and_population_information(self):
        previous = 0.0
        for n in range(1, 5):
            binned = truth.binned_truth(n)
            raw = truth.unbinned_truth(n)["information_bits"]
            self.assertGreater(binned, previous)
            self.assertLess(binned, raw)
            self.assertLess(raw, 1.0)
            previous = binned

    def test_no_silent_population_or_tolerance_substitution(self):
        for invalid in (0, 5, True, 2.0, None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                truth.binned_truth(invalid)
        for invalid in (True, 0, -1, float("nan"), float("inf"), "0.01", 1e-20):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                truth.unbinned_truth(1, invalid)


class SummaryControls(unittest.TestCase):
    def test_negative_estimates_and_source_mean_sem_are_retained(self):
        output = truth.summarize(packet())
        self.assertEqual(len(output["cells"]), 16)
        for row in output["cells"]:
            self.assertEqual(row["total_observations"], 40)
            self.assertAlmostEqual(row["mean_estimate_bits"], -0.13)
            # sample variance of integers 1..25 is 25*26/12.
            self.assertAlmostEqual(row["sem_estimate_bits"], math.sqrt(25 * 26 / 12) / 500)
            self.assertEqual(row["per_repeat_estimate_bits"][0], -0.01)
            self.assertAlmostEqual(row["signed_error_vs_binned_truth_bits"],
                                   -0.13 - truth.binned_truth(row["n_neurons"]))
        self.assertFalse(output["original_sample_grid_verified"])

    def test_input_order_does_not_change_cell_aggregation(self):
        first = packet()
        second = copy.deepcopy(first)
        second["estimates"].reverse()
        self.assertEqual(truth.summarize(first)["cells"], truth.summarize(second)["cells"])

    def test_complete_four_method_panel_required(self):
        first = packet()
        first["estimates"] = [row for row in first["estimates"] if row["method"] != "ksg"]
        with self.assertRaisesRegex(ValueError, "Missing estimates"):
            truth.summarize(first)

    def test_missing_population_repeat_or_candidate_rejected(self):
        for mutation in ("population", "repeat", "candidate"):
            first = packet()
            if mutation == "population":
                first["estimates"] = [r for r in first["estimates"] if r["n_neurons"] != 4]
            elif mutation == "repeat":
                first["estimates"].pop()
            else:
                first["candidate_methods"] = ["candidate"]
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "Missing estimates"):
                truth.summarize(first)

    def test_duplicate_row_and_mismatched_draw_rejected(self):
        first = packet()
        first["estimates"].append(first["estimates"][0])
        with self.assertRaisesRegex(ValueError, "duplicated"):
            truth.summarize(first)
        second = packet()
        second["estimates"][0]["draw_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "same draw"):
            truth.summarize(second)

    def test_relabelled_replication_is_rejected(self):
        first = packet()
        for row in first["estimates"]:
            row["draw_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "not 25 repetitions"):
            truth.summarize(first)

    def test_malformed_and_nonfinite_estimates_rejected(self):
        for field, value in (("estimate_bits", float("nan")), ("estimate_bits", True),
                             ("estimate_bits", float("inf")), ("repeat", True),
                             ("draw_sha256", "unverified"), ("method", [])):
            first = packet()
            first["estimates"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                truth.summarize(first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
