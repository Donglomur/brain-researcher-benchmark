"""Generated controls only: no neonatal data, fitting or scientific execution."""

import copy
from fractions import Fraction
import hashlib
import itertools
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate import evaluate
from protocol import ContractError
from test_metrics import fixture, predictions
from uncertainty_v1 import METHOD, _indices, _quantile, paired_infant_bootstrap


def reports(*, durations=None, labels=None):
    reference, _, _ = fixture(durations=durations, labels=labels)
    return (evaluate(reference, predictions(reference, 0)),
            evaluate(reference, predictions(reference, 1)))


class InfantBootstrapControls(unittest.TestCase):
    def test_complete_generated_reports_produce_constant_paired_interval(self):
        left, right = reports()
        result = paired_infant_bootstrap(left, right, seed="fixed", resamples=20)
        self.assertEqual(result["n_infants"], 79)
        self.assertEqual(result["n_cases"], 79)
        self.assertEqual(result["point_right_minus_left_soft_vote_brier"], 1)
        self.assertEqual(result["percentile_interval"], {"confidence": .95, "lower": 1, "upper": 1})
        self.assertEqual(result["bootstrap_standard_error"], 0)

    def test_identical_arms_with_heterogeneous_losses_stay_paired(self):
        left, _ = reports(labels=lambda rid, _k: (1, 1, 1) if rid == "eeg79" else (0, 0, 0))
        result = paired_infant_bootstrap(left, left, seed="fixed", resamples=100)
        self.assertEqual(result["point_right_minus_left_soft_vote_brier"], 0)
        self.assertEqual(result["bootstrap_standard_error"], 0)
        self.assertEqual(result["percentile_interval"]["lower"], 0)
        self.assertEqual(result["percentile_interval"]["upper"], 0)

    def test_more_windows_do_not_increase_an_infants_sampling_weight(self):
        labels = lambda rid, _k: (1, 1, 1) if rid == "eeg79" else (0, 0, 0)
        short = reports(labels=labels)
        long = reports(labels=labels, durations={"eeg79": 108})
        a = paired_infant_bootstrap(*short, seed="length-check", resamples=200)
        b = paired_infant_bootstrap(*long, seed="length-check", resamples=200)
        self.assertEqual(a["n_cases"], 79)
        self.assertEqual(b["n_cases"], 157)
        self.assertAlmostEqual(a["point_right_minus_left_soft_vote_brier"], float(Fraction(77, 79)))
        for key in ("point_right_minus_left_soft_vote_brier", "percentile_interval",
                    "bootstrap_standard_error", "replicate_sha256"):
            self.assertEqual(a[key], b[key])

    def test_known_resamples_move_whole_infants_and_keep_the_arms_paired(self):
        left, right = reports(labels=lambda rid, _k: (1, 1, 1) if rid == "eeg79" else (0, 0, 0))
        special = next(i for i, row in enumerate(left["infants"]) if row["recording_id"] == "eeg79")
        # First replicate selects each infant once: 77/79. Second repeats the
        # single exceptional infant 79 times: -1. The interval uses interpolation.
        schedule = itertools.chain(range(79), itertools.repeat(special, 79))
        with patch("uncertainty_v1._indices", return_value=iter(schedule)):
            result = paired_infant_bootstrap(left, right, seed="controlled", resamples=2, confidence=.5)
        self.assertAlmostEqual(result["percentile_interval"]["lower"], float(Fraction(-40, 79)))
        self.assertAlmostEqual(result["percentile_interval"]["upper"], float(Fraction(38, 79)))
        self.assertAlmostEqual(result["bootstrap_standard_error"], float(Fraction(156, 79)) / math.sqrt(2))

    def test_direction_reversal_reverses_interval_and_preserves_standard_error(self):
        left, right = reports(labels=lambda rid, _k: (1, 1, 1) if rid == "eeg79" else (0, 0, 0))
        a = paired_infant_bootstrap(left, right, seed="direction", resamples=128)
        b = paired_infant_bootstrap(right, left, seed="direction", resamples=128)
        self.assertEqual(a["point_right_minus_left_soft_vote_brier"], -b["point_right_minus_left_soft_vote_brier"])
        self.assertAlmostEqual(a["percentile_interval"]["lower"], -b["percentile_interval"]["upper"])
        self.assertAlmostEqual(a["percentile_interval"]["upper"], -b["percentile_interval"]["lower"])
        self.assertEqual(a["bootstrap_standard_error"], b["bootstrap_standard_error"])

    def test_reproducible_without_global_random_state_or_input_mutation(self):
        left, right = reports()
        before = copy.deepcopy((left, right))
        a = paired_infant_bootstrap(left, right, seed="fixed", resamples=10)
        self.assertEqual(a, paired_infant_bootstrap(left, right, seed="fixed", resamples=10))
        self.assertEqual(before, (left, right))
        b = paired_infant_bootstrap(left, right, seed="changed", resamples=10)
        self.assertNotEqual(a["specification_sha256"], b["specification_sha256"])

    def test_integer_stream_matches_published_serialization_and_rejects_bias_tail(self):
        # Independently serialize the documented first block without the helper.
        import json
        prefix = json.dumps([METHOD, "stream"], separators=(",", ":"), ensure_ascii=True).encode()
        raw = hashlib.sha256(prefix + b"\0" * 8).digest()
        expected = [int.from_bytes(raw[i:i + 4], "big") % 79 for i in range(0, 32, 4)
                    if int.from_bytes(raw[i:i + 4], "big") < (2**32 // 79) * 79]
        self.assertEqual(list(itertools.islice(_indices("stream"), len(expected))), expected)
        class HashBlock:
            def digest(self):
                return b"\xff" * 4 + (80).to_bytes(4, "big") * 7
        with patch("uncertainty_v1.hashlib.sha256", return_value=HashBlock()):
            self.assertEqual(list(itertools.islice(_indices("ignored"), 7)), [1] * 7)

    def test_linear_percentile_definition_has_independent_exact_expectations(self):
        self.assertEqual(_quantile([-1, 0, 1], 0), -1)
        self.assertEqual(_quantile([-1, 0, 1], 1), 1)
        self.assertEqual(_quantile([-1, 0, 1], .125), -.75)

    def test_invalid_parameters_refuse_before_resampling(self):
        left, right = reports()
        for arguments in ({"seed": ""}, {"seed": 3}, {"resamples": True},
                          {"resamples": 1}, {"resamples": 2.0},
                          {"confidence": True}, {"confidence": 0}, {"confidence": 1},
                          {"confidence": float("nan")}, {"confidence": float("inf")}):
            params = {"seed": "fixed", "resamples": 2, **arguments}
            with self.subTest(arguments=arguments), self.assertRaises(ContractError):
                paired_infant_bootstrap(left, right, **params)

    def test_incomplete_mismatched_and_fabricated_support_refuses(self):
        left, right = reports()
        mutations = [lambda r: r["infants"].pop(),
                     lambda r: r.update(reference_sha256="f" * 64),
                     lambda r: r["infants"][0].update(n=0),
                     lambda r: r.update(n_cases=1),
                     lambda r: r.update(primary_soft_vote_brier=.5),
                     lambda r: r["infants"].reverse()]
        for mutate in mutations:
            broken = copy.deepcopy(right)
            mutate(broken)
            with self.subTest(mutation=mutate), self.assertRaises(ContractError):
                paired_infant_bootstrap(left, broken, seed="fixed", resamples=2)


if __name__ == "__main__":
    unittest.main()
